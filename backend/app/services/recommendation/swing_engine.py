"""Pipeline E: Swing 召回，补充小圈子共现信号。"""
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations

from app import db
from app.models.behavior import UserBehavior
from app.services.redis_service import redis_service
from app.utils.helpers import min_max_normalize

from .cf_engine import CFEngine, ONLINE_FALLBACK_DAYS

SWING_ALPHA = 1.0
SWING_MIN_COMMON_USERS = 3
SWING_SIM_TTL = 30 * 86400
SWING_TOP_K = 50


class SwingEngine:

    def __init__(self):
        self.cf_engine = CFEngine()

    def precompute_item_similarity(self):
        """离线预计算 Swing item-item 相似度矩阵。"""
        behaviors = db.session.scalars(db.select(UserBehavior)).all()
        user_items, item_users = self.cf_engine._build_interaction_matrices(behaviors)
        item_sets = {
            user_id: set(items.keys())
            for user_id, items in user_items.items()
        }

        item_ids = list(item_users.keys())
        count = 0

        for i, item_i in enumerate(item_ids):
            sims = {}
            for item_j in item_ids:
                if item_i == item_j:
                    continue
                similarity = self._compute_pair_swing(
                    item_i,
                    item_j,
                    item_users,
                    item_sets,
                )
                if similarity > 0:
                    sims[str(item_j)] = similarity

            top_sims = dict(sorted(sims.items(), key=lambda item: -item[1])[:SWING_TOP_K])
            if top_sims:
                redis_service.set_sorted_set(f"swing_sim:{item_i}", top_sims, ttl=SWING_SIM_TTL)
                count += 1

            if (i + 1) % 500 == 0:
                print(f"  Swing预计算进度: {i + 1}/{len(item_ids)}")

        print(f"  Swing相似度计算完成，共 {count} 个物品")

    def recommend(self, user_id, candidate_ids=None, top_n=200, exclude_post_ids=None,
                  user_behaviors=None):
        """在线推荐：为用户生成 Swing 得分。"""
        exclude_post_ids = exclude_post_ids or set()
        if user_behaviors is not None:
            behaviors = user_behaviors
        else:
            stmt = db.select(UserBehavior).filter_by(user_id=user_id)
            behaviors = db.session.scalars(stmt).all()
        if not behaviors:
            return {}

        user_ratings = {}
        for behavior in behaviors:
            score = self.cf_engine._behavior_score(behavior)
            user_ratings[behavior.post_id] = max(user_ratings.get(behavior.post_id, 0.0), score)

        interacted = set(user_ratings.keys())
        skip = interacted | exclude_post_ids
        scores = defaultdict(float)
        cache_hits = 0

        for item_id, rating in user_ratings.items():
            try:
                similar = redis_service.get_top_from_sorted_set(f"swing_sim:{item_id}", 20)
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
            ranked = dict(sorted(scores.items(), key=lambda item: -item[1])[:top_n])
            return min_max_normalize(ranked)

        if cache_hits == 0:
            return self._recommend_online(user_ratings, candidate_ids, top_n, exclude_post_ids)

        return {}

    def _recommend_online(self, user_ratings, candidate_ids=None, top_n=200, exclude_post_ids=None):
        exclude_post_ids = exclude_post_ids or set()
        cutoff = datetime.now() - timedelta(days=ONLINE_FALLBACK_DAYS)
        behaviors = db.session.scalars(
            db.select(UserBehavior).filter(UserBehavior.created_at >= cutoff)
        ).all()
        user_items, item_users = self.cf_engine._build_interaction_matrices(behaviors)
        item_sets = {
            user_id: set(items.keys())
            for user_id, items in user_items.items()
        }

        interacted = set(user_ratings.keys())
        skip = interacted | exclude_post_ids
        scores = defaultdict(float)

        for item_id, rating in user_ratings.items():
            for other_item_id in item_users:
                if other_item_id == item_id or other_item_id in skip:
                    continue
                if candidate_ids and other_item_id not in candidate_ids:
                    continue

                similarity = self._compute_pair_swing(
                    item_id,
                    other_item_id,
                    item_users,
                    item_sets,
                )
                if similarity <= 0:
                    continue
                scores[other_item_id] += similarity * rating

        ranked = dict(sorted(scores.items(), key=lambda item: -item[1])[:top_n])
        return min_max_normalize(ranked)

    def _compute_pair_swing(self, item_i, item_j, item_users, item_sets):
        common_users = list(item_users[item_i] & item_users[item_j])
        if len(common_users) < SWING_MIN_COMMON_USERS:
            return 0.0

        score = 0.0
        for user_left, user_right in combinations(common_users, 2):
            overlap_count = len(item_sets[user_left] & item_sets[user_right])
            score += 1.0 / (SWING_ALPHA + overlap_count)
        return score / len(common_users)
