"""
纯冷启动用户评估：0 行为，仅注册时选择的兴趣标签。
在旧数据集上创建冷启动用户 → 同步 Neo4j → 评估 → 合并到报告 cold 行。

用法: cd backend && MYSQL_URI="mysql+pymysql://root@localhost:3306/knowledge_community_old" \
      EVAL_REPORT_DIR="reports/evaluation_old_dataset" \
      PYTHONUNBUFFERED=1 uv run python -m scripts.evaluate_cold_start_pure
"""
import csv
import math
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.domain import Domain
from app.models.post import Post
from app.models.tag import Tag
from app.models.user import User
from app.services.recommendation import RecommendationEngine

REPORT_DIR = os.environ.get(
    'EVAL_REPORT_DIR',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "evaluation_old_dataset"),
)
K_VALUES = [5, 10, 20]
NUM_COLD_USERS = 50

ABLATION_CONFIGS = {
    "CF_only":        {'cf': 1.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Swing_only":     {'cf': 0.0, 'swing': 1.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Graph_only":     {'cf': 0.0, 'swing': 0.0, 'graph': 1.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Semantic_only":  {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 1.0, 'knowledge': 0.0, 'hot': 0.0},
    "Knowledge_only": {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 1.0, 'hot': 0.0},
    "Hot_only":       {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 1.0},
    "Full_Fusion":    {'cf': 0.28, 'swing': 0.08, 'graph': 0.22, 'semantic': 0.20, 'knowledge': 0.12, 'hot': 0.10},
    "GBDT_Ranking":   None,
}


# ── 指标函数 ──

def precision_at_k(recommended, relevant, k):
    rec_k = set(recommended[:k])
    return len(rec_k & relevant) / k if rec_k else 0.0

def recall_at_k(recommended, relevant, k):
    rec_k = set(recommended[:k])
    return len(rec_k & relevant) / len(relevant) if relevant else 0.0

def ndcg_at_k(recommended, relevant, k):
    dcg = sum(1.0 / math.log2(i + 2) for i, item in enumerate(recommended[:k]) if item in relevant)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / idcg if idcg > 0 else 0.0

def hitrate_at_k(recommended, relevant, k):
    return 1.0 if set(recommended[:k]) & relevant else 0.0

def coverage_at_k(rec_ids, k, pdmap, total_d):
    return len({pdmap.get(pid) for pid in rec_ids[:k]} - {None}) / total_d if total_d else 0.0

def entropy_at_k(rec_ids, k, pdmap):
    dl = [pdmap.get(pid) for pid in rec_ids[:k] if pdmap.get(pid) is not None]
    if not dl: return 0.0
    c = Counter(dl); t = len(dl)
    return -sum((v/t) * math.log2(v/t) for v in c.values())

def ils_at_k(rec_ids, k, pdmap):
    ds = [pdmap.get(pid) for pid in rec_ids[:k]]; n = len(ds)
    if n < 2: return 0.0
    s = sum(1 for i in range(n) for j in range(i+1, n) if ds[i] is not None and ds[i] == ds[j])
    return s / (n*(n-1)/2)


def create_pure_cold_users():
    """创建纯冷启动用户：0 行为，注册兴趣标签。
    GT = 兴趣标签覆盖的帖子中，被其他用户 like/favorite 最多的热门帖子。
    """
    print(f"\n创建 {NUM_COLD_USERS} 个纯冷启动用户（0行为，仅兴趣标签）...")

    all_tags = db.session.scalars(db.select(Tag)).all()
    domain_tags = defaultdict(list)
    for t in all_tags:
        if t.domain_id:
            domain_tags[t.domain_id].append(t)

    # 帖子-标签映射
    from app.models.post import post_tag as pt_table
    pt_rows = db.session.execute(pt_table.select()).fetchall()
    tag_posts = defaultdict(set)
    for pid, tid in pt_rows:
        tag_posts[tid].add(pid)

    # 帖子热度（被 like/favorite 的次数）
    pop_rows = db.session.execute(
        db.select(UserBehavior.post_id, db.func.count().label('cnt'))
        .filter(UserBehavior.behavior_type.in_(['like', 'favorite']))
        .group_by(UserBehavior.post_id)
    ).all()
    post_pop = {r[0]: r[1] for r in pop_rows}

    rng = random.Random(54321)
    all_domain_ids = list(domain_tags.keys())
    max_id = db.session.scalar(db.select(db.func.max(User.id))) or 0

    test_set = {}
    created_ids = []

    for i in range(NUM_COLD_USERS):
        # 随机选 2-4 个领域
        n_d = rng.randint(2, min(4, len(all_domain_ids)))
        chosen_ds = rng.sample(all_domain_ids, n_d)
        tags = []
        for did in chosen_ds:
            pool = domain_tags[did]
            tags.extend(rng.sample(pool, min(rng.randint(1, 3), len(pool))))

        user = User(
            id=max_id + i + 1,
            username=f"pure_cold_{i+1}",
            email=f"purecold{i+1}@test.local",
            password_hash="no_login",
        )
        db.session.add(user)
        db.session.flush()
        user.interest_tags = tags

        # GT：兴趣标签覆盖的热门帖子
        candidate = set()
        for t in tags:
            candidate |= tag_posts.get(t.id, set())
        ranked = sorted(candidate, key=lambda p: post_pop.get(p, 0), reverse=True)
        gt_size = min(rng.randint(3, 8), len(ranked))
        gt = set(ranked[:gt_size])

        if len(gt) >= 2:
            test_set[user.id] = {'post_ids': gt}
            created_ids.append(user.id)

    db.session.commit()
    print(f"  有效用户: {len(test_set)}")
    print(f"  平均兴趣标签: {sum(len(u.interest_tags) for u in db.session.scalars(db.select(User).filter(User.id.in_(created_ids))).all()) / max(len(created_ids),1):.1f}")
    print(f"  平均 GT 帖子: {sum(len(v['post_ids']) for v in test_set.values()) / max(len(test_set),1):.1f}")
    return test_set, created_ids


def sync_cold_users_to_neo4j(user_ids):
    """把冷启动用户的 INTERESTED_IN 关系同步到 Neo4j。"""
    from app.services.neo4j_service import neo4j_service
    for uid in user_ids:
        user = db.session.get(User, uid)
        if not user:
            continue
        neo4j_service.run_write(
            "MERGE (u:User {id: $uid}) SET u.username = $name",
            {"uid": user.id, "name": user.username},
        )
        for tag in user.interest_tags:
            neo4j_service.run_write(
                "MATCH (u:User {id: $uid}), (t:Tag {id: $tid}) "
                "MERGE (u)-[r:INTERESTED_IN]->(t) SET r.weight = 1",
                {"uid": user.id, "tid": tag.id},
            )
    print(f"  {len(user_ids)} 个冷启动用户已同步到 Neo4j (INTERESTED_IN)")


def cleanup(user_ids):
    if not user_ids:
        return
    from app.models.user import user_tag as ut_table
    db.session.execute(ut_table.delete().where(ut_table.c.user_id.in_(user_ids)))
    db.session.execute(db.delete(User).where(User.id.in_(user_ids)))
    db.session.commit()
    print(f"已清理 {len(user_ids)} 个冷启动用户")


def sync_neo4j_full():
    """把旧数据库完整同步到 Neo4j。"""
    from app.models.post import post_tag as pt_table
    from app.models.behavior import UserFollow
    from app.services.neo4j_service import neo4j_service

    print("同步 Neo4j（旧数据集）...")
    neo4j_service.run_write("MATCH (n) DETACH DELETE n")

    domains = db.session.scalars(db.select(Domain)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (d:Domain {id: item.id}) SET d.name = item.name",
        {"items": [{"id": d.id, "name": d.name} for d in domains]},
    )
    tags = db.session.scalars(db.select(Tag)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (t:Tag {id: item.id}) SET t.name = item.name",
        {"items": [{"id": t.id, "name": t.name} for t in tags]},
    )
    neo4j_service.run_write(
        "UNWIND $items AS item MATCH (t:Tag {id: item.tid}), (d:Domain {id: item.did}) MERGE (t)-[:BELONGS_TO]->(d)",
        {"items": [{"tid": t.id, "did": t.domain_id} for t in tags if t.domain_id]},
    )
    users = db.session.execute(db.select(User.id, User.username)).all()
    for s in range(0, len(users), 1000):
        b = users[s:s+1000]
        neo4j_service.run_write("UNWIND $items AS i MERGE (u:User {id: i.id}) SET u.username = i.name",
                                {"items": [{"id": u[0], "name": u[1]} for u in b]})
    posts = db.session.execute(db.select(Post.id, Post.title, Post.domain_id)).all()
    for s in range(0, len(posts), 2000):
        b = posts[s:s+2000]
        neo4j_service.run_write("UNWIND $items AS i MERGE (p:Post {id: i.id}) SET p.title = i.title, p.domain_id = i.did",
                                {"items": [{"id": p[0], "title": p[1], "did": p[2]} for p in b]})
    pt_rows = db.session.execute(pt_table.select()).fetchall()
    for s in range(0, len(pt_rows), 2000):
        b = pt_rows[s:s+2000]
        neo4j_service.run_write("UNWIND $items AS i MATCH (p:Post {id: i.pid}), (t:Tag {id: i.tid}) MERGE (p)-[:TAGGED_WITH]->(t)",
                                {"items": [{"pid": r[0], "tid": r[1]} for r in b]})
    for btype, rel in [('like', 'LIKED'), ('favorite', 'FAVORITED'), ('browse', 'BROWSED')]:
        behaviors = db.session.execute(db.select(UserBehavior.user_id, UserBehavior.post_id).filter_by(behavior_type=btype)).all()
        for s in range(0, len(behaviors), 2000):
            b = behaviors[s:s+2000]
            neo4j_service.run_write(f"UNWIND $items AS i MATCH (u:User {{id: i.uid}}), (p:Post {{id: i.pid}}) MERGE (u)-[:{rel}]->(p)",
                                    {"items": [{"uid": x[0], "pid": x[1]} for x in b]})
        print(f"  {rel}: {len(behaviors)}")
    follows = db.session.execute(db.select(UserFollow.follower_id, UserFollow.followed_id)).all()
    for s in range(0, len(follows), 2000):
        b = follows[s:s+2000]
        neo4j_service.run_write("UNWIND $items AS i MATCH (a:User {id: i.src}), (b:User {id: i.tgt}) MERGE (a)-[:FOLLOWS]->(b)",
                                {"items": [{"src": f[0], "tgt": f[1]} for f in b]})
    print(f"  FOLLOWS: {len(follows)}")
    neo4j_service.run_write(
        "MATCH (u:User)-[r:LIKED|FAVORITED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
        "WITH u, t, count(r) AS cnt WHERE cnt >= 2 "
        "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
    )
    print("  INTERESTED_IN 已派生\n  Neo4j 同步完成")


def main():
    random.seed(42)
    app = create_app()
    with app.app_context():
        # 1. 同步 Neo4j
        sync_neo4j_full()

        # 2. CF/Swing 预计算
        print("\n预计算 CF/Swing...")
        engine = RecommendationEngine()
        engine.precompute()

        # 3. 创建冷启动用户
        test_set, cold_ids = create_pure_cold_users()
        if not test_set:
            print("无有效冷启动用户")
            return

        # 4. 同步到 Neo4j
        sync_cold_users_to_neo4j(cold_ids)

        try:
            post_rows = db.session.execute(db.select(Post.id, Post.domain_id)).all()
            pdmap = {pid: did for pid, did in post_rows}
            total_d = len(set(did for did in pdmap.values() if did is not None))
            max_k = max(K_VALUES)

            # 5. 预缓存召回
            print("\n预缓存冷启动召回...")
            recall_cache = {}
            uids = list(test_set.keys())
            for i, uid in enumerate(uids):
                try:
                    recall_cache[uid] = engine._parallel_recall(uid, enable_llm=False)
                except Exception as e:
                    print(f"  user {uid} error: {e}")
                if (i+1) % 10 == 0:
                    print(f"  进度: {i+1}/{len(uids)}")
            print(f"  缓存完成: {len(recall_cache)}")

            # 6. 评估
            all_results = {}
            for cfg_name, weights in ABLATION_CONFIGS.items():
                print(f"评估: {cfg_name}")
                metrics = {k: {m: [] for m in ['precision','recall','ndcg','hitrate','coverage','entropy','ils']} for k in K_VALUES}

                for uid in uids:
                    relevant = test_set[uid]['post_ids']
                    try:
                        if uid in recall_cache:
                            rm = recall_cache[uid]
                            if weights is None and engine.ranker.is_available():
                                res, _ = engine._gbdt_ranking_pipeline(uid, rm, max_k, set(), None, True)
                            else:
                                res, _ = engine._legacy_fusion_pipeline(uid, rm, max_k, set(), None, weights, True, True)
                            rec = [r['post_id'] for r in res]
                        else:
                            rec = []
                    except Exception as e:
                        print(f"  [{cfg_name}] user {uid}: {e}")
                        rec = []

                    for k in K_VALUES:
                        metrics[k]['precision'].append(precision_at_k(rec, relevant, k))
                        metrics[k]['recall'].append(recall_at_k(rec, relevant, k))
                        metrics[k]['ndcg'].append(ndcg_at_k(rec, relevant, k))
                        metrics[k]['hitrate'].append(hitrate_at_k(rec, relevant, k))
                        metrics[k]['coverage'].append(coverage_at_k(rec, k, pdmap, total_d))
                        metrics[k]['entropy'].append(entropy_at_k(rec, k, pdmap))
                        metrics[k]['ils'].append(ils_at_k(rec, k, pdmap))

                avg = {}
                for k in K_VALUES:
                    n = len(metrics[k]['precision'])
                    avg[k] = {m: sum(metrics[k][m])/n if n else 0 for m in metrics[k]}
                all_results[cfg_name] = avg

            # 7. 打印
            print(f"\n{'='*100}")
            print(f"纯冷启动评估（{len(test_set)} 用户，0 行为，仅兴趣标签）")
            print(f"{'='*100}")
            print(f"{'配置':<20} | {'P@5':>6} {'HR@5':>6} {'NDCG@5':>8} | {'P@10':>6} {'HR@10':>6} {'NDCG@10':>8} | {'P@20':>6} {'HR@20':>6} {'NDCG@20':>8}")
            print("-"*100)
            for name, avg in all_results.items():
                print(f"{name:<20} | {avg[5]['precision']:.4f} {avg[5]['hitrate']:.4f} {avg[5]['ndcg']:.6f} "
                      f"| {avg[10]['precision']:.4f} {avg[10]['hitrate']:.4f} {avg[10]['ndcg']:.6f} "
                      f"| {avg[20]['precision']:.4f} {avg[20]['hitrate']:.4f} {avg[20]['ndcg']:.6f}")
            print("="*100)

            # 8. 保存 CSV
            os.makedirs(REPORT_DIR, exist_ok=True)
            csv_path = os.path.join(REPORT_DIR, "coldstart_pure_metrics.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp)
                w.writerow(["config","k","precision","recall","ndcg","hitrate","coverage","entropy","ils"])
                for name, avg in all_results.items():
                    for k in K_VALUES:
                        m = avg[k]
                        w.writerow([name, k, *[round(m[x], 6) for x in ['precision','recall','ndcg','hitrate','coverage','entropy','ils']]])
            print(f"\n报告已写入: {csv_path}")

        finally:
            cleanup(cold_ids)


if __name__ == '__main__':
    main()
