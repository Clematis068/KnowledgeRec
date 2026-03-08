"""Pipeline A: 基于物品的协同过滤 (Item-Based CF + IUF加权)"""
import math
from collections import defaultdict

from app import db
from app.models.behavior import UserBehavior
from app.services.redis_service import redis_service
from app.utils.helpers import min_max_normalize

BEHAVIOR_WEIGHTS = {
    'browse': 1.0,    # × min(duration/60, 3.0)
    'like': 3.0,
    'favorite': 5.0,
    'comment': 4.0,
}


class CFEngine:

    def precompute_item_similarity(self):
        """离线预计算物品相似度矩阵，存入 Redis"""
        behaviors = UserBehavior.query.all()

        # 构建 user-item 交互矩阵
        user_items = defaultdict(dict)   # {user_id: {post_id: score}}
        item_users = defaultdict(set)    # {post_id: {user_ids}}

        for b in behaviors:
            score = self._behavior_score(b)
            user_items[b.user_id][b.post_id] = max(
                user_items[b.user_id].get(b.post_id, 0), score
            )
            item_users[b.post_id].add(b.user_id)

        # 计算 item-item 相似度 (IUF加权余弦)
        item_ids = list(item_users.keys())
        count = 0

        for i, item_i in enumerate(item_ids):
            sims = {}
            for item_j in item_ids:
                if item_i == item_j:
                    continue
                common = item_users[item_i] & item_users[item_j]
                if not common:
                    continue
                # IUF: 惩罚过于活跃的用户
                numerator = sum(
                    1.0 / math.log(1 + len(user_items[u]))
                    for u in common
                )
                denominator = math.sqrt(len(item_users[item_i]) * len(item_users[item_j]))
                if denominator > 0:
                    sims[str(item_j)] = numerator / denominator

            # 只保留 Top-50 相似物品
            top_sims = dict(sorted(sims.items(), key=lambda x: -x[1])[:50])
            if top_sims:
                redis_service.set_sorted_set(f"item_sim:{item_i}", top_sims, ttl=86400)
                count += 1

            if (i + 1) % 500 == 0:
                print(f"  CF预计算进度: {i + 1}/{len(item_ids)}")

        print(f"  物品相似度计算完成，共 {count} 个物品")

    def recommend(self, user_id, candidate_ids=None, top_n=200):
        """
        在线推荐：为用户生成 CF 得分
        返回 {post_id: normalized_score}
        """
        behaviors = UserBehavior.query.filter_by(user_id=user_id).all()
        user_ratings = {}
        for b in behaviors:
            score = self._behavior_score(b)
            user_ratings[b.post_id] = max(user_ratings.get(b.post_id, 0), score)

        interacted = set(user_ratings.keys())
        scores = defaultdict(float)

        for item_id, rating in user_ratings.items():
            similar = redis_service.get_top_from_sorted_set(f"item_sim:{item_id}", 20)
            for sim_item_str, sim_score in similar:
                sim_item = int(sim_item_str)
                if sim_item in interacted:
                    continue
                if candidate_ids and sim_item not in candidate_ids:
                    continue
                scores[sim_item] += sim_score * rating

        return min_max_normalize(dict(scores))

    def _behavior_score(self, behavior):
        if behavior.behavior_type == 'browse':
            return BEHAVIOR_WEIGHTS['browse'] * min((behavior.duration or 30) / 60.0, 3.0)
        return BEHAVIOR_WEIGHTS.get(behavior.behavior_type, 1.0)
