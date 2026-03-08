"""推荐引擎入口：编排三路 Pipeline 并融合"""
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

        return self.fusion.fuse_with_details(
            cf_scores, graph_scores, semantic_scores, top_n
        )

    def precompute(self):
        """离线预计算（物品相似度矩阵等）"""
        print("开始预计算...")
        self.cf.precompute_item_similarity()
        print("预计算完成")


recommendation_engine = RecommendationEngine()
