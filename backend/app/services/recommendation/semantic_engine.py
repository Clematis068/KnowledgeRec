"""Pipeline C: LLM 语义增强推荐 (Embedding + LLM Reranking)"""
import logging
import re
from datetime import datetime, timedelta

import numpy as np
from sklearn.cluster import KMeans

from app import db
from app.models.user import User
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.services.qwen_service import qwen_service
from app.services.redis_service import redis_service
from app.services.user_interest_service import BEHAVIOR_PROFILE_WEIGHTS
from app.services.vector_index import post_vector_index
from app.utils.helpers import cosine_similarity, min_max_normalize

logger = logging.getLogger(__name__)

SHORT_TERM_LIMIT = 20
LONG_TERM_LIMIT = 120
SHORT_TERM_DECAY = 0.08
LONG_TERM_DECAY = 0.015
SHORT_TERM_WEIGHT = 0.65
LONG_TERM_WEIGHT = 0.35
POSITION_DECAY = 0.05          # 位置衰减系数：越靠后权重越低

# 多兴趣聚类参数
MULTI_INTEREST_MAX_K = 3       # 最多 3 个兴趣簇
MULTI_INTEREST_MIN_SAMPLES = 8 # 至少 8 条有效行为才聚类


class SemanticEngine:
    def recommend(self, user_id, candidate_ids=None, top_n=200, enable_llm_rerank=True, exclude_post_ids=None):
        """
        语义推荐：长短期兴趣融合 + 可选LLM重排序
        返回 {post_id: normalized_score}
        """
        exclude_post_ids = exclude_post_ids or set()
        user = db.session.get(User, user_id)
        if not user:
            return {}

        profile = self._build_user_semantic_profile(user_id, user)
        if not profile["short_term_embedding"] and not profile["long_term_embedding"]:
            return {}

        # Stage 1: 长短期兴趣双路语义召回
        # - 无外部候选约束时：走 Faiss 向量索引（全量搜索，O(log N)）
        # - 有候选约束时（候选集 ≤200，评估/上游筛选场景）：走 brute-force，省去索引开销
        if candidate_ids:
            embedding_scores = self._brute_score_on_candidates(
                profile, candidate_ids, exclude_post_ids,
            )
        else:
            embedding_scores = self._faiss_score(
                profile,
                k=max(top_n * 2, 300),
                exclude_ids=exclude_post_ids,
            )
            # 索引尚未就绪 / 为空时回退到原始暴力路径（只会在极冷启动命中）
            if not embedding_scores:
                embedding_scores = self._brute_score_fallback(
                    profile, user_id, user, exclude_post_ids,
                )

        embedding_scores = min_max_normalize(embedding_scores)

        if not enable_llm_rerank:
            return dict(sorted(embedding_scores.items(), key=lambda x: -x[1])[:top_n])

        # Stage 2: LLM 对 Top-50 候选重排序
        top_candidates = sorted(embedding_scores.items(), key=lambda x: -x[1])[:50]
        top_ids = [pid for pid, _ in top_candidates]

        # 批量查询，避免 N+1
        post_map = {
            p.id: p
            for p in db.session.scalars(db.select(Post).filter(Post.id.in_(top_ids))).all()
        }

        llm_combined = {}
        for post_id, emb_score in top_candidates:
            post = post_map.get(post_id)
            if not post:
                continue
            llm_score = self._llm_relevance_score(user, post)
            # emb_score 已 min-max 到 [0,1]，llm_score 也在 [0,1]，量级对齐
            llm_combined[post_id] = 0.6 * emb_score + 0.4 * llm_score

        # 合并：Top-50 用 LLM 组合分，其余保留原 embedding 分（不再打折，避免双分布错位）
        final = dict(embedding_scores)
        final.update(llm_combined)

        return dict(sorted(final.items(), key=lambda x: -x[1])[:top_n])

    # ──────────────── 候选检索 ────────────────

    def _faiss_score(self, profile, k, exclude_ids):
        """用 Faiss 向量索引完成短/长期双路检索，线性加权合并。

        cosine ∈ [-1, 1] → 映射到 [0, 1] 对齐权重。
        长期兴趣多簇心时，取 max（最接近的兴趣簇胜出），与原 `_score_post` 语义一致。
        """
        short_vec = profile.get("short_term_embedding")
        long_vec = profile.get("long_term_embedding")
        centroids = profile.get("interest_centroids") or ([long_vec] if long_vec else [])

        scores = {}
        total_weight = 0.0

        if short_vec:
            for pid, cos in post_vector_index.search(short_vec, k=k, exclude_ids=exclude_ids):
                scores[pid] = scores.get(pid, 0.0) + SHORT_TERM_WEIGHT * ((cos + 1) / 2)
            total_weight += SHORT_TERM_WEIGHT

        if centroids:
            long_per_post = {}
            for vec in centroids:
                if not vec:
                    continue
                for pid, cos in post_vector_index.search(vec, k=k, exclude_ids=exclude_ids):
                    val = (cos + 1) / 2
                    if val > long_per_post.get(pid, 0.0):
                        long_per_post[pid] = val
            if long_per_post:
                for pid, val in long_per_post.items():
                    scores[pid] = scores.get(pid, 0.0) + LONG_TERM_WEIGHT * val
                total_weight += LONG_TERM_WEIGHT

        if total_weight <= 0:
            return {}
        return {pid: v / total_weight for pid, v in scores.items()}

    def _brute_score_on_candidates(self, profile, candidate_ids, exclude_post_ids):
        """候选集受限时（上游已筛过），直接 DB 批量加载再逐一打分。"""
        stmt = db.select(Post).filter(Post.id.in_(candidate_ids))
        if exclude_post_ids:
            stmt = stmt.filter(~Post.id.in_(exclude_post_ids))
        posts = db.session.scalars(stmt).all()
        scores = {}
        for post in posts:
            if not post.content_embedding:
                continue
            scores[post.id] = self._score_post(profile, post)
        return scores

    def _brute_score_fallback(self, profile, user_id, user, exclude_post_ids):
        """Faiss 索引为空时的极冷启动回退（与旧路径等价，仅保留不常走到）。"""
        domain_ids = self._get_user_domain_ids(user_id, user)
        base_filter = [Post.content_embedding.isnot(None)]
        if exclude_post_ids:
            base_filter.append(~Post.id.in_(exclude_post_ids))
        if domain_ids:
            cutoff = datetime.now() - timedelta(days=90)
            stmt = db.select(Post).filter(
                *base_filter, Post.domain_id.in_(domain_ids), Post.created_at >= cutoff,
            )
            posts = db.session.scalars(stmt).all()
            if len(posts) < 50:
                stmt = db.select(Post).filter(*base_filter, Post.domain_id.in_(domain_ids))
                posts = db.session.scalars(stmt).all()
            if len(posts) < 50:
                stmt = db.select(Post).filter(*base_filter)
                posts = db.session.scalars(stmt).all()
        else:
            stmt = db.select(Post).filter(*base_filter)
            posts = db.session.scalars(stmt).all()
        scores = {}
        for post in posts:
            if not post.content_embedding:
                continue
            scores[post.id] = self._score_post(profile, post)
        return scores

    def _llm_relevance_score(self, user, post):
        """调用千问为用户-帖子匹配打分 (0-10)"""
        cache_key = f"llm_rel:{user.id}:{post.id}"
        cached = redis_service.get_json(cache_key)
        if cached is not None:
            return cached

        prompt = (
            f"你是推荐系统评分助手。\n"
            f"用户兴趣画像：{user.interest_profile or '未知'}\n"
            f"候选文章标题：{post.title}\n"
            f"候选文章摘要：{post.summary or (post.content[:200] if post.content else '无')}\n"
            f"请评估该文章与用户兴趣的匹配度，返回0到10的整数评分，只返回数字。"
        )

        try:
            result = qwen_service.chat(prompt)
            # LLM 可能返回 "评分：8"、"8分" 之类，正则提第一个数字
            m = re.search(r'\d+(?:\.\d+)?', result or '')
            if m:
                score = float(m.group(0)) / 10.0
                score = max(0.0, min(1.0, score))
            else:
                score = 0.5
        except Exception:
            score = 0.5

        redis_service.set_json(cache_key, score, ttl=3600)
        return score

    def _build_user_semantic_profile(self, user_id, user):
        long_term_embedding = user.interest_embedding or self._build_user_embedding_from_behaviors(
            user_id,
            recent_limit=LONG_TERM_LIMIT,
            decay_lambda=LONG_TERM_DECAY,
        )
        short_term_embedding = self._build_user_embedding_from_behaviors(
            user_id,
            recent_limit=SHORT_TERM_LIMIT,
            decay_lambda=SHORT_TERM_DECAY,
        )

        if not long_term_embedding:
            long_term_embedding = self._build_interest_tag_embedding(user)
        if not short_term_embedding:
            short_term_embedding = long_term_embedding

        # 多兴趣聚类：长期行为聚成多个簇心，捕获多元兴趣
        interest_centroids = self._build_multi_interest_centroids(user_id)

        return {
            "short_term_embedding": short_term_embedding,
            "long_term_embedding": long_term_embedding,
            "interest_centroids": interest_centroids,
        }

    def _build_interest_tag_embedding(self, user):
        tag_names = [tag.name for tag in user.interest_tags]
        if not tag_names:
            return None
        try:
            tag_text = "兴趣领域：" + "、".join(tag_names)
            return qwen_service.get_embedding(tag_text)
        except Exception:
            return None

    def _score_post(self, profile, post):
        short_term_score = self._embedding_similarity(
            profile["short_term_embedding"],
            post.content_embedding,
        )

        # 长期兴趣：优先用多簇心 max-cosine，退化为单向量
        centroids = profile.get("interest_centroids")
        if centroids:
            long_term_score = max(
                (self._embedding_similarity(c, post.content_embedding) or 0.0)
                for c in centroids
            )
        else:
            long_term_score = self._embedding_similarity(
                profile["long_term_embedding"],
                post.content_embedding,
            )

        weighted_score = 0.0
        total_weight = 0.0
        if short_term_score is not None:
            weighted_score += short_term_score * SHORT_TERM_WEIGHT
            total_weight += SHORT_TERM_WEIGHT
        if long_term_score is not None:
            weighted_score += long_term_score * LONG_TERM_WEIGHT
            total_weight += LONG_TERM_WEIGHT

        if total_weight <= 0:
            return 0.0
        return weighted_score / total_weight

    def _embedding_similarity(self, user_embedding, post_embedding):
        if not user_embedding or not post_embedding:
            return None
        return (cosine_similarity(user_embedding, post_embedding) + 1) / 2

    def _get_user_domain_ids(self, user_id, user):
        """从用户兴趣标签的 domain_id + 行为关联帖子的 domain_id 取并集。"""
        domain_ids = set()
        if user and user.interest_tags:
            for tag in user.interest_tags:
                if tag.domain_id:
                    domain_ids.add(tag.domain_id)

        behavior_domain_stmt = (
            db.select(Post.domain_id)
            .join(UserBehavior, UserBehavior.post_id == Post.id)
            .filter(
                UserBehavior.user_id == user_id,
                UserBehavior.behavior_type.in_(['favorite', 'like', 'comment', 'browse']),
                Post.domain_id.isnot(None),
            )
            .distinct()
        )
        for did in db.session.scalars(behavior_domain_stmt).all():
            domain_ids.add(did)

        return domain_ids

    def _build_multi_interest_centroids(self, user_id):
        """对用户长期行为的帖子 embedding 做加权 KMeans 聚类，返回多个兴趣簇心。

        行为权重参与聚类（sample_weight），使高价值行为对簇心影响更大。
        行为数 < 8 时返回 None，退化为单向量模式。
        """
        behaviors = db.session.scalars(
            db.select(UserBehavior)
            .filter_by(user_id=user_id)
            .filter(UserBehavior.behavior_type.in_(['favorite', 'like', 'comment', 'browse']))
            .order_by(UserBehavior.created_at.desc())
            .limit(LONG_TERM_LIMIT)
        ).all()

        # 批量加载帖子，避免 N+1
        post_ids = list({b.post_id for b in behaviors})
        post_map = {
            p.id: p
            for p in db.session.scalars(db.select(Post).filter(Post.id.in_(post_ids))).all()
        }

        embeddings = []
        weights = []
        now = datetime.now()
        for idx, b in enumerate(behaviors):
            post = post_map.get(b.post_id)
            if not post or not post.content_embedding:
                continue
            w = BEHAVIOR_PROFILE_WEIGHTS.get(b.behavior_type, 1.0)
            if b.behavior_type == 'browse':
                w *= min((b.duration or 30) / 60.0, 2.0)
            if b.created_at:
                age_days = max((now - b.created_at).days, 0)
                w *= np.exp(-LONG_TERM_DECAY * age_days)
            w *= np.exp(-POSITION_DECAY * idx)
            embeddings.append(np.array(post.content_embedding))
            weights.append(w)

        if len(embeddings) < MULTI_INTEREST_MIN_SAMPLES:
            return None

        X = np.array(embeddings)
        W = np.array(weights)
        k = min(MULTI_INTEREST_MAX_K, len(embeddings) // 4)
        k = max(k, 2)

        try:
            km = KMeans(n_clusters=k, n_init=3, max_iter=50, random_state=42)
            km.fit(X, sample_weight=W)
            logger.debug("User %s: %d behaviors → %d interest clusters", user_id, len(embeddings), k)
            return [c.tolist() for c in km.cluster_centers_]
        except Exception as e:
            logger.warning("Multi-interest clustering failed for user %s: %s", user_id, e)
            return None

    def _build_user_embedding_from_behaviors(self, user_id, recent_limit=100, decay_lambda=0.0):
        behaviors = (
            db.select(UserBehavior)
            .filter_by(user_id=user_id)
            .filter(UserBehavior.behavior_type.in_(['favorite', 'like', 'comment', 'browse']))
            .order_by(UserBehavior.created_at.desc())
            .limit(recent_limit)
        )
        behaviors = db.session.scalars(behaviors).all()
        if not behaviors:
            return None

        # 批量加载帖子，避免 N+1
        post_ids = list({b.post_id for b in behaviors})
        post_map = {
            p.id: p
            for p in db.session.scalars(db.select(Post).filter(Post.id.in_(post_ids))).all()
        }

        embeddings = []
        weights = []
        for idx, behavior in enumerate(behaviors):
            post = post_map.get(behavior.post_id)
            if not post or not post.content_embedding:
                continue

            weight = BEHAVIOR_PROFILE_WEIGHTS.get(behavior.behavior_type, 1.0)
            if behavior.behavior_type == 'browse':
                weight *= min((behavior.duration or 30) / 60.0, 2.0)
            if decay_lambda > 0 and behavior.created_at:
                age_days = max((datetime.now() - behavior.created_at).days, 0)
                weight *= np.exp(-decay_lambda * age_days)
            # 位置衰减：序号越大（越旧）权重越低，让行为顺序影响结果
            weight *= np.exp(-POSITION_DECAY * idx)
            embeddings.append(np.array(post.content_embedding))
            weights.append(weight)

        if not embeddings:
            return None

        weights = np.array(weights)
        weighted_avg = np.average(embeddings, axis=0, weights=weights)
        return weighted_avg.tolist()
