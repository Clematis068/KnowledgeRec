"""基于 tag 关系的轻量召回增强与知识逻辑约束。"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import or_

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.tag import Tag
from app.models.tag_taxonomy import TagRelation
from app.models.user import User
from app.utils.helpers import min_max_normalize

POSITIVE_BEHAVIORS = {
    "browse": 0.18,
    "like": 0.55,
    "comment": 0.70,
    "favorite": 0.90,
}
APPROVED_STATUSES = ("approved", "auto_approved")
RECENT_BEHAVIOR_LIMIT = 80
EXPLICIT_TAG_WEIGHT = 1.0
TAG_RECALL_LIMIT = 24
POST_RECALL_LIMIT = 240
PREREQUISITE_FORWARD_RECALL = 0.32
PREREQUISITE_BACKWARD_RECALL = 0.16
PARENT_FORWARD_RECALL = 0.26
PARENT_BACKWARD_RECALL = 0.12
RELATED_RECALL = 0.11
PREREQUISITE_READY_BONUS = 0.045
PREREQUISITE_MISSING_PENALTY = 0.065
PREREQUISITE_REMEDIAL_BONUS = 0.02
PARENT_CHILD_BONUS = 0.03
PARENT_PARENT_BONUS = 0.015
RELATED_BONUS = 0.012
PREREQUISITE_CHAIN_MAX_DEPTH = 3    # 前置链最大递归深度
PREREQUISITE_CHAIN_DECAY = 0.5      # 每多一跳惩罚衰减为上一跳的 50%
MAX_LOGIC_BONUS = 0.12
MAX_LOGIC_PENALTY = 0.14


class LogicConstraintEngine:

    def recall(self, user_id, top_n=200, exclude_post_ids=None):
        exclude_post_ids = exclude_post_ids or set()
        profile = self._build_user_tag_profile(user_id)
        if not profile["engaged_tag_ids"]:
            return {}

        relations = self._load_relations(profile["engaged_tag_ids"])
        if not relations:
            return {}

        candidate_tag_scores = defaultdict(float)
        for relation in relations:
            self._accumulate_relation_recall(candidate_tag_scores, profile["tag_strength"], relation)

        if not candidate_tag_scores:
            return {}

        ranked_tag_ids = [
            tag_id
            for tag_id, _score in sorted(candidate_tag_scores.items(), key=lambda item: -item[1])[:TAG_RECALL_LIMIT]
        ]
        interacted_post_ids = self._load_interacted_post_ids(user_id)
        interacted_post_ids |= exclude_post_ids
        post_scores = self._score_posts_from_tags(ranked_tag_ids, candidate_tag_scores, interacted_post_ids)
        ranked_scores = dict(sorted(post_scores.items(), key=lambda item: -item[1])[:max(top_n, POST_RECALL_LIMIT)])
        return min_max_normalize(ranked_scores)

    def apply(self, user_id, results, post_cache=None):
        if not results:
            return []

        profile = self._build_user_tag_profile(user_id)
        if not profile["engaged_tag_ids"]:
            return results

        relations = self._load_relations(profile["engaged_tag_ids"])
        if not relations:
            return results

        relation_index = self._build_relation_index(relations)
        adjusted = []
        for item in results:
            post = (post_cache.get(item["post_id"]) if post_cache else None) or db.session.get(Post, item["post_id"])
            if not post:
                continue

            logic_bonus, logic_penalty, logic_reasons = self._score_post_logic(
                post,
                profile,
                relation_index,
            )
            updated = dict(item)
            updated["logic_bonus"] = round(logic_bonus, 4)
            updated["logic_penalty"] = round(logic_penalty, 4)
            if logic_reasons:
                updated["logic_reasons"] = logic_reasons[:4]
            updated["final_score"] = round(
                max(item.get("final_score", 0.0) + logic_bonus - logic_penalty, 0.0),
                4,
            )
            adjusted.append(updated)

        adjusted.sort(key=lambda record: -record["final_score"])
        return adjusted

    def _build_user_tag_profile(self, user_id):
        user = db.session.get(User, user_id)
        tag_strength = defaultdict(float)
        explicit_tag_ids = set()
        if user:
            for tag in user.interest_tags:
                explicit_tag_ids.add(tag.id)
                tag_strength[tag.id] += EXPLICIT_TAG_WEIGHT

        behaviors = db.session.scalars(
            db.select(UserBehavior)
            .filter(
                UserBehavior.user_id == user_id,
                UserBehavior.behavior_type.in_(list(POSITIVE_BEHAVIORS)),
            )
            .order_by(UserBehavior.created_at.desc(), UserBehavior.id.desc())
            .limit(RECENT_BEHAVIOR_LIMIT)
        ).all()

        now = datetime.now()
        for idx, behavior in enumerate(behaviors):
            post = db.session.get(Post, behavior.post_id)
            if not post or not post.tags:
                continue

            behavior_weight = POSITIVE_BEHAVIORS.get(behavior.behavior_type, 0.0)
            age_days = max((now - behavior.created_at).days, 0) if behavior.created_at else idx
            recency_weight = max(0.35, 1 - age_days / 45.0)
            strength = behavior_weight * recency_weight
            tag_weight = strength / max(len(post.tags), 1)
            for tag in post.tags:
                tag_strength[tag.id] += tag_weight

        engaged_tag_ids = {tag_id for tag_id, score in tag_strength.items() if score >= 0.22}
        mastered_tag_ids = {
            tag_id
            for tag_id, score in tag_strength.items()
            if score >= 0.75 or tag_id in explicit_tag_ids
        }
        return {
            "tag_strength": dict(tag_strength),
            "engaged_tag_ids": engaged_tag_ids,
            "mastered_tag_ids": mastered_tag_ids,
        }

    def _load_relations(self, tag_ids):
        if not tag_ids:
            return []
        stmt = (
            db.select(TagRelation)
            .filter(TagRelation.status.in_(APPROVED_STATUSES))
            .filter(
                or_(
                    TagRelation.source_tag_id.in_(tag_ids),
                    TagRelation.target_tag_id.in_(tag_ids),
                )
            )
            .order_by(TagRelation.final_score.desc(), TagRelation.id.asc())
        )
        return db.session.scalars(stmt).all()

    def _build_relation_index(self, relations):
        outgoing = defaultdict(list)
        incoming = defaultdict(list)
        for relation in relations:
            outgoing[relation.source_tag_id].append(relation)
            incoming[relation.target_tag_id].append(relation)
        return {"outgoing": outgoing, "incoming": incoming}

    def _accumulate_relation_recall(self, candidate_tag_scores, tag_strength, relation):
        source_strength = tag_strength.get(relation.source_tag_id, 0.0)
        target_strength = tag_strength.get(relation.target_tag_id, 0.0)

        if relation.relation_type == "PREREQUISITE":
            if source_strength > 0:
                candidate_tag_scores[relation.target_tag_id] += source_strength * PREREQUISITE_FORWARD_RECALL
            if target_strength > 0:
                candidate_tag_scores[relation.source_tag_id] += target_strength * PREREQUISITE_BACKWARD_RECALL
            return

        if relation.relation_type == "PARENT_OF":
            if source_strength > 0:
                candidate_tag_scores[relation.target_tag_id] += source_strength * PARENT_FORWARD_RECALL
            if target_strength > 0:
                candidate_tag_scores[relation.source_tag_id] += target_strength * PARENT_BACKWARD_RECALL
            return

        if relation.relation_type == "RELATED_TO":
            if source_strength > 0:
                candidate_tag_scores[relation.target_tag_id] += source_strength * RELATED_RECALL
            if target_strength > 0:
                candidate_tag_scores[relation.source_tag_id] += target_strength * RELATED_RECALL

    def _load_interacted_post_ids(self, user_id):
        stmt = (
            db.select(UserBehavior.post_id)
            .filter(UserBehavior.user_id == user_id)
            .distinct()
        )
        return {post_id for post_id in db.session.scalars(stmt).all() if post_id}

    def _score_posts_from_tags(self, tag_ids, candidate_tag_scores, interacted_post_ids):
        if not tag_ids:
            return {}

        posts = db.session.scalars(
            db.select(Post)
            .join(Post.tags)
            .filter(Tag.id.in_(tag_ids))
        ).unique().all()

        post_scores = defaultdict(float)
        for post in posts:
            if post.id in interacted_post_ids:
                continue
            matched_scores = sorted(
                (candidate_tag_scores.get(tag.id, 0.0) for tag in post.tags if tag.id in candidate_tag_scores),
                reverse=True,
            )
            if not matched_scores:
                continue
            post_scores[post.id] = matched_scores[0] + 0.35 * sum(matched_scores[1:3])
        return post_scores

    def _score_post_logic(self, post, profile, relation_index):
        post_tag_ids = {tag.id for tag in post.tags}
        engaged_tag_ids = profile["engaged_tag_ids"]
        mastered_tag_ids = profile["mastered_tag_ids"]
        tag_strength = profile["tag_strength"]
        logic_bonus = 0.0
        logic_penalty = 0.0
        logic_reasons = []

        for tag_id in post_tag_ids:
            for relation in relation_index["incoming"].get(tag_id, []):
                if relation.source_tag_id not in engaged_tag_ids:
                    continue
                strength = min(tag_strength.get(relation.source_tag_id, 0.0), 1.0)
                if relation.relation_type == "PREREQUISITE":
                    if relation.source_tag_id in mastered_tag_ids:
                        logic_bonus += PREREQUISITE_READY_BONUS * strength
                        logic_reasons.append("matched_prerequisite_ready")
                    else:
                        logic_penalty += PREREQUISITE_MISSING_PENALTY * max(0.6, strength)
                        logic_reasons.append("missing_prerequisite")
                    # 递归检查前置链：A→B→C，帖子标签是C，检查A是否掌握
                    chain_penalty, chain_reasons = self._check_prerequisite_chain(
                        relation.source_tag_id, mastered_tag_ids, relation_index, depth=1,
                    )
                    logic_penalty += chain_penalty
                    logic_reasons.extend(chain_reasons)
                elif relation.relation_type == "PARENT_OF":
                    logic_bonus += PARENT_CHILD_BONUS * strength
                    logic_reasons.append("matched_child_topic")
                elif relation.relation_type == "RELATED_TO":
                    logic_bonus += RELATED_BONUS * strength
                    logic_reasons.append("matched_related_topic")

            for relation in relation_index["outgoing"].get(tag_id, []):
                if relation.target_tag_id not in engaged_tag_ids:
                    continue
                strength = min(tag_strength.get(relation.target_tag_id, 0.0), 1.0)
                if relation.relation_type == "PREREQUISITE":
                    logic_bonus += PREREQUISITE_REMEDIAL_BONUS * strength
                    logic_reasons.append("matched_remedial_topic")
                elif relation.relation_type == "PARENT_OF":
                    logic_bonus += PARENT_PARENT_BONUS * strength
                    logic_reasons.append("matched_parent_topic")
                elif relation.relation_type == "RELATED_TO":
                    logic_bonus += RELATED_BONUS * strength
                    logic_reasons.append("matched_related_topic")

        return (
            min(logic_bonus, MAX_LOGIC_BONUS),
            min(logic_penalty, MAX_LOGIC_PENALTY),
            list(dict.fromkeys(logic_reasons)),
        )

    def _check_prerequisite_chain(self, tag_id, mastered_tag_ids, relation_index, depth):
        """递归检查前置链：如果 tag_id 本身也有 PREREQUISITE 前置，
        且该前置未掌握，则追加衰减惩罚。最多递归 PREREQUISITE_CHAIN_MAX_DEPTH 层。
        """
        if depth >= PREREQUISITE_CHAIN_MAX_DEPTH:
            return 0.0, []

        penalty = 0.0
        reasons = []
        for relation in relation_index["incoming"].get(tag_id, []):
            if relation.relation_type != "PREREQUISITE":
                continue
            prereq_id = relation.source_tag_id
            if prereq_id not in mastered_tag_ids:
                hop_penalty = PREREQUISITE_MISSING_PENALTY * (PREREQUISITE_CHAIN_DECAY ** depth)
                penalty += hop_penalty
                reasons.append(f"missing_prereq_chain_depth_{depth + 1}")
                # 继续向上追溯
                sub_penalty, sub_reasons = self._check_prerequisite_chain(
                    prereq_id, mastered_tag_ids, relation_index, depth + 1,
                )
                penalty += sub_penalty
                reasons.extend(sub_reasons)

        return penalty, reasons
