"""推荐引擎入口：编排三路 Pipeline 并融合"""
import random

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.utils.content_filter import get_blocked_author_ids, get_blocked_domain_ids
from app.utils.context import compute_post_context_bonus, resolve_effective_context

from .cf_engine import CFEngine
from .graph_engine import GraphEngine
from .hot_engine import HotEngine
from .semantic_engine import SemanticEngine
from .fusion import FusionEngine

USER_STAGE_WEIGHTS = {
    'cold': {'cf': 0.00, 'graph': 0.28, 'semantic': 0.30, 'hot': 0.42},
    'warm': {'cf': 0.18, 'graph': 0.32, 'semantic': 0.28, 'hot': 0.22},
    'active': {'cf': 0.40, 'graph': 0.27, 'semantic': 0.23, 'hot': 0.10},
}

MAX_SAME_AUTHOR = 2
MAX_SAME_DOMAIN = 3
COLD_MAX_SAME_AUTHOR = 3
COLD_MAX_SAME_DOMAIN = 6
DIVERSITY_BUFFER_MULTIPLIER = 4
EXPLORATION_EPSILON = 0.10
EXPLORATION_MAX_INSERTS = 2
EXPLORATION_POOL_MULTIPLIER = 3


class RecommendationEngine:

    def __init__(self):
        self.cf = CFEngine()
        self.graph = GraphEngine()
        self.semantic = SemanticEngine()
        self.hot = HotEngine()
        self.fusion = FusionEngine()

    def recommend(
        self,
        user_id,
        top_n=20,
        enable_llm=True,
        enable_hot=True,
        request_context=None,
        weights=None,
        enable_exploration=True,
    ):
        results, _ = self.recommend_with_debug(
            user_id,
            top_n=top_n,
            enable_llm=enable_llm,
            enable_hot=enable_hot,
            request_context=request_context,
            weights=weights,
            enable_exploration=enable_exploration,
        )
        return results

    def recommend_with_debug(
        self,
        user_id,
        top_n=20,
        enable_llm=True,
        enable_hot=True,
        request_context=None,
        weights=None,
        enable_exploration=True,
    ):
        """
        完整三路融合推荐
        1. 协同过滤 -> cf_scores
        2. 图谱传播 -> graph_scores
        3. 语义增强独立召回 -> semantic_scores
        4. 加权融合 -> fusion ranking
        5. 滑动窗口打散
        6. 轻量探索插入
        """
        # Pipeline A: 协同过滤
        cf_scores = self.cf.recommend(user_id)

        # Pipeline B: 知识图谱传播
        graph_scores = self.graph.recommend(user_id)

        # Pipeline C: 语义增强独立召回，不再只对 CF/Graph 做 rerank
        semantic_scores = self.semantic.recommend(
            user_id,
            enable_llm_rerank=enable_llm,
        )

        # Pipeline D: 热门召回，缓解冷启动和候选不足
        hot_scores = self.hot.recommend(user_id) if enable_hot else {}

        resolved_weights, debug_info = self._resolve_weights(
            user_id,
            cf_scores,
            graph_scores,
            semantic_scores,
            hot_scores,
            requested_weights=weights,
        )

        buffer_n = max(top_n * DIVERSITY_BUFFER_MULTIPLIER, top_n)
        results = self.fusion.fuse_with_details(
            cf_scores,
            graph_scores,
            semantic_scores,
            hot_scores,
            buffer_n,
            weights=resolved_weights,
        )
        resolved_context = self._resolve_context(user_id, request_context)
        context_results = self._apply_context_bonus(results, resolved_context)
        filtered_results = self._apply_negative_feedback(user_id, context_results, buffer_n)
        diversified_results = self._apply_diversity_window(
            filtered_results,
            top_n,
            debug_info.get('user_stage', 'unknown'),
        )
        if enable_exploration:
            final_results = self._apply_exploration(user_id, diversified_results, filtered_results, top_n)
        else:
            final_results = diversified_results[:top_n]
        final_post_ids = {item['post_id'] for item in final_results}
        debug_info['negative_feedback_applied'] = True
        debug_info['diversity_applied'] = True
        debug_info['diversity_limits'] = self._get_diversity_limits(debug_info.get('user_stage', 'unknown'))
        debug_info['exploration_enabled'] = bool(enable_exploration)
        debug_info['hot_enabled'] = bool(enable_hot)
        debug_info['context'] = resolved_context
        debug_info['context_enabled'] = bool(resolved_context.get('region_code') or resolved_context.get('time_slot'))
        debug_info['result_count_before_filter'] = len(results)
        debug_info['result_count_after_negative_filter'] = len(filtered_results)
        debug_info['result_count_after_diversity'] = len(diversified_results)
        debug_info['result_count_after_filter'] = len(final_results)
        debug_info['route_samples'] = {
            'cf': self._build_route_samples(cf_scores, final_post_ids),
            'graph': self._build_route_samples(graph_scores, final_post_ids),
            'semantic': self._build_route_samples(semantic_scores, final_post_ids),
            'hot': self._build_route_samples(hot_scores, final_post_ids),
        }
        debug_info['fusion_preview'] = self._build_result_preview(results)
        debug_info['diversity_preview'] = self._build_result_preview(diversified_results)
        debug_info['final_preview'] = self._build_result_preview(final_results)
        return final_results, debug_info

    def precompute(self):
        """离线预计算（物品相似度矩阵等）"""
        print("开始预计算...")
        self.cf.precompute_item_similarity()
        print("预计算完成")

    def _apply_negative_feedback(self, user_id, results, top_n):
        """对明确点过“不感兴趣”的内容做过滤和相似内容降权。"""
        blocked_author_ids = get_blocked_author_ids(user_id)
        blocked_domain_ids = get_blocked_domain_ids(user_id)
        stmt = db.select(UserBehavior).filter_by(
            user_id=user_id,
            behavior_type='dislike',
        )
        disliked_behaviors = db.session.scalars(stmt).all()
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

        stmt = db.select(Post).filter(Post.id.in_([behavior.post_id for behavior in disliked_behaviors]))
        disliked_posts = db.session.scalars(stmt).all()
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

    def _apply_diversity_window(self, results, top_n, user_stage):
        if not results:
            return []

        limits = self._get_diversity_limits(user_stage)
        selected = []
        deferred = []
        author_counts = {}
        domain_counts = {}

        for item in results:
            post = db.session.get(Post, item['post_id'])
            if not post:
                continue

            author_count = author_counts.get(post.author_id, 0)
            domain_count = domain_counts.get(post.domain_id, 0)
            if author_count >= limits['author'] or domain_count >= limits['domain']:
                deferred.append((item, post))
                continue

            picked = dict(item)
            picked['diversity_kept'] = True
            selected.append(picked)
            author_counts[post.author_id] = author_count + 1
            domain_counts[post.domain_id] = domain_count + 1
            if len(selected) >= top_n:
                return selected

        for item, _post in deferred:
            if len(selected) >= top_n:
                break
            fallback_item = dict(item)
            fallback_item['diversity_fallback'] = True
            selected.append(fallback_item)

        return selected[:top_n]

    def _get_diversity_limits(self, user_stage):
        if user_stage == 'cold':
            return {
                'author': COLD_MAX_SAME_AUTHOR,
                'domain': COLD_MAX_SAME_DOMAIN,
            }
        return {
            'author': MAX_SAME_AUTHOR,
            'domain': MAX_SAME_DOMAIN,
        }

    def _apply_exploration(self, user_id, selected_results, ranked_results, top_n):
        if not selected_results:
            return []

        selected_ids = {selected['post_id'] for selected in selected_results}
        exploration_pool = [
            dict(item)
            for item in ranked_results[top_n: top_n * EXPLORATION_POOL_MULTIPLIER]
            if item['post_id'] not in selected_ids
        ]
        if not exploration_pool:
            return selected_results[:top_n]

        rng = random.Random(user_id * 9973 + top_n * 131)
        if rng.random() >= EXPLORATION_EPSILON:
            return selected_results[:top_n]

        insert_count = 1 if top_n < 12 else EXPLORATION_MAX_INSERTS
        insert_count = min(insert_count, len(exploration_pool), len(selected_results))
        insertion_positions = list(range(max(top_n // 2, 1), len(selected_results)))
        if not insertion_positions:
            return selected_results[:top_n]

        rng.shuffle(exploration_pool)
        rng.shuffle(insertion_positions)
        final_results = [dict(item) for item in selected_results[:top_n]]

        for idx in range(insert_count):
            position = insertion_positions[idx]
            exploration_item = dict(exploration_pool[idx])
            exploration_item['is_exploration'] = True
            exploration_item['exploration_source_rank'] = ranked_results.index(exploration_pool[idx]) + 1
            final_results[position] = exploration_item

        return final_results[:top_n]

    def _resolve_context(self, user_id, request_context=None):
        from app.models.user import User

        user = db.session.get(User, user_id)
        return resolve_effective_context(user=user, request_context=request_context)

    def _apply_context_bonus(self, results, context):
        if not results:
            return results

        if not context.get('region_code') and not context.get('time_slot'):
            return results

        rescored_results = []
        for item in results:
            post = db.session.get(Post, item['post_id'])
            if not post:
                continue

            bonus, matches = compute_post_context_bonus(post, context)
            updated_item = dict(item)
            updated_item['context_score'] = round(bonus, 4)
            updated_item['context_region_match'] = matches['region_match']
            updated_item['context_time_slot_match'] = matches['time_slot_match']
            updated_item['final_score'] = round(item['final_score'] + bonus, 4)
            rescored_results.append(updated_item)

        rescored_results.sort(key=lambda result: -result['final_score'])
        return rescored_results

    def _resolve_weights(self, user_id, cf_scores, graph_scores, semantic_scores, hot_scores, requested_weights=None):
        stage = self._get_user_stage(user_id)
        if requested_weights:
            hot_weight = USER_STAGE_WEIGHTS[stage].get('hot', 0.0)
            normalized_requested = self.fusion._normalize_weights({
                'cf': requested_weights.get('cf', 0.0),
                'graph': requested_weights.get('graph', 0.0),
                'semantic': requested_weights.get('semantic', 0.0),
            })
            remaining_weight = max(1.0 - hot_weight, 0.0)
            base_weights = {
                'cf': normalized_requested['cf'] * remaining_weight,
                'graph': normalized_requested['graph'] * remaining_weight,
                'semantic': normalized_requested['semantic'] * remaining_weight,
                'hot': hot_weight,
            }
        else:
            base_weights = USER_STAGE_WEIGHTS[stage]
        normalized = self.fusion._normalize_weights(base_weights)
        availability = {
            'cf': bool(cf_scores),
            'graph': bool(graph_scores),
            'semantic': bool(semantic_scores),
            'hot': bool(hot_scores),
        }

        available_names = [name for name, available in availability.items() if available]
        if not available_names:
            return normalized, {
                'user_stage': stage,
                'weights_base': normalized,
                'weights_used': normalized,
                'route_availability': availability,
                'route_counts': {
                    'cf': len(cf_scores),
                    'graph': len(graph_scores),
                    'semantic': len(semantic_scores),
                    'hot': len(hot_scores),
                },
            }

        redistributed_total = sum(
            normalized[name]
            for name, available in availability.items()
            if not available
        )
        available_total = sum(normalized[name] for name in available_names)

        if available_total <= 0:
            even_weight = 1.0 / len(available_names)
            used_weights = {
                name: (even_weight if name in available_names else 0.0)
                for name in normalized
            }
        else:
            used_weights = {}
            for name in normalized:
                if not availability[name]:
                    used_weights[name] = 0.0
                    continue
                share = normalized[name] / available_total
                used_weights[name] = normalized[name] + redistributed_total * share

        used_weights = self.fusion._normalize_weights(used_weights)
        debug_info = {
            'user_stage': stage,
            'weights_base': {name: round(value, 4) for name, value in normalized.items()},
            'weights_used': {name: round(value, 4) for name, value in used_weights.items()},
            'route_availability': availability,
            'route_counts': {
                'cf': len(cf_scores),
                'graph': len(graph_scores),
                'semantic': len(semantic_scores),
                'hot': len(hot_scores),
            },
        }
        return used_weights, debug_info

    def _build_route_samples(self, scores, selected_post_ids, limit=5):
        ranked = sorted(scores.items(), key=lambda item: -item[1])[:limit]
        samples = []
        for post_id, score in ranked:
            post = db.session.get(Post, post_id)
            if not post:
                continue
            samples.append({
                'post_id': post.id,
                'title': post.title,
                'summary': post.summary,
                'domain_id': post.domain_id,
                'author_id': post.author_id,
                'score': round(score, 4),
                'selected': post.id in selected_post_ids,
            })
        return samples

    def _build_result_preview(self, items, limit=10):
        preview = []
        for item in items[:limit]:
            post = db.session.get(Post, item['post_id'])
            if not post:
                continue
            preview.append({
                'post_id': post.id,
                'title': post.title,
                'final_score': round(item.get('final_score', 0.0), 4),
                'cf_score': round(item.get('cf_score', 0.0), 4),
                'graph_score': round(item.get('graph_score', 0.0), 4),
                'semantic_score': round(item.get('semantic_score', 0.0), 4),
                'hot_score': round(item.get('hot_score', 0.0), 4),
                'context_score': round(item.get('context_score', 0.0), 4),
                'negative_penalty': round(item.get('negative_penalty', 0.0), 4),
                'diversity_kept': bool(item.get('diversity_kept')),
                'diversity_fallback': bool(item.get('diversity_fallback')),
                'is_exploration': bool(item.get('is_exploration')),
            })
        return preview

    def _get_user_stage(self, user_id):
        behavior_count = (
            db.session.scalar(
                db.select(db.func.count())
                .select_from(UserBehavior)
                .filter(
                    UserBehavior.user_id == user_id,
                    UserBehavior.behavior_type.in_(['browse', 'like', 'favorite', 'comment'])
                )
            )
        )
        if behavior_count == 0:
            return 'cold'
        if behavior_count < 15:
            return 'warm'
        return 'active'


recommendation_engine = RecommendationEngine()
