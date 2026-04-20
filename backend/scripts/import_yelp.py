"""
导入 Yelp Academic Dataset 到独立的 MySQL 数据库（不覆盖现有 knowledge_community_old）。

数据源（需先从 https://www.yelp.com/dataset 下载，或 Kaggle 镜像）:
  backend/data/yelp/
    ├── yelp_academic_dataset_business.json
    ├── yelp_academic_dataset_user.json
    └── yelp_academic_dataset_review.json

映射规则:
  - business.categories（首项）→ Domain；business → Post
  - user → User，user.friends → UserFollow（双向）
  - review.stars 5 → favorite，4 → like，1-3 → browse；review.text 进 Post.content（取最长一条）

子集策略（默认）:
  - city = "Philadelphia"
  - 迭代 k-core(k=10)：保证用户和商家都至少 10 条评论
  - 限制最多 5000 用户

环境变量:
  YELP_DATA_DIR   默认 backend/data/yelp
  YELP_DB         默认 knowledge_community_yelp（新库，自动创建）
  YELP_CITY       默认 Philadelphia
  YELP_KCORE      默认 10
  YELP_MAX_USERS  默认 5000
  YELP_SKIP_NEO4J 默认 1（避免覆盖当前 Neo4j 数据；改为 0 才同步）

用法: cd backend && uv run python -m scripts.import_yelp
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

import pymysql
from sqlalchemy.engine.url import make_url

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import Config


DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "yelp")
DATA_DIR = os.environ.get("YELP_DATA_DIR", DEFAULT_DATA_DIR)
TARGET_DB = os.environ.get("YELP_DB", "knowledge_community_yelp")
TARGET_CITY = os.environ.get("YELP_CITY", "Philadelphia")
KCORE = int(os.environ.get("YELP_KCORE", "10"))
MAX_USERS = int(os.environ.get("YELP_MAX_USERS", "5000"))
SKIP_NEO4J = os.environ.get("YELP_SKIP_NEO4J", "1") != "0"

BUSINESS_FILE = os.path.join(DATA_DIR, "yelp_academic_dataset_business.json")
USER_FILE = os.path.join(DATA_DIR, "yelp_academic_dataset_user.json")
REVIEW_FILE = os.path.join(DATA_DIR, "yelp_academic_dataset_review.json")


def ensure_data_files():
    missing = [p for p in (BUSINESS_FILE, USER_FILE, REVIEW_FILE) if not os.path.exists(p)]
    if missing:
        print("✗ 缺少 Yelp 数据文件：")
        for p in missing:
            print(f"  - {p}")
        print(f"\n请将 Yelp Academic Dataset 解压到 {DATA_DIR}，确保包含上述 3 个 JSON。")
        print("下载入口: https://www.yelp.com/dataset 或 Kaggle 镜像 yelp-dataset/yelp-dataset")
        sys.exit(1)


def ensure_database():
    """连到 MySQL server，CREATE DATABASE IF NOT EXISTS。"""
    url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    conn = pymysql.connect(
        host=url.host or "localhost",
        port=url.port or 3306,
        user=url.username or "root",
        password=url.password or "",
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{TARGET_DB}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()
    new_url = url.set(database=TARGET_DB)
    new_uri = str(new_url)
    # SQLAlchemy URL.render_as_string 默认隐藏密码，但 set() 已保留——直接 str() 即可
    os.environ["MYSQL_URI"] = new_uri
    Config.SQLALCHEMY_DATABASE_URI = new_uri
    print(f"✓ 目标数据库: {TARGET_DB}")


def stream_json_lines(path):
    with open(path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def filter_businesses_by_city(city):
    """读 business.json，按城市过滤，返回 {business_id: business_dict}"""
    print(f"[扫描] 过滤 city='{city}' 的商家...")
    biz_map = {}
    total = 0
    for biz in stream_json_lines(BUSINESS_FILE):
        total += 1
        if biz.get("city") == city and biz.get("categories"):
            biz_map[biz["business_id"]] = biz
        if total % 50000 == 0:
            print(f"  已扫 {total} 条，匹配 {len(biz_map)} 条")
    print(f"  共 {total} 商家，匹配 {len(biz_map)} 条")
    return biz_map


def collect_reviews(biz_ids):
    """读 review.json，过滤到候选商家，返回 [(uid, bid, stars, text, date, useful), ...]"""
    print(f"[扫描] 收集对 {len(biz_ids)} 个商家的 reviews...")
    biz_set = set(biz_ids)
    reviews = []
    total = 0
    for r in stream_json_lines(REVIEW_FILE):
        total += 1
        if r["business_id"] in biz_set:
            reviews.append((
                r["user_id"], r["business_id"], int(r["stars"]),
                r.get("text", ""), r.get("date", ""),
                int(r.get("useful", 0) or 0),
            ))
        if total % 500000 == 0:
            print(f"  已扫 {total} 条 review，匹配 {len(reviews)} 条")
    print(f"  共 {total} reviews，匹配 {len(reviews)} 条")
    return reviews


def kcore_filter(reviews, k=10, max_iter=10):
    """二部图 k-core：迭代删除 review 数 < k 的用户/商家。"""
    print(f"[过滤] k-core(k={k})...")
    cur_reviews = reviews
    for it in range(max_iter):
        u_cnt = Counter(r[0] for r in cur_reviews)
        b_cnt = Counter(r[1] for r in cur_reviews)
        keep_u = {u for u, c in u_cnt.items() if c >= k}
        keep_b = {b for b, c in b_cnt.items() if c >= k}
        new_reviews = [r for r in cur_reviews if r[0] in keep_u and r[1] in keep_b]
        print(f"  iter {it + 1}: users={len(keep_u)} bizs={len(keep_b)} reviews={len(new_reviews)}")
        if len(new_reviews) == len(cur_reviews):
            break
        cur_reviews = new_reviews
    return cur_reviews


def cap_users(reviews, max_users):
    """按用户 review 数降序取前 max_users 个，再过滤 reviews。"""
    if max_users <= 0:
        return reviews
    u_cnt = Counter(r[0] for r in reviews)
    if len(u_cnt) <= max_users:
        return reviews
    top_users = {u for u, _ in u_cnt.most_common(max_users)}
    print(f"[限制] 取最活跃 {len(top_users)}/{len(u_cnt)} 用户")
    return [r for r in reviews if r[0] in top_users]


def collect_friends(user_set):
    """读 user.json，仅保留双方都在子集中的好友关系。"""
    print(f"[扫描] 提取 {len(user_set)} 用户之间的 friends...")
    edges = []
    total = 0
    matched_users = 0
    for u in stream_json_lines(USER_FILE):
        total += 1
        if u["user_id"] not in user_set:
            continue
        matched_users += 1
        friends = u.get("friends", "")
        if not friends or friends == "None":
            continue
        for f in friends.split(", "):
            f = f.strip()
            if f and f in user_set and f != u["user_id"]:
                edges.append((u["user_id"], f))
        if total % 200000 == 0:
            print(f"  已扫 {total} 用户，匹配 {matched_users} / 边 {len(edges)}")
    print(f"  匹配 {matched_users} 用户，{len(edges)} 条 friend 边")
    return edges


def main():
    random.seed(42)
    ensure_data_files()
    ensure_database()

    # ── 流式过滤 ──
    biz_map = filter_businesses_by_city(TARGET_CITY)
    if not biz_map:
        print(f"✗ 未匹配任何 {TARGET_CITY} 商家，请检查 city 名拼写")
        sys.exit(1)
    reviews = collect_reviews(set(biz_map.keys()))
    reviews = kcore_filter(reviews, k=KCORE)
    reviews = cap_users(reviews, MAX_USERS)
    if not reviews:
        print("✗ 过滤后无 review 残留，可调小 YELP_KCORE")
        sys.exit(1)

    user_ids = sorted({r[0] for r in reviews})
    biz_ids = sorted({r[1] for r in reviews})
    biz_map = {b: biz_map[b] for b in biz_ids}
    print(f"\n=== 子集规模 ===")
    print(f"  users:    {len(user_ids)}")
    print(f"  business: {len(biz_ids)}")
    print(f"  reviews:  {len(reviews)}")

    friend_edges = collect_friends(set(user_ids))

    # ── 创建表（Flask app 用新 DB） ──
    print("\n[初始化] 在新库创建表...")
    from app import create_app, db
    from app.models.behavior import UserBehavior, UserFollow
    from app.models.domain import Domain
    from app.models.post import Post, post_tag
    from app.models.tag import Tag
    from app.models.user import User

    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("✓ 表已建")

        # ── Domain：每个一级 category ──
        print("\n[1/6] 创建 Domain...")
        cats = Counter()
        for b in biz_map.values():
            for c in [s.strip() for s in (b.get("categories") or "").split(",") if s.strip()]:
                cats[c] += 1
        # 取热门 category 作为 Domain，余下作为 Tag
        top_cats = [c for c, _ in cats.most_common(40)]
        cat_to_domain = {}
        for c in top_cats:
            d = Domain(name=c[:80], description=f"Yelp category: {c}")
            db.session.add(d)
            db.session.flush()
            cat_to_domain[c] = d.id
        db.session.commit()
        print(f"  Domain: {len(cat_to_domain)}")

        # ── Tag：每个 category 都建 tag，归属第一个匹配的 Domain ──
        print("[2/6] 创建 Tag...")
        cat_to_tag = {}
        default_domain_id = next(iter(cat_to_domain.values()))
        for c in cats:
            domain_id = cat_to_domain.get(c, default_domain_id)
            t = Tag(name=c[:80], domain_id=domain_id)
            db.session.add(t)
            db.session.flush()
            cat_to_tag[c] = t.id
        db.session.commit()
        print(f"  Tag: {len(cat_to_tag)}")

        # ── User ──
        print("[3/6] 创建 User...")
        system_user = User(
            username="yelp_system", email="system@yelp.local",
            password_hash="system", bio="Yelp system author",
        )
        db.session.add(system_user)
        db.session.flush()
        system_uid = system_user.id

        orig_to_new_user = {}
        batch = []
        for i, uid in enumerate(user_ids):
            short = uid.replace("-", "")[:20]
            batch.append({
                "username": f"yelp_{short}",
                "email": f"{short}@yelp.local",
                "password_hash": "yelp",
                "bio": f"Yelp user {uid}",
            })
            if len(batch) >= 500 or i == len(user_ids) - 1:
                db.session.execute(db.insert(User), batch)
                db.session.commit()
                batch = []
        rows = db.session.execute(db.select(User.id, User.username)).all()
        username_to_uid = {n: i for i, n in rows}
        for uid in user_ids:
            short = uid.replace("-", "")[:20]
            new_uid = username_to_uid.get(f"yelp_{short}")
            if new_uid:
                orig_to_new_user[uid] = new_uid
        print(f"  User: {len(orig_to_new_user)}")

        # ── Post（business） ──
        print("[4/6] 创建 Post...")
        # 每个 business 取 top-3 review（按 useful 票数降序，相同则按 stars+长度），
        # 拼成多视角 content。useful 全 0 时退化为长度排序。
        biz_reviews = defaultdict(list)
        for uid, bid, stars, text, date, useful in reviews:
            if text:
                biz_reviews[bid].append((useful, stars, len(text), text, stars, date))

        def build_content(bid, biz_name, biz_cats):
            picks = biz_reviews.get(bid, [])
            picks.sort(key=lambda x: (-x[0], -x[2]))  # useful desc, length desc
            top = picks[:3]
            if not top:
                return f"{biz_name} in {biz_cats}"
            header = f"{biz_name}（{biz_cats}）\n"
            blocks = []
            for _useful, _s, _len, text, stars, date in top:
                star_str = "★" * int(stars) + "☆" * (5 - int(stars))
                date_short = (date or "")[:10]
                blocks.append(f"{star_str} — {date_short}\n{text.strip()}")
            return header + "\n\n".join(blocks)

        # 选 author：每个 business 取 top-useful 评论作者，每用户最多 MAX_POSTS_PER_AUTHOR 个，
        # 余下退回到 system_user，避免超级 reviewer 垄断 author 字段。
        MAX_POSTS_PER_AUTHOR = 5
        biz_review_meta = defaultdict(list)
        for uid, bid, stars, _text, _date, useful in reviews:
            biz_review_meta[bid].append((useful, stars, uid))
        biz_to_author = {}
        author_post_count = Counter()
        capped_count = 0
        for bid in biz_ids:
            cands = sorted(biz_review_meta.get(bid, []), key=lambda x: (-x[0], -x[1]))
            chosen = system_uid
            for _useful, _stars, uid in cands:
                new_uid = orig_to_new_user.get(uid)
                if new_uid is None:
                    continue
                if author_post_count[new_uid] < MAX_POSTS_PER_AUTHOR:
                    chosen = new_uid
                    author_post_count[new_uid] += 1
                    break
            else:
                # 所有候选都被 cap 满
                if cands:
                    capped_count += 1
            biz_to_author[bid] = chosen
        real_author_n = sum(1 for a in biz_to_author.values() if a != system_uid)
        print(f"  Author 分配: 真实用户 {real_author_n}, 系统兜底 {len(biz_ids) - real_author_n} "
              f"(其中 {capped_count} 因作者已达 {MAX_POSTS_PER_AUTHOR} 篇上限退回 system)")

        like_counts = Counter()
        view_counts = Counter()
        biz_to_post = {}
        batch = []
        # 记录 Post 表当前最大 id，导入后据此区分新建 post
        prev_max_id = db.session.scalar(db.select(db.func.coalesce(db.func.max(Post.id), 0)))
        for i, bid in enumerate(biz_ids):
            b = biz_map[bid]
            cats_for_biz = [s.strip() for s in (b.get("categories") or "").split(",") if s.strip()]
            primary_cat = cats_for_biz[0] if cats_for_biz else top_cats[0]
            domain_id = cat_to_domain.get(primary_cat, default_domain_id)
            cats_label = " · ".join(cats_for_biz[:3]) if cats_for_biz else (b.get("city") or "")
            content = build_content(bid, b.get("name") or f"Business {bid}", cats_label)
            content = content[:6000]  # embedding 限长
            # summary 取首条 review 前 160 字（跳过 header）
            first_para = content.split("\n\n", 2)
            preview = first_para[1] if len(first_para) > 1 else content
            summary = (preview[:160] + "…") if len(preview) > 160 else preview
            batch.append({
                "title": (b.get("name") or f"Business {bid}")[:200],
                "content": content,
                "summary": summary,
                "author_id": biz_to_author[bid],
                "domain_id": domain_id,
                "view_count": 0,
                "like_count": 0,
            })
            if len(batch) >= 500 or i == len(biz_ids) - 1:
                db.session.execute(db.insert(Post), batch)
                db.session.commit()
                batch = []

        # 按插入顺序回查 post.id（id > prev_max_id 即本次新增）
        rows = db.session.execute(
            db.select(Post.id).where(Post.id > prev_max_id).order_by(Post.id.asc())
        ).all()
        for (pid,), bid in zip(rows, biz_ids):
            biz_to_post[bid] = pid
        print(f"  Post: {len(biz_to_post)}")

        # post-tag 关联
        print("  关联 post-tag...")
        pt_batch = []
        for bid in biz_ids:
            pid = biz_to_post.get(bid)
            if not pid:
                continue
            for c in [s.strip() for s in (biz_map[bid].get("categories") or "").split(",") if s.strip()][:5]:
                tid = cat_to_tag.get(c)
                if tid:
                    pt_batch.append({"post_id": pid, "tag_id": tid})
            if len(pt_batch) >= 1000:
                db.session.execute(post_tag.insert(), pt_batch)
                db.session.commit()
                pt_batch = []
        if pt_batch:
            db.session.execute(post_tag.insert(), pt_batch)
            db.session.commit()

        # 用户兴趣标签：取 stars >= 4 的 review 对应商家的 top categories
        print("  设置用户兴趣标签...")
        user_cat_counts = defaultdict(Counter)
        for uid, bid, stars, _t, _d, _u in reviews:
            if stars >= 4:
                for c in [s.strip() for s in (biz_map[bid].get("categories") or "").split(",") if s.strip()][:3]:
                    user_cat_counts[uid][c] += 1
        for uid, ccnt in user_cat_counts.items():
            new_uid = orig_to_new_user.get(uid)
            if not new_uid:
                continue
            user = db.session.get(User, new_uid)
            if not user:
                continue
            tags = []
            for c, _ in ccnt.most_common(4):
                tid = cat_to_tag.get(c)
                if tid:
                    tag = db.session.get(Tag, tid)
                    if tag:
                        tags.append(tag)
            if tags:
                user.interest_tags = tags
        db.session.commit()

        # ── UserBehavior ──
        print("[5/6] 创建 UserBehavior...")
        batch = []
        for i, (uid, bid, stars, _t, date, _useful) in enumerate(reviews):
            new_uid = orig_to_new_user.get(uid)
            new_pid = biz_to_post.get(bid)
            if not new_uid or not new_pid:
                continue
            if stars >= 5:
                btype = "favorite"
                like_counts[new_pid] += 1
            elif stars >= 4:
                btype = "like"
                like_counts[new_pid] += 1
            else:
                btype = "browse"
                view_counts[new_pid] += 1
            try:
                created_at = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                created_at = datetime.now()
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
                    print(f"  进度: {i + 1}/{len(reviews)}")
        if batch:
            db.session.execute(db.insert(UserBehavior), batch)
            db.session.commit()

        for pid, cnt in like_counts.items():
            db.session.execute(db.update(Post).where(Post.id == pid).values(like_count=cnt))
        for pid, cnt in view_counts.items():
            db.session.execute(db.update(Post).where(Post.id == pid).values(view_count=cnt))
        db.session.commit()

        beh_total = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
        print(f"  UserBehavior: {beh_total}")

        # ── UserFollow（friends 是双向，每条边导入两次以保证 follower/followed 对称） ──
        print("[6/6] 创建 UserFollow...")
        batch = []
        for src, tgt in friend_edges:
            ns = orig_to_new_user.get(src)
            nt = orig_to_new_user.get(tgt)
            if ns and nt and ns != nt:
                batch.append({"follower_id": ns, "followed_id": nt})
            if len(batch) >= 1000:
                try:
                    db.session.execute(db.insert(UserFollow), batch)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    for it in batch:
                        try:
                            db.session.execute(db.insert(UserFollow), [it])
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
        print(f"  UserFollow: {follow_total}")

        if SKIP_NEO4J:
            print("\n⚠ 已跳过 Neo4j 同步（YELP_SKIP_NEO4J=1，避免覆盖现有 graph）。")
            print("  Yelp 评估若需要 graph 通道，请：")
            print("    a) 等当前评估完成后，手动 export 现有 Neo4j → 再 import Yelp；或")
            print("    b) 启动第二个 Neo4j 实例（端口 7688），改 NEO4J_URI 后重跑此脚本（YELP_SKIP_NEO4J=0）")
        else:
            print("\n[Neo4j] 同步...（会清空现有 graph）")
            from app.services.neo4j_service import neo4j_service
            neo4j_service.run_write("MATCH (n) DETACH DELETE n")
            # Domain
            domains = db.session.scalars(db.select(Domain)).all()
            neo4j_service.run_write(
                "UNWIND $items AS i MERGE (d:Domain {id:i.id}) SET d.name=i.name",
                {"items": [{"id": d.id, "name": d.name} for d in domains]},
            )
            # Tag
            tags = db.session.scalars(db.select(Tag)).all()
            neo4j_service.run_write(
                "UNWIND $items AS i MERGE (t:Tag {id:i.id}) SET t.name=i.name",
                {"items": [{"id": t.id, "name": t.name} for t in tags]},
            )
            neo4j_service.run_write(
                "UNWIND $items AS i MATCH (t:Tag {id:i.tid}),(d:Domain {id:i.did}) MERGE (t)-[:BELONGS_TO]->(d)",
                {"items": [{"tid": t.id, "did": t.domain_id} for t in tags]},
            )
            # User / Post / Edges 略（沿用 import_epinions 的批处理写法）
            users = db.session.execute(db.select(User.id, User.username)).all()
            for s in range(0, len(users), 1000):
                neo4j_service.run_write(
                    "UNWIND $items AS i MERGE (u:User {id:i.id}) SET u.username=i.name",
                    {"items": [{"id": u[0], "name": u[1]} for u in users[s:s + 1000]]},
                )
            posts = db.session.execute(db.select(Post.id, Post.title)).all()
            for s in range(0, len(posts), 2000):
                neo4j_service.run_write(
                    "UNWIND $items AS i MERGE (p:Post {id:i.id}) SET p.title=i.title",
                    {"items": [{"id": p[0], "title": p[1]} for p in posts[s:s + 2000]]},
                )
            pt_rows = db.session.execute(post_tag.select()).fetchall()
            for s in range(0, len(pt_rows), 2000):
                neo4j_service.run_write(
                    "UNWIND $items AS i MATCH (p:Post {id:i.pid}),(t:Tag {id:i.tid}) MERGE (p)-[:TAGGED_WITH]->(t)",
                    {"items": [{"pid": r[0], "tid": r[1]} for r in pt_rows[s:s + 2000]]},
                )
            for btype, rel in [("like", "LIKED"), ("favorite", "FAVORITED"), ("browse", "BROWSED")]:
                bs = db.session.execute(
                    db.select(UserBehavior.user_id, UserBehavior.post_id).filter_by(behavior_type=btype)
                ).all()
                for s in range(0, len(bs), 2000):
                    neo4j_service.run_write(
                        f"UNWIND $items AS i MATCH (u:User {{id:i.uid}}),(p:Post {{id:i.pid}}) MERGE (u)-[:{rel}]->(p)",
                        {"items": [{"uid": x[0], "pid": x[1]} for x in bs[s:s + 2000]]},
                    )
                print(f"  {rel}: {len(bs)}")
            follows = db.session.execute(db.select(UserFollow.follower_id, UserFollow.followed_id)).all()
            for s in range(0, len(follows), 2000):
                neo4j_service.run_write(
                    "UNWIND $items AS i MATCH (a:User {id:i.src}),(b:User {id:i.tgt}) MERGE (a)-[:FOLLOWS]->(b)",
                    {"items": [{"src": f[0], "tgt": f[1]} for f in follows[s:s + 2000]]},
                )
            print(f"  FOLLOWS: {len(follows)}")
            print("✓ Neo4j 同步完成")

        print("\n=== 完成 ===")
        print(f"数据库: {TARGET_DB}")
        print(f"用户: {len(orig_to_new_user)}, 帖子: {len(biz_to_post)}, "
              f"行为: {beh_total}, 关注: {follow_total}")
        print("\n后续步骤:")
        print("  1) MYSQL_URI=mysql+pymysql://...@localhost:3306/" + TARGET_DB +
              " uv run python -m scripts.generate_tag_relations")
        print("  2) MYSQL_URI=...  uv run python -c 'from app.services.semantic_engine import SemanticEngine; "
              "SemanticEngine().rebuild_all_embeddings()'   # 生成 embedding")
        print("  3) MYSQL_URI=...  uv run python -m scripts.evaluate")


if __name__ == "__main__":
    main()
