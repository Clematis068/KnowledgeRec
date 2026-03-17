"""
修复被过度清洗的社区帖子：从原始 JSONL 重新读取 markdown，
两阶段清洗：代码规则粗过滤 → 千问 LLM 精洗。

用法：
  cd backend && uv run python -m scripts.fix_overcleaned_posts
  cd backend && uv run python -m scripts.fix_overcleaned_posts --dry-run
  cd backend && uv run python -m scripts.fix_overcleaned_posts --no-llm   # 跳过LLM精洗
  cd backend && uv run python -m scripts.fix_overcleaned_posts --limit 5   # 只处理5篇
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from sqlalchemy import select, func

from app import create_app, db
from app.models.post import Post
from app.utils.markdown_cleaner import clean_markdown, markdown_to_plaintext
from app.services.qwen_service import qwen_service


JSONL_PATH = Path(__file__).resolve().parent.parent.parent / ".firecrawl" / "community-batch" / "posts.jsonl"

COMMUNITY_LABELS = {
    "csdn": "CSDN",
    "cnblogs": "博客园",
    "juejin": "稀土掘金",
    "oschina": "开源中国",
    "51cto": "51CTO",
}

# LLM 精洗 prompt —— 直接输出纯文本，避免 JSON 转义问题
LLM_SYSTEM_PROMPT = """你是一个文章内容清洗助手。

任务：从下面的 markdown 文章中，删除所有非正文内容，只保留文章正文。

需要删除的内容（不论以何种形式出现）：
- 评论区、点赞、收藏、分享、打赏按钮及计数
- 广告、推广、热门推荐、相关推荐、推荐阅读
- 导航栏、侧边栏、页脚、面包屑
- 弹窗文案（收藏成功、温馨提示、沉浸阅读等）
- 作者信息栏、关注按钮、粉丝数
- 公众号/微信推广
- 版权声明、转载说明
- "上一篇/下一篇"导航

要求：
- 不要改写、缩写或总结，保持正文内容完整
- 保留所有 markdown 格式（标题、代码块、列表、图片等）
- 直接输出清洗后的正文，不要加任何说明或前缀"""


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_url_from_content(content: str) -> str | None:
    match = re.search(r"原文链接[：:]\s*(https?://\S+)", content or "")
    return match.group(1).strip() if match else None


def llm_clean(text: str) -> str | None:
    """用千问 LLM 精洗文本，返回清洗后的正文，失败返回 None。"""
    truncated = text[:12000]
    try:
        result = qwen_service.chat(truncated, system_prompt=LLM_SYSTEM_PROMPT).strip()
        return result if len(result) > 50 else None
    except Exception as e:
        print(f"    LLM 清洗失败: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="两阶段清洗修复帖子（代码规则 + LLM）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印不写数据库")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 精洗，只用代码规则")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 篇")
    args = parser.parse_args()

    if not JSONL_PATH.exists():
        raise SystemExit(f"JSONL 文件不存在: {JSONL_PATH}")

    records = load_records(JSONL_PATH)
    url_to_record: dict[str, dict] = {}
    for r in records:
        url = (r.get("url") or "").strip()
        if url:
            url_to_record[url] = r

    app = create_app()
    with app.app_context():
        # 只处理内容 ≤200 字的帖子（未修复的）
        posts = db.session.scalars(
            select(Post)
            .where(Post.content.contains("原文链接"))
            .where(func.length(Post.content) <= 200)
            .order_by(Post.id)
        ).all()

        if args.limit:
            posts = posts[:args.limit]

        fixed = 0
        skipped = 0
        llm_used = 0

        print(f"===== 两阶段清洗 =====")
        print(f"帖子数: {len(posts)}, LLM精洗: {'否' if args.no_llm else '是'}, dry_run: {args.dry_run}")
        print()

        for i, post in enumerate(posts, start=1):
            url = extract_url_from_content(post.content)
            if not url or url not in url_to_record:
                skipped += 1
                continue

            record = url_to_record[url]
            community_key = record.get("community", "")
            community_label = COMMUNITY_LABELS.get(community_key, community_key)
            raw_markdown = (record.get("markdown") or "").strip()

            # ── 第一阶段：代码规则粗过滤 ──
            cleaned = clean_markdown(raw_markdown, community_key)

            if len(cleaned) < 30:
                if args.dry_run:
                    print(f"  SKIP (太短) id={post.id} {post.title[:40]}")
                skipped += 1
                continue

            # ── 第二阶段：LLM 精洗 ──
            if not args.no_llm:
                llm_result = llm_clean(cleaned)
                if llm_result and len(llm_result) > len(cleaned) * 0.3:
                    # LLM 结果有效且没被过度截断
                    cleaned = llm_result
                    llm_used += 1
                else:
                    print(f"  [{i}] id={post.id} LLM 结果无效，使用代码规则结果")

                # 控制请求频率，避免触发限流
                time.sleep(0.5)

            # ── 拼来源尾注 ──
            footer_parts = []
            if url:
                footer_parts.append(f"原文链接：{url}")
            if community_label:
                footer_parts.append(f"来源：{community_label}")

            new_content = cleaned
            if footer_parts:
                new_content += "\n\n---\n\n" + " | ".join(footer_parts)

            new_content = new_content[:15000]
            new_summary = markdown_to_plaintext(cleaned, max_length=300)

            if args.dry_run:
                tag = " [LLM]" if not args.no_llm and llm_used == (fixed + 1) else ""
                print(f"  [{i}] id={post.id} 旧{len(post.content):>6} -> 新{len(new_content):>6}{tag} | {post.title[:40]}")
            else:
                post.content = new_content
                post.summary = new_summary

            fixed += 1

            if not args.dry_run and fixed % 50 == 0:
                db.session.commit()
                print(f"  进度: {fixed}/{len(posts)}")

        if not args.dry_run:
            db.session.commit()

        print()
        print(f"===== 完成 =====")
        print(f"修复: {fixed}")
        print(f"跳过: {skipped}")
        if not args.no_llm:
            print(f"LLM精洗成功: {llm_used}/{fixed}")


if __name__ == "__main__":
    main()
