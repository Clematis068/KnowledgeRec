"""多路推荐分数融合"""

DEFAULT_WEIGHTS = {
    'cf': 0.31,
    'swing': 0.08,
    'graph': 0.24,
    'semantic': 0.24,
    'knowledge': 0.13,
    'hot': 0.0,
}


class FusionEngine:

    def __init__(self, weights=None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def fuse(self, cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores=None, hot_scores=None, top_n=20, weights=None):
        """
        加权线性融合多路得分
        返回 [(post_id, final_score), ...]
        """
        cf_scores = cf_scores or {}
        swing_scores = swing_scores or {}
        graph_scores = graph_scores or {}
        semantic_scores = semantic_scores or {}
        knowledge_scores = knowledge_scores or {}
        hot_scores = hot_scores or {}
        weights = self._normalize_weights(weights or self.weights)
        all_candidates = set(cf_scores) | set(swing_scores) | set(graph_scores) | set(semantic_scores) | set(knowledge_scores) | set(hot_scores)

        final = {}
        for pid in all_candidates:
            final[pid] = (
                weights['cf'] * cf_scores.get(pid, 0.0)
                + weights['swing'] * swing_scores.get(pid, 0.0)
                + weights['graph'] * graph_scores.get(pid, 0.0)
                + weights['semantic'] * semantic_scores.get(pid, 0.0)
                + weights['knowledge'] * knowledge_scores.get(pid, 0.0)
                + weights['hot'] * hot_scores.get(pid, 0.0)
            )

        ranked = sorted(final.items(), key=lambda x: -x[1])
        return ranked[:top_n]

    def fuse_with_details(self, cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores=None, hot_scores=None, top_n=20, weights=None):
        """融合并返回各路详细得分，方便前端展示和论文分析"""
        cf_scores = cf_scores or {}
        swing_scores = swing_scores or {}
        graph_scores = graph_scores or {}
        semantic_scores = semantic_scores or {}
        knowledge_scores = knowledge_scores or {}
        hot_scores = hot_scores or {}
        weights = self._normalize_weights(weights or self.weights)
        all_candidates = set(cf_scores) | set(swing_scores) | set(graph_scores) | set(semantic_scores) | set(knowledge_scores) | set(hot_scores)

        results = []
        for pid in all_candidates:
            cf = cf_scores.get(pid, 0.0)
            swing = swing_scores.get(pid, 0.0)
            graph = graph_scores.get(pid, 0.0)
            semantic = semantic_scores.get(pid, 0.0)
            knowledge = knowledge_scores.get(pid, 0.0)
            hot = hot_scores.get(pid, 0.0)
            final = (
                weights['cf'] * cf
                + weights['swing'] * swing
                + weights['graph'] * graph
                + weights['semantic'] * semantic
                + weights['knowledge'] * knowledge
                + weights['hot'] * hot
            )
            results.append({
                'post_id': pid,
                'final_score': round(final, 4),
                'cf_score': round(cf, 4),
                'swing_score': round(swing, 4),
                'graph_score': round(graph, 4),
                'semantic_score': round(semantic, 4),
                'knowledge_score': round(knowledge, 4),
                'hot_score': round(hot, 4),
            })

        results.sort(key=lambda x: -x['final_score'])
        return results[:top_n]

    def _normalize_weights(self, weights):
        total = sum(max(value, 0.0) for value in weights.values())
        if total <= 0:
            return DEFAULT_WEIGHTS.copy()
        return {
            name: max(value, 0.0) / total
            for name, value in weights.items()
        }
