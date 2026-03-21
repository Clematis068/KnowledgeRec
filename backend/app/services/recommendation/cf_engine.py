"""Pipeline A: 基于物品的协同过滤 (Item-Based CF + IUF加权 + 时间衰减)"""
import math
from collections import defaultdict
from datetime import datetime

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

TIME_DECAY_LAMBDA = 0.03

ITEM_SIM_TTL = 30 * 86400


class CFEngine:

    def precompute_item_similarity(self):
        """离线预计算物品相似度矩阵，存入 Redis"""
        behaviors = db.session.scalars(db.select(UserBehavior)).all()

        # 构建 user-item 交互矩阵
        user_items, item_users = self._build_interaction_matrices(behaviors)

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
                redis_service.set_sorted_set(f"item_sim:{item_i}", top_sims, ttl=ITEM_SIM_TTL)
                count += 1

            if (i + 1) % 500 == 0:
                print(f"  CF预计算进度: {i + 1}/{len(item_ids)}")

        print(f"  物品相似度计算完成，共 {count} 个物品")

    def recommend(self, user_id, candidate_ids=None, top_n=200, exclude_post_ids=None):
        """
        在线推荐：为用户生成 CF 得分
        返回 {post_id: normalized_score}
        """
        exclude_post_ids = exclude_post_ids or set()
        stmt = db.select(UserBehavior).filter_by(user_id=user_id)
        behaviors = db.session.scalars(stmt).all()
        if not behaviors:
            return {}

        user_ratings = {}
        for b in behaviors:
            score = self._behavior_score(b)
            user_ratings[b.post_id] = max(user_ratings.get(b.post_id, 0), score)

        interacted = set(user_ratings.keys())
        skip = interacted | exclude_post_ids
        scores = defaultdict(float)
        cache_hits = 0

        for item_id, rating in user_ratings.items():
            try:
                similar = redis_service.get_top_from_sorted_set(f"item_sim:{item_id}", 20)
            except Exception:
                similar = []
            if similar:
                cache_hits += 1
            for sim_item_str, sim_score in similar:
                sim_item = int(sim_item_str)
                if sim_item in skip:
                    continue
                if candidate_ids and sim_item not in candidate_ids:
                    continue
                scores[sim_item] += sim_score * rating

        if scores:
            return min_max_normalize(dict(scores))

        # Redis 中还没有离线相似度缓存时，回退到在线共现计算，避免 CF 分支长期为 0
        if cache_hits == 0:
            return self._recommend_online(user_ratings, candidate_ids, top_n, exclude_post_ids)

        return min_max_normalize(dict(scores))

    def _behavior_score(self, behavior):
        if behavior.behavior_type == 'browse':
            base = BEHAVIOR_WEIGHTS['browse'] * min((behavior.duration or 30) / 60.0, 3.0)
        else:
            base = BEHAVIOR_WEIGHTS.get(behavior.behavior_type, 1.0)
        if behavior.created_at:
            age_days = (datetime.now() - behavior.created_at).days
            base *= math.exp(-TIME_DECAY_LAMBDA * age_days)
        return base

    def _build_interaction_matrices(self, behaviors):
        user_items = defaultdict(dict)   # {user_id: {post_id: score}}
        item_users = defaultdict(set)    # {post_id: {user_ids}}

        for behavior in behaviors:
            score = self._behavior_score(behavior)
            user_items[behavior.user_id][behavior.post_id] = max(
                user_items[behavior.user_id].get(behavior.post_id, 0),
                score,
            )
            item_users[behavior.post_id].add(behavior.user_id)

        return user_items, item_users

    def _recommend_online(self, user_ratings, candidate_ids=None, top_n=200, exclude_post_ids=None):
        exclude_post_ids = exclude_post_ids or set()
        behaviors = db.session.scalars(db.select(UserBehavior)).all()
        user_items, item_users = self._build_interaction_matrices(behaviors)

        interacted = set(user_ratings.keys())
        skip = interacted | exclude_post_ids
        scores = defaultdict(float)

        for item_id, rating in user_ratings.items():
            for other_item_id, other_users in item_users.items():
                if other_item_id == item_id or other_item_id in skip:
                    continue
                if candidate_ids and other_item_id not in candidate_ids:
                    continue

                common = item_users[item_id] & other_users
                if not common:
                    continue

                numerator = sum(
                    1.0 / math.log(1 + len(user_items[user_id]))
                    for user_id in common
                )
                denominator = math.sqrt(len(item_users[item_id]) * len(other_users))
                if denominator <= 0:
                    continue

                similarity = numerator / denominator
                scores[other_item_id] += similarity * rating

        ranked = dict(sorted(scores.items(), key=lambda item: -item[1])[:top_n])
        return min_max_normalize(ranked)
