"""
同步已导入的 Firecrawl 社区帖子到 Neo4j，并为其批量生成点赞/评论。

特性：
1. 仅处理正文中带“原文链接：”的导入帖子
2. 同步 Post / User / Tag / Domain 及关系到 Neo4j
3. 用千问 API 基于帖子内容生成评论
4. 为帖子分配不同测试用户的点赞、评论

用法：
  cd backend && uv run python -m scripts.sync_imported_posts_and_generate_engagement
  cd backend && uv run python -m scripts.sync_imported_posts_and_generate_engagement --post-limit 10 --dry-run
  cd backend && uv run python -m scripts.sync_imported_posts_and_generate_engagement --likes-per-post 5 --comments-per-post 2
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.domain import Domain
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.user import User
from app.services.neo4j_service import neo4j_service
from app.services.qwen_service import qwen_service


SOURCE_MARKER = "原文链接：http"
COMMENT_FALLBACKS = [
    "这篇内容把核心思路讲清楚了，读完很有收获。",
    "案例和解释都比较具体，适合继续深入看下去。",
    "这篇文章的信息密度挺高，对理解主题很有帮助。",
    "读完之后对这个主题的整体脉络更清晰了。",
]


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def imported_posts(limit: int | None = None) -> list[Post]:
    stmt = (
        select(Post)
        .where(Post.content.contains(SOURCE_MARKER))
        .order_by(Post.id)
    )
    if limit:
        stmt = stmt.limit(limit)
    return db.session.scalars(stmt).all()


def all_users() -> list[User]:
    users = db.session.scalars(select(User).order_by(User.id)).all()
    if not users:
        raise RuntimeError("没有可用用户，无法生成互动。")
    return users


def extract_source_url(content: str) -> str:
    match = re.search(r"原文链接：(https?://\S+)", content or "")
    return match.group(1).strip() if match else ""


def build_comment_prompt(post: Post, desired_count: int) -> str:
    tag_names = [tag.name for tag in post.tags]
    content = post.content or ""
    body = content.split("\n\n---\n\n", 1)[-1]
    body = body[:1800]
    source_url = extract_source_url(content)

    return (
        "请你扮演知识社区的真实用户，基于给定帖子内容，生成自然、简短、像真人写的中文评论。\n"
        "要求：\n"
        "1. 返回严格 JSON，不要输出其他内容；\n"
        f"2. comments 数组长度必须是 {desired_count}；\n"
        "3. 每条评论 18-55 字；\n"
        "4. 风格要口语化，但不要太水，不要出现表情包、营销话术；\n"
        "5. 评论要和文章内容强相关，可以包含提问、总结、补充理解，但不要编造没出现的具体事实；\n"
        '6. JSON 格式：{"comments":["...", "..."]}\n\n'
        f"帖子标题：{post.title}\n"
        f"帖子摘要：{post.summary or ''}\n"
        f"标签：{'、'.join(tag_names) if tag_names else '无'}\n"
        f"原文链接：{source_url}\n"
        f"正文节选：\n{body}"
    )


def generate_comments_with_qwen(post: Post, desired_count: int) -> list[str]:
    prompt = build_comment_prompt(post, desired_count)
    try:
        result = qwen_service.chat_json(
            prompt,
            system_prompt="你是中文技术社区评论生成助手，只输出 JSON。",
        )
        comments = result.get("comments") or []
        cleaned = []
        for item in comments:
            text = str(item).strip().replace("\n", " ")
            if 8 <= len(text) <= 80:
                cleaned.append(text[:80])
        if cleaned:
            return cleaned[:desired_count]
    except Exception as e:
        print(f"  [Qwen失败] post={post.id} {e}")

    tag_text = post.tags[0].name if post.tags else "这个主题"
    fallback = [
        f"这篇把{tag_text}的关键点梳理得挺顺，适合先建立整体认识。",
        f"文中这部分对我理解{tag_text}很有帮助，尤其是脉络讲得比较清楚。",
    ]
    merged = fallback + COMMENT_FALLBACKS
    return merged[:desired_count]


def reset_existing_engagement(post_ids: list[int], dry_run: bool) -> dict[str, int]:
    like_count = db.session.scalar(
        select(db.func.count()).select_from(UserBehavior).where(
            UserBehavior.post_id.in_(post_ids),
            UserBehavior.behavior_type == "like",
        )
    ) or 0
    comment_count = db.session.scalar(
        select(db.func.count()).select_from(UserBehavior).where(
            UserBehavior.post_id.in_(post_ids),
            UserBehavior.behavior_type == "comment",
        )
    ) or 0

    if not dry_run:
        db.session.execute(
            delete(UserBehavior).where(
                UserBehavior.post_id.in_(post_ids),
                UserBehavior.behavior_type.in_(["like", "comment"]),
            )
        )
        for post in db.session.scalars(select(Post).where(Post.id.in_(post_ids))).all():
            post.like_count = 0

    return {"likes": int(like_count), "comments": int(comment_count)}


def pick_users_for_post(users: list[User], post: Post, likes_per_post: int, comments_per_post: int, rng: random.Random):
    candidates = [u for u in users if u.id != post.author_id]
    if not candidates:
        return [], []

    likes_n = min(likes_per_post, len(candidates))
    like_users = rng.sample(candidates, likes_n)

    remaining = [u for u in candidates if u.id not in {x.id for x in like_users}]
    if len(remaining) >= comments_per_post:
        comment_users = rng.sample(remaining, comments_per_post)
    else:
        comment_users = rng.sample(candidates, min(comments_per_post, len(candidates)))
    return like_users, comment_users


def create_engagement(posts: list[Post], users: list[User], likes_per_post: int, comments_per_post: int, dry_run: bool):
    rng = random.Random(20260316)
    stats = {
        "likes": 0,
        "comments": 0,
        "posts_processed": 0,
        "by_user_like": Counter(),
        "by_user_comment": Counter(),
    }

    for idx, post in enumerate(posts, start=1):
        like_users, comment_users = pick_users_for_post(users, post, likes_per_post, comments_per_post, rng)
        comments = generate_comments_with_qwen(post, len(comment_users)) if comment_users else []

        if not dry_run:
            base_time = post.created_at or datetime.now() - timedelta(days=30)

            for offset, user in enumerate(like_users, start=1):
                behavior = UserBehavior(
                    user_id=user.id,
                    post_id=post.id,
                    behavior_type="like",
                    created_at=base_time + timedelta(days=1, minutes=offset),
                )
                db.session.add(behavior)
                post.like_count = (post.like_count or 0) + 1
                stats["by_user_like"][user.id] += 1

            for offset, user in enumerate(comment_users, start=1):
                text = comments[offset - 1] if offset - 1 < len(comments) else COMMENT_FALLBACKS[(offset - 1) % len(COMMENT_FALLBACKS)]
                behavior = UserBehavior(
                    user_id=user.id,
                    post_id=post.id,
                    behavior_type="comment",
                    comment_text=text,
                    created_at=base_time + timedelta(days=2, minutes=offset),
                )
                db.session.add(behavior)
                stats["by_user_comment"][user.id] += 1

        stats["likes"] += len(like_users)
        stats["comments"] += len(comment_users)
        stats["posts_processed"] += 1

        if not dry_run and idx % 20 == 0:
            db.session.commit()
            print(f"  互动生成进度: {idx}/{len(posts)}，likes={stats['likes']} comments={stats['comments']}")

        time.sleep(0.15)

    return stats


def sync_posts_and_behaviors_to_neo4j(posts: list[Post], all_sync_users: list[User], dry_run: bool):
    if dry_run or not posts:
        return

    post_ids = [post.id for post in posts]
    domain_ids = sorted({post.domain_id for post in posts})

    domains = db.session.scalars(select(Domain).where(Domain.id.in_(domain_ids))).all()
    pt_rows = db.session.execute(
        select(post_tag.c.post_id, post_tag.c.tag_id).where(post_tag.c.post_id.in_(post_ids))
    ).fetchall()
    tag_ids = sorted({row[1] for row in pt_rows})
    tags = db.session.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all() if tag_ids else []

    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (d:Domain {id: item.id}) "
        "SET d.name = item.name, d.description = item.description",
        {"items": [{"id": d.id, "name": d.name, "description": d.description or ""} for d in domains]},
    )
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (u:User {id: item.id}) SET u.username = item.username",
        {"items": [{"id": u.id, "username": u.username} for u in all_sync_users]},
    )
    if tags:
        neo4j_service.run_write(
            "UNWIND $items AS item MERGE (t:Tag {id: item.id}) "
            "SET t.name = item.name, t.domain_id = item.domain_id",
            {"items": [{"id": t.id, "name": t.name, "domain_id": t.domain_id} for t in tags]},
        )
        neo4j_service.run_write(
            "UNWIND $items AS item "
            "MATCH (t:Tag {id: item.tag_id}), (d:Domain {id: item.domain_id}) "
            "MERGE (t)-[:BELONGS_TO]->(d)",
            {"items": [{"tag_id": t.id, "domain_id": t.domain_id} for t in tags]},
        )

    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (p:Post {id: item.id}) "
        "SET p.title = item.title, p.summary = item.summary, p.domain_id = item.domain_id",
        {
            "items": [
                {"id": p.id, "title": p.title, "summary": p.summary or "", "domain_id": p.domain_id}
                for p in posts
            ]
        },
    )
    neo4j_service.run_write(
        "UNWIND $items AS item "
        "MATCH (u:User {id: item.author_id}), (p:Post {id: item.post_id}) "
        "MERGE (u)-[:AUTHORED]->(p)",
        {"items": [{"author_id": p.author_id, "post_id": p.id} for p in posts]},
    )
    if pt_rows:
        neo4j_service.run_write(
            "UNWIND $items AS item "
            "MATCH (p:Post {id: item.post_id}), (t:Tag {id: item.tag_id}) "
            "MERGE (p)-[:TAGGED_WITH]->(t)",
            {"items": [{"post_id": row[0], "tag_id": row[1]} for row in pt_rows]},
        )

    neo4j_service.run_write(
        "UNWIND $post_ids AS pid MATCH (:User)-[r:LIKED|COMMENTED]->(p:Post {id: pid}) DELETE r",
        {"post_ids": post_ids},
    )

    for behavior_type, rel_type in [("like", "LIKED"), ("comment", "COMMENTED")]:
        behaviors = db.session.scalars(
            select(UserBehavior).where(
                UserBehavior.post_id.in_(post_ids),
                UserBehavior.behavior_type == behavior_type,
            )
        ).all()
        if not behaviors:
            continue
        for batch in chunked(behaviors, 500):
            neo4j_service.run_write(
                f"UNWIND $items AS item "
                f"MATCH (u:User {{id: item.user_id}}), (p:Post {{id: item.post_id}}) "
                f"MERGE (u)-[:{rel_type}]->(p)",
                {"items": [{"user_id": b.user_id, "post_id": b.post_id} for b in batch]},
            )

    neo4j_service.run_write(
        "MATCH (u:User)-[r:INTERESTED_IN]->(:Tag) DELETE r"
    )
    neo4j_service.run_write(
        "MATCH (u:User)-[r:LIKED|FAVORITED|COMMENTED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
        "WITH u, t, count(r) AS cnt WHERE cnt >= 1 "
        "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
    )


def main():
    parser = argparse.ArgumentParser(description="同步导入社区帖并生成互动")
    parser.add_argument("--post-limit", type=int, default=None, help="仅处理前 N 篇导入帖子")
    parser.add_argument("--likes-per-post", type=int, default=4, help="每帖点赞数，默认 4")
    parser.add_argument("--comments-per-post", type=int, default=2, help="每帖评论数，默认 2")
    parser.add_argument("--dry-run", action="store_true", help="仅预演，不写库")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        posts = imported_posts(args.post_limit)
        if not posts:
            print("未找到导入社区帖。")
            return
        users = all_users()
        post_ids = [post.id for post in posts]

        print("===== 导入社区帖同步与互动生成 =====")
        print(f"帖子数: {len(posts)}")
        print(f"用户数: {len(users)}")
        print(f"每帖点赞: {args.likes_per_post}")
        print(f"每帖评论: {args.comments_per_post}")
        print(f"dry_run: {args.dry_run}")

        reset_stats = reset_existing_engagement(post_ids, args.dry_run)
        print(f"已清理旧互动 -> likes={reset_stats['likes']} comments={reset_stats['comments']}")

        engagement_stats = create_engagement(
            posts,
            users,
            likes_per_post=args.likes_per_post,
            comments_per_post=args.comments_per_post,
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            db.session.commit()
            sync_posts_and_behaviors_to_neo4j(posts, users, dry_run=False)

        print("===== 完成 =====")
        print(json.dumps({
            "posts_processed": engagement_stats["posts_processed"],
            "likes_created": engagement_stats["likes"],
            "comments_created": engagement_stats["comments"],
            "unique_like_users": len(engagement_stats["by_user_like"]),
            "unique_comment_users": len(engagement_stats["by_user_comment"]),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
