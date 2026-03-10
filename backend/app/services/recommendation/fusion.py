"""三路推荐分数融合"""
from app.utils.helpers import min_max_normalize

DEFAULT_WEIGHTS = {
    'cf': 0.35,
    'graph': 0.35,
    'semantic': 0.30,
}


class FusionEngine:

    def __init__(self, weights=None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def fuse(self, cf_scores, graph_scores, semantic_scores, top_n=20, weights=None):
        """
        加权线性融合三路得分
        返回 [(post_id, final_score), ...]
        """
        weights = self._normalize_weights(weights or self.weights)
        all_candidates = set(cf_scores) | set(graph_scores) | set(semantic_scores)

        final = {}
        for pid in all_candidates:
            final[pid] = (
                weights['cf'] * cf_scores.get(pid, 0.0)
                + weights['graph'] * graph_scores.get(pid, 0.0)
                + weights['semantic'] * semantic_scores.get(pid, 0.0)
            )

        ranked = sorted(final.items(), key=lambda x: -x[1])
        return ranked[:top_n]

    def fuse_with_details(self, cf_scores, graph_scores, semantic_scores, top_n=20, weights=None):
        """融合并返回各路详细得分，方便前端展示和论文分析"""
        weights = self._normalize_weights(weights or self.weights)
        all_candidates = set(cf_scores) | set(graph_scores) | set(semantic_scores)

        results = []
        for pid in all_candidates:
            cf = cf_scores.get(pid, 0.0)
            graph = graph_scores.get(pid, 0.0)
            semantic = semantic_scores.get(pid, 0.0)
            final = (
                weights['cf'] * cf
                + weights['graph'] * graph
                + weights['semantic'] * semantic
            )
            results.append({
                'post_id': pid,
                'final_score': round(final, 4),
                'cf_score': round(cf, 4),
                'graph_score': round(graph, 4),
                'semantic_score': round(semantic, 4),
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
