"""
一次性清洗数据库中已导入的 Firecrawl 社区帖子 content 字段。

清洗规则：
  1. 提取 content 中 --- 分隔符后的 markdown 正文
  2. 调用 clean_markdown() 去除导航栏、广告、搜索栏等噪声
  3. 将清洗后的 markdown 作为新的 content
  4. 来源信息移到末尾
  5. 更新 summary 为清洗后正文的前 200 字纯文本

用法：
  cd backend && uv run python -m scripts.clean_existing_posts
  cd backend && uv run python -m scripts.clean_existing_posts --dry-run
  cd backend && uv run python -m scripts.clean_existing_posts --limit 10
"""
from __future__ import annotations

import argparse
import re

from sqlalchemy import select

from app import create_app, db
from app.models.post import Post
from app.utils.markdown_cleaner import clean_markdown, markdown_to_plaintext


SOURCE_MARKER = "原文链接：http"


def extract_community(content: str) -> str:
    """从帖子 content 的头部信息中提取社区标识。"""
    community_map = {
        "CSDN": "csdn",
        "博客园": "cnblogs",
        "稀土掘金": "juejin",
        "开源中国": "oschina",
        "51CTO": "51cto",
    }
    match = re.search(r"来源社区：(\S+)", content or "")
    if match:
        label = match.group(1).strip()
        return community_map.get(label, "")
    return ""


def extract_source_info(content: str) -> dict:
    """提取帖子头部的来源元信息。"""
    info = {}
    for pattern, key in [
        (r"来源社区：(\S+)", "community"),
        (r"抓取关键词：(\S+)", "keyword"),
        (r"原文链接：(https?://\S+)", "url"),
    ]:
        match = re.search(pattern, content or "")
        if match:
            info[key] = match.group(1).strip()
    return info


def extract_markdown_body(content: str) -> str:
    """提取 --- 分隔符后的 markdown 正文。"""
    parts = content.split("\n\n---\n\n", 1)
    if len(parts) == 2:
        return parts[1]
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="清洗已导入帖子的 content")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写数据库")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 篇")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stmt = (
            select(Post)
            .where(Post.content.contains(SOURCE_MARKER))
            .order_by(Post.id)
        )
        if args.limit:
            stmt = stmt.limit(args.limit)

        posts = db.session.scalars(stmt).all()
        if not posts:
            print("未找到导入社区帖。")
            return

        print(f"===== 清洗已导入帖子 =====")
        print(f"帖子数: {len(posts)}")
        print(f"dry_run: {args.dry_run}")
        print()

        cleaned_count = 0
        skipped_count = 0

        for i, post in enumerate(posts, start=1):
            community = extract_community(post.content)
            source_info = extract_source_info(post.content)
            raw_md = extract_markdown_body(post.content)

            cleaned = clean_markdown(raw_md, community)

            if len(cleaned) < 30:
                skipped_count += 1
                if args.dry_run:
                    print(f"  [{i}] SKIP (太短) id={post.id} {post.title[:40]}")
                continue

            # 来源信息放末尾
            footer_parts = []
            if source_info.get("url"):
                footer_parts.append(f"原文链接：{source_info['url']}")
            if source_info.get("community"):
                footer_parts.append(f"来源：{source_info['community']}")

            if footer_parts:
                new_content = cleaned + "\n\n---\n\n" + " | ".join(footer_parts)
            else:
                new_content = cleaned

            new_summary = markdown_to_plaintext(cleaned, max_length=300)

            if args.dry_run:
                print(f"  [{i}] id={post.id} 原始{len(post.content):>6} -> 清洗{len(new_content):>6} | {post.title[:40]}")
            else:
                post.content = new_content
                post.summary = new_summary

            cleaned_count += 1

            if not args.dry_run and i % 50 == 0:
                db.session.commit()
                print(f"  进度: {i}/{len(posts)}")

        if not args.dry_run:
            db.session.commit()

        print()
        print(f"===== 完成 =====")
        print(f"清洗: {cleaned_count}")
        print(f"跳过: {skipped_count}")


if __name__ == "__main__":
    main()
