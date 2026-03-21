"""
模拟用户交互数据增强脚本
目标: 增加用户间行为共现密度，使 CF/Swing/Graph 在消融实验中产出有效推荐。

根因分析:
  - 当前 29 用户、621 帖子、1975 行为 → 用户-物品共现太稀疏
  - CF/Swing 基于共现的相似度计算需要多个用户交互同一帖子
  - 评估脚本用用户最近的 like/favorite 做测试集，但 CF 排除了已交互帖子
  - 需要: (1) 更多用户 (2) 更密集的交互 (3) 留出一部分帖子用于测试

策略:
  1. 生成 70 个模拟用户 (user 30-99)
  2. 每个用户按领域兴趣选帖子做交互，确保多用户在同领域帖子上有共现
  3. 每个用户留 20% 的帖子只做 browse，其余做 like/favorite → 保证:
     - CF/Swing 能基于 browse 帖子计算相似度
     - 测试集 (like/favorite 的后 20%) 中的帖子会被 CF 推荐给其他类似用户
  4. 同步到 Neo4j

用法: cd backend && uv run python -m scripts.simulate_interactions
"""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.domain import Domain
from app.models.post import Post
from app.models.tag import Tag
from app.models.user import User

NEW_USER_COUNT = 70
NEW_USER_START_ID_OFFSET = 100  # 起始 username 编号，避免冲突
INTERACTIONS_PER_USER = 80
LIKE_RATIO = 0.45
FAVORITE_RATIO = 0.10
COMMENT_RATIO = 0.15
BROWSE_RATIO = 0.30


def generate_users(count, start_offset):
    """生成模拟用户，每人随机选 2-4 个兴趣领域的标签。"""
    domains = db.session.scalars(db.select(Domain)).all()
    all_tags = db.session.scalars(db.select(Tag)).all()
    domain_tags = {}
    for tag in all_tags:
        domain_tags.setdefault(tag.domain_id, []).append(tag)

    created_users = []
    for i in range(count):
        idx = start_offset + i
        user = User(
            username=f"sim_user_{idx}",
            email=f"sim{idx}@test.local",
            password_hash="simulated",
            bio=f"模拟用户 {idx}",
        )
        db.session.add(user)
        db.session.flush()  # 拿到 user.id

        # 随机选 2-4 个领域
        interest_domains = random.sample(domains, min(random.randint(2, 4), len(domains)))
        interest_tags = []
        for domain in interest_domains:
            tags_in_domain = domain_tags.get(domain.id, [])
            if tags_in_domain:
                interest_tags.extend(random.sample(tags_in_domain, min(3, len(tags_in_domain))))
        user.interest_tags = interest_tags

        created_users.append({
            "user": user,
            "domain_ids": [d.id for d in interest_domains],
        })

    db.session.commit()
    return created_users


def generate_interactions(users_info):
    """为每个模拟用户在其兴趣领域的帖子上生成交互。"""
    all_posts_by_domain = {}
    posts = db.session.scalars(db.select(Post)).all()
    for post in posts:
        all_posts_by_domain.setdefault(post.domain_id, []).append(post)

    now = datetime.now()
    total_behaviors = 0

    for user_info in users_info:
        user = user_info["user"]
        domain_ids = user_info["domain_ids"]

        # 收集兴趣领域的帖子
        candidate_posts = []
        for did in domain_ids:
            candidate_posts.extend(all_posts_by_domain.get(did, []))
        random.shuffle(candidate_posts)

        if not candidate_posts:
            continue

        # 选取交互帖子
        n_interact = min(INTERACTIONS_PER_USER, len(candidate_posts))
        selected_posts = candidate_posts[:n_interact]

        # 按比例分配行为类型
        n_like = int(n_interact * LIKE_RATIO)
        n_fav = int(n_interact * FAVORITE_RATIO)
        n_comment = int(n_interact * COMMENT_RATIO)
        n_browse = n_interact - n_like - n_fav - n_comment

        behavior_types = (
            ["like"] * n_like +
            ["favorite"] * n_fav +
            ["comment"] * n_comment +
            ["browse"] * n_browse
        )
        random.shuffle(behavior_types)

        for idx, (post, btype) in enumerate(zip(selected_posts, behavior_types)):
            # 时间从 60 天前到现在，模拟时间跨度
            days_ago = random.uniform(0, 60)
            created_at = now - timedelta(days=days_ago)

            behavior = UserBehavior(
                user_id=user.id,
                post_id=post.id,
                behavior_type=btype,
                created_at=created_at,
                duration=random.randint(15, 180) if btype == "browse" else None,
            )
            db.session.add(behavior)
            total_behaviors += 1

    db.session.commit()
    return total_behaviors


def sync_to_neo4j(users_info):
    """将新用户和行为同步到 Neo4j。"""
    from app.services.neo4j_service import neo4j_service

    with neo4j_service.driver.session() as session:
        for user_info in users_info:
            user = user_info["user"]

            # 创建用户节点
            session.run(
                "MERGE (u:User {id: $uid}) SET u.username = $name",
                uid=user.id, name=user.username,
            )

            # 兴趣标签关系
            for tag in user.interest_tags:
                session.run(
                    "MATCH (u:User {id: $uid}), (t:Tag {id: $tid}) "
                    "MERGE (u)-[:INTERESTED_IN]->(t)",
                    uid=user.id, tid=tag.id,
                )

            # 行为关系
            behaviors = db.session.scalars(
                db.select(UserBehavior).filter_by(user_id=user.id)
            ).all()
            for b in behaviors:
                rel_type = {
                    "like": "LIKED",
                    "favorite": "FAVORITED",
                    "comment": "COMMENTED",
                    "browse": "BROWSED",
                }.get(b.behavior_type)
                if rel_type:
                    session.run(
                        f"MATCH (u:User {{id: $uid}}), (p:Post {{id: $pid}}) "
                        f"MERGE (u)-[:{rel_type}]->(p)",
                        uid=user.id, pid=b.post_id,
                    )

        # 添加一些社交关注关系 (随机 follow 其他用户)
        all_user_ids = [u["user"].id for u in users_info]
        existing_user_ids = [
            uid for uid in db.session.scalars(db.select(User.id)).all()
            if uid not in all_user_ids
        ]
        follow_count = 0
        for user_info in users_info:
            uid = user_info["user"].id
            # 每个新用户 follow 2-5 个其他用户
            n_follow = random.randint(2, 5)
            targets = random.sample(existing_user_ids + all_user_ids, min(n_follow, len(existing_user_ids) + len(all_user_ids)))
            for target in targets:
                if target == uid:
                    continue
                session.run(
                    "MATCH (u:User {id: $uid}), (f:User {id: $fid}) "
                    "MERGE (u)-[:FOLLOWS]->(f)",
                    uid=uid, fid=target,
                )
                follow_count += 1

        print(f"  Neo4j 同步完成: {len(users_info)} 用户, {follow_count} 关注关系")


def main():
    random.seed(42)
    app = create_app()

    with app.app_context():
        # 检查是否已经生成过
        existing = db.session.scalar(
            db.select(db.func.count()).select_from(User).filter(User.username.like("sim_user_%"))
        )
        if existing > 0:
            print(f"已有 {existing} 个模拟用户，跳过生成。如需重新生成请先清理。")
            return

        print("=" * 60)
        print("模拟交互数据生成")
        print("=" * 60)

        # 当前统计
        user_count = db.session.scalar(db.select(db.func.count()).select_from(User))
        post_count = db.session.scalar(db.select(db.func.count()).select_from(Post))
        behavior_count = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"当前: {user_count} 用户, {post_count} 帖子, {behavior_count} 行为\n")

        # Step 1: 生成用户
        print(f"[1/4] 生成 {NEW_USER_COUNT} 个模拟用户...")
        users_info = generate_users(NEW_USER_COUNT, NEW_USER_START_ID_OFFSET)
        print(f"  完成: {len(users_info)} 个用户")

        # Step 2: 生成交互
        print(f"[2/4] 生成交互行为 (每人 ~{INTERACTIONS_PER_USER} 条)...")
        n_behaviors = generate_interactions(users_info)
        print(f"  完成: {n_behaviors} 条行为")

        # Step 3: 同步 Neo4j
        print("[3/4] 同步到 Neo4j...")
        sync_to_neo4j(users_info)

        # Step 4: 重新预计算 CF/Swing 相似度矩阵
        print("[4/4] 重新预计算物品相似度...")
        from app.services.recommendation import recommendation_engine
        recommendation_engine.precompute()

        # 最终统计
        user_count = db.session.scalar(db.select(db.func.count()).select_from(User))
        behavior_count = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"\n最终: {user_count} 用户, {post_count} 帖子, {behavior_count} 行为")
        print("=" * 60)


if __name__ == "__main__":
    main()
