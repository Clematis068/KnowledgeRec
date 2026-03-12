"""Pipeline C: LLM 语义增强推荐 (Embedding + LLM Reranking)"""
from datetime import datetime

import numpy as np

from app import db
from app.models.user import User
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.services.qwen_service import qwen_service
from app.services.redis_service import redis_service
from app.services.user_interest_service import BEHAVIOR_PROFILE_WEIGHTS
from app.utils.helpers import cosine_similarity, min_max_normalize

SHORT_TERM_LIMIT = 20
LONG_TERM_LIMIT = 120
SHORT_TERM_DECAY = 0.08
LONG_TERM_DECAY = 0.015
SHORT_TERM_WEIGHT = 0.65
LONG_TERM_WEIGHT = 0.35


class SemanticEngine:
    def recommend(self, user_id, candidate_ids=None, top_n=200, enable_llm_rerank=True):
        """
        语义推荐：长短期兴趣融合 + 可选LLM重排序
        返回 {post_id: normalized_score}
        """
        user = db.session.get(User, user_id)
        if not user:
            return {}

        profile = self._build_user_semantic_profile(user_id, user)
        if not profile["short_term_embedding"] and not profile["long_term_embedding"]:
            return {}

        # Stage 1: 长短期兴趣双路语义召回
        if candidate_ids:
            stmt = db.select(Post).filter(Post.id.in_(candidate_ids))
            posts = db.session.scalars(stmt).all()
        else:
            stmt = db.select(Post).filter(Post.content_embedding.isnot(None))
            posts = db.session.scalars(stmt).all()

        embedding_scores = {}
        for post in posts:
            if not post.content_embedding:
                continue
            embedding_scores[post.id] = self._score_post(profile, post)

        embedding_scores = min_max_normalize(embedding_scores)

        if not enable_llm_rerank:
            return dict(sorted(embedding_scores.items(), key=lambda x: -x[1])[:top_n])

        # Stage 2: LLM 对 Top-50 候选重排序
        top_candidates = sorted(embedding_scores.items(), key=lambda x: -x[1])[:50]
        llm_scores = {}

        for post_id, emb_score in top_candidates:
            post = db.session.get(Post, post_id)
            llm_score = self._llm_relevance_score(user, post)
            llm_scores[post_id] = 0.6 * emb_score + 0.4 * llm_score

        # 合并: LLM重排的用组合分，其余只用Embedding分(打折)
        final = {}
        for post_id, emb_score in embedding_scores.items():
            if post_id in llm_scores:
                final[post_id] = llm_scores[post_id]
            else:
                final[post_id] = emb_score * 0.6

        return min_max_normalize(dict(sorted(final.items(), key=lambda x: -x[1])[:top_n]))

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
            score = int(result.strip()) / 10.0
            score = max(0.0, min(1.0, score))
        except (ValueError, Exception):
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

        return {
            "short_term_embedding": short_term_embedding,
            "long_term_embedding": long_term_embedding,
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

        embeddings = []
        weights = []
        for behavior in behaviors:
            post = db.session.get(Post, behavior.post_id)
            if not post or not post.content_embedding:
                continue

            weight = BEHAVIOR_PROFILE_WEIGHTS.get(behavior.behavior_type, 1.0)
            if behavior.behavior_type == 'browse':
                weight *= min((behavior.duration or 30) / 60.0, 2.0)
            if decay_lambda > 0 and behavior.created_at:
                age_days = max((datetime.now() - behavior.created_at).days, 0)
                weight *= np.exp(-decay_lambda * age_days)
            embeddings.append(np.array(post.content_embedding))
            weights.append(weight)

        if not embeddings:
            return None

        weights = np.array(weights)
        weighted_avg = np.average(embeddings, axis=0, weights=weights)
        return weighted_avg.tolist()
