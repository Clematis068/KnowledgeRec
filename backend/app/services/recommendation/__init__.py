"""推荐引擎入口：编排三路 Pipeline 并融合"""
from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.utils.content_filter import get_blocked_author_ids, get_blocked_domain_ids

from .cf_engine import CFEngine
from .graph_engine import GraphEngine
from .semantic_engine import SemanticEngine
from .fusion import FusionEngine


class RecommendationEngine:

    def __init__(self):
        self.cf = CFEngine()
        self.graph = GraphEngine()
        self.semantic = SemanticEngine()
        self.fusion = FusionEngine()

    def recommend(self, user_id, top_n=20, enable_llm=True, weights=None):
        """
        完整三路融合推荐
        1. 协同过滤 -> cf_scores
        2. 图谱传播 -> graph_scores
        3. 语义增强 -> semantic_scores
        4. 加权融合 -> final ranking
        """
        if weights:
            self.fusion.weights = weights

        # Pipeline A: 协同过滤
        cf_scores = self.cf.recommend(user_id)

        # Pipeline B: 知识图谱传播
        graph_scores = self.graph.recommend(user_id)

        # 候选集 = CF + Graph 的并集
        candidate_ids = set(cf_scores.keys()) | set(graph_scores.keys())

        # Pipeline C: 语义增强（在候选集上运行）
        semantic_scores = self.semantic.recommend(
            user_id,
            candidate_ids=candidate_ids if candidate_ids else None,
            enable_llm_rerank=enable_llm,
        )

        results = self.fusion.fuse_with_details(
            cf_scores, graph_scores, semantic_scores, top_n
        )
        return self._apply_negative_feedback(user_id, results, top_n)

    def precompute(self):
        """离线预计算（物品相似度矩阵等）"""
        print("开始预计算...")
        self.cf.precompute_item_similarity()
        print("预计算完成")

    def _apply_negative_feedback(self, user_id, results, top_n):
        """对明确点过“不感兴趣”的内容做过滤和相似内容降权。"""
        blocked_author_ids = get_blocked_author_ids(user_id)
        blocked_domain_ids = get_blocked_domain_ids(user_id)
        disliked_behaviors = UserBehavior.query.filter_by(
            user_id=user_id,
            behavior_type='dislike',
        ).all()
        if not disliked_behaviors and not blocked_author_ids and not blocked_domain_ids:
            return results[:top_n]
        if not disliked_behaviors:
            filtered = []
            for item in results:
                post = db.session.get(Post, item['post_id'])
                if not post:
                    continue
                if post.author_id in blocked_author_ids or post.domain_id in blocked_domain_ids:
                    continue
                filtered.append(item)
            return filtered[:top_n]

        disliked_posts = (
            Post.query
            .filter(Post.id.in_([behavior.post_id for behavior in disliked_behaviors]))
            .all()
        )
        disliked_post_ids = {post.id for post in disliked_posts}
        disliked_author_ids = {post.author_id for post in disliked_posts}
        disliked_domain_ids = {post.domain_id for post in disliked_posts}
        disliked_tag_names = {
            tag.name
            for post in disliked_posts
            for tag in post.tags
        }

        rescored_results = []
        for item in results:
            if item['post_id'] in disliked_post_ids:
                continue

            post = db.session.get(Post, item['post_id'])
            if not post:
                continue
            if post.author_id in blocked_author_ids or post.domain_id in blocked_domain_ids:
                continue

            penalty = 0.0
            if post.author_id in disliked_author_ids:
                penalty += 0.2
            if post.domain_id in disliked_domain_ids:
                penalty += 0.12

            overlap_count = sum(1 for tag in post.tags if tag.name in disliked_tag_names)
            penalty += min(overlap_count * 0.06, 0.18)

            updated_item = dict(item)
            updated_item['negative_penalty'] = round(penalty, 4)
            updated_item['final_score'] = round(max(item['final_score'] - penalty, 0.0), 4)
            rescored_results.append(updated_item)

        rescored_results.sort(key=lambda result: -result['final_score'])
        return rescored_results[:top_n]


recommendation_engine = RecommendationEngine()
