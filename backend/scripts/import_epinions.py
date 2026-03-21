"""
导入 Epinions 真实数据集到现有 MySQL + Neo4j 数据模型。

数据源: MSU Epinions dataset (.mat 格式)
  - rating.mat: [user_id, item_id, category_id, rating(1-5)]
  - trustnetwork.mat: [user_id, trusted_user_id]

映射规则:
  - category → Domain
  - item → Post (title="Epinions Item #id", domain=category)
  - rating 4-5 → like/favorite, 1-3 → browse
  - trust → UserFollow (Neo4j FOLLOWS)

子采样: 取 5000 活跃用户 + >=5次交互的物品

用法: cd backend && uv run python -m scripts.import_epinions
"""
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
import scipy.io as sio

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "epinions", "epinions")
MAX_USERS = 5000
MIN_USER_RATINGS = 10
MIN_ITEM_RATINGS = 5


def load_and_subsample():
    """加载 .mat 并子采样。"""
    rating = sio.loadmat(os.path.join(DATA_DIR, "rating.mat"))["rating"]
    trust = sio.loadmat(os.path.join(DATA_DIR, "trustnetwork.mat"))["trustnetwork"]

    # 活跃用户（>=MIN_USER_RATINGS 条评分，有信任关系的优先）
    user_counts = Counter(rating[:, 0])
    active = sorted([u for u, c in user_counts.items() if c >= MIN_USER_RATINGS],
                    key=lambda u: -user_counts[u])
    trust_src = set(trust[:, 0])
    with_trust = [u for u in active if u in trust_src]
    without_trust = [u for u in active if u not in trust_src]
    selected_users = set((with_trust + without_trust)[:MAX_USERS])

    # 筛选评分
    mask = np.isin(rating[:, 0], list(selected_users))
    sub_rating = rating[mask]

    # 物品 >= MIN_ITEM_RATINGS 次交互
    item_counts = Counter(sub_rating[:, 1])
    valid_items = set(i for i, c in item_counts.items() if c >= MIN_ITEM_RATINGS)
    mask2 = np.isin(sub_rating[:, 1], list(valid_items))
    sub_rating = sub_rating[mask2]

    # 过滤掉无评分的用户
    remaining_users = set(sub_rating[:, 0])

    # 信任关系子集
    trust_mask = np.isin(trust[:, 0], list(remaining_users)) & np.isin(trust[:, 1], list(remaining_users))
    sub_trust = trust[trust_mask]

    print(f"子采样: {len(remaining_users)} 用户, {len(valid_items)} 物品, "
          f"{len(sub_rating)} 评分, {len(sub_trust)} 信任")
    return sub_rating, sub_trust, remaining_users, valid_items


def main():
    random.seed(42)
    app_module = __import__("app", fromlist=["create_app", "db"])
    create_app = app_module.create_app
    db = app_module.db

    from app.models.behavior import UserBehavior, UserFollow
    from app.models.domain import Domain
    from app.models.post import Post
    from app.models.tag import Tag
    from app.models.user import User

    app = create_app()
    with app.app_context():
        # ── 清空旧数据 ──
        print("清空旧数据...")
        db.drop_all()
        db.create_all()

        # ── 加载数据 ──
        sub_rating, sub_trust, user_set, item_set = load_and_subsample()

        # ── 创建 Domain (category) ──
        print("\n[1/6] 创建 Domain...")
        cat_ids = sorted(set(sub_rating[:, 2]))
        cat_to_domain = {}
        for cat_id in cat_ids:
            domain = Domain(name=f"Category_{cat_id}", description=f"Epinions category {cat_id}")
            db.session.add(domain)
            db.session.flush()
            cat_to_domain[cat_id] = domain.id
        db.session.commit()
        print(f"  {len(cat_to_domain)} 个 Domain")

        # ── 创建 Tag (每个 category 一个同名 tag) ──
        print("[2/6] 创建 Tag...")
        domain_to_tag = {}
        for cat_id, domain_id in cat_to_domain.items():
            tag = Tag(name=f"cat_{cat_id}", domain_id=domain_id)
            db.session.add(tag)
            db.session.flush()
            domain_to_tag[domain_id] = tag.id
        db.session.commit()

        # ── 创建 User ──
        print("[3/6] 创建 User...")
        # 先建一个系统用户做 author
        system_user = User(username="epinions_system", email="system@epinions.local",
                           password_hash="system", bio="Epinions system user")
        db.session.add(system_user)
        db.session.flush()
        system_uid = system_user.id

        orig_to_new_user = {}
        user_list = sorted(user_set)
        batch = []
        for i, orig_uid in enumerate(user_list):
            batch.append({
                "username": f"ep_user_{orig_uid}",
                "email": f"ep{orig_uid}@epinions.local",
                "password_hash": "epinions",
                "bio": f"Epinions user {orig_uid}",
            })
            if len(batch) >= 500 or i == len(user_list) - 1:
                db.session.execute(db.insert(User), batch)
                db.session.commit()
                batch = []

        # 建立映射
        rows = db.session.execute(db.select(User.id, User.username)).all()
        for uid, uname in rows:
            if uname.startswith("ep_user_"):
                orig_id = int(uname.replace("ep_user_", ""))
                orig_to_new_user[orig_id] = uid
        print(f"  {len(orig_to_new_user)} 个 User")

        # ── 创建 Post (item) ──
        print("[4/6] 创建 Post...")
        # item → category 映射（取该 item 最常出现的 category）
        item_cat = {}
        for row in sub_rating:
            iid, cid = int(row[1]), int(row[2])
            item_cat.setdefault(iid, Counter())[cid] += 1
        item_primary_cat = {iid: counts.most_common(1)[0][0] for iid, counts in item_cat.items()}

        orig_to_new_post = {}
        item_list = sorted(item_set)
        batch = []
        from app.models.post import post_tag
        post_tag_batch = []

        for i, orig_iid in enumerate(item_list):
            cat_id = item_primary_cat.get(orig_iid, cat_ids[0])
            domain_id = cat_to_domain[cat_id]
            batch.append({
                "title": f"Item #{orig_iid}",
                "content": f"Epinions review item in category {cat_id}",
                "summary": f"Category {cat_id} item",
                "author_id": system_uid,
                "domain_id": domain_id,
                "view_count": 0,
                "like_count": 0,
            })
            if len(batch) >= 500 or i == len(item_list) - 1:
                db.session.execute(db.insert(Post), batch)
                db.session.commit()
                batch = []

        # 建立映射
        rows = db.session.execute(db.select(Post.id, Post.title)).all()
        for pid, title in rows:
            if title.startswith("Item #"):
                orig_id = int(title.replace("Item #", ""))
                orig_to_new_post[orig_id] = pid
        print(f"  {len(orig_to_new_post)} 个 Post")

        # post-tag 关联
        for orig_iid in item_list:
            new_pid = orig_to_new_post.get(orig_iid)
            cat_id = item_primary_cat.get(orig_iid, cat_ids[0])
            domain_id = cat_to_domain[cat_id]
            tag_id = domain_to_tag.get(domain_id)
            if new_pid and tag_id:
                post_tag_batch.append({"post_id": new_pid, "tag_id": tag_id})
            if len(post_tag_batch) >= 500:
                db.session.execute(post_tag.insert(), post_tag_batch)
                db.session.commit()
                post_tag_batch = []
        if post_tag_batch:
            db.session.execute(post_tag.insert(), post_tag_batch)
            db.session.commit()

        # 用户兴趣标签（从评分推断）
        print("  设置用户兴趣标签...")
        user_cats = defaultdict(Counter)
        for row in sub_rating:
            if row[3] >= 4:  # 高评分才算兴趣
                user_cats[int(row[0])][int(row[2])] += 1
        for orig_uid, cat_counts in user_cats.items():
            new_uid = orig_to_new_user.get(orig_uid)
            if not new_uid:
                continue
            user = db.session.get(User, new_uid)
            if not user:
                continue
            top_cats = [c for c, _ in cat_counts.most_common(4)]
            tags = []
            for c in top_cats:
                did = cat_to_domain.get(c)
                tid = domain_to_tag.get(did) if did else None
                if tid:
                    tag = db.session.get(Tag, tid)
                    if tag:
                        tags.append(tag)
            user.interest_tags = tags
        db.session.commit()

        # ── 创建 UserBehavior (rating) ──
        print("[5/6] 创建 UserBehavior...")
        now = datetime.now()
        batch = []
        like_counts = Counter()
        view_counts = Counter()

        for i, row in enumerate(sub_rating):
            orig_uid, orig_iid, cat_id, score = int(row[0]), int(row[1]), int(row[2]), int(row[3])
            new_uid = orig_to_new_user.get(orig_uid)
            new_pid = orig_to_new_post.get(orig_iid)
            if not new_uid or not new_pid:
                continue

            # 评分映射
            if score >= 5:
                btype = "favorite"
                like_counts[new_pid] += 1
            elif score >= 4:
                btype = "like"
                like_counts[new_pid] += 1
            else:
                btype = "browse"
                view_counts[new_pid] += 1

            # 时间：随机分布在过去 90 天
            days_ago = random.uniform(0, 90)
            created_at = now - timedelta(days=days_ago)

            batch.append({
                "user_id": new_uid, "post_id": new_pid,
                "behavior_type": btype, "created_at": created_at,
                "duration": random.randint(10, 180) if btype == "browse" else None,
            })

            if len(batch) >= 1000:
                db.session.execute(db.insert(UserBehavior), batch)
                db.session.commit()
                batch = []
                if (i + 1) % 50000 == 0:
                    print(f"  进度: {i + 1}/{len(sub_rating)}")

        if batch:
            db.session.execute(db.insert(UserBehavior), batch)
            db.session.commit()

        # 更新 Post 计数
        for pid, cnt in like_counts.items():
            db.session.execute(
                db.update(Post).where(Post.id == pid).values(like_count=cnt)
            )
        for pid, cnt in view_counts.items():
            db.session.execute(
                db.update(Post).where(Post.id == pid).values(view_count=cnt)
            )
        db.session.commit()

        beh_total = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"  {beh_total} 条 UserBehavior")

        # ── 创建 UserFollow (trust) ──
        print("[6/6] 创建 UserFollow...")
        batch = []
        for row in sub_trust:
            src, tgt = int(row[0]), int(row[1])
            new_src = orig_to_new_user.get(src)
            new_tgt = orig_to_new_user.get(tgt)
            if new_src and new_tgt and new_src != new_tgt:
                batch.append({"follower_id": new_src, "followed_id": new_tgt})
            if len(batch) >= 1000:
                try:
                    db.session.execute(db.insert(UserFollow), batch)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    # 逐条插入（跳过重复）
                    for item in batch:
                        try:
                            db.session.execute(db.insert(UserFollow), [item])
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                batch = []
        if batch:
            try:
                db.session.execute(db.insert(UserFollow), batch)
                db.session.commit()
            except Exception:
                db.session.rollback()

        follow_total = db.session.scalar(db.select(db.func.count()).select_from(UserFollow))
        print(f"  {follow_total} 条 UserFollow")

        # ── Neo4j 同步 ──
        print("\n同步 Neo4j...")
        try:
            from app.services.neo4j_service import neo4j_service

            # 清空
            neo4j_service.run_write("MATCH (n) DETACH DELETE n")

            # Domain
            domains = db.session.scalars(db.select(Domain)).all()
            neo4j_service.run_write(
                "UNWIND $items AS item MERGE (d:Domain {id: item.id}) SET d.name = item.name",
                {"items": [{"id": d.id, "name": d.name} for d in domains]},
            )

            # Tag
            tags = db.session.scalars(db.select(Tag)).all()
            neo4j_service.run_write(
                "UNWIND $items AS item MERGE (t:Tag {id: item.id}) SET t.name = item.name",
                {"items": [{"id": t.id, "name": t.name} for t in tags]},
            )
            neo4j_service.run_write(
                "UNWIND $items AS item MATCH (t:Tag {id: item.tid}), (d:Domain {id: item.did}) MERGE (t)-[:BELONGS_TO]->(d)",
                {"items": [{"tid": t.id, "did": t.domain_id} for t in tags]},
            )

            # User (分批)
            users = db.session.execute(db.select(User.id, User.username)).all()
            for start in range(0, len(users), 1000):
                batch = users[start:start + 1000]
                neo4j_service.run_write(
                    "UNWIND $items AS item MERGE (u:User {id: item.id}) SET u.username = item.name",
                    {"items": [{"id": u[0], "name": u[1]} for u in batch]},
                )

            # Post (分批)
            posts = db.session.execute(db.select(Post.id, Post.title, Post.domain_id)).all()
            for start in range(0, len(posts), 2000):
                batch = posts[start:start + 2000]
                neo4j_service.run_write(
                    "UNWIND $items AS item MERGE (p:Post {id: item.id}) SET p.title = item.title",
                    {"items": [{"id": p[0], "title": p[1]} for p in batch]},
                )

            # Post-Tag
            from app.models.post import post_tag as pt_table
            pt_rows = db.session.execute(pt_table.select()).fetchall()
            for start in range(0, len(pt_rows), 2000):
                batch = pt_rows[start:start + 2000]
                neo4j_service.run_write(
                    "UNWIND $items AS item MATCH (p:Post {id: item.pid}), (t:Tag {id: item.tid}) MERGE (p)-[:TAGGED_WITH]->(t)",
                    {"items": [{"pid": r[0], "tid": r[1]} for r in batch]},
                )

            # Behavior relations (分批)
            for btype, rel in [('like', 'LIKED'), ('favorite', 'FAVORITED'), ('browse', 'BROWSED')]:
                behaviors = db.session.execute(
                    db.select(UserBehavior.user_id, UserBehavior.post_id)
                    .filter_by(behavior_type=btype)
                ).all()
                for start in range(0, len(behaviors), 2000):
                    batch = behaviors[start:start + 2000]
                    neo4j_service.run_write(
                        f"UNWIND $items AS item MATCH (u:User {{id: item.uid}}), (p:Post {{id: item.pid}}) MERGE (u)-[:{rel}]->(p)",
                        {"items": [{"uid": b[0], "pid": b[1]} for b in batch]},
                    )
                print(f"  {rel}: {len(behaviors)}")

            # FOLLOWS
            follows = db.session.execute(db.select(UserFollow.follower_id, UserFollow.followed_id)).all()
            for start in range(0, len(follows), 2000):
                batch = follows[start:start + 2000]
                neo4j_service.run_write(
                    "UNWIND $items AS item MATCH (a:User {id: item.src}), (b:User {id: item.tgt}) MERGE (a)-[:FOLLOWS]->(b)",
                    {"items": [{"src": f[0], "tgt": f[1]} for f in batch]},
                )
            print(f"  FOLLOWS: {len(follows)}")

            # INTERESTED_IN
            neo4j_service.run_write(
                "MATCH (u:User)-[r:LIKED|FAVORITED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
                "WITH u, t, count(r) AS cnt WHERE cnt >= 2 "
                "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
            )
            print("  INTERESTED_IN 已派生")
            print("  Neo4j 同步完成")
        except Exception as e:
            print(f"  Neo4j 同步失败: {e}")

        # ── CF/Swing 预计算 ──
        print("\n预计算 CF/Swing 相似度...")
        try:
            from app.services.recommendation import RecommendationEngine
            engine = RecommendationEngine()
            engine.precompute()
        except Exception as e:
            print(f"  预计算失败: {e}")

        # 最终统计
        print("\n" + "=" * 60)
        print(f"Epinions 数据导入完成")
        print(f"  Domain: {db.session.scalar(db.select(db.func.count()).select_from(Domain))}")
        print(f"  Tag:    {db.session.scalar(db.select(db.func.count()).select_from(Tag))}")
        print(f"  User:   {db.session.scalar(db.select(db.func.count()).select_from(User))}")
        print(f"  Post:   {db.session.scalar(db.select(db.func.count()).select_from(Post))}")
        print(f"  Behavior: {db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))}")
        print(f"  Follow: {db.session.scalar(db.select(db.func.count()).select_from(UserFollow))}")
        print("=" * 60)


if __name__ == "__main__":
    main()
