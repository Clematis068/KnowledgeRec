"""
补充冷启动用户：生成一批低活跃用户(3-10条行为)，让分层评估有意义。

策略:
  - 50 个 cold 用户: 仅 3-5 条行为 (只有 browse，无 like/favorite)
  - 80 个 warm 用户: 6-14 条行为 (少量 like/favorite)
  - 这些用户有兴趣标签(供 Knowledge/Semantic 使用)，但行为太少 CF/Swing 无法工作
  - 时间跨度需要覆盖 cutoff 前后，确保测试集中有这些用户

用法: cd backend && uv run python -m scripts.add_coldstart_users
"""
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior, UserFollow
from app.models.domain import Domain
from app.models.post import Post
from app.models.tag import Tag
from app.models.user import User

COMMENT_TEMPLATES = [
    "写得非常好，学到了很多！",
    "感谢分享，收藏了慢慢看",
    "请问有推荐的参考书目吗？",
    "正好在学这个，太及时了",
]


def main():
    random.seed(123)
    app = create_app()

    with app.app_context():
        domains = db.session.scalars(db.select(Domain)).all()
        all_tags = db.session.scalars(db.select(Tag)).all()
        domain_tags = defaultdict(list)
        for tag in all_tags:
            domain_tags[tag.domain_id].append(tag)

        all_posts = db.session.scalars(db.select(Post)).all()
        posts_by_domain = defaultdict(list)
        for post in all_posts:
            posts_by_domain[post.domain_id].append(post)

        # 找 cutoff 时间点 (与 evaluate.py 一致: 80% 分位)
        all_times = db.session.execute(
            db.select(UserBehavior.created_at).order_by(UserBehavior.created_at)
        ).scalars().all()
        cutoff_idx = int(len(all_times) * 0.8)
        cutoff_time = all_times[cutoff_idx]
        print(f"Cutoff 时间: {cutoff_time}")

        # 找最大 sim_user 编号
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

        user_count_before = db.session.scalar(db.select(db.func.count()).select_from(User))
        beh_count_before = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"当前: {user_count_before} 用户, {beh_count_before} 行为")

        all_new_users = []

        # ── Cold 用户: 3-5 条训练期行为 + 2-3 条测试期 like ──
        print("\n生成 cold 用户 (50个, 3-5条训练行为)...")
        for i in range(50):
            idx = start_idx + i
            interest_domains = random.sample(domains, min(random.randint(2, 3), len(domains)))

            user = User(
                username=f"sim_user_{idx}",
                email=f"sim{idx}@test.local",
                password_hash="simulated",
                bio=f"冷启动用户 {idx}",
                created_at=cutoff_time - timedelta(days=random.randint(10, 60)),
            )
            db.session.add(user)
            db.session.flush()

            # 兴趣标签 (Knowledge/Semantic 的信号来源)
            interest_tags = []
            for domain in interest_domains:
                tags_in_d = domain_tags.get(domain.id, [])
                if tags_in_d:
                    interest_tags.extend(random.sample(tags_in_d, min(2, len(tags_in_d))))
            user.interest_tags = interest_tags

            domain_ids = [d.id for d in interest_domains]

            # 训练期行为: 3-5 条 browse (无 like → CF/Swing 信号极弱)
            n_train = random.randint(3, 5)
            for _ in range(n_train):
                did = random.choice(domain_ids)
                pool = posts_by_domain.get(did, all_posts)
                post = random.choice(pool)
                db.session.add(UserBehavior(
                    user_id=user.id, post_id=post.id, behavior_type='browse',
                    duration=random.randint(15, 120),
                    created_at=cutoff_time - timedelta(days=random.uniform(1, 30)),
                ))

            # 测试期行为: 2-3 条 like/favorite (ground truth)
            n_test = random.randint(2, 3)
            for _ in range(n_test):
                did = random.choice(domain_ids)
                pool = posts_by_domain.get(did, all_posts)
                post = random.choice(pool)
                btype = random.choice(['like', 'favorite'])
                db.session.add(UserBehavior(
                    user_id=user.id, post_id=post.id, behavior_type=btype,
                    created_at=cutoff_time + timedelta(days=random.uniform(0.1, 15)),
                ))

            all_new_users.append(user)

        # ── Warm 用户: 6-14 条训练期行为 + 2-4 条测试期 like ──
        print("生成 warm 用户 (80个, 6-14条训练行为)...")
        for i in range(80):
            idx = start_idx + 50 + i
            interest_domains = random.sample(domains, min(random.randint(2, 4), len(domains)))

            user = User(
                username=f"sim_user_{idx}",
                email=f"sim{idx}@test.local",
                password_hash="simulated",
                bio=f"低活跃用户 {idx}",
                created_at=cutoff_time - timedelta(days=random.randint(15, 90)),
            )
            db.session.add(user)
            db.session.flush()

            interest_tags = []
            for domain in interest_domains:
                tags_in_d = domain_tags.get(domain.id, [])
                if tags_in_d:
                    interest_tags.extend(random.sample(tags_in_d, min(3, len(tags_in_d))))
            user.interest_tags = interest_tags

            domain_ids = [d.id for d in interest_domains]

            # 训练期行为: 6-14 条 (混合 browse/like/comment)
            n_train = random.randint(6, 14)
            for j in range(n_train):
                did = random.choice(domain_ids)
                pool = posts_by_domain.get(did, all_posts)
                post = random.choice(pool)
                # 前几条 browse，后面有少量 like
                if j < n_train * 0.6:
                    btype = 'browse'
                elif j < n_train * 0.85:
                    btype = 'like'
                else:
                    btype = 'comment'
                db.session.add(UserBehavior(
                    user_id=user.id, post_id=post.id, behavior_type=btype,
                    duration=random.randint(15, 180) if btype == 'browse' else None,
                    comment_text=random.choice(COMMENT_TEMPLATES) if btype == 'comment' else None,
                    created_at=cutoff_time - timedelta(days=random.uniform(1, 45)),
                ))

            # 测试期行为: 2-4 条 like/favorite
            n_test = random.randint(2, 4)
            for _ in range(n_test):
                did = random.choice(domain_ids)
                pool = posts_by_domain.get(did, all_posts)
                post = random.choice(pool)
                btype = random.choice(['like', 'favorite'])
                db.session.add(UserBehavior(
                    user_id=user.id, post_id=post.id, behavior_type=btype,
                    created_at=cutoff_time + timedelta(days=random.uniform(0.1, 15)),
                ))

            all_new_users.append(user)

        db.session.commit()

        # 关注关系
        all_user_ids = [uid for uid, in db.session.execute(db.select(User.id)).all()]
        for user in all_new_users:
            n_follow = random.randint(1, 4)
            targets = random.sample([x for x in all_user_ids if x != user.id],
                                    min(n_follow, len(all_user_ids) - 1))
            for tid in targets:
                db.session.add(UserFollow(follower_id=user.id, followed_id=tid))
        db.session.commit()

        # Neo4j 同步
        print("\n同步 Neo4j...")
        try:
            from app.services.neo4j_service import neo4j_service
            user_items = [{"id": u.id, "username": u.username} for u in all_new_users]
            neo4j_service.run_write(
                "UNWIND $items AS item MERGE (u:User {id: item.id}) SET u.username = item.username",
                {"items": user_items},
            )
            # 行为关系
            for user in all_new_users:
                behaviors = db.session.scalars(
                    db.select(UserBehavior).filter_by(user_id=user.id)
                ).all()
                for b in behaviors:
                    rel = {'like': 'LIKED', 'favorite': 'FAVORITED', 'comment': 'COMMENTED', 'browse': 'BROWSED'}.get(b.behavior_type)
                    if rel:
                        neo4j_service.run_write(
                            f"MATCH (u:User {{id: $uid}}), (p:Post {{id: $pid}}) MERGE (u)-[:{rel}]->(p)",
                            {"uid": user.id, "pid": b.post_id},
                        )
            # INTERESTED_IN 重建
            neo4j_service.run_write(
                "MATCH (u:User)-[r:LIKED|FAVORITED|COMMENTED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
                "WITH u, t, count(r) AS cnt WHERE cnt >= 2 "
                "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
            )
            print("  Neo4j 同步完成")
        except Exception as e:
            print(f"  Neo4j 同步跳过: {e}")

        # 最终统计
        user_count = db.session.scalar(db.select(db.func.count()).select_from(User))
        beh_count = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"\n完成: {user_count} 用户 (+{user_count - user_count_before}), "
              f"{beh_count} 行为 (+{beh_count - beh_count_before})")
        print(f"  Cold 用户: 50 (3-5条训练行为)")
        print(f"  Warm 用户: 80 (6-14条训练行为)")


if __name__ == "__main__":
    main()
