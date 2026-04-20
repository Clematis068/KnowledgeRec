"""
生成用户社交网络（FOLLOWS 关系）。

基于用户兴趣标签相似度 + 随机性生成关注关系，模拟真实社交网络特征：
- 幂律分布：少数用户有很多粉丝，大部分用户粉丝较少
- 兴趣聚类：相似兴趣的用户更可能互相关注
- 互惠性：被关注的用户有一定概率回关

用法:
  cd backend && uv run python -m scripts.generate_social_network
  cd backend && uv run python -m scripts.generate_social_network --avg-follows 8 --reciprocal-prob 0.3
  cd backend && uv run python -m scripts.generate_social_network --clear-existing --dry-run
"""
import argparse
import random
from collections import defaultdict

from app import create_app, db
from app.models.user import User
from app.services.neo4j_service import neo4j_service
from app.utils.helpers import cosine_similarity


def parse_args():
    parser = argparse.ArgumentParser(description="生成用户社交网络")
    parser.add_argument("--avg-follows", type=int, default=10, help="平均每人关注数（实际会有幂律分布）")
    parser.add_argument("--reciprocal-prob", type=float, default=0.25, help="互惠关注概率（被关注后回关的概率）")
    parser.add_argument("--interest-weight", type=float, default=0.7, help="兴趣相似度权重（0-1，越高越基于兴趣）")
    parser.add_argument("--clear-existing", action="store_true", help="先清除已有 FOLLOWS 关系")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    return parser.parse_args()


def compute_user_similarity(user_a: User, user_b: User) -> float:
    """计算两个用户的兴趣相似度（基于兴趣标签 embedding）。"""
    if not user_a.interest_embedding or not user_b.interest_embedding:
        return 0.0
    return max(cosine_similarity(user_a.interest_embedding, user_b.interest_embedding), 0.0)


def power_law_sample(n: int, avg: int, alpha: float = 2.5) -> list[int]:
    """生成幂律分布的关注数列表（少数人关注很多，大部分人关注较少）。"""
    # Zipf 分布近似幂律
    weights = [1.0 / (i ** alpha) for i in range(1, n + 1)]
    total_weight = sum(weights)
    normalized = [w / total_weight for w in weights]

    # 按权重分配总关注数
    total_follows = n * avg
    follows_per_user = []
    for w in normalized:
        count = int(w * total_follows)
        follows_per_user.append(max(1, count))  # 至少关注1人

    # 调整总数
    diff = total_follows - sum(follows_per_user)
    for i in range(abs(diff)):
        if diff > 0:
            follows_per_user[i % n] += 1
        else:
            if follows_per_user[i % n] > 1:
                follows_per_user[i % n] -= 1

    random.shuffle(follows_per_user)
    return follows_per_user


def generate_follows(users: list[User], avg_follows: int, interest_weight: float, reciprocal_prob: float, rng: random.Random):
    """生成关注关系。"""
    n = len(users)
    follows_counts = power_law_sample(n, avg_follows)

    # 计算用户间相似度矩阵（只计算上三角）
    similarity = {}
    for i in range(n):
        for j in range(i + 1, n):
            sim = compute_user_similarity(users[i], users[j])
            similarity[(i, j)] = sim

    follows = []  # [(follower_id, followed_id)]
    follow_set = set()
    reciprocal_candidates = defaultdict(list)  # {followed_id: [follower_ids]}

    for idx, user in enumerate(users):
        target_count = follows_counts[idx]
        candidates = []

        # 构建候选列表（排除自己和已关注的）
        for j, other in enumerate(users):
            if j == idx:
                continue
            if (user.id, other.id) in follow_set:
                continue

            # 计算选择概率（兴趣相似度 + 随机性）
            if (idx, j) in similarity:
                sim = similarity[(idx, j)]
            elif (j, idx) in similarity:
                sim = similarity[(j, idx)]
            else:
                sim = 0.0

            # 混合兴趣相似度和随机性
            score = interest_weight * sim + (1 - interest_weight) * rng.random()
            candidates.append((score, j, other))

        # 按分数排序，选择 top-N
        candidates.sort(key=lambda x: -x[0])
        selected = candidates[:target_count]

        for _, _, followed in selected:
            follows.append((user.id, followed.id))
            follow_set.add((user.id, followed.id))
            reciprocal_candidates[followed.id].append(user.id)

    # 互惠关注：被关注的用户有一定概率回关
    reciprocal_follows = []
    for followed_id, follower_ids in reciprocal_candidates.items():
        for follower_id in follower_ids:
            if (followed_id, follower_id) in follow_set:
                continue  # 已经互关
            if rng.random() < reciprocal_prob:
                reciprocal_follows.append((followed_id, follower_id))
                follow_set.add((followed_id, follower_id))

    return follows + reciprocal_follows


def write_to_mysql(follows: list[tuple[int, int]], dry_run: bool):
    """写入 MySQL user_follow 表（如果存在）。"""
    if dry_run:
        return

    # 检查是否有 user_follow 表
    try:
        from app.models.user import user_follow
        db.session.execute(db.delete(user_follow))
        for follower_id, followed_id in follows:
            db.session.execute(
                user_follow.insert().values(follower_id=follower_id, followed_id=followed_id)
            )
        db.session.commit()
        print(f"  已写入 MySQL user_follow 表")
    except Exception as e:
        print(f"  [WARN] MySQL 写入失败（可能没有 user_follow 表）: {e}")


def write_to_neo4j(follows: list[tuple[int, int]], clear_existing: bool, dry_run: bool):
    """写入 Neo4j FOLLOWS 关系。"""
    if dry_run:
        return

    if clear_existing:
        neo4j_service.run_write("MATCH ()-[r:FOLLOWS]->() DELETE r")
        print(f"  已清除 Neo4j 中已有 FOLLOWS 关系")

    # 批量写入（每批500条）
    batch_size = 500
    for i in range(0, len(follows), batch_size):
        batch = follows[i:i + batch_size]
        neo4j_service.run_write(
            "UNWIND $items AS item "
            "MATCH (a:User {id: item.follower_id}), (b:User {id: item.followed_id}) "
            "MERGE (a)-[:FOLLOWS]->(b)",
            {"items": [{"follower_id": f, "followed_id": t} for f, t in batch]}
        )
    print(f"  已写入 Neo4j FOLLOWS 关系")


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        users = db.session.scalars(db.select(User).order_by(User.id)).all()
        if len(users) < 2:
            print("用户数不足，无法生成社交网络")
            return

        print(f"===== 社交网络生成 =====")
        print(f"用户数: {len(users)}")
        print(f"平均关注数: {args.avg_follows}")
        print(f"互惠概率: {args.reciprocal_prob}")
        print(f"兴趣权重: {args.interest_weight}")
        print(f"dry_run: {args.dry_run}")

        rng = random.Random(20260413)
        follows = generate_follows(
            users,
            args.avg_follows,
            args.interest_weight,
            args.reciprocal_prob,
            rng,
        )

        print(f"\n生成关注关系: {len(follows)} 条")

        # 统计分布
        follower_counts = defaultdict(int)
        followed_counts = defaultdict(int)
        for follower_id, followed_id in follows:
            follower_counts[follower_id] += 1
            followed_counts[followed_id] += 1

        print(f"  关注数分布: min={min(follower_counts.values())}, max={max(follower_counts.values())}, avg={sum(follower_counts.values())/len(follower_counts):.1f}")
        print(f"  粉丝数分布: min={min(followed_counts.values()) if followed_counts else 0}, max={max(followed_counts.values()) if followed_counts else 0}, avg={sum(followed_counts.values())/len(followed_counts) if followed_counts else 0:.1f}")

        # 互惠关注统计
        reciprocal = sum(1 for f, t in follows if (t, f) in follows)
        print(f"  互惠关注: {reciprocal} 对 ({reciprocal/len(follows)*100:.1f}%)")

        if args.dry_run:
            print("\n[DRY-RUN] 未写入数据库")
            # 打印前10条
            for i, (f, t) in enumerate(follows[:10]):
                print(f"  {i+1}. User#{f} -> User#{t}")
            return

        write_to_mysql(follows, args.dry_run)
        write_to_neo4j(follows, args.clear_existing, args.dry_run)

        print("\n===== 完成 =====")


if __name__ == "__main__":
    main()
