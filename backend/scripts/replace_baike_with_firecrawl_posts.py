"""
删除之前的百科抓取帖子，并导入 Firecrawl 批量抓取的社区帖子。

默认删除规则：
  - 标题包含「知识百科」
  - 标题包含「核心概念与前沿发展」

默认导入文件：
  ../.firecrawl/community-batch/posts.jsonl

用法：
  cd backend && uv run python -m scripts.replace_baike_with_firecrawl_posts
  cd backend && uv run python -m scripts.replace_baike_with_firecrawl_posts --input ../.firecrawl/community-batch/posts.jsonl
  cd backend && uv run python -m scripts.replace_baike_with_firecrawl_posts --dry-run
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, or_, select

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.user import User


from app.utils.markdown_cleaner import clean_markdown, markdown_to_plaintext


COMMUNITY_LABELS = {
    "csdn": "CSDN",
    "cnblogs": "博客园",
    "juejin": "稀土掘金",
    "oschina": "开源中国",
    "51cto": "51CTO",
}


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def build_tag_map() -> dict[str, Tag]:
    tags = db.session.scalars(select(Tag).order_by(Tag.name, Tag.domain_id, Tag.id)).all()
    tag_map: dict[str, Tag] = {}
    for tag in tags:
        tag_map.setdefault(tag.name, tag)
    return tag_map


def choose_users() -> list[User]:
    users = db.session.scalars(select(User).order_by(User.id)).all()
    if not users:
        raise RuntimeError("数据库中没有用户，无法分配作者。")
    return users


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    posts = db.session.scalars(select(Post.content).where(Post.content.contains("原文链接："))).all()
    for content in posts:
        if not content:
            continue
        match = re.search(r"原文链接：(https?://\S+)", content)
        if match:
            urls.add(match.group(1).strip())
    return urls


def compose_content(record: dict) -> str:
    community_key = record.get("community", "")
    community = COMMUNITY_LABELS.get(community_key, community_key or "未知社区")
    url = record.get("url", "")
    markdown = (record.get("markdown") or "").strip()

    # 清洗 markdown 噪声
    cleaned = clean_markdown(markdown, community_key)

    # 来源信息放末尾
    footer_parts = []
    if url:
        footer_parts.append(f"原文链接：{url}")
    if community:
        footer_parts.append(f"来源：{community}")

    if footer_parts:
        content = cleaned + "\n\n---\n\n" + " | ".join(footer_parts)
    else:
        content = cleaned

    return content[:15000]


def summary_for(record: dict, content: str) -> str:
    summary = (record.get("description") or "").strip()
    if not summary:
        # 从清洗后的 markdown 中提取纯文本摘要
        summary = markdown_to_plaintext(content, max_length=300)
    return summary[:500]


def created_at_for(index: int) -> datetime:
    base = datetime.now() - timedelta(days=random.randint(1, 120))
    return base + timedelta(minutes=index % 1440)


def delete_old_baike_posts(dry_run: bool) -> dict[str, int]:
    stmt = select(Post.id).where(
        or_(
            Post.title.contains("知识百科"),
            Post.title.contains("核心概念与前沿发展"),
        )
    )
    ids = [row[0] for row in db.session.execute(stmt).all()]
    if not ids:
        return {"posts": 0, "post_tags": 0, "behaviors": 0}

    tag_link_count = db.session.execute(
        select(db.func.count()).select_from(post_tag).where(post_tag.c.post_id.in_(ids))
    ).scalar_one()
    behavior_count = db.session.execute(
        select(db.func.count()).select_from(UserBehavior).where(UserBehavior.post_id.in_(ids))
    ).scalar_one()

    if dry_run:
        return {
            "posts": len(ids),
            "post_tags": int(tag_link_count),
            "behaviors": int(behavior_count),
        }

    db.session.execute(delete(UserBehavior).where(UserBehavior.post_id.in_(ids)))
    db.session.execute(delete(post_tag).where(post_tag.c.post_id.in_(ids)))
    db.session.execute(delete(Post).where(Post.id.in_(ids)))
    db.session.flush()

    return {
        "posts": len(ids),
        "post_tags": int(tag_link_count),
        "behaviors": int(behavior_count),
    }


def import_records(records: list[dict], dry_run: bool) -> dict[str, object]:
    users = choose_users()
    tag_map = build_tag_map()
    imported_urls = existing_source_urls()

    inserted = 0
    skipped = 0
    by_community: Counter[str] = Counter()
    by_user: Counter[int] = Counter()
    missing_tags: Counter[str] = Counter()

    for index, record in enumerate(records):
        title = (record.get("title") or "").strip()[:255]
        # 去除来源平台后缀
        title = re.sub(
            r"\s*[-–—]\s*(?:CSDN博客|博客园|稀土掘金|开源中国|51CTO博客|OSCHINA.*)\s*$",
            "",
            title,
        ).strip()
        keyword = (record.get("keyword") or "").strip()
        url = (record.get("url") or "").strip()
        if not title:
            skipped += 1
            continue
        if url and url in imported_urls:
            skipped += 1
            continue

        tag = tag_map.get(keyword)
        if not tag:
            missing_tags[keyword] += 1
            skipped += 1
            continue

        author = users[index % len(users)]
        content = compose_content(record)
        if len(content) < 50:
            skipped += 1
            continue

        if not dry_run:
            post = Post(
                title=title,
                content=content,
                summary=summary_for(record, content),
                author_id=author.id,
                domain_id=tag.domain_id,
                view_count=random.randint(20, 1500),
                like_count=random.randint(0, 150),
                created_at=created_at_for(index),
            )
            db.session.add(post)
            db.session.flush()
            db.session.execute(post_tag.insert().values(post_id=post.id, tag_id=tag.id))

        if url:
            imported_urls.add(url)
        inserted += 1
        by_community[record.get("community", "unknown")] += 1
        by_user[author.id] += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "by_community": dict(by_community),
        "by_user": dict(by_user),
        "missing_tags": dict(missing_tags),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="替换百科帖子为 Firecrawl 社区帖子")
    parser.add_argument(
        "--input",
        default="../.firecrawl/community-batch/posts.jsonl",
        help="Firecrawl posts.jsonl 路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的操作，不写数据库")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在: {input_path}")

    records = load_records(input_path)
    app = create_app()
    random.seed(42)

    with app.app_context():
        before_count = db.session.scalar(select(db.func.count()).select_from(Post))
        delete_stats = delete_old_baike_posts(args.dry_run)
        import_stats = import_records(records, args.dry_run)

        if args.dry_run:
            after_count = before_count - delete_stats["posts"] + import_stats["inserted"]
        else:
            db.session.commit()
            after_count = db.session.scalar(select(db.func.count()).select_from(Post))

        print("===== 替换完成 =====")
        print(f"dry_run: {args.dry_run}")
        print(f"导入文件: {input_path}")
        print(f"删除百科帖子: {delete_stats['posts']}")
        print(f"删除 post_tag 关联: {delete_stats['post_tags']}")
        print(f"删除行为记录: {delete_stats['behaviors']}")
        print(f"导入帖子: {import_stats['inserted']}")
        print(f"跳过帖子: {import_stats['skipped']}")
        print(f"导入后帖子总数: {after_count}")
        print(f"按社区导入: {json.dumps(import_stats['by_community'], ensure_ascii=False)}")
        print(f"按用户分配: {json.dumps(import_stats['by_user'], ensure_ascii=False)}")
        if import_stats["missing_tags"]:
            print(f"缺失标签: {json.dumps(import_stats['missing_tags'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
