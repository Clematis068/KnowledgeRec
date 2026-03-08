"""Pipeline C: LLM 语义增强推荐 (Embedding + LLM Reranking)"""
from app import db
from app.models.user import User
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.services.qwen_service import qwen_service
from app.services.redis_service import redis_service
from app.utils.helpers import cosine_similarity, min_max_normalize


class SemanticEngine:

    def recommend(self, user_id, candidate_ids=None, top_n=200, enable_llm_rerank=True):
        """
        语义推荐：Embedding相似度 + 可选LLM重排序
        返回 {post_id: normalized_score}
        """
        user = db.session.get(User, user_id)
        if not user:
            return {}

        user_emb = user.interest_embedding

        # 冷启动：没有 embedding 时用兴趣标签实时生成
        if not user_emb:
            tag_names = [t.name for t in user.interest_tags]
            if not tag_names:
                return {}
            try:
                tag_text = "兴趣领域：" + "、".join(tag_names)
                user_emb = qwen_service.get_embedding(tag_text)
            except Exception:
                return {}

        # Stage 1: Embedding 余弦相似度
        if candidate_ids:
            posts = Post.query.filter(Post.id.in_(candidate_ids)).all()
        else:
            posts = Post.query.filter(Post.content_embedding.isnot(None)).all()

        embedding_scores = {}
        for post in posts:
            if not post.content_embedding:
                continue
            sim = cosine_similarity(user_emb, post.content_embedding)
            embedding_scores[post.id] = (sim + 1) / 2  # [-1,1] -> [0,1]

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
