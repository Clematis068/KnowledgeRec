"""
半自动生成标签关系候选。

关系类型：
- PREREQUISITE
- PARENT_OF
- RELATED_TO

用法:
  cd backend && uv run python -m scripts.generate_tag_relations --domain-ids 1 2 --enable-llm
  cd backend && uv run python -m scripts.generate_tag_relations --max-candidates-per-tag 8 --replace-generated
"""
import argparse
import math
import os
import sys
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.tag import Tag
from app.models.tag_taxonomy import TagRelation
from app.services.qwen_service import qwen_service
from app.utils.helpers import cosine_similarity

RELATION_NONE = "NONE"
RELATION_PREREQUISITE = "PREREQUISITE"
RELATION_PARENT = "PARENT_OF"
RELATION_RELATED = "RELATED_TO"
POSITIVE_BEHAVIORS = ["browse", "like", "favorite", "comment"]
LEARN_FIRST_LEFT = "left"
LEARN_FIRST_RIGHT = "right"
LEARN_FIRST_NEITHER = "neither"
BROADER_LEFT = "left"
BROADER_RIGHT = "right"
BROADER_NEITHER = "neither"
TAG_STAGE_ORDER = {
    "FOUNDATION": 0,
    "CORE": 1,
    "METHOD": 2,
    "APPLICATION": 3,
    "ADVANCED": 4,
    "UNKNOWN": 99,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain-ids", type=int, nargs="*", help="只处理这些 domain_id 下的标签")
    parser.add_argument("--max-candidates-per-tag", type=int, default=10, help="每个 tag 最多保留多少个候选关系")
    parser.add_argument("--min-cooccurrence-score", type=float, default=0.18, help="最小帖子共现分数")
    parser.add_argument("--min-embedding-similarity", type=float, default=0.72, help="最小 embedding 相似度")
    parser.add_argument("--min-sequence-support", type=float, default=0.60, help="最小顺序支持度")
    parser.add_argument("--min-final-score", type=float, default=0.60, help="最终置信度低于该值的关系默认不保留")
    parser.add_argument("--auto-approve-threshold", type=float, default=0.80, help="超过该阈值自动通过")
    parser.add_argument("--enable-llm", action="store_true", help="启用 LLM 判断候选关系类型和方向")
    parser.add_argument("--llm-required", action="store_true", help="要求候选关系必须通过 LLM 判断后才会写入")
    parser.add_argument("--replace-generated", action="store_true", help="先删除当前范围内已有的 semi-auto 关系再重建")
    return parser.parse_args()


def load_tags(domain_ids=None):
    stmt = db.select(Tag).order_by(Tag.domain_id.asc(), Tag.name.asc())
    if domain_ids:
        stmt = stmt.filter(Tag.domain_id.in_(domain_ids))
    tags = db.session.scalars(stmt).all()
    return tags


def build_post_cooccurrence(tag_ids):
    tag_ids = set(tag_ids)
    tag_post_count = defaultdict(int)
    pair_count = defaultdict(int)

    posts = db.session.scalars(db.select(Post)).all()
    for post in posts:
        post_tag_ids = sorted({tag.id for tag in post.tags if tag.id in tag_ids})
        if not post_tag_ids:
            continue
        for tag_id in post_tag_ids:
            tag_post_count[tag_id] += 1
        for left_id, right_id in combinations(post_tag_ids, 2):
            pair_count[(left_id, right_id)] += 1

    pair_score = {}
    for (left_id, right_id), count in pair_count.items():
        denom = math.sqrt(tag_post_count[left_id] * tag_post_count[right_id])
        pair_score[(left_id, right_id)] = (count / denom) if denom > 0 else 0.0

    return pair_score


def build_sequence_support(tag_ids):
    tag_ids = set(tag_ids)
    direction_count = defaultdict(int)
    behaviors = db.session.scalars(
        db.select(UserBehavior)
        .filter(UserBehavior.behavior_type.in_(POSITIVE_BEHAVIORS))
        .order_by(UserBehavior.user_id.asc(), UserBehavior.created_at.asc(), UserBehavior.id.asc())
    ).all()

    current_user = None
    seen_tags = set()
    for behavior in behaviors:
        if behavior.user_id != current_user:
            current_user = behavior.user_id
            seen_tags = set()

        post = db.session.get(Post, behavior.post_id)
        if not post:
            continue
        current_tags = {tag.id for tag in post.tags if tag.id in tag_ids}
        if not current_tags:
            continue

        for prev_tag in seen_tags:
            for next_tag in current_tags:
                if prev_tag != next_tag:
                    direction_count[(prev_tag, next_tag)] += 1

        seen_tags.update(current_tags)

    return direction_count


def embedding_similarity(left_tag, right_tag):
    if not left_tag.embedding or not right_tag.embedding:
        return 0.0
    return max(cosine_similarity(left_tag.embedding, right_tag.embedding), 0.0)


def shortlist_pairs(tags, args):
    tags_by_id = {tag.id: tag for tag in tags}
    tags_by_domain = defaultdict(list)
    for tag in tags:
        tags_by_domain[tag.domain_id].append(tag)

    cooccurrence = build_post_cooccurrence(tags_by_id)
    direction_count = build_sequence_support(tags_by_id)
    candidate_scores = defaultdict(list)

    for domain_tags in tags_by_domain.values():
        for left_tag, right_tag in combinations(domain_tags, 2):
            key = (min(left_tag.id, right_tag.id), max(left_tag.id, right_tag.id))
            cooccur_score = cooccurrence.get(key, 0.0)
            emb_score = embedding_similarity(left_tag, right_tag)
            seq_lr = directional_support(direction_count, left_tag.id, right_tag.id)
            seq_rl = directional_support(direction_count, right_tag.id, left_tag.id)
            seed_score = 0.45 * cooccur_score + 0.35 * emb_score + 0.20 * max(seq_lr, seq_rl)

            if (
                cooccur_score < args.min_cooccurrence_score
                and emb_score < args.min_embedding_similarity
                and max(seq_lr, seq_rl) < args.min_sequence_support
            ):
                continue

            candidate_scores[left_tag.id].append((seed_score, right_tag.id))
            candidate_scores[right_tag.id].append((seed_score, left_tag.id))

    selected_pairs = set()
    for source_tag_id, items in candidate_scores.items():
        for _score, target_tag_id in sorted(items, key=lambda item: -item[0])[:args.max_candidates_per_tag]:
            selected_pairs.add(tuple(sorted((source_tag_id, target_tag_id))))

    return selected_pairs, cooccurrence, direction_count


def directional_support(direction_count, source_tag_id, target_tag_id):
    forward = direction_count.get((source_tag_id, target_tag_id), 0)
    reverse = direction_count.get((target_tag_id, source_tag_id), 0)
    total = forward + reverse
    if total <= 0:
        return 0.0
    return forward / total


def classify_pair(left_tag, right_tag, stats, enable_llm):
    if enable_llm:
        llm_result = classify_with_llm(left_tag, right_tag, stats)
        if llm_result["relation_type"] != RELATION_NONE:
            return llm_result
        return llm_result

    return classify_with_heuristics(left_tag, right_tag, stats)


def classify_with_llm(left_tag, right_tag, stats):
    system_prompt = (
        "你是知识图谱标签关系构建助手。"
        "请基于知识逻辑判断两个知识标签之间的最主要关系。"
        "relation_type 只允许为 PREREQUISITE、PARENT_OF、RELATED_TO、NONE。"
        "direction 只允许为 left_to_right、right_to_left、bidirectional、none。"
        "confidence 返回 0 到 1 之间的小数。"
        "PREREQUISITE 必须表示明确的学习前置关系，不能把常见共现或浏览顺序误判为先修。"
        "PARENT_OF 必须表示主题包含或上下位关系。"
        "RELATED_TO 只表示主题相关，不代表先修。"
        "如果只能判断为相关但无法确定学习先后，优先返回 RELATED_TO。"
        '严格返回 JSON：{"relation_type":"","direction":"","confidence":0,"reason":""}'
    )
    user_message = (
        f"左标签：{left_tag.name}\n"
        f"右标签：{right_tag.name}\n"
        f"领域：{left_tag.domain.name if left_tag.domain else left_tag.domain_id}\n"
        f"帖子共现分数：{stats['cooccurrence_score']:.4f}\n"
        f"左->右顺序支持度：{stats['sequence_lr']:.4f}\n"
        f"右->左顺序支持度：{stats['sequence_rl']:.4f}\n"
        f"embedding 相似度：{stats['embedding_similarity']:.4f}\n"
    )
    try:
        result = qwen_service.chat_json(user_message, system_prompt=system_prompt)
    except Exception:
        return {
            "relation_type": RELATION_NONE,
            "direction": "none",
            "confidence": 0.0,
            "reason": "",
            "source_method": "semi-auto-llm",
        }

    relation_type = (result.get("relation_type") or RELATION_NONE).upper()
    direction = (result.get("direction") or "none").lower()
    confidence = clamp_score(result.get("confidence"))
    if relation_type not in {RELATION_PREREQUISITE, RELATION_PARENT, RELATION_RELATED, RELATION_NONE}:
        relation_type = RELATION_NONE
    if direction not in {"left_to_right", "right_to_left", "bidirectional", "none"}:
        direction = "none"
    classification = {
        "relation_type": relation_type,
        "direction": direction,
        "confidence": confidence,
        "reason": result.get("reason") or "",
        "source_method": "semi-auto-llm",
    }
    if relation_type in {RELATION_PREREQUISITE, RELATION_PARENT}:
        classification = refine_structural_relation_with_llm(left_tag, right_tag, stats, classification)
    return classification


def refine_structural_relation_with_llm(left_tag, right_tag, stats, classification):
    verifier_prompt = (
        "你是知识结构关系校验助手。"
        "目标是区分两个知识标签之间的主要关系是先修依赖、主题包含还是仅仅相关。"
        "不要参考用户点击顺序，只依据知识逻辑本身判断。"
        "如果一个标签是更大的学科/主题范围，另一个是其中的子分支、专题或具体方向，必须优先返回 PARENT_OF，而不是 PREREQUISITE。"
        "relation_type 只允许为 PREREQUISITE、PARENT_OF、RELATED_TO、NONE。"
        "learn_first 只允许为 left、right、neither。"
        "broader_tag 只允许为 left、right、neither。"
        "left_stage/right_stage 只允许为 FOUNDATION、CORE、METHOD、APPLICATION、ADVANCED、UNKNOWN。"
        "如果两个标签只是相关、并列主题，或先后顺序不稳定，不能返回 PREREQUISITE。"
        '严格返回 JSON：{"relation_type":"","learn_first":"","broader_tag":"","confidence":0,"left_stage":"","right_stage":"","reason":""}'
    )
    verifier_message = (
        f"左标签：{left_tag.name}\n"
        f"右标签：{right_tag.name}\n"
        f"领域：{left_tag.domain.name if left_tag.domain else left_tag.domain_id}\n"
        f"当前候选关系：{classification['relation_type']}\n"
        f"初始判断理由：{classification['reason']}\n"
        f"帖子共现分数：{stats['cooccurrence_score']:.4f}\n"
        f"embedding 相似度：{stats['embedding_similarity']:.4f}\n"
    )
    try:
        result = qwen_service.chat_json(verifier_message, system_prompt=verifier_prompt)
    except Exception:
        return downgrade_relation(classification, stats, "结构关系校验失败，降级为相关关系")

    verified_relation_type = (result.get("relation_type") or RELATION_NONE).upper()
    learn_first = (result.get("learn_first") or "").lower()
    broader_tag = (result.get("broader_tag") or "").lower()
    verify_confidence = clamp_score(result.get("confidence"))
    left_stage = normalize_stage(result.get("left_stage"))
    right_stage = normalize_stage(result.get("right_stage"))
    verify_reason = result.get("reason") or ""

    if verified_relation_type not in {RELATION_PREREQUISITE, RELATION_PARENT, RELATION_RELATED, RELATION_NONE}:
        verified_relation_type = RELATION_NONE
    if learn_first not in {LEARN_FIRST_LEFT, LEARN_FIRST_RIGHT, LEARN_FIRST_NEITHER}:
        learn_first = LEARN_FIRST_NEITHER
    if broader_tag not in {BROADER_LEFT, BROADER_RIGHT, BROADER_NEITHER}:
        broader_tag = BROADER_NEITHER

    if verified_relation_type == RELATION_PARENT:
        if broader_tag == BROADER_NEITHER or verify_confidence < 0.60:
            return downgrade_relation(
                classification,
                stats,
                verify_reason or "主题层级方向不明确",
                verification_confidence=verify_confidence,
            )
        direction = "left_to_right" if broader_tag == BROADER_LEFT else "right_to_left"
        combined_confidence = round(0.55 * classification["confidence"] + 0.45 * verify_confidence, 4)
        if combined_confidence < 0.68:
            return downgrade_relation(
                classification,
                stats,
                verify_reason or "主题层级置信度不足",
                verification_confidence=verify_confidence,
            )
        reason_parts = [part for part in [classification["reason"], verify_reason] if part]
        return {
            **classification,
            "relation_type": RELATION_PARENT,
            "direction": direction,
            "confidence": combined_confidence,
            "reason": "；".join(reason_parts),
            "left_stage": left_stage,
            "right_stage": right_stage,
        }

    if verified_relation_type == RELATION_PREREQUISITE:
        if learn_first == LEARN_FIRST_NEITHER or verify_confidence < 0.60:
            return downgrade_relation(
                classification,
                stats,
                verify_reason or "知识逻辑无法稳定判断学习先后",
                verification_confidence=verify_confidence,
            )
        direction = "left_to_right" if learn_first == LEARN_FIRST_LEFT else "right_to_left"
        source_stage, target_stage = resolve_stage_pair(direction, left_stage, right_stage)
        if TAG_STAGE_ORDER[source_stage] > TAG_STAGE_ORDER[target_stage]:
            return downgrade_relation(
                classification,
                stats,
                verify_reason or "学习阶段显示候选方向与知识逻辑不一致",
                verification_confidence=verify_confidence,
            )
        combined_confidence = round(0.55 * classification["confidence"] + 0.45 * verify_confidence, 4)
        if combined_confidence < 0.72:
            return downgrade_relation(
                classification,
                stats,
                verify_reason or "学习顺序置信度不足",
                verification_confidence=verify_confidence,
            )
        reason_parts = [part for part in [classification["reason"], verify_reason] if part]
        return {
            **classification,
            "relation_type": RELATION_PREREQUISITE,
            "direction": direction,
            "confidence": combined_confidence,
            "reason": "；".join(reason_parts),
            "left_stage": left_stage,
            "right_stage": right_stage,
        }

    if verified_relation_type == RELATION_RELATED:
        return downgrade_relation(
            classification,
            stats,
            verify_reason or "两者主要是相关关系，不形成稳定层级或先修",
            verification_confidence=verify_confidence,
        )

    return {
        **classification,
        "relation_type": RELATION_NONE,
        "direction": "none",
        "confidence": 0.0,
        "reason": verify_reason or "未形成稳定知识结构关系",
        "left_stage": left_stage,
        "right_stage": right_stage,
    }


def normalize_stage(raw_stage):
    stage = (raw_stage or "UNKNOWN").upper()
    if stage not in TAG_STAGE_ORDER:
        return "UNKNOWN"
    return stage


def resolve_stage_pair(direction, left_stage, right_stage):
    if direction == "right_to_left":
        return right_stage, left_stage
    return left_stage, right_stage


def downgrade_relation(classification, stats, reason, verification_confidence=None):
    base_confidence = classification["confidence"]
    if verification_confidence is not None and verification_confidence > 0:
        base_confidence = 0.55 * classification["confidence"] + 0.45 * verification_confidence
    related_confidence = min(
        max(
            0.52,
            0.55 * base_confidence
            + 0.25 * stats["cooccurrence_score"]
            + 0.20 * stats["embedding_similarity"],
        ),
        0.82,
    )
    if related_confidence < 0.58:
        return {
            **classification,
            "relation_type": RELATION_NONE,
            "direction": "none",
            "confidence": 0.0,
            "reason": reason,
        }
    return {
        **classification,
        "relation_type": RELATION_RELATED,
        "direction": "bidirectional",
        "confidence": round(related_confidence, 4),
        "reason": reason,
    }


def classify_with_heuristics(left_tag, right_tag, stats):
    seq_lr = stats["sequence_lr"]
    seq_rl = stats["sequence_rl"]
    cooccur_score = stats["cooccurrence_score"]
    emb_score = stats["embedding_similarity"]

    if seq_lr >= 0.68 and seq_lr >= seq_rl + 0.15:
        return {
            "relation_type": RELATION_PREREQUISITE,
            "direction": "left_to_right",
            "confidence": min(0.55 + seq_lr * 0.35, 0.92),
            "reason": "用户行为序列显示左标签通常早于右标签出现",
            "source_method": "semi-auto-rule",
        }
    if seq_rl >= 0.68 and seq_rl >= seq_lr + 0.15:
        return {
            "relation_type": RELATION_PREREQUISITE,
            "direction": "right_to_left",
            "confidence": min(0.55 + seq_rl * 0.35, 0.92),
            "reason": "用户行为序列显示右标签通常早于左标签出现",
            "source_method": "semi-auto-rule",
        }

    if left_tag.name in right_tag.name and len(left_tag.name) < len(right_tag.name):
        return {
            "relation_type": RELATION_PARENT,
            "direction": "left_to_right",
            "confidence": min(0.50 + emb_score * 0.30 + cooccur_score * 0.20, 0.88),
            "reason": "标签名称呈现父子主题包含关系",
            "source_method": "semi-auto-rule",
        }
    if right_tag.name in left_tag.name and len(right_tag.name) < len(left_tag.name):
        return {
            "relation_type": RELATION_PARENT,
            "direction": "right_to_left",
            "confidence": min(0.50 + emb_score * 0.30 + cooccur_score * 0.20, 0.88),
            "reason": "标签名称呈现父子主题包含关系",
            "source_method": "semi-auto-rule",
        }

    if max(cooccur_score, emb_score) >= 0.58:
        return {
            "relation_type": RELATION_RELATED,
            "direction": "bidirectional",
            "confidence": min(0.45 + max(cooccur_score, emb_score) * 0.40, 0.85),
            "reason": "标签语义和内容共现较接近",
            "source_method": "semi-auto-rule",
        }

    return {
        "relation_type": RELATION_NONE,
        "direction": "none",
        "confidence": 0.0,
        "reason": "",
        "source_method": "semi-auto-rule",
    }


def score_relation(relation_type, llm_confidence, stats, direction):
    if relation_type == RELATION_PREREQUISITE:
        direction_gap = max(stats["sequence_lr"] - stats["sequence_rl"], 0.0)
        if direction == "right_to_left":
            direction_gap = max(stats["sequence_rl"] - stats["sequence_lr"], 0.0)
        return min(
            0.80 * llm_confidence
            + 0.10 * max(stats["sequence_lr"], stats["sequence_rl"])
            + 0.10 * direction_gap,
            1.0,
        )

    if relation_type == RELATION_PARENT:
        return min(
            0.50 * llm_confidence
            + 0.25 * stats["cooccurrence_score"]
            + 0.25 * stats["embedding_similarity"],
            1.0,
        )

    if relation_type == RELATION_RELATED:
        return min(
            0.35 * llm_confidence
            + 0.35 * stats["cooccurrence_score"]
            + 0.30 * stats["embedding_similarity"],
            1.0,
        )

    return 0.0


def normalize_direction(left_tag, right_tag, classification):
    relation_type = classification["relation_type"]
    direction = classification["direction"]
    if relation_type == RELATION_NONE:
        return None
    if relation_type == RELATION_RELATED or direction == "bidirectional":
        return left_tag.id, right_tag.id
    if direction == "right_to_left":
        return right_tag.id, left_tag.id
    return left_tag.id, right_tag.id


def clamp_score(raw_value):
    try:
        score = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(score):
        return 0.0
    if score > 1:
        score = score / 10.0
    return max(0.0, min(score, 1.0))


def upsert_relation(source_tag_id, target_tag_id, relation_type, final_score, classification, stats, auto_threshold):
    status = "auto_approved" if final_score >= auto_threshold else "pending"
    relation = db.session.scalar(
        db.select(TagRelation).filter_by(
            source_tag_id=source_tag_id,
            target_tag_id=target_tag_id,
            relation_type=relation_type,
        )
    )
    if not relation:
        relation = TagRelation(
            source_tag_id=source_tag_id,
            target_tag_id=target_tag_id,
            relation_type=relation_type,
        )
        db.session.add(relation)

    relation.status = status
    relation.source_method = classification.get("source_method", "semi-auto")
    relation.llm_confidence = round(classification["confidence"], 4)
    relation.sequence_support = round(max(stats["sequence_lr"], stats["sequence_rl"]), 4)
    relation.cooccurrence_score = round(stats["cooccurrence_score"], 4)
    relation.embedding_similarity = round(stats["embedding_similarity"], 4)
    relation.final_score = round(final_score, 4)
    relation.llm_reason = classification["reason"]
    return status


def clear_generated_relations(tag_ids):
    if not tag_ids:
        return 0
    stmt = db.delete(TagRelation).where(
        TagRelation.source_tag_id.in_(tag_ids),
        TagRelation.target_tag_id.in_(tag_ids),
        TagRelation.source_method.like("semi-auto%"),
    )
    result = db.session.execute(stmt)
    return result.rowcount or 0


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        tags = load_tags(args.domain_ids)
        if len(tags) < 2:
            print("[SKIP] 标签数量不足，无法构建关系")
            return

        if args.replace_generated:
            deleted = clear_generated_relations([tag.id for tag in tags])
            print(f"[CLEAN] 已删除已有 semi-auto 关系: {deleted}")

        selected_pairs, cooccurrence, direction_count = shortlist_pairs(tags, args)
        tags_by_id = {tag.id: tag for tag in tags}

        created_or_updated = 0
        pending_count = 0
        auto_approved_count = 0

        for left_id, right_id in sorted(selected_pairs):
            left_tag = tags_by_id[left_id]
            right_tag = tags_by_id[right_id]
            stats = {
                "cooccurrence_score": round(cooccurrence.get((left_id, right_id), 0.0), 4),
                "sequence_lr": round(directional_support(direction_count, left_id, right_id), 4),
                "sequence_rl": round(directional_support(direction_count, right_id, left_id), 4),
                "embedding_similarity": round(embedding_similarity(left_tag, right_tag), 4),
            }
            classification = classify_pair(left_tag, right_tag, stats, args.enable_llm)
            if args.llm_required and classification.get("source_method") != "semi-auto-llm":
                continue
            if classification["relation_type"] == RELATION_NONE:
                continue

            direction = normalize_direction(left_tag, right_tag, classification)
            if not direction:
                continue
            source_tag_id, target_tag_id = direction
            final_score = score_relation(
                classification["relation_type"],
                classification["confidence"],
                stats,
                classification["direction"],
            )
            if final_score < args.min_final_score:
                continue

            status = upsert_relation(
                source_tag_id,
                target_tag_id,
                classification["relation_type"],
                final_score,
                classification,
                stats,
                args.auto_approve_threshold,
            )
            created_or_updated += 1
            if status == "auto_approved":
                auto_approved_count += 1
            else:
                pending_count += 1

        db.session.commit()
        print(f"[DONE] 候选关系写入完成: {created_or_updated}")
        print(f"  auto_approved: {auto_approved_count}")
        print(f"  pending: {pending_count}")


if __name__ == "__main__":
    main()
