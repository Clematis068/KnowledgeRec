"""
将 .firecrawl/domain-batch/ 下的搜索结果导入数据库。
每个 JSON 文件对应一个领域，文件名即领域名（如 数学.json）。
自动匹配领域下的标签，两阶段清洗（代码规则 + LLM）。

用法：
  cd backend && uv run python -m scripts.import_domain_batch
  cd backend && uv run python -m scripts.import_domain_batch --dry-run
  cd backend && uv run python -m scripts.import_domain_batch --no-llm
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from sqlalchemy import select

from app import create_app, db
from app.models.domain import Domain
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.user import User
from app.services.qwen_service import qwen_service
from app.utils.markdown_cleaner import clean_markdown, markdown_to_plaintext

BATCH_DIR = Path(__file__).resolve().parent.parent.parent / ".firecrawl" / "domain-batch"

LLM_SYSTEM_PROMPT = """你是一个文章内容清洗助手。

任务：从下面的 markdown 文章中，删除所有非正文内容，只保留文章正文。

需要删除的内容（不论以何种形式出现）：
- 评论区、点赞、收藏、分享、打赏按钮及计数
- 广告、推广、热门推荐、相关推荐、推荐阅读
- 导航栏、侧边栏、页脚、面包屑
- 弹窗文案（收藏成功、温馨提示、沉浸阅读等）
- 作者信息栏、关注按钮、粉丝数
- 公众号/微信推广、版权声明、转载说明
- "上一篇/下一篇"导航

要求：
- 不要改写、缩写或总结，保持正文内容完整
- 保留所有 markdown 格式（标题、代码块、列表、图片等）
- 直接输出清洗后的正文，不要加任何说明或前缀"""


def llm_clean(text: str) -> str | None:
    try:
        result = qwen_service.chat(text[:12000], system_prompt=LLM_SYSTEM_PROMPT).strip()
        return result if len(result) > 50 else None
    except Exception as e:
        print(f"    LLM 失败: {e}")
        return None


def existing_urls() -> set[str]:
    urls: set[str] = set()
    posts = db.session.scalars(select(Post.content).where(Post.content.contains("原文链接"))).all()
    for content in posts:
        m = re.search(r"原文链接[：:]\s*(https?://\S+)", content or "")
        if m:
            urls.add(m.group(1).strip())
    return urls


def pick_tag_for_domain(domain_obj: Domain, title: str, url: str) -> Tag | None:
    """从领域的标签里挑一个最匹配标题的（没有则取第一个空帖子标签）"""
    tags = db.session.scalars(select(Tag).where(Tag.domain_id == domain_obj.id)).all()
    if not tags:
        return None
    # 标题命中优先
    for tag in tags:
        if tag.name in title:
            return tag
    # 否则取帖子数最少的标签
    from sqlalchemy import func, text
    rows = db.session.execute(
        text("SELECT tag_id, COUNT(*) as cnt FROM post_tag WHERE tag_id IN :ids GROUP BY tag_id"),
        {"ids": tuple(t.id for t in tags) or (0,)}
    ).all()
    tag_cnt = {r[0]: r[1] for r in rows}
    tags_sorted = sorted(tags, key=lambda t: tag_cnt.get(t.id, 0))
    return tags_sorted[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    json_files = sorted(BATCH_DIR.glob("*.json"))
    if not json_files:
        raise SystemExit(f"没有找到 JSON 文件: {BATCH_DIR}")

    app = create_app()
    random.seed(42)

    with app.app_context():
        users = db.session.scalars(select(User).order_by(User.id)).all()
        if not users:
            raise SystemExit("数据库中没有用户")

        known_urls = existing_urls()
        inserted = 0
        skipped = 0

        print(f"===== 导入 domain-batch =====")
        print(f"文件数: {len(json_files)}, LLM: {'否' if args.no_llm else '是'}, dry_run: {args.dry_run}")
        print()

        for jf in json_files:
            domain_name = jf.stem  # 文件名即领域名
            domain_obj = db.session.scalars(
                select(Domain).where(Domain.name == domain_name)
            ).first()
            if not domain_obj:
                print(f"  [SKIP] 领域不存在: {domain_name}")
                skipped += 1
                continue

            data = json.loads(jf.read_text(encoding="utf-8"))
            items = [x for x in data.get("data", {}).get("web", []) if x.get("markdown")]

            print(f"  [{domain_name}] {len(items)} 篇")

            for item in items:
                url = (item.get("url") or "").strip()
                title = (item.get("title") or "").strip()[:255]
                raw_md = (item.get("markdown") or "").strip()

                if not title or not raw_md:
                    skipped += 1
                    continue
                if url and url in known_urls:
                    print(f"    跳过重复: {title[:40]}")
                    skipped += 1
                    continue

                # 匹配标签
                tag = pick_tag_for_domain(domain_obj, title, url)
                if not tag:
                    print(f"    跳过无标签: {title[:40]}")
                    skipped += 1
                    continue

                # 第一阶段：代码规则清洗
                cleaned = clean_markdown(raw_md, "")
                if len(cleaned) < 50:
                    skipped += 1
                    continue

                # 第二阶段：LLM 精洗
                if not args.no_llm:
                    llm_result = llm_clean(cleaned)
                    if llm_result and len(llm_result) > len(cleaned) * 0.3:
                        cleaned = llm_result
                    time.sleep(0.3)

                # 拼来源尾注
                footer = f"\n\n---\n\n原文链接：{url}" if url else ""
                content = (cleaned + footer)[:15000]
                summary = markdown_to_plaintext(cleaned, max_length=300)

                if args.dry_run:
                    print(f"    [{tag.name}] {len(content):>5}字 {title[:40]}")
                else:
                    from datetime import datetime, timedelta
                    author = users[inserted % len(users)]
                    created_at = datetime.now() - timedelta(days=random.randint(1, 180))
                    p = Post(
                        title=title,
                        content=content,
                        summary=summary,
                        author_id=author.id,
                        domain_id=domain_obj.id,
                        view_count=random.randint(10, 800),
                        like_count=random.randint(0, 80),
                        created_at=created_at,
                    )
                    db.session.add(p)
                    db.session.flush()
                    db.session.execute(post_tag.insert().values(post_id=p.id, tag_id=tag.id))
                    if url:
                        known_urls.add(url)

                inserted += 1

        if not args.dry_run:
            db.session.commit()

        print()
        print(f"===== 完成 =====")
        print(f"导入: {inserted}, 跳过: {skipped}")


if __name__ == "__main__":
    main()
