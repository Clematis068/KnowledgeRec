"""
数据扩充脚本：在保留现有帖子/用户的基础上增加用户和行为密度。

目标:
  - 新增 ~200 模拟用户
  - 每个新用户 ~120 条行为
  - 每个老用户追加 ~50 条行为
  - 补齐所有帖子的 embedding
  - 同步 Neo4j + 重算 CF/Swing 相似度

用法: cd backend && uv run python -m scripts.expand_data
"""
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.domain import Domain
from app.models.post import Post
from app.models.tag import Tag
from app.models.user import User
from app.models.behavior import UserFollow

# ── 配置 ──
NEW_USER_COUNT = 200
NEW_USER_INTERACTIONS = 120      # 每个新用户的行为数
EXISTING_USER_EXTRA = 50         # 每个老用户追加的行为数
INTEREST_DOMAIN_RATIO = 0.85     # 85% 交互在兴趣领域内
BEHAVIOR_DIST = {                # 行为类型分布
    'browse': 0.50,
    'like': 0.25,
    'favorite': 0.10,
    'comment': 0.15,
}

COMMENT_TEMPLATES = [
    "写得非常好，学到了很多！",
    "感谢分享，收藏了慢慢看",
    "这个观点很新颖，值得思考",
    "请问有推荐的参考书目吗？",
    "文章很有深度，期待更多",
    "总结得很全面，适合入门",
    "正好在学这个，太及时了",
    "分析得很到位，赞一个",
    "能否展开讲讲实际应用场景？",
    "补充一点：这部分还可以参考某某的论文",
    "这个方法我也试过，确实有效",
    "有没有相关的代码实现可以参考？",
]


def pick_behavior_type():
    r = random.random()
    cumulative = 0.0
    for btype, prob in BEHAVIOR_DIST.items():
        cumulative += prob
        if r < cumulative:
            return btype
    return 'browse'


def create_new_users(domains, domain_tags):
    """创建新模拟用户，每人 2-4 个兴趣领域。"""
    # 找到当前最大的 sim_user 编号
    existing_sim = db.session.scalars(
        db.select(User.username).filter(User.username.like("sim_user_%"))
    ).all()
    max_idx = 0
    for name in existing_sim:
        try:
            idx = int(name.replace("sim_user_", ""))
            max_idx = max(max_idx, idx)
        except ValueError:
            pass
    start_idx = max_idx + 1

    users_info = []
    for i in range(NEW_USER_COUNT):
        idx = start_idx + i
        n_domains = random.randint(2, 4)
        interest_domains = random.sample(domains, min(n_domains, len(domains)))

        user = User(
            username=f"sim_user_{idx}",
            email=f"sim{idx}@test.local",
            password_hash="simulated",
            bio=f"模拟用户 {idx}，关注 {'、'.join(d.name for d in interest_domains[:2])} 等领域",
            created_at=datetime.now() - timedelta(days=random.randint(30, 180)),
        )
        db.session.add(user)
        db.session.flush()

        # 分配兴趣标签
        interest_tags = []
        for domain in interest_domains:
            tags_in_domain = domain_tags.get(domain.id, [])
            if tags_in_domain:
                interest_tags.extend(random.sample(tags_in_domain, min(3, len(tags_in_domain))))
        user.interest_tags = interest_tags

        users_info.append({
            "user": user,
            "domain_ids": [d.id for d in interest_domains],
        })

    db.session.commit()
    return users_info


def generate_interactions(user_id, domain_ids, posts_by_domain, all_posts, n_interactions, time_range_days=90):
    """为单个用户生成 n_interactions 条行为。"""
    now = datetime.now()
    behaviors = []

    # 构建候选池：兴趣领域帖子 + 全局帖子
    interest_pool = []
    for did in domain_ids:
        interest_pool.extend(posts_by_domain.get(did, []))

    for _ in range(n_interactions):
        # 按概率选帖子
        if interest_pool and random.random() < INTEREST_DOMAIN_RATIO:
            post = random.choice(interest_pool)
        else:
            post = random.choice(all_posts)

        btype = pick_behavior_type()
        days_ago = random.uniform(0, time_range_days)
        created_at = now - timedelta(days=days_ago)

        behavior = UserBehavior(
            user_id=user_id,
            post_id=post.id,
            behavior_type=btype,
            created_at=created_at,
            duration=random.randint(10, 300) if btype == 'browse' else None,
            comment_text=random.choice(COMMENT_TEMPLATES) if btype == 'comment' else None,
        )
        behaviors.append(behavior)

        # 更新帖子计数
        if btype == 'like':
            post.like_count = (post.like_count or 0) + 1
        elif btype == 'browse':
            post.view_count = (post.view_count or 0) + 1

    db.session.add_all(behaviors)
    return len(behaviors)


def generate_follows(new_users_info, all_user_ids):
    """为新用户生成关注关系。"""
    count = 0
    for user_info in new_users_info:
        uid = user_info["user"].id
        n_follow = random.randint(3, 8)
        targets = random.sample([x for x in all_user_ids if x != uid],
                                min(n_follow, len(all_user_ids) - 1))
        for tid in targets:
            db.session.add(UserFollow(follower_id=uid, followed_id=tid))
            count += 1
    db.session.commit()
    return count


def sync_new_data_to_neo4j(new_users_info):
    """将新数据同步到 Neo4j。"""
    from app.services.neo4j_service import neo4j_service

    # 新用户节点
    user_items = [{"id": u["user"].id, "username": u["user"].username} for u in new_users_info]
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (u:User {id: item.id}) SET u.username = item.username",
        {"items": user_items},
    )

    # 所有行为关系（全量重建更简单）
    for btype, rel_type in [('like', 'LIKED'), ('favorite', 'FAVORITED'),
                             ('comment', 'COMMENTED'), ('browse', 'BROWSED')]:
        behaviors = db.session.scalars(
            db.select(UserBehavior).filter_by(behavior_type=btype)
        ).all()
        if not behaviors:
            continue
        batch_size = 1000
        for start in range(0, len(behaviors), batch_size):
            batch = behaviors[start:start + batch_size]
            neo4j_service.run_write(
                f"UNWIND $items AS item "
                f"MATCH (u:User {{id: item.user_id}}), (p:Post {{id: item.post_id}}) "
                f"MERGE (u)-[:{rel_type}]->(p)",
                {"items": [{"user_id": b.user_id, "post_id": b.post_id} for b in batch]},
            )
        print(f"  {rel_type}: {len(behaviors)} 条")

    # 关注关系
    follows = db.session.scalars(db.select(UserFollow)).all()
    if follows:
        batch_size = 1000
        for start in range(0, len(follows), batch_size):
            batch = follows[start:start + batch_size]
            neo4j_service.run_write(
                "UNWIND $items AS item "
                "MATCH (a:User {id: item.follower}), (b:User {id: item.followed}) "
                "MERGE (a)-[:FOLLOWS]->(b)",
                {"items": [{"follower": f.follower_id, "followed": f.followed_id} for f in batch]},
            )
        print(f"  FOLLOWS: {len(follows)} 条")

    # INTERESTED_IN 重建
    neo4j_service.run_write(
        "MATCH (u:User)-[r:LIKED|FAVORITED|COMMENTED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
        "WITH u, t, count(r) AS cnt WHERE cnt >= 2 "
        "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
    )
    print("  INTERESTED_IN 关系已更新")


def generate_missing_embeddings():
    """为缺少 embedding 的帖子和标签生成 embedding。"""
    from app.services.qwen_service import qwen_service

    # 标签 embedding
    tags = db.session.scalars(db.select(Tag).filter(Tag.embedding.is_(None))).all()
    if tags:
        print(f"  生成标签 embedding ({len(tags)} 个)...")
        for i, tag in enumerate(tags):
            try:
                tag.embedding = qwen_service.get_embedding(tag.name)
                if (i + 1) % 20 == 0:
                    db.session.commit()
                    print(f"    标签进度: {i + 1}/{len(tags)}")
                time.sleep(0.1)
            except Exception as e:
                print(f"    标签 {tag.name} 失败: {e}")
                break
        db.session.commit()

    # 帖子 embedding
    posts = db.session.scalars(db.select(Post).filter(Post.content_embedding.is_(None))).all()
    if posts:
        print(f"  生成帖子 embedding ({len(posts)} 个)...")
        for i, post in enumerate(posts):
            try:
                text = post.title + " " + (post.content[:200] if post.content else "")
                post.content_embedding = qwen_service.get_embedding(text)
                if (i + 1) % 50 == 0:
                    db.session.commit()
                    print(f"    帖子进度: {i + 1}/{len(posts)}")
                time.sleep(0.1)
            except Exception as e:
                print(f"    帖子 {post.id} 失败: {e}")
                break
        db.session.commit()

    # 用户兴趣向量
    import numpy as np
    users = db.session.scalars(db.select(User).filter(User.interest_embedding.is_(None))).all()
    updated = 0
    for user in users:
        behaviors = db.session.scalars(
            db.select(UserBehavior)
            .filter_by(user_id=user.id)
            .filter(UserBehavior.behavior_type.in_(['like', 'favorite']))
        ).all()
        if not behaviors:
            continue
        embeddings, weights = [], []
        for b in behaviors:
            post = db.session.get(Post, b.post_id)
            if post and post.content_embedding:
                embeddings.append(np.array(post.content_embedding))
                weights.append(2.0 if b.behavior_type == 'favorite' else 1.0)
        if embeddings:
            user.interest_embedding = np.average(embeddings, axis=0, weights=weights).tolist()
            updated += 1
    db.session.commit()
    if updated:
        print(f"  更新 {updated} 个用户兴趣向量")


def main():
    random.seed(42)
    app = create_app()

    with app.app_context():
        # 当前统计
        user_count = db.session.scalar(db.select(db.func.count()).select_from(User))
        post_count = db.session.scalar(db.select(db.func.count()).select_from(Post))
        beh_count = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print("=" * 60)
        print("数据扩充")
        print(f"当前: {user_count} 用户, {post_count} 帖子, {beh_count} 行为")
        print("=" * 60)

        # 准备数据
        domains = db.session.scalars(db.select(Domain)).all()
        all_tags = db.session.scalars(db.select(Tag)).all()
        domain_tags = defaultdict(list)
        for tag in all_tags:
            domain_tags[tag.domain_id].append(tag)

        all_posts = db.session.scalars(db.select(Post)).all()
        posts_by_domain = defaultdict(list)
        for post in all_posts:
            posts_by_domain[post.domain_id].append(post)

        # Step 1: 创建新用户
        print(f"\n[1/6] 创建 {NEW_USER_COUNT} 个新用户...")
        new_users_info = create_new_users(domains, domain_tags)
        print(f"  完成: {len(new_users_info)} 个新用户")

        # Step 2: 为新用户生成行为
        print(f"\n[2/6] 为新用户生成行为 (每人 ~{NEW_USER_INTERACTIONS})...")
        new_total = 0
        for i, user_info in enumerate(new_users_info):
            n = generate_interactions(
                user_info["user"].id, user_info["domain_ids"],
                posts_by_domain, all_posts, NEW_USER_INTERACTIONS,
            )
            new_total += n
            if (i + 1) % 50 == 0:
                db.session.commit()
                print(f"  进度: {i + 1}/{len(new_users_info)} ({new_total} 条)")
        db.session.commit()
        print(f"  完成: {new_total} 条新行为")

        # Step 3: 为老用户追加行为
        print(f"\n[3/6] 为老用户追加行为 (每人 ~{EXISTING_USER_EXTRA})...")
        existing_users = db.session.scalars(
            db.select(User).filter(~User.username.like("sim_user_%"))
        ).all()
        # 获取老用户的兴趣领域（从已有行为推断）
        extra_total = 0
        for user in existing_users:
            # 推断兴趣领域
            user_behaviors = db.session.scalars(
                db.select(UserBehavior).filter_by(user_id=user.id).limit(50)
            ).all()
            user_domain_ids = set()
            for b in user_behaviors:
                post = db.session.get(Post, b.post_id)
                if post and post.domain_id:
                    user_domain_ids.add(post.domain_id)
            if not user_domain_ids:
                user_domain_ids = {random.choice(domains).id}

            n = generate_interactions(
                user.id, list(user_domain_ids),
                posts_by_domain, all_posts, EXISTING_USER_EXTRA,
            )
            extra_total += n
        db.session.commit()
        print(f"  完成: {extra_total} 条追加行为 (for {len(existing_users)} 个老用户)")

        # 也为模拟老用户追加一些
        existing_sim = db.session.scalars(
            db.select(User).filter(User.username.like("sim_user_%")).filter(
                User.id.notin_([u["user"].id for u in new_users_info])
            )
        ).all()
        sim_extra = 0
        for user in existing_sim:
            user_behaviors = db.session.scalars(
                db.select(UserBehavior).filter_by(user_id=user.id).limit(30)
            ).all()
            user_domain_ids = set()
            for b in user_behaviors:
                post = db.session.get(Post, b.post_id)
                if post and post.domain_id:
                    user_domain_ids.add(post.domain_id)
            if not user_domain_ids:
                user_domain_ids = {random.choice(domains).id}

            n = generate_interactions(
                user.id, list(user_domain_ids),
                posts_by_domain, all_posts, 40,
            )
            sim_extra += n
        db.session.commit()
        if sim_extra:
            print(f"  追加 {sim_extra} 条行为 (for {len(existing_sim)} 个已有模拟用户)")

        # Step 4: 生成关注关系
        print("\n[4/6] 生成关注关系...")
        all_user_ids = [uid for uid, in db.session.execute(db.select(User.id)).all()]
        follow_count = generate_follows(new_users_info, all_user_ids)
        print(f"  完成: {follow_count} 条关注")

        # Step 5: 补齐 embedding
        print("\n[5/6] 补齐 embedding...")
        try:
            generate_missing_embeddings()
        except Exception as e:
            print(f"  Embedding 生成跳过: {e}")

        # Step 6: Neo4j 同步 + CF/Swing 重算
        print("\n[6/6] 同步 Neo4j...")
        try:
            sync_new_data_to_neo4j(new_users_info)
        except Exception as e:
            print(f"  Neo4j 同步跳过: {e}")

        print("\n重算 CF/Swing 相似度...")
        try:
            from app.services.recommendation import recommendation_engine
            recommendation_engine.precompute()
        except Exception as e:
            print(f"  预计算跳过: {e}")

        # 最终统计
        user_count = db.session.scalar(db.select(db.func.count()).select_from(User))
        beh_count = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        emb_count = db.session.scalar(
            db.select(db.func.count()).select_from(Post).filter(Post.content_embedding.isnot(None))
        )
        print("\n" + "=" * 60)
        print(f"扩充完成: {user_count} 用户, {post_count} 帖子, {beh_count} 行为")
        print(f"帖子 embedding: {emb_count}/{post_count}")
        print("=" * 60)


if __name__ == "__main__":
    main()
