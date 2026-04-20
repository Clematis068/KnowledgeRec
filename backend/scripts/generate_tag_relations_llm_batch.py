"""
LLM 批量生成标签知识关系。

按领域分批，将同领域所有标签一次性交给千问，由 LLM 输出
PREREQUISITE / PARENT_OF / RELATED_TO 关系，再计算 embedding
相似度作为辅助置信分，写入 MySQL tag_relation 表。

用法:
  cd backend && uv run python -m scripts.generate_tag_relations_llm_batch
  cd backend && uv run python -m scripts.generate_tag_relations_llm_batch --domain-ids 3 4 5
  cd backend && uv run python -m scripts.generate_tag_relations_llm_batch --replace-generated --auto-approve-threshold 0.75
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.domain import Domain
from app.models.tag import Tag
from app.models.tag_taxonomy import TagRelation
from app.services.qwen_service import qwen_service
from app.utils.helpers import cosine_similarity

VALID_RELATION_TYPES = {"PREREQUISITE", "PARENT_OF", "RELATED_TO"}

SYSTEM_PROMPT = """\
你是知识图谱构建专家。给定一个学科领域下的所有知识标签列表，请输出它们之间的知识关系。

关系类型（只允许以下三种）：
- PREREQUISITE: source 是学习 target 的前置知识（必须先学 source 才能学 target）。例：线性代数 → 机器学习（先学线性代数才能学机器学习）
- PARENT_OF: source 是 target 的上位/父话题（source 是更大的范畴，target 是其子分支）。例：物理化学 → 化学动力学（物理化学是更大主题，化学动力学是其子分支）
- RELATED_TO: source 和 target 密切相关但无层级或先修关系

规则：
1. 只输出确定性高的关系，不确定的不要输出
2. PREREQUISITE 必须是严格的学习先后依赖，不能把常见关联误判为先修
3. PARENT_OF 的方向务必正确：source 必须是更宽泛的上位概念，target 是更具体的下位子领域
4. 每个标签至少出现在1条关系中（如果某标签确实与其他标签无关则可以不出现）
5. source 和 target 必须严格使用给定列表中的原始标签名，不要修改
6. 关系数量要充分，同领域标签间通常有较多关联，不要遗漏明显的关系

严格返回 JSON 数组，不要输出任何其他内容：
[{"source":"标签A", "target":"标签B", "type":"PREREQUISITE", "confidence":0.9, "reason":"简短理由"}]"""


def parse_args():
    parser = argparse.ArgumentParser(description="LLM 批量生成标签知识关系")
    parser.add_argument("--domain-ids", type=int, nargs="*", help="只处理这些 domain_id（默认全部）")
    parser.add_argument("--auto-approve-threshold", type=float, default=0.80, help="final_score >= 此值自动通过")
    parser.add_argument("--replace-generated", action="store_true", help="先删除已有的 llm-batch 关系再重建")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    return parser.parse_args()


def load_domains(domain_ids=None):
    stmt = db.select(Domain).order_by(Domain.id)
    if domain_ids:
        stmt = stmt.filter(Domain.id.in_(domain_ids))
    return db.session.scalars(stmt).all()


def load_tags_for_domain(domain_id):
    return db.session.scalars(
        db.select(Tag).filter_by(domain_id=domain_id).order_by(Tag.name)
    ).all()


def call_llm_for_domain(domain_name, tag_names):
    user_message = f"领域：{domain_name}\n标签列表：{json.dumps(tag_names, ensure_ascii=False)}"
    content = qwen_service.chat(user_message, system_prompt=SYSTEM_PROMPT).strip()
    # 提取 JSON 数组
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.S)
        if match:
            return json.loads(match.group(0))
        print(f"  [WARN] LLM 返回非 JSON: {content[:200]}")
        return []


def compute_embedding_similarity(tag_a, tag_b):
    if tag_a.embedding and tag_b.embedding:
        return max(cosine_similarity(tag_a.embedding, tag_b.embedding), 0.0)
    return 0.0


def compute_final_score(llm_confidence, emb_sim):
    return min(0.65 * llm_confidence + 0.35 * emb_sim, 1.0)


def clamp_confidence(raw):
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if v > 1:
        v = v / 10.0
    return max(0.0, min(v, 1.0))


def clear_generated(domain_ids=None):
    stmt = db.delete(TagRelation).where(TagRelation.source_method == "llm-batch")
    if domain_ids:
        tag_ids_stmt = db.select(Tag.id).filter(Tag.domain_id.in_(domain_ids))
        tag_ids = [t for t in db.session.scalars(tag_ids_stmt)]
        if tag_ids:
            stmt = stmt.where(
                TagRelation.source_tag_id.in_(tag_ids),
                TagRelation.target_tag_id.in_(tag_ids),
            )
    result = db.session.execute(stmt)
    db.session.commit()
    return result.rowcount or 0


def find_uncovered_tags(tags_by_name):
    """找出还没出现在任何 approved/auto_approved 关系中的标签。"""
    tag_ids = {t.id for t in tags_by_name.values()}
    approved_statuses = ("approved", "auto_approved")
    src_ids = set(db.session.scalars(
        db.select(TagRelation.source_tag_id)
        .filter(TagRelation.status.in_(approved_statuses), TagRelation.source_tag_id.in_(tag_ids))
    ).all())
    tgt_ids = set(db.session.scalars(
        db.select(TagRelation.target_tag_id)
        .filter(TagRelation.status.in_(approved_statuses), TagRelation.target_tag_id.in_(tag_ids))
    ).all())
    covered_ids = src_ids | tgt_ids
    return [name for name, tag in tags_by_name.items() if tag.id not in covered_ids]


SUPPLEMENT_PROMPT = """\
你是知识图谱构建专家。给定一个学科领域下的标签列表，其中"未覆盖标签"尚未出现在任何知识关系中。
请为这些未覆盖标签补充与该领域其他标签之间的关系。

关系类型（只允许以下三种）：
- PREREQUISITE: source 是学习 target 的前置知识（必须先学 source 才能学 target）
- PARENT_OF: source 是 target 的上位/父话题（source 是更大的范畴，target 是其子分支）
- RELATED_TO: source 和 target 密切相关但无层级或先修关系

规则：
1. 每个未覆盖标签必须至少出现在1条关系中
2. source 和 target 可以是该领域内的任意标签（不限于未覆盖标签）
3. PARENT_OF 方向：source 必须是更宽泛的上位概念
4. 严格使用给定列表中的原始标签名

严格返回 JSON 数组：
[{"source":"标签A", "target":"标签B", "type":"PREREQUISITE", "confidence":0.9, "reason":"简短理由"}]"""


def call_llm_supplement(domain_name, all_tag_names, uncovered_names):
    user_message = (
        f"领域：{domain_name}\n"
        f"全部标签：{json.dumps(all_tag_names, ensure_ascii=False)}\n"
        f"未覆盖标签：{json.dumps(uncovered_names, ensure_ascii=False)}"
    )
    content = qwen_service.chat(user_message, system_prompt=SUPPLEMENT_PROMPT).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.S)
        if match:
            return json.loads(match.group(0))
        print(f"  [WARN] 补充 LLM 返回非 JSON: {content[:200]}")
        return []


def process_domain(domain, tags_by_name, auto_threshold, dry_run):
    tag_names = sorted(tags_by_name.keys())
    print(f"\n[{domain.id}] {domain.name} ({len(tag_names)} 标签)")

    relations = call_llm_for_domain(domain.name, tag_names)
    if not relations:
        print(f"  LLM 未返回有效关系")
        return 0, 0

    created, skipped = upsert_relations(relations, tags_by_name, auto_threshold, dry_run)
    if not dry_run:
        db.session.commit()
    print(f"  第1轮: 写入={created}  跳过={skipped}")

    # 补充轮：对未覆盖标签追加关系
    if not dry_run:
        uncovered = find_uncovered_tags(tags_by_name)
        if uncovered:
            print(f"  补充轮: {len(uncovered)} 个未覆盖标签")
            time.sleep(1)
            supplement = call_llm_supplement(domain.name, tag_names, uncovered)
            c2, s2 = upsert_relations(supplement, tags_by_name, auto_threshold, dry_run)
            db.session.commit()
            created += c2
            skipped += s2
            print(f"  补充轮: 写入={c2}  跳过={s2}")

    print(f"  合计: 写入={created}  跳过={skipped}")
    return created, skipped


def upsert_relations(relations, tags_by_name, auto_threshold, dry_run):
    created = 0
    skipped = 0
    for item in relations:
        source_name = (item.get("source") or "").strip()
        target_name = (item.get("target") or "").strip()
        rel_type = (item.get("type") or "").upper()
        confidence = clamp_confidence(item.get("confidence"))
        reason = (item.get("reason") or "")[:200]

        if rel_type not in VALID_RELATION_TYPES:
            skipped += 1
            continue
        if source_name not in tags_by_name or target_name not in tags_by_name:
            skipped += 1
            continue
        if source_name == target_name:
            skipped += 1
            continue

        source_tag = tags_by_name[source_name]
        target_tag = tags_by_name[target_name]
        emb_sim = compute_embedding_similarity(source_tag, target_tag)
        final_score = compute_final_score(confidence, emb_sim)
        status = "auto_approved" if final_score >= auto_threshold else "pending"

        if dry_run:
            print(f"  [DRY] {rel_type:13s} {source_name} -> {target_name}  "
                  f"llm={confidence:.2f} emb={emb_sim:.2f} final={final_score:.3f} [{status}]")
            created += 1
            continue

        existing = db.session.scalar(
            db.select(TagRelation).filter_by(
                source_tag_id=source_tag.id,
                target_tag_id=target_tag.id,
                relation_type=rel_type,
            )
        )
        if existing:
            existing.llm_confidence = round(confidence, 4)
            existing.embedding_similarity = round(emb_sim, 4)
            existing.final_score = round(final_score, 4)
            existing.llm_reason = reason
            existing.source_method = "llm-batch"
            if existing.status not in ("approved", "rejected"):
                existing.status = status
        else:
            relation = TagRelation(
                source_tag_id=source_tag.id,
                target_tag_id=target_tag.id,
                relation_type=rel_type,
                status=status,
                source_method="llm-batch",
                llm_confidence=round(confidence, 4),
                embedding_similarity=round(emb_sim, 4),
                final_score=round(final_score, 4),
                llm_reason=reason,
            )
            db.session.add(relation)
        created += 1
    return created, skipped


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        if args.replace_generated:
            deleted = clear_generated(args.domain_ids)
            print(f"[CLEAN] 删除已有 llm-batch 关系: {deleted}")

        domains = load_domains(args.domain_ids)
        total_created = 0
        total_skipped = 0

        for domain in domains:
            tags = load_tags_for_domain(domain.id)
            if len(tags) < 2:
                print(f"\n[{domain.id}] {domain.name} 标签不足，跳过")
                continue

            tags_by_name = {tag.name: tag for tag in tags}
            created, skipped = process_domain(
                domain, tags_by_name, args.auto_approve_threshold, args.dry_run,
            )
            total_created += created
            total_skipped += skipped
            time.sleep(1)  # API 限速

        print(f"\n[DONE] 总计写入: {total_created}  跳过: {total_skipped}")

        if not args.dry_run:
            from sqlalchemy import func
            counts = db.session.execute(
                db.select(TagRelation.relation_type, TagRelation.status, func.count(TagRelation.id))
                .group_by(TagRelation.relation_type, TagRelation.status)
                .order_by(TagRelation.relation_type, TagRelation.status)
            ).all()
            print("\n最终关系统计:")
            for r_type, status, cnt in counts:
                print(f"  {r_type:15s} {status:15s} {cnt}")


if __name__ == "__main__":
    main()
