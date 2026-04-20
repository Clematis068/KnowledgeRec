"""推荐引擎入口：多路召回 + GBDT精排 / 加权线性融合"""
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from flask import current_app
from sqlalchemy.orm import joinedload

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.services.redis_service import redis_service
from app.utils.content_filter import get_blocked_author_ids, get_blocked_domain_ids
from app.utils.context import compute_post_context_bonus, resolve_effective_context

from .cf_engine import CFEngine
from .feature_extractor import FeatureExtractor
from .fusion import FusionEngine
from .graph_engine import GraphEngine
from .hot_engine import HotEngine
from .logic_constraint_engine import LogicConstraintEngine
from .ranker import GBDTRanker
from .semantic_engine import SemanticEngine
from .swing_engine import SwingEngine

logger = logging.getLogger(__name__)

POST_CACHE_TTL = 1800  # Post 元数据 Redis 缓存 30 分钟


class _PostMeta:
    """轻量 Post 代理，字段与 Post ORM 兼容，用于避免重复 DB 查询。"""
    __slots__ = ('id', 'title', 'summary', 'author_id', 'domain_id',
                 'view_count', 'like_count', 'tags', 'target_regions',
                 'target_time_slots', 'created_at')

    def __init__(self, data):
        self.id = data['id']
        self.title = data.get('title', '')
        self.summary = data.get('summary')
        self.author_id = data.get('author_id')
        self.domain_id = data.get('domain_id')
        self.view_count = data.get('view_count', 0)
        self.like_count = data.get('like_count', 0)
        self.target_regions = data.get('target_regions') or []
        self.target_time_slots = data.get('target_time_slots') or []
        # tags 存为轻量对象列表
        tag_ids = data.get('tag_ids', [])
        tag_names = data.get('tag_names', [])
        self.tags = [type('Tag', (), {'id': tid, 'name': tn, 'domain_id': None})()
                     for tid, tn in zip(tag_ids, tag_names)]
        ca = data.get('created_at')
        if ca and isinstance(ca, str):
            from datetime import datetime
            try:
                self.created_at = datetime.fromisoformat(ca)
            except Exception:
                self.created_at = None
        else:
            self.created_at = ca


def _batch_load_posts(post_ids):
    """批量加载 Post，优先走 Redis 缓存，未命中再查 DB 并回填。
    返回 {post_id: Post | _PostMeta}。
    """
    if not post_ids:
        return {}

    post_ids = list(set(post_ids))
    result = {}

    # 1) 尝试从 Redis 批量获取
    import json as _json
    cache_keys = [f"post_meta:{pid}" for pid in post_ids]
    try:
        cached_values = redis_service.client.mget(cache_keys)
    except Exception:
        cached_values = [None] * len(post_ids)

    miss_ids = []
    for pid, cached in zip(post_ids, cached_values):
        if cached is not None:
            try:
                result[pid] = _PostMeta(_json.loads(cached))
            except Exception:
                miss_ids.append(pid)
        else:
            miss_ids.append(pid)

    # 2) 未命中的查 DB 并写入缓存
    if miss_ids:
        posts = db.session.scalars(
            db.select(Post)
            .options(joinedload(Post.tags), joinedload(Post.author), joinedload(Post.domain))
            .filter(Post.id.in_(miss_ids))
        ).unique().all()

        pipe = redis_service.client.pipeline(transaction=False)
        for p in posts:
            result[p.id] = p
            meta = {
                'id': p.id, 'title': p.title, 'summary': p.summary,
                'author_id': p.author_id, 'domain_id': p.domain_id,
                'view_count': p.view_count or 0, 'like_count': p.like_count or 0,
                'tag_ids': [t.id for t in p.tags],
                'tag_names': [t.name for t in p.tags],
                'target_regions': p.target_regions or [],
                'target_time_slots': p.target_time_slots or [],
                'created_at': p.created_at.isoformat() if p.created_at else None,
            }
            pipe.setex(f"post_meta:{p.id}", POST_CACHE_TTL, _json.dumps(meta, ensure_ascii=False))
        try:
            pipe.execute()
        except Exception:
            pass

    return result


USER_STAGE_WEIGHTS = {
    'cold': {'cf': 0.00, 'swing': 0.00, 'graph': 0.23, 'semantic': 0.24, 'knowledge': 0.11, 'hot': 0.42},
    'warm': {'cf': 0.14, 'swing': 0.06, 'graph': 0.25, 'semantic': 0.22, 'knowledge': 0.11, 'hot': 0.22},
    'active': {'cf': 0.28, 'swing': 0.08, 'graph': 0.22, 'semantic': 0.20, 'knowledge': 0.12, 'hot': 0.10},
}

DIVERSITY_BUFFER_MULTIPLIER = 4
EXPLORATION_POOL_MULTIPLIER = 3
RECALL_ROUTE_NAMES = ('cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot')


class RecommendationEngine:

    # 共享线程池：所有请求复用，避免高并发下线程数爆炸
    _executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix='recall')

    def __init__(self):
        self.cf = CFEngine()
        self.swing = SwingEngine()
        self.graph = GraphEngine()
        self.semantic = SemanticEngine()
        self.hot = HotEngine()
        self.fusion = FusionEngine()
        self.logic = LogicConstraintEngine()
        self.feature_extractor = FeatureExtractor()
        self.ranker = GBDTRanker()
        self.ranker.load()
        # 评估专用缓存：存放预加载的 user_stage / dislike 信息，
        # 供 _get_user_stage / _apply_negative_feedback 优先读取。
        # 生产请求时为空，对现网路径无影响；评估结束需调用 clear_evaluation_cache。
        self._eval_cache = {'enabled': False, 'user_stages': {}, 'user_dislikes': {}}

    # ── 评估缓存：跨 18 配置复用 user_stage / dislike 预加载 ──

    def warm_evaluation_cache(self, user_ids):
        """预加载 user_stages 和 dislike 信息，避免评估时每个用户每个配置都重查 DB。

        - user_stage：对同一用户，所有配置间相同。
        - dislike：同理。mask 环境下查到的是 cutoff 前的 dislike，与生产语义一致。
        """
        user_ids = list(user_ids)
        if not user_ids:
            self._eval_cache = {'enabled': True, 'user_stages': {}, 'user_dislikes': {}}
            return

        # ── 批量算 user_stage ──
        stage_counts = dict(db.session.execute(
            db.select(
                UserBehavior.user_id,
                db.func.count(UserBehavior.id),
            )
            .filter(
                UserBehavior.user_id.in_(user_ids),
                UserBehavior.behavior_type.in_(['browse', 'like', 'favorite', 'comment']),
            )
            .group_by(UserBehavior.user_id)
        ).all())
        user_stages = {}
        for uid in user_ids:
            c = stage_counts.get(uid, 0)
            user_stages[uid] = 'cold' if c == 0 else ('warm' if c < 15 else 'active')

        # ── 批量算 dislike 信息 ──
        dislikes_rows = db.session.scalars(
            db.select(UserBehavior).filter(
                UserBehavior.user_id.in_(user_ids),
                UserBehavior.behavior_type == 'dislike',
            )
        ).all()
        user_to_post_ids = {}
        for b in dislikes_rows:
            user_to_post_ids.setdefault(b.user_id, set()).add(b.post_id)

        # 一次性加载所有 dislike 的 Post（含标签），按用户组织
        all_disliked_post_ids = {pid for pids in user_to_post_ids.values() for pid in pids}
        post_map = {}
        if all_disliked_post_ids:
            from sqlalchemy.orm import joinedload
            disliked_posts = db.session.scalars(
                db.select(Post)
                .options(joinedload(Post.tags))
                .filter(Post.id.in_(all_disliked_post_ids))
            ).unique().all()
            post_map = {p.id: p for p in disliked_posts}

        user_dislikes = {}
        for uid in user_ids:
            pids = user_to_post_ids.get(uid)
            if not pids:
                user_dislikes[uid] = None  # 无 dislike，短路标记
                continue
            posts = [post_map[pid] for pid in pids if pid in post_map]
            user_dislikes[uid] = {
                'post_ids': set(pids),
                'author_ids': {p.author_id for p in posts},
                'domain_ids': {p.domain_id for p in posts},
                'tag_names': {tag.name for p in posts for tag in p.tags},
            }

        self._eval_cache = {
            'enabled': True,
            'user_stages': user_stages,
            'user_dislikes': user_dislikes,
        }

    def clear_evaluation_cache(self):
        self._eval_cache = {'enabled': False, 'user_stages': {}, 'user_dislikes': {}}

    def recommend(
        self,
        user_id,
        top_n=20,
        enable_llm=True,
        enable_hot=True,
        request_context=None,
        weights=None,
        exclude_post_ids=None,
        enable_exploration=True,
        enable_swing=True,
        enabled_routes=None,
    ):
        results, _ = self.recommend_with_debug(
            user_id,
            top_n=top_n,
            enable_llm=enable_llm,
            enable_hot=enable_hot,
            request_context=request_context,
            weights=weights,
            exclude_post_ids=exclude_post_ids,
            enable_exploration=enable_exploration,
            enable_swing=enable_swing,
            enabled_routes=enabled_routes,
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
        exclude_post_ids=None,
        enable_exploration=True,
        enable_swing=True,
        enabled_routes=None,
    ):
        """
        多路召回 + 加权线性融合推荐流水线。
        """
        # ── 多路召回 ──
        results_map = self._parallel_recall(
            user_id,
            enable_llm=enable_llm,
            enable_hot=enable_hot,
            enable_swing=enable_swing,
            enabled_routes=enabled_routes,
        )

        cf_scores = results_map['cf']
        swing_scores = results_map['swing']
        graph_scores = results_map['graph']
        semantic_scores = results_map['semantic']
        hot_scores = results_map['hot']
        knowledge_scores = results_map['knowledge']

        excluded_ids = {
            int(post_id)
            for post_id in (exclude_post_ids or [])
            if str(post_id).isdigit()
        }

        if self.ranker.is_available() and weights is None:
            final_results, debug_info = self._gbdt_ranking_pipeline(
                user_id, results_map, top_n, excluded_ids,
                request_context, enable_exploration,
            )
        else:
            final_results, debug_info = self._legacy_fusion_pipeline(
                user_id, results_map, top_n, excluded_ids,
                request_context, weights, enable_exploration, enable_swing,
            )

        # ── 公共 debug 信息 ──
        final_post_ids = {item['post_id'] for item in final_results}
        all_post_ids = final_post_ids.copy()
        for scores in (cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores, hot_scores):
            for pid in sorted(scores, key=scores.get, reverse=True)[:5]:
                all_post_ids.add(pid)
        post_cache = _batch_load_posts(all_post_ids)

        debug_info['recall_stats'] = getattr(self, '_last_recall_stats', {})
        debug_info['exploration_enabled'] = bool(enable_exploration)
        debug_info['swing_enabled'] = bool(enable_swing)
        debug_info['hot_enabled'] = bool(enable_hot)
        debug_info['knowledge_enabled'] = bool(knowledge_scores)
        debug_info['exclude_post_ids_count'] = len(excluded_ids)
        debug_info['result_count_after_filter'] = len(final_results)
        debug_info['route_samples'] = {
            'cf': self._build_route_samples(cf_scores, final_post_ids, post_cache),
            'swing': self._build_route_samples(swing_scores, final_post_ids, post_cache),
            'graph': self._build_route_samples(graph_scores, final_post_ids, post_cache),
            'semantic': self._build_route_samples(semantic_scores, final_post_ids, post_cache),
            'knowledge': self._build_route_samples(knowledge_scores, final_post_ids, post_cache),
            'hot': self._build_route_samples(hot_scores, final_post_ids, post_cache),
        }
        debug_info['final_preview'] = self._build_result_preview(final_results, post_cache)

        return final_results, debug_info

    # ══════════════════════════════════════════════════
    #  加权融合流水线
    # ══════════════════════════════════════════════════

    def _legacy_fusion_pipeline(self, user_id, results_map, top_n, excluded_ids,
                                request_context, weights, enable_exploration, enable_swing):
        """加权线性融合 → 后处理逻辑。"""
        cf_scores = results_map['cf']
        swing_scores = results_map['swing']
        graph_scores = results_map['graph']
        semantic_scores = results_map['semantic']
        hot_scores = results_map['hot']
        knowledge_scores = results_map['knowledge']

        resolved_weights, debug_info = self._resolve_weights(
            user_id, cf_scores, swing_scores, graph_scores,
            semantic_scores, knowledge_scores, hot_scores,
            requested_weights=weights,
        )

        buffer_n = max(
            (top_n + len(excluded_ids)) * DIVERSITY_BUFFER_MULTIPLIER,
            top_n * DIVERSITY_BUFFER_MULTIPLIER,
            top_n,
        )
        results = self.fusion.fuse_with_details(
            cf_scores, swing_scores, graph_scores,
            semantic_scores, knowledge_scores, hot_scores,
            buffer_n, weights=resolved_weights,
        )

        all_post_ids = {item['post_id'] for item in results}
        for scores in (cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores, hot_scores):
            for pid in sorted(scores, key=scores.get, reverse=True)[:5]:
                all_post_ids.add(pid)
        post_cache = _batch_load_posts(all_post_ids)

        resolved_context = self._resolve_context(user_id, request_context)
        context_results = self._apply_context_bonus(results, resolved_context, post_cache)
        filtered_results = self._apply_negative_feedback(user_id, context_results, buffer_n, post_cache)
        unseen_results = self._exclude_seen_posts(filtered_results, excluded_ids)
        logic_adjusted_results = self.logic.apply(user_id, unseen_results, post_cache=post_cache)
        diversified_results = self._apply_diversity_window(
            logic_adjusted_results, top_n,
            debug_info.get('user_stage', 'unknown'), post_cache,
        )
        if enable_exploration:
            final_results = self._apply_exploration(user_id, diversified_results, unseen_results, top_n)
        else:
            final_results = diversified_results[:top_n]

        debug_info['negative_feedback_applied'] = True
        debug_info['diversity_applied'] = True
        debug_info['diversity_limits'] = self._get_diversity_limits(debug_info.get('user_stage', 'unknown'))
        debug_info['context'] = resolved_context
        debug_info['context_enabled'] = bool(resolved_context.get('region_code') or resolved_context.get('time_slot'))
        debug_info['result_count_before_filter'] = len(results)
        debug_info['result_count_after_negative_filter'] = len(filtered_results)
        debug_info['result_count_after_exclude_seen'] = len(unseen_results)
        debug_info['result_count_after_logic'] = len(logic_adjusted_results)
        debug_info['result_count_after_diversity'] = len(diversified_results)
        debug_info['fusion_preview'] = self._build_result_preview(results, post_cache)
        debug_info['logic_preview'] = self._build_result_preview(logic_adjusted_results, post_cache)
        debug_info['diversity_preview'] = self._build_result_preview(diversified_results, post_cache)

        return final_results, debug_info

    # ══════════════════════════════════════════════════
    #  GBDT 精排流水线
    # ══════════════════════════════════════════════════

    def _gbdt_ranking_pipeline(self, user_id, results_map, top_n, excluded_ids,
                               request_context, enable_exploration):
        """GBDT 精排 → 后处理逻辑。"""
        cf_scores = results_map['cf']
        swing_scores = results_map['swing']
        graph_scores = results_map['graph']
        semantic_scores = results_map['semantic']
        hot_scores = results_map['hot']
        knowledge_scores = results_map['knowledge']

        # 每路取 top-K 候选再合并（避免候选池过大导致精排失效）
        RECALL_TOP_K = 50
        all_candidate_ids = set()
        for scores in (cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores, hot_scores):
            top_ids = sorted(scores, key=scores.get, reverse=True)[:RECALL_TOP_K]
            all_candidate_ids.update(top_ids)
        if not all_candidate_ids:
            return [], {'ranking_method': 'gbdt', 'user_stage': self._get_user_stage(user_id)}

        buffer_n = max(
            (top_n + len(excluded_ids)) * DIVERSITY_BUFFER_MULTIPLIER,
            top_n * DIVERSITY_BUFFER_MULTIPLIER,
            top_n,
        )

        post_ids = list(all_candidate_ids)
        post_cache = _batch_load_posts(post_ids)

        # 构建 recall_scores dict: {post_id: {'cf': x, 'swing': x, ...}}
        recall_scores = {}
        for pid in post_ids:
            recall_scores[pid] = {
                'cf': cf_scores.get(pid, 0.0),
                'swing': swing_scores.get(pid, 0.0),
                'graph': graph_scores.get(pid, 0.0),
                'semantic': semantic_scores.get(pid, 0.0),
                'knowledge': knowledge_scores.get(pid, 0.0),
                'hot': hot_scores.get(pid, 0.0),
            }

        # 特征提取
        resolved_context = self._resolve_context(user_id, request_context)
        self.feature_extractor.warm_user_cache(user_id, logic_engine=self.logic)
        features = self.feature_extractor.extract_batch(
            user_id, post_ids, recall_scores, resolved_context, post_cache,
        )

        # GBDT 预测
        gbdt_probs = self.ranker.predict(features)

        # 构建结果列表（与 fusion 格式兼容）
        results = []
        for i, pid in enumerate(post_ids):
            rs = recall_scores[pid]
            results.append({
                'post_id': pid,
                'final_score': round(gbdt_probs[i], 4),
                'gbdt_score': round(gbdt_probs[i], 4),
                'cf_score': round(rs['cf'], 4),
                'swing_score': round(rs['swing'], 4),
                'graph_score': round(rs['graph'], 4),
                'semantic_score': round(rs['semantic'], 4),
                'knowledge_score': round(rs['knowledge'], 4),
                'hot_score': round(rs['hot'], 4),
            })
        results.sort(key=lambda r: -r['final_score'])
        results = results[:buffer_n]

        # 后处理（不调用 context_bonus，因为特征 13/14 已编码上下文）
        filtered_results = self._apply_negative_feedback(user_id, results, buffer_n, post_cache)
        unseen_results = self._exclude_seen_posts(filtered_results, excluded_ids)
        logic_adjusted_results = self.logic.apply(user_id, unseen_results, post_cache=post_cache)
        stage = self._get_user_stage(user_id)
        diversified_results = self._apply_diversity_window(
            logic_adjusted_results, top_n, stage, post_cache,
        )
        if enable_exploration:
            final_results = self._apply_exploration(user_id, diversified_results, unseen_results, top_n)
        else:
            final_results = diversified_results[:top_n]

        self.feature_extractor.clear_cache()

        debug_info = {
            'ranking_method': 'gbdt',
            'user_stage': stage,
            'negative_feedback_applied': True,
            'diversity_applied': True,
            'diversity_limits': self._get_diversity_limits(stage),
            'context': resolved_context,
            'context_enabled': bool(resolved_context.get('region_code') or resolved_context.get('time_slot')),
            'result_count_before_filter': len(results),
            'result_count_after_negative_filter': len(filtered_results),
            'result_count_after_exclude_seen': len(unseen_results),
            'result_count_after_logic': len(logic_adjusted_results),
            'result_count_after_diversity': len(diversified_results),
            'route_counts': {
                'cf': len(cf_scores), 'swing': len(swing_scores),
                'graph': len(graph_scores), 'semantic': len(semantic_scores),
                'knowledge': len(knowledge_scores), 'hot': len(hot_scores),
            },
        }

        return final_results, debug_info

    def _parallel_recall(self, user_id, enable_llm=True, enable_hot=True, enable_swing=True, enabled_routes=None):
        """6 路并行召回，返回 {name: {post_id: score}}。"""
        app = current_app._get_current_object()
        enabled_routes = set(enabled_routes or RECALL_ROUTE_NAMES)

        # ── 黑名单前置：一次性加载，传递给各召回引擎 ──
        blocked_author_ids = get_blocked_author_ids(user_id)
        blocked_domain_ids = get_blocked_domain_ids(user_id)
        exclude_post_ids = set()
        if blocked_author_ids or blocked_domain_ids:
            stmt = db.select(Post.id)
            conditions = []
            if blocked_author_ids:
                conditions.append(Post.author_id.in_(blocked_author_ids))
            if blocked_domain_ids:
                conditions.append(Post.domain_id.in_(blocked_domain_ids))
            from sqlalchemy import or_
            stmt = stmt.filter(or_(*conditions))
            exclude_post_ids = set(db.session.scalars(stmt).all())
        self._last_exclude_post_ids = exclude_post_ids

        # ── 预加载用户行为，供 CF / Swing / Knowledge 共享，避免重复 DB 查询 ──
        user_behaviors = db.session.scalars(
            db.select(UserBehavior).filter_by(user_id=user_id)
        ).all()

        pipeline_factories = {
            'cf':        lambda: self.cf.recommend(user_id, exclude_post_ids=exclude_post_ids,
                                                   user_behaviors=user_behaviors),
            'swing':     lambda: self.swing.recommend(user_id, exclude_post_ids=exclude_post_ids,
                                                      user_behaviors=user_behaviors) if enable_swing else {},
            'graph':     lambda: self.graph.recommend(user_id, exclude_post_ids=exclude_post_ids),
            'semantic':  lambda: self.semantic.recommend(user_id, enable_llm_rerank=enable_llm, exclude_post_ids=exclude_post_ids),
            'hot':       lambda: self.hot.recommend(
                user_id, exclude_post_ids=exclude_post_ids,
                exclude_author_ids=blocked_author_ids, exclude_domain_ids=blocked_domain_ids,
            ) if enable_hot else {},
            'knowledge': lambda: self.logic.recall(user_id, exclude_post_ids=exclude_post_ids,
                                                   user_behaviors=user_behaviors),
        }
        results_map = {name: {} for name in RECALL_ROUTE_NAMES}
        recall_stats = {
            name: {'count': 0, 'latency_ms': 0.0, 'skipped': name not in enabled_routes}
            for name in RECALL_ROUTE_NAMES
        }
        recall_start = time.perf_counter()
        future_to_name = {
            self._executor.submit(self._run_pipeline_timed, pipeline_factories[name], app): name
            for name in RECALL_ROUTE_NAMES
            if name in enabled_routes
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                scores, elapsed_ms = future.result()
                results_map[name] = scores
                recall_stats[name] = {
                    'count': len(scores),
                    'latency_ms': elapsed_ms,
                }
            except Exception as e:
                logger.warning("Pipeline %s failed: %s", name, e)
                results_map[name] = {}
                recall_stats[name] = {'count': 0, 'latency_ms': -1, 'error': str(e)}
        total_ms = round((time.perf_counter() - recall_start) * 1000, 1)
        slowest = max(recall_stats.items(), key=lambda x: x[1].get('latency_ms', 0))
        logger.info(
            "Recall done for user=%s total=%.1fms | %s | slowest=%s(%.1fms)",
            user_id, total_ms,
            " ".join(f"{n}={s['count']}/{s['latency_ms']:.0f}ms" for n, s in recall_stats.items()),
            slowest[0], slowest[1].get('latency_ms', 0),
        )
        self._last_recall_stats = recall_stats
        return results_map

    def precompute(self):
        """离线预计算（物品相似度矩阵等），可由定时任务或手动触发。"""
        logger.info("开始预计算 CF + Swing 相似度矩阵...")
        self.cf.precompute_item_similarity()
        self.swing.precompute_item_similarity()
        logger.info("预计算完成")

    @staticmethod
    def _run_pipeline_timed(fn, app):
        with app.app_context():
            t0 = time.perf_counter()
            result = fn()
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            return result, elapsed_ms

    # ── 后处理方法 ──

    def _apply_negative_feedback(self, user_id, results, top_n, post_cache):
        # 黑名单过滤已前置到召回层，这里只处理 dislike 降权
        # 优先读评估缓存（跨 18 配置复用，避免重复 SQL）
        if self._eval_cache['enabled'] and user_id in self._eval_cache['user_dislikes']:
            cached_info = self._eval_cache['user_dislikes'][user_id]
            if cached_info is None:
                return results[:top_n]
            disliked_post_ids = cached_info['post_ids']
            disliked_author_ids = cached_info['author_ids']
            disliked_domain_ids = cached_info['domain_ids']
            disliked_tag_names = cached_info['tag_names']
        else:
            stmt = db.select(UserBehavior).filter_by(
                user_id=user_id, behavior_type='dislike',
            )
            disliked_behaviors = db.session.scalars(stmt).all()
            if not disliked_behaviors:
                return results[:top_n]

            stmt = db.select(Post).filter(Post.id.in_([b.post_id for b in disliked_behaviors]))
            disliked_posts = db.session.scalars(stmt).all()
            disliked_post_ids = {p.id for p in disliked_posts}
            disliked_author_ids = {p.author_id for p in disliked_posts}
            disliked_domain_ids = {p.domain_id for p in disliked_posts}
            disliked_tag_names = {tag.name for p in disliked_posts for tag in p.tags}

        rescored = []
        for item in results:
            if item['post_id'] in disliked_post_ids:
                continue
            post = post_cache.get(item['post_id']) or db.session.get(Post, item['post_id'])
            if not post:
                continue
            penalty = 0.0
            if post.author_id in disliked_author_ids:
                penalty += 0.2
            if post.domain_id in disliked_domain_ids:
                penalty += 0.12
            overlap_count = sum(1 for tag in post.tags if tag.name in disliked_tag_names)
            penalty += min(overlap_count * 0.06, 0.18)
            updated = dict(item)
            updated['negative_penalty'] = round(penalty, 4)
            updated['final_score'] = round(max(item['final_score'] - penalty, 0.0), 4)
            rescored.append(updated)
        rescored.sort(key=lambda r: -r['final_score'])
        return rescored[:top_n]

    def _exclude_seen_posts(self, results, exclude_post_ids):
        if not exclude_post_ids:
            return results
        return [item for item in results if item['post_id'] not in exclude_post_ids]

    def _apply_diversity_window(self, results, top_n, user_stage, post_cache):
        if not results:
            return []
        limits = self._get_diversity_limits(user_stage)
        selected = []
        deferred = []
        author_counts = {}
        domain_counts = {}
        tag_counts = {}
        for item in results:
            post = post_cache.get(item['post_id']) or db.session.get(Post, item['post_id'])
            if not post:
                continue
            ac = author_counts.get(post.author_id, 0)
            dc = domain_counts.get(post.domain_id, 0)
            # 检查 tag 维度：帖子的主标签（第一个）是否已出现过多
            primary_tag = post.tags[0].name if post.tags else None
            tc = tag_counts.get(primary_tag, 0) if primary_tag else 0
            if ac >= limits['author'] or dc >= limits['domain'] or (primary_tag and tc >= limits['tag']):
                deferred.append((item, post))
                continue
            picked = dict(item)
            picked['diversity_kept'] = True
            selected.append(picked)
            author_counts[post.author_id] = ac + 1
            domain_counts[post.domain_id] = dc + 1
            if primary_tag:
                tag_counts[primary_tag] = tc + 1
            if len(selected) >= top_n:
                return selected
        for item, _post in deferred:
            if len(selected) >= top_n:
                break
            fallback = dict(item)
            fallback['diversity_fallback'] = True
            selected.append(fallback)
        return selected[:top_n]

    def _get_diversity_limits(self, user_stage):
        if user_stage == 'cold':
            return {'author': 3, 'domain': 6, 'tag': 5}
        return {'author': 2, 'domain': 3, 'tag': 4}

    def _apply_exploration(self, user_id, selected_results, ranked_results, top_n):
        if not selected_results:
            return []
        selected_ids = {s['post_id'] for s in selected_results}
        pool = [
            dict(item)
            for item in ranked_results[top_n: top_n * EXPLORATION_POOL_MULTIPLIER]
            if item['post_id'] not in selected_ids
        ]
        if not pool:
            return selected_results[:top_n]
        # 种子加入日期，使每天探索内容不同
        day_seed = date.today().toordinal()
        rng = random.Random(user_id * 9973 + top_n * 131 + day_seed)
        if rng.random() >= 0.10:
            return selected_results[:top_n]
        insert_count = 1 if top_n < 12 else 2
        insert_count = min(insert_count, len(pool), len(selected_results))
        positions = list(range(max(top_n // 2, 1), len(selected_results)))
        if not positions:
            return selected_results[:top_n]
        rng.shuffle(pool)
        rng.shuffle(positions)
        final = [dict(item) for item in selected_results[:top_n]]
        for idx in range(insert_count):
            pos = positions[idx]
            explore_item = dict(pool[idx])
            explore_item['is_exploration'] = True
            final[pos] = explore_item
        return final[:top_n]

    def _resolve_context(self, user_id, request_context=None):
        from app.models.user import User
        user = db.session.get(User, user_id)
        return resolve_effective_context(user=user, request_context=request_context)

    def _apply_context_bonus(self, results, context, post_cache):
        if not results:
            return results
        if not context.get('region_code') and not context.get('time_slot'):
            return results
        rescored = []
        for item in results:
            post = post_cache.get(item['post_id']) or db.session.get(Post, item['post_id'])
            if not post:
                continue
            bonus, matches = compute_post_context_bonus(post, context)
            updated = dict(item)
            updated['context_score'] = round(bonus, 4)
            updated['context_region_match'] = matches['region_match']
            updated['context_time_slot_match'] = matches['time_slot_match']
            updated['final_score'] = round(item['final_score'] + bonus, 4)
            rescored.append(updated)
        rescored.sort(key=lambda r: -r['final_score'])
        return rescored

    def _resolve_weights(self, user_id, cf_scores, swing_scores, graph_scores,
                         semantic_scores, knowledge_scores, hot_scores, requested_weights=None):
        stage = self._get_user_stage(user_id)
        if requested_weights:
            all_keys = {'cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot'}
            if all_keys <= set(requested_weights.keys()):
                # 消融实验：全部 6 路权重由调用方指定，直接使用
                base_weights = {k: requested_weights[k] for k in all_keys}
            else:
                # 前端调权：只传 cf/swing/graph/semantic，knowledge/hot 用阶段默认
                hot_weight = USER_STAGE_WEIGHTS[stage].get('hot', 0.0)
                knowledge_weight = USER_STAGE_WEIGHTS[stage].get('knowledge', 0.0)
                normalized_requested = self.fusion._normalize_weights({
                    'cf': requested_weights.get('cf', 0.0),
                    'swing': requested_weights.get('swing', 0.0),
                    'graph': requested_weights.get('graph', 0.0),
                    'semantic': requested_weights.get('semantic', 0.0),
                })
                remaining_weight = max(1.0 - hot_weight - knowledge_weight, 0.0)
                base_weights = {
                    'cf': normalized_requested['cf'] * remaining_weight,
                    'swing': normalized_requested['swing'] * remaining_weight,
                    'graph': normalized_requested['graph'] * remaining_weight,
                    'semantic': normalized_requested['semantic'] * remaining_weight,
                    'knowledge': knowledge_weight,
                    'hot': hot_weight,
                }
        else:
            base_weights = dict(USER_STAGE_WEIGHTS[stage])
            if swing_scores:
                base_weights['swing'] *= self._estimate_swing_weight_factor(swing_scores)
        normalized = self.fusion._normalize_weights(base_weights)
        availability = {
            'cf': bool(cf_scores), 'swing': bool(swing_scores),
            'graph': bool(graph_scores), 'semantic': bool(semantic_scores),
            'knowledge': bool(knowledge_scores), 'hot': bool(hot_scores),
        }
        available_names = [name for name, avail in availability.items() if avail]
        if not available_names:
            return normalized, {
                'user_stage': stage,
                'weights_base': normalized,
                'weights_used': normalized,
                'route_availability': availability,
                'route_counts': {n: len(s) for n, s in zip(
                    ['cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot'],
                    [cf_scores, swing_scores, graph_scores, semantic_scores, knowledge_scores, hot_scores])},
            }
        redistributed_total = sum(normalized[n] for n, a in availability.items() if not a)
        available_total = sum(normalized[n] for n in available_names)
        if available_total <= 0:
            even = 1.0 / len(available_names)
            used_weights = {n: (even if n in available_names else 0.0) for n in normalized}
        else:
            used_weights = {}
            for n in normalized:
                if not availability[n]:
                    used_weights[n] = 0.0
                else:
                    share = normalized[n] / available_total
                    used_weights[n] = normalized[n] + redistributed_total * share
        used_weights = self.fusion._normalize_weights(used_weights)
        debug_info = {
            'user_stage': stage,
            'weights_base': {n: round(v, 4) for n, v in normalized.items()},
            'weights_used': {n: round(v, 4) for n, v in used_weights.items()},
            'route_availability': availability,
            'route_counts': {
                'cf': len(cf_scores), 'swing': len(swing_scores),
                'graph': len(graph_scores), 'semantic': len(semantic_scores),
                'knowledge': len(knowledge_scores), 'hot': len(hot_scores),
            },
        }
        return used_weights, debug_info

    def _estimate_swing_weight_factor(self, swing_scores):
        if not swing_scores:
            return 0.0
        BASELINE = 0.6
        top_scores = sorted(swing_scores.values(), reverse=True)[:10]
        avg_score = sum(top_scores) / len(top_scores)
        coverage = min(len(swing_scores) / 80.0, 1.0)
        raw = avg_score * coverage
        # 用 baseline 平滑：80% baseline + 20% 数据驱动，避免波动过大
        return max(0.3, min(BASELINE * 0.8 + raw * 0.2, 1.0))

    def _build_route_samples(self, scores, selected_post_ids, post_cache, limit=5):
        ranked = sorted(scores.items(), key=lambda item: -item[1])[:limit]
        samples = []
        for post_id, score in ranked:
            post = post_cache.get(post_id) or db.session.get(Post, post_id)
            if not post:
                continue
            samples.append({
                'post_id': post.id, 'title': post.title, 'summary': post.summary,
                'domain_id': post.domain_id, 'author_id': post.author_id,
                'score': round(score, 4), 'selected': post.id in selected_post_ids,
            })
        return samples

    def _build_result_preview(self, items, post_cache, limit=10):
        preview = []
        for item in items[:limit]:
            post = post_cache.get(item['post_id']) or db.session.get(Post, item['post_id'])
            if not post:
                continue
            preview.append({
                'post_id': post.id, 'title': post.title,
                'final_score': round(item.get('final_score', 0.0), 4),
                'cf_score': round(item.get('cf_score', 0.0), 4),
                'swing_score': round(item.get('swing_score', 0.0), 4),
                'graph_score': round(item.get('graph_score', 0.0), 4),
                'semantic_score': round(item.get('semantic_score', 0.0), 4),
                'knowledge_score': round(item.get('knowledge_score', 0.0), 4),
                'hot_score': round(item.get('hot_score', 0.0), 4),
                'context_score': round(item.get('context_score', 0.0), 4),
                'negative_penalty': round(item.get('negative_penalty', 0.0), 4),
                'logic_bonus': round(item.get('logic_bonus', 0.0), 4),
                'logic_penalty': round(item.get('logic_penalty', 0.0), 4),
                'diversity_kept': bool(item.get('diversity_kept')),
                'diversity_fallback': bool(item.get('diversity_fallback')),
                'is_exploration': bool(item.get('is_exploration')),
            })
        return preview

    def _get_user_stage(self, user_id):
        if self._eval_cache['enabled']:
            cached = self._eval_cache['user_stages'].get(user_id)
            if cached is not None:
                return cached
        behavior_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(UserBehavior)
            .filter(
                UserBehavior.user_id == user_id,
                UserBehavior.behavior_type.in_(['browse', 'like', 'favorite', 'comment']),
            )
        ) or 0
        if behavior_count == 0:
            return 'cold'
        if behavior_count < 15:
            return 'warm'
        return 'active'


recommendation_engine = RecommendationEngine()
