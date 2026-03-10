import math
import re

from app import db
from app.models.domain import Domain
from app.models.tag import Tag
from app.models.tag_taxonomy import PendingTag, TagAlias
from app.services.qwen_service import qwen_service
from app.taxonomy import FIXED_DOMAINS, build_domain_prompt_text
from app.utils.helpers import cosine_similarity


class TagTaxonomyService:
    AUTO_MATCH_THRESHOLD = 0.72
    AUTO_CREATE_THRESHOLD = 0.78
    CLOSE_DOMAIN_MARGIN = 0.04

    def normalize_text(self, text):
        text = (text or "").strip()
        if not text:
            return ""
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("·", " ").replace("/", " ")
        text = re.sub(r"\s+", " ", text)
        return text[:64]

    def sync_domain_to_neo4j(self, domain):
        try:
            from app.services.neo4j_service import neo4j_service

            neo4j_service.run_write(
                "MERGE (d:Domain {id: $id}) "
                "SET d.name = $name, d.description = $description",
                {
                    "id": domain.id,
                    "name": domain.name,
                    "description": domain.description or "",
                },
            )
        except Exception:
            pass

    def sync_tag_to_neo4j(self, tag):
        try:
            from app.services.neo4j_service import neo4j_service

            self.sync_domain_to_neo4j(tag.domain)
            neo4j_service.run_write(
                "MERGE (t:Tag {id: $id}) "
                "SET t.name = $name, t.domain_id = $domain_id",
                {
                    "id": tag.id,
                    "name": tag.name,
                    "domain_id": tag.domain_id,
                },
            )
            neo4j_service.run_write(
                "MATCH (t:Tag {id: $tag_id}), (d:Domain {id: $domain_id}) "
                "MERGE (t)-[:BELONGS_TO]->(d)",
                {"tag_id": tag.id, "domain_id": tag.domain_id},
            )
        except Exception:
            pass

    def sync_user_interest_tags(self, user):
        tag_ids = [tag.id for tag in user.interest_tags]
        domain_weight_map = {}
        for tag in user.interest_tags:
            domain_weight_map[tag.domain_id] = domain_weight_map.get(tag.domain_id, 0) + 1
        try:
            from app.services.neo4j_service import neo4j_service

            neo4j_service.run_write(
                "MERGE (u:User {id: $uid}) SET u.username = $name",
                {"uid": user.id, "name": user.username},
            )
            neo4j_service.run_write(
                "MATCH (u:User {id: $uid})-[r:INTERESTED_IN]->(:Tag) DELETE r",
                {"uid": user.id},
            )
            neo4j_service.run_write(
                "MATCH (u:User {id: $uid})-[r:INTERESTED_DOMAIN]->(:Domain) DELETE r",
                {"uid": user.id},
            )
            if tag_ids:
                neo4j_service.run_write(
                    "MATCH (u:User {id: $uid}) "
                    "UNWIND $tids AS tid "
                    "MATCH (t:Tag {id: tid}) "
                    "MERGE (u)-[:INTERESTED_IN {weight: 1}]->(t)",
                    {"uid": user.id, "tids": tag_ids},
                )
            if domain_weight_map:
                neo4j_service.run_write(
                    "MATCH (u:User {id: $uid}) "
                    "UNWIND $items AS item "
                    "MATCH (d:Domain {id: item.domain_id}) "
                    "MERGE (u)-[r:INTERESTED_DOMAIN]->(d) "
                    "SET r.weight = item.weight",
                    {
                        "uid": user.id,
                        "items": [
                            {"domain_id": domain_id, "weight": weight}
                            for domain_id, weight in domain_weight_map.items()
                        ],
                    },
                )
        except Exception:
            pass

    def resolve_tag_names(self, raw_names, domain_id, source_user_id=None, source_post_id=None):
        resolved_tags = []
        resolutions = []
        seen_ids = set()

        for raw_name in raw_names or []:
            resolution = self.resolve_single_tag(
                raw_name,
                domain_id,
                source_user_id=source_user_id,
                source_post_id=source_post_id,
            )
            resolutions.append(resolution)
            tag = resolution.get("tag")
            if tag and tag.id not in seen_ids:
                seen_ids.add(tag.id)
                resolved_tags.append(tag)

        return resolved_tags, resolutions

    def resolve_single_tag(self, raw_name, domain_id, source_user_id=None, source_post_id=None):
        normalized_raw = self.normalize_text(raw_name)
        if not normalized_raw:
            return {"status": "ignored", "raw_name": raw_name, "tag": None}

        direct_tag = Tag.query.filter_by(domain_id=domain_id, name=normalized_raw).first()
        if direct_tag:
            self._ensure_tag_embedding(direct_tag)
            return {
                "status": "exact",
                "raw_name": raw_name,
                "normalized_name": normalized_raw,
                "tag": direct_tag,
            }

        alias = TagAlias.query.filter_by(domain_id=domain_id, name=normalized_raw).first()
        if alias:
            self._ensure_tag_embedding(alias.canonical_tag)
            return {
                "status": "alias",
                "raw_name": raw_name,
                "normalized_name": normalized_raw,
                "tag": alias.canonical_tag,
            }

        standardized = self._standardize_with_llm(normalized_raw)
        normalized_name = self.normalize_text(standardized.get("normalized_name") or normalized_raw)
        candidate_aliases = [
            self.normalize_text(item)
            for item in standardized.get("aliases", [])
            if self.normalize_text(item)
        ]

        for name in [normalized_name] + candidate_aliases:
            tag = Tag.query.filter_by(domain_id=domain_id, name=name).first()
            if tag:
                self._upsert_aliases([normalized_raw] + candidate_aliases, domain_id, tag, source="llm-match")
                return {
                    "status": "normalized_match",
                    "raw_name": raw_name,
                    "normalized_name": normalized_name,
                    "tag": tag,
                }

            alias = TagAlias.query.filter_by(domain_id=domain_id, name=name).first()
            if alias:
                self._upsert_aliases([normalized_raw] + candidate_aliases, domain_id, alias.canonical_tag, source="llm-match")
                return {
                    "status": "normalized_alias",
                    "raw_name": raw_name,
                    "normalized_name": normalized_name,
                    "tag": alias.canonical_tag,
                }

        embedding = self._safe_embedding(normalized_name)
        domain_match = self._classify_domain(embedding, fallback_domain_id=domain_id)
        match = self._match_existing_tag_with_llm(normalized_name, domain_id)
        should_create = self._should_auto_create(domain_id, domain_match, match)

        if match["tag"] and match["score"] >= self.AUTO_MATCH_THRESHOLD:
            self._ensure_tag_embedding(match["tag"], normalized_name, embedding)
            self._upsert_aliases([normalized_raw, normalized_name] + candidate_aliases, domain_id, match["tag"], source="llm-match")
            return {
                "status": "matched_existing",
                "raw_name": raw_name,
                "normalized_name": normalized_name,
                "domain_match": domain_match,
                "tag": match["tag"],
                "confidence": match["score"],
            }

        if should_create:
            tag = self._get_or_create_tag(domain_id, normalized_name, embedding=embedding)
            self._upsert_aliases([normalized_raw] + candidate_aliases, domain_id, tag, source="llm-created")
            return {
                "status": "created",
                "raw_name": raw_name,
                "normalized_name": normalized_name,
                "domain_match": domain_match,
                "tag": tag,
                "confidence": domain_match["selected_score"],
            }

        if not embedding:
            tag = self._get_or_create_tag(domain_id, normalized_name, embedding=None)
            self._upsert_aliases([normalized_raw] + candidate_aliases, domain_id, tag, source="fallback-created")
            return {
                "status": "created_fallback",
                "raw_name": raw_name,
                "normalized_name": normalized_name,
                "domain_match": domain_match,
                "tag": tag,
                "confidence": 0.0,
            }

        pending = PendingTag(
            raw_name=normalized_raw,
            normalized_name=normalized_name,
            source_user_id=source_user_id,
            source_post_id=source_post_id,
            domain_id=domain_id,
            suggested_domain_id=domain_match["predicted_domain"].id if domain_match["predicted_domain"] else None,
            matched_tag_id=match["tag"].id if match["tag"] else None,
            confidence=round(max(domain_match["selected_score"], match["score"]), 4),
            status="pending",
            llm_reason=standardized.get("reason") or match["reason"],
        )
        db.session.add(pending)
        return {
            "status": "pending",
            "raw_name": raw_name,
            "normalized_name": normalized_name,
            "domain_match": domain_match,
            "tag": None,
            "confidence": pending.confidence,
        }

    def _standardize_with_llm(self, text):
        system_prompt = (
            "你是知识社区标签标准化助手。"
            "请把用户输入规范成简洁、可复用的知识主题短语，并给出2个以内常见别名。"
            "严格返回JSON："
            '{"normalized_name":"", "aliases": [], "reason": ""}'
        )
        try:
            result = qwen_service.chat_json(text, system_prompt=system_prompt)
            return {
                "normalized_name": result.get("normalized_name") or text,
                "aliases": result.get("aliases") or [],
                "reason": result.get("reason") or "",
            }
        except Exception:
            return {"normalized_name": text, "aliases": [], "reason": ""}

    def _classify_domain(self, embedding, fallback_domain_id=None):
        domains = Domain.query.order_by(Domain.id.asc()).all()
        if not domains:
            return {
                "predicted_domain": None,
                "predicted_score": 0.0,
                "selected_score": 0.0,
                "selected_domain": None,
            }

        predicted_domain = None
        predicted_score = -1.0
        selected_domain = db.session.get(Domain, fallback_domain_id) if fallback_domain_id else None
        selected_score = 0.0

        for domain in domains:
            score = self._domain_similarity(domain, embedding)
            if domain.id == fallback_domain_id:
                selected_score = score
            if score > predicted_score:
                predicted_score = score
                predicted_domain = domain

        return {
            "predicted_domain": predicted_domain,
            "predicted_score": round(max(predicted_score, 0.0), 4),
            "selected_domain": selected_domain,
            "selected_score": round(max(selected_score, 0.0), 4),
        }

    def _match_existing_tag_with_llm(self, tag_name, domain_id):
        tags = Tag.query.filter_by(domain_id=domain_id).order_by(Tag.name.asc()).all()
        if not tags:
            return {"tag": None, "score": 0.0, "reason": ""}

        tag_names = [tag.name for tag in tags]
        system_prompt = (
            "你是知识社区标签映射助手。"
            "请判断输入标签是否能映射到候选标签列表中的某一个。"
            "如果没有合适的匹配，就返回 null。"
            "严格返回JSON："
            '{"matched_tag_name": null, "confidence": 0, "reason": ""}'
        )
        user_message = (
            f"当前领域标签列表：{tag_names}\n"
            f"用户标准化标签：{tag_name}"
        )
        try:
            result = qwen_service.chat_json(user_message, system_prompt=system_prompt)
            matched_name = self.normalize_text(result.get("matched_tag_name") or "")
            confidence = self._clamp_score(result.get("confidence"))
            tag = next((item for item in tags if item.name == matched_name), None)
            return {
                "tag": tag,
                "score": confidence if tag else 0.0,
                "reason": result.get("reason") or "",
            }
        except Exception:
            return {"tag": None, "score": 0.0, "reason": ""}

    def _should_auto_create(self, domain_id, domain_match, match):
        if match["tag"] and match["score"] >= self.AUTO_MATCH_THRESHOLD:
            return False

        predicted = domain_match["predicted_domain"]
        if predicted and predicted.id == domain_id and domain_match["predicted_score"] >= self.AUTO_CREATE_THRESHOLD:
            return True

        predicted_score = domain_match["predicted_score"]
        selected_score = domain_match["selected_score"]
        if selected_score >= self.AUTO_CREATE_THRESHOLD:
            return True
        if selected_score and predicted_score and predicted_score - selected_score <= self.CLOSE_DOMAIN_MARGIN:
            return True
        return False

    def _upsert_aliases(self, names, domain_id, canonical_tag, source):
        for name in names:
            normalized = self.normalize_text(name)
            if not normalized or normalized == canonical_tag.name:
                continue
            exists = TagAlias.query.filter_by(domain_id=domain_id, name=normalized).first()
            if exists:
                if exists.canonical_tag_id != canonical_tag.id:
                    exists.canonical_tag_id = canonical_tag.id
                    exists.source = source
                continue
            db.session.add(
                TagAlias(
                    name=normalized,
                    domain_id=domain_id,
                    canonical_tag_id=canonical_tag.id,
                    source=source,
                )
            )

    def _domain_similarity(self, domain, embedding):
        if not embedding:
            return 0.0
        domain_embedding = self._safe_embedding(self._domain_prompt(domain))
        if not domain_embedding:
            return 0.0
        return cosine_similarity(embedding, domain_embedding)

    def _domain_prompt(self, domain):
        spec = next((item for item in FIXED_DOMAINS if item["name"] == domain.name), None)
        if spec:
            return build_domain_prompt_text(spec)
        return f"{domain.name}：{domain.description or ''}"

    def _ensure_tag_embedding(self, tag, text=None, embedding=None):
        if tag.embedding:
            return tag.embedding
        vector = embedding or self._safe_embedding(text or tag.name)
        if vector:
            tag.embedding = vector
        return tag.embedding

    def _get_or_create_tag(self, domain_id, tag_name, embedding=None):
        tag = Tag.query.filter_by(domain_id=domain_id, name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name, domain_id=domain_id, embedding=embedding)
            db.session.add(tag)
            db.session.flush()
            return tag
        self._ensure_tag_embedding(tag, tag_name, embedding)
        return tag

    def _safe_embedding(self, text):
        normalized = self.normalize_text(text)
        if not normalized:
            return None
        try:
            return qwen_service.get_embedding(normalized)
        except Exception:
            return None

    def _clamp_score(self, raw_score):
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(score):
            return 0.0
        if score > 1:
            score = score / 10.0
        return max(0.0, min(score, 1.0))


tag_taxonomy_service = TagTaxonomyService()
