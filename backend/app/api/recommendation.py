import json

from flask import Blueprint, request, jsonify, g, Response, stream_with_context
from sqlalchemy.orm import joinedload

from app import db
from app.models.post import Post
from app.services.recommendation import recommendation_engine
from app.services.qwen_service import qwen_service
from app.services.redis_service import redis_service
from app.utils.auth import login_required
from app.utils.context import build_request_context

REASON_CACHE_TTL = 3600  # 推荐理由缓存 1 小时

# 推荐理由专用采样：高温度+高 top_p 让措辞更多样，presence_penalty 抑制模板腔复读
REASON_GEN_KWARGS = {
    "temperature": 0.95,
    "top_p": 0.92,
    "presence_penalty": 0.6,
    "max_tokens": 120,
}

rec_bp = Blueprint('recommendation', __name__)


def _parse_exclude_post_ids(raw_value):
    if not raw_value:
        return []
    return [
        int(item)
        for item in raw_value.split(',')
        if item.strip().isdigit()
    ]


def _attach_post_snapshot(item, post):
    if not post:
        return
    post_data = post.to_dict()
    item.update({
        'title': post_data.get('title'),
        'summary': post_data.get('summary'),
        'image_url': post_data.get('image_url'),
        'author_id': post_data.get('author_id'),
        'author_name': post_data.get('author_name'),
        'domain_id': post_data.get('domain_id'),
        'domain_name': post_data.get('domain_name'),
        'view_count': post_data.get('view_count'),
        'like_count': post_data.get('like_count'),
        'tags': post_data.get('tags', []),
        'created_at': post_data.get('created_at'),
    })


@rec_bp.route('/recommend/<int:user_id>', methods=['GET'])
def get_recommendations(user_id):
    """获取用户的个性化推荐"""
    top_n = request.args.get('top_n', 20, type=int)
    enable_llm = request.args.get('enable_llm', 'true').lower() == 'true'
    enable_hot = request.args.get('enable_hot', 'true').lower() == 'true'
    debug = request.args.get('debug', 'false').lower() == 'true'
    exclude_post_ids = _parse_exclude_post_ids(request.args.get('exclude_post_ids', ''))
    request_context = build_request_context(request)

    # 可选自定义权重
    w_cf = request.args.get('w_cf', type=float)
    w_graph = request.args.get('w_graph', type=float)
    w_semantic = request.args.get('w_semantic', type=float)
    weights = None
    if all(w is not None for w in [w_cf, w_graph, w_semantic]):
        weights = {'cf': w_cf, 'graph': w_graph, 'semantic': w_semantic}

    try:
        if debug:
            results, debug_info = recommendation_engine.recommend_with_debug(
                user_id,
                top_n=top_n,
                enable_llm=enable_llm,
                enable_hot=enable_hot,
                request_context=request_context,
                weights=weights,
                exclude_post_ids=exclude_post_ids,
            )
        else:
            results = recommendation_engine.recommend(
                user_id,
                top_n=top_n,
                enable_llm=enable_llm,
                enable_hot=enable_hot,
                request_context=request_context,
                weights=weights,
                exclude_post_ids=exclude_post_ids,
            )
            debug_info = None

        result_post_ids = [item['post_id'] for item in results]
        graph_paths = recommendation_engine.graph.explain_paths(user_id, result_post_ids) if result_post_ids else {}

        # 批量加载帖子详情
        if result_post_ids:
            posts_map = {
                p.id: p
                for p in db.session.scalars(
                    db.select(Post)
                    .options(joinedload(Post.tags), joinedload(Post.author), joinedload(Post.domain))
                    .filter(Post.id.in_(result_post_ids))
                ).unique().all()
            }
        else:
            posts_map = {}

        for item in results:
            post = posts_map.get(item['post_id'])
            _attach_post_snapshot(item, post)
            graph_path = graph_paths.get(item['post_id'])
            if graph_path:
                item['graph_path'] = graph_path or {'type': 'graph_signal'}
                item['graph_path_text'] = (
                    graph_path.get('text')
                    if graph_path else
                    '该帖子与你的兴趣标签、领域偏好或社交关系存在图结构关联'
                )

        payload = {"user_id": user_id, "recommendations": results}
        if debug:
            payload["debug"] = debug_info
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@rec_bp.route('/recommend/me', methods=['GET'])
@login_required
def get_my_recommendations():
    """当前登录用户的个性化推荐"""
    user_id = g.current_user.id
    top_n = request.args.get('top_n', 20, type=int)
    enable_llm = request.args.get('enable_llm', 'true').lower() == 'true'
    enable_hot = request.args.get('enable_hot', 'true').lower() == 'true'
    debug = request.args.get('debug', 'false').lower() == 'true'
    exclude_post_ids = _parse_exclude_post_ids(request.args.get('exclude_post_ids', ''))
    request_context = build_request_context(request)

    w_cf = request.args.get('w_cf', type=float)
    w_graph = request.args.get('w_graph', type=float)
    w_semantic = request.args.get('w_semantic', type=float)
    weights = None
    if all(w is not None for w in [w_cf, w_graph, w_semantic]):
        weights = {'cf': w_cf, 'graph': w_graph, 'semantic': w_semantic}

    try:
        if debug:
            results, debug_info = recommendation_engine.recommend_with_debug(
                user_id,
                top_n=top_n,
                enable_llm=enable_llm,
                enable_hot=enable_hot,
                request_context=request_context,
                weights=weights,
                exclude_post_ids=exclude_post_ids,
            )
        else:
            results = recommendation_engine.recommend(
                user_id,
                top_n=top_n,
                enable_llm=enable_llm,
                enable_hot=enable_hot,
                request_context=request_context,
                weights=weights,
                exclude_post_ids=exclude_post_ids,
            )
            debug_info = None

        result_post_ids = [item['post_id'] for item in results]
        graph_paths = recommendation_engine.graph.explain_paths(user_id, result_post_ids) if result_post_ids else {}

        # 批量加载帖子详情
        if result_post_ids:
            posts_map = {
                p.id: p
                for p in db.session.scalars(
                    db.select(Post)
                    .options(joinedload(Post.tags), joinedload(Post.author), joinedload(Post.domain))
                    .filter(Post.id.in_(result_post_ids))
                ).unique().all()
            }
        else:
            posts_map = {}

        for item in results:
            post = posts_map.get(item['post_id'])
            _attach_post_snapshot(item, post)
            graph_path = graph_paths.get(item['post_id'])
            if graph_path:
                item['graph_path'] = graph_path or {'type': 'graph_signal'}
                item['graph_path_text'] = (
                    graph_path.get('text')
                    if graph_path else
                    '该帖子与你的兴趣标签、领域偏好或社交关系存在图结构关联'
                )

        payload = {"user_id": user_id, "recommendations": results}
        if debug:
            payload["debug"] = debug_info
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_CHANNEL_LABELS = {
    'cf': '协同过滤（行为相似用户都喜欢）',
    'swing': 'Swing 小圈子相似',
    'graph': '知识图谱 / 社交关系',
    'semantic': '语义向量相似',
    'knowledge': '标签知识约束',
    'hot': '社区热度',
}


def _top_channels(channel_scores, k=2, min_score=1e-3):
    """按得分排序取前 k 个有信号的召回通道"""
    filtered = [(c, s) for c, s in channel_scores.items() if s and s > min_score]
    filtered.sort(key=lambda x: -x[1])
    return filtered[:k]


def _build_reason_context(user_id, post_id):
    """加载用户+帖子+图路径+通道分数，返回 (payload_meta, prompt) 或 (None, error_msg, status)。"""
    from app.models.user import User

    user = db.session.get(User, user_id)
    post = db.session.get(Post, post_id)
    if not user or not post:
        return None, "用户或帖子不存在", 404

    channel_scores = {}
    for channel in _CHANNEL_LABELS:
        val = request.args.get(f'{channel}_score', type=float)
        if val is not None:
            channel_scores[channel] = val

    top_channels = _top_channels(channel_scores)

    graph_paths = []
    try:
        context = recommendation_engine.graph.retrieve_paths_context(
            user_id, [post_id], max_per_post=3,
        )
        graph_paths = (context.get(post_id) or {}).get('paths', [])
    except Exception:
        graph_paths = []

    if graph_paths:
        retrieved_block = "\n".join(
            f"  [{idx + 1}] ({p['type']}) {p.get('text', '')}"
            for idx, p in enumerate(graph_paths)
        )
    else:
        retrieved_block = "  （未检索到显式图路径证据）"

    channel_block = "；".join(
        f"{_CHANNEL_LABELS[c]}（{s:.2f}）" for c, s in top_channels
    ) if top_channels else "（无）"

    prompt = (
        "你是一个懂用户的朋友，正向 TA 顺手安利一篇可能感兴趣的帖子。\n"
        "语气要像微信里跟人聊天：自然、轻松、有温度，可以用 '你' '哈' '嗯'，"
        "可以用 '—' 破折号和问号带点情绪，但别夸张别卖萌。\n"
        "硬性要求：\n"
        "  • 必须基于 <retrieved_paths> 中的事实（朋友名、标签名、种子帖标题），一个字都不能编；\n"
        "  • 不出现 '算法' '召回' '分数' '图谱' '推荐系统' 这类词；\n"
        "  • 不写 '为你推荐' '向你推送' 这种平台腔；\n"
        "  • 1-2 句话，40-80 字，直接说，不要开场白。\n\n"
        "风格示例（仅供模仿语感，内容别抄）：\n"
        "  好 ✓：你关注的张三刚收藏了这篇，而且跟你之前看的《深度学习入门》都在聊 Transformer，应该合你胃口。\n"
        "  好 ✓：最近你在追「向量数据库」这个话题，这篇正好把 Faiss 和 Milvus 做了一次正面对比，可以顺手看看。\n"
        "  差 ✗：基于您的兴趣偏好，系统为您智能推荐本篇优质内容。（太公文）\n"
        "  差 ✗：哇塞！这篇超棒的！快来看看吧～（太油腻）\n\n"
        f"<user_profile>{user.interest_profile or user.bio or '未提供'}</user_profile>\n"
        f"<candidate_post>\n  标题：{post.title}\n  摘要：{post.summary or '无'}\n</candidate_post>\n"
        f"<retrieved_paths>\n{retrieved_block}\n</retrieved_paths>\n"
        f"<channel_signals>{channel_block}</channel_signals>\n"
    )

    # 记录 prompt 变量，方便调用处传入采样参数
    meta = {"graph_paths": graph_paths}
    if graph_paths:
        meta["graph_path"] = graph_paths[0]
    if top_channels:
        meta["top_channels"] = [
            {"channel": c, "label": _CHANNEL_LABELS[c], "score": round(s, 4)}
            for c, s in top_channels
        ]
    channel_sig = ','.join(c for c, _ in top_channels) or 'none'
    cache_key = f"rec_reason:{user_id}:{post_id}:{channel_sig}"
    return meta, prompt, cache_key


@rec_bp.route('/recommend/<int:user_id>/reason/<int:post_id>', methods=['GET'])
def get_recommendation_reason(user_id, post_id):
    """Graph-RAG 推荐理由生成（非流式，兼容保留）。"""
    ctx = _build_reason_context(user_id, post_id)
    if ctx[0] is None:
        return jsonify({"error": ctx[1]}), ctx[2]
    meta, prompt, cache_key = ctx

    cached = redis_service.get_json(cache_key)
    if cached is not None:
        return jsonify(cached)

    try:
        reason = qwen_service.chat(prompt, **REASON_GEN_KWARGS)
        payload = {"reason": reason, **meta}
        redis_service.set_json(cache_key, payload, ttl=REASON_CACHE_TTL)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _sse(event, data):
    """封装 SSE 消息帧。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@rec_bp.route('/recommend/<int:user_id>/reason/<int:post_id>/stream', methods=['GET'])
def get_recommendation_reason_stream(user_id, post_id):
    """Graph-RAG 推荐理由流式输出（SSE）。

    事件序列：
      meta  → 一次性下发 graph_paths / top_channels（前端立即渲染证据面板）
      delta → LLM 流式增量文本（首字 < 500ms）
      done  → 结束事件，payload = 完整文本
      error → 异常
    缓存命中时一次性 emit 全文 delta + done，延迟 ~5ms。
    """
    ctx = _build_reason_context(user_id, post_id)
    if len(ctx) == 3 and isinstance(ctx[2], int):
        return jsonify({"error": ctx[1]}), ctx[2]
    meta, prompt, cache_key = ctx

    cached = redis_service.get_json(cache_key)

    @stream_with_context
    def generate():
        yield _sse('meta', meta)

        if cached is not None and cached.get('reason'):
            yield _sse('delta', {"text": cached['reason']})
            yield _sse('done', {"reason": cached['reason'], "cached": True})
            return

        chunks = []
        try:
            for delta in qwen_service.chat_stream(prompt, **REASON_GEN_KWARGS):
                chunks.append(delta)
                yield _sse('delta', {"text": delta})
        except Exception as e:
            yield _sse('error', {"message": str(e)})
            return

        full = ''.join(chunks)
        payload = {"reason": full, **meta}
        try:
            redis_service.set_json(cache_key, payload, ttl=REASON_CACHE_TTL)
        except Exception:
            pass
        yield _sse('done', {"reason": full, "cached": False})

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # 关闭反代层缓冲，保证实时推
        },
    )


@rec_bp.route('/precompute', methods=['POST'])
def precompute():
    """触发离线预计算"""
    try:
        recommendation_engine.precompute()
        return jsonify({"status": "预计算完成"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
