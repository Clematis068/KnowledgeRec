"""18 维特征提取器：为 GBDT 精排提供候选帖子的特征向量。"""
import math
from collections import defaultdict
from datetime import datetime

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User
from app.utils.context import (
    effective_post_regions,
    effective_post_time_slots,
    normalize_region_code,
    normalize_time_slot,
)

POSITIVE_BEHAVIORS = ("browse", "like", "comment", "favorite")
RECALL_KEYS = ("cf", "swing", "graph", "semantic", "knowledge", "hot")


class FeatureExtractor:
    """从用户画像 + 帖子属性 + 召回分数 构造 18 维特征。"""

    def __init__(self):
        self._cache = {}

    # ── public ──

    def warm_user_cache(self, user_id, logic_engine=None):
        """预热用户侧特征缓存，避免逐帖子查 DB。"""
        user = db.session.get(User, user_id)

        # tag_strength / engaged_tag_ids（复用 logic_engine）
        if logic_engine is not None:
            profile = logic_engine._build_user_tag_profile(user_id)
            tag_strength = profile["tag_strength"]
            interest_tag_ids = profile["engaged_tag_ids"]
        else:
            tag_strength = {}
            interest_tag_ids = set()

        # 用户显式兴趣标签名
        interest_tag_names = set()
        if user:
            interest_tag_names = {t.name for t in user.interest_tags}

        # 用户兴趣领域
        interest_domain_ids = set()
        if user:
            behaviors = db.session.scalars(
                db.select(UserBehavior)
                .filter(
                    UserBehavior.user_id == user_id,
                    UserBehavior.behavior_type.in_(POSITIVE_BEHAVIORS),
                )
                .order_by(UserBehavior.created_at.desc())
                .limit(80)
            ).all()
            for b in behaviors:
                post = db.session.get(Post, b.post_id)
                if post and post.domain_id:
                    interest_domain_ids.add(post.domain_id)

        # user_stage
        behavior_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(UserBehavior)
            .filter(
                UserBehavior.user_id == user_id,
                UserBehavior.behavior_type.in_(POSITIVE_BEHAVIORS),
            )
        ) or 0
        if behavior_count == 0:
            user_stage = 0  # cold
        elif behavior_count < 15:
            user_stage = 1  # warm
        else:
            user_stage = 2  # active

        # author_post_count：用户交互过的作者各发帖数量
        author_post_counts = {}
        if behavior_count > 0:
            rows = db.session.execute(
                db.text(
                    "SELECT p.author_id, COUNT(DISTINCT p.id) "
                    "FROM user_behavior ub JOIN post p ON ub.post_id = p.id "
                    "WHERE ub.user_id = :uid AND ub.behavior_type IN ('browse','like','comment','favorite') "
                    "GROUP BY p.author_id"
                ),
                {"uid": user_id},
            ).all()
            author_post_counts = {row[0]: row[1] for row in rows}

        # 用户上下文
        region_code = normalize_region_code(getattr(user, "last_login_region", None)) if user else None
        time_slot = normalize_time_slot(getattr(user, "last_login_time_slot", None)) if user else None

        self._cache[user_id] = {
            "tag_strength": tag_strength,
            "interest_tag_ids": interest_tag_ids,
            "interest_tag_names": interest_tag_names,
            "interest_domain_ids": interest_domain_ids,
            "user_stage": user_stage,
            "behavior_count": behavior_count,
            "author_post_counts": author_post_counts,
            "region_code": region_code,
            "time_slot": time_slot,
        }

    def extract_batch(self, user_id, post_ids, recall_scores, context, post_cache):
        """批量提取特征。

        Args:
            user_id: 用户 ID
            post_ids: 候选帖子 ID 列表
            recall_scores: {post_id: {'cf': score, 'swing': score, ...}}
            context: resolve_effective_context 返回的 dict
            post_cache: {post_id: Post}

        Returns:
            list[list[float]]  —— 每行 18 维
        """
        uc = self._cache.get(user_id, {})
        tag_strength = uc.get("tag_strength", {})
        interest_tag_names = uc.get("interest_tag_names", set())
        interest_domain_ids = uc.get("interest_domain_ids", set())
        user_stage = uc.get("user_stage", 0)
        behavior_count = uc.get("behavior_count", 0)
        author_post_counts = uc.get("author_post_counts", {})
        region_code = context.get("region_code") or uc.get("region_code")
        time_slot = context.get("time_slot") or uc.get("time_slot")
        now = datetime.now()

        features = []
        for pid in post_ids:
            scores = recall_scores.get(pid, {})
            post = post_cache.get(pid)

            # 0-5: 6 路召回分数
            cf_s = scores.get("cf", 0.0)
            swing_s = scores.get("swing", 0.0)
            graph_s = scores.get("graph", 0.0)
            semantic_s = scores.get("semantic", 0.0)
            knowledge_s = scores.get("knowledge", 0.0)
            hot_s = scores.get("hot", 0.0)

            # 6: recall_source_count
            source_count = sum(1 for k in RECALL_KEYS if scores.get(k, 0.0) > 0)

            # 7: tag_overlap_ratio
            tag_overlap_ratio = 0.0
            if post and post.tags:
                post_tag_names = {t.name for t in post.tags}
                if post_tag_names:
                    tag_overlap_ratio = len(post_tag_names & interest_tag_names) / len(post_tag_names)

            # 8: tag_strength_sum
            tag_strength_sum = 0.0
            if post and post.tags:
                tag_strength_sum = sum(tag_strength.get(t.id, 0.0) for t in post.tags)

            # 9: domain_match
            domain_match = 1.0 if (post and post.domain_id in interest_domain_ids) else 0.0

            # 10: user_stage
            stage_val = float(user_stage)

            # 11: post_freshness
            post_freshness = 0.5
            if post and post.created_at:
                age_days = max((now - post.created_at).days, 0)
                post_freshness = 1.0 - min(age_days / 90.0, 1.0)

            # 12: post_popularity
            post_popularity = 0.0
            if post:
                post_popularity = math.log1p(
                    (post.view_count or 0) + (post.like_count or 0) * 3
                )

            # 13: region_match
            region_match = 0.0
            if post and region_code:
                post_regions = effective_post_regions(post)
                if region_code in post_regions:
                    region_match = 1.0

            # 14: time_slot_match
            time_slot_match = 0.0
            if post and time_slot:
                post_slots = effective_post_time_slots(post)
                if time_slot in post_slots:
                    time_slot_match = 1.0

            # 15: author_post_count
            author_count = 0.0
            if post:
                author_count = float(author_post_counts.get(post.author_id, 0))

            # 16: behavior_count
            beh_count = float(behavior_count)

            # 17: max_recall_score
            max_recall = max(cf_s, swing_s, graph_s, semantic_s, knowledge_s, hot_s)

            features.append([
                cf_s, swing_s, graph_s, semantic_s, knowledge_s, hot_s,  # 0-5
                float(source_count),                                     # 6
                tag_overlap_ratio,                                       # 7
                tag_strength_sum,                                        # 8
                domain_match,                                            # 9
                stage_val,                                               # 10
                post_freshness,                                          # 11
                post_popularity,                                         # 12
                region_match,                                            # 13
                time_slot_match,                                         # 14
                author_count,                                            # 15
                beh_count,                                               # 16
                max_recall,                                              # 17
            ])
        return features

    def clear_cache(self):
        self._cache.clear()
