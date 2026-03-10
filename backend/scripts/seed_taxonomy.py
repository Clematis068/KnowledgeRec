"""
领域与标签初始化脚本

用法:
  cd backend && uv run python -m scripts.seed_taxonomy
  cd backend && uv run python -m scripts.seed_taxonomy --generate-tags --per-domain 20
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.domain import Domain
from app.models.tag import Tag
from app.services.qwen_service import qwen_service
from app.services.tag_taxonomy_service import tag_taxonomy_service
from app.taxonomy import FIXED_DOMAINS, build_domain_prompt_text


def upsert_domains():
    created = 0
    updated = 0

    for spec in FIXED_DOMAINS:
        domain = Domain.query.filter_by(name=spec["name"]).first()
        if domain:
            domain.description = spec["description"]
            updated += 1
        else:
            domain = Domain(name=spec["name"], description=spec["description"])
            db.session.add(domain)
            created += 1

    db.session.commit()

    for domain in Domain.query.order_by(Domain.id.asc()).all():
        tag_taxonomy_service.sync_domain_to_neo4j(domain)

    print(f"[OK] 领域已同步: 新增 {created}，更新 {updated}")


def generate_tags_for_domain(domain, per_domain):
    spec = next((item for item in FIXED_DOMAINS if item["name"] == domain.name), None)
    domain_prompt = build_domain_prompt_text(spec) if spec else f"{domain.name}：{domain.description or ''}"
    system_prompt = (
        "你是知识社区 taxonomy 设计助手。"
        "请围绕给定一级领域，生成一组适合知识社区注册兴趣选择和推荐召回的二级标签。"
        "要求标签简洁、稳定、可复用、避免重复。"
        "严格返回 JSON："
        '{"tags": ["标签1", "标签2"]}'
    )
    message = (
        f"{domain_prompt}\n"
        f"请生成 {per_domain} 个标签。"
    )
    payload = qwen_service.chat_json(message, system_prompt=system_prompt)
    return payload.get("tags") or []


def upsert_tags(per_domain):
    for domain in Domain.query.order_by(Domain.id.asc()).all():
        try:
            tags = generate_tags_for_domain(domain, per_domain)
        except Exception as exc:
            print(f"[WARN] 领域 {domain.name} 生成标签失败: {exc}")
            continue

        created = 0
        for raw_tag in tags:
            name = tag_taxonomy_service.normalize_text(raw_tag)
            if not name:
                continue
            tag = Tag.query.filter_by(domain_id=domain.id, name=name).first()
            if tag:
                continue
            embedding = None
            try:
                embedding = qwen_service.get_embedding(name)
            except Exception:
                pass
            tag = Tag(name=name, domain_id=domain.id, embedding=embedding)
            db.session.add(tag)
            db.session.flush()
            tag_taxonomy_service.sync_tag_to_neo4j(tag)
            created += 1

        db.session.commit()
        print(f"[OK] {domain.name} 新增标签 {created} 个")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-tags", action="store_true", help="调用千问为每个领域生成标签")
    parser.add_argument("--per-domain", type=int, default=20, help="每个领域生成多少个标签")
    return parser.parse_args()


def main():
    args = parse_args()
    app = create_app()
    with app.app_context():
        upsert_domains()
        if args.generate_tags:
            upsert_tags(args.per_domain)
        print("[DONE] taxonomy 初始化完成")


if __name__ == "__main__":
    main()
