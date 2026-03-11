from flask import Blueprint, request, jsonify, g
from app import db
from app.models.post import Post
from app.services.recommendation import recommendation_engine
from app.services.qwen_service import qwen_service
from app.utils.auth import login_required

rec_bp = Blueprint('recommendation', __name__)


@rec_bp.route('/recommend/<int:user_id>', methods=['GET'])
def get_recommendations(user_id):
    """获取用户的个性化推荐"""
    top_n = request.args.get('top_n', 20, type=int)
    enable_llm = request.args.get('enable_llm', 'true').lower() == 'true'
    enable_hot = request.args.get('enable_hot', 'true').lower() == 'true'
    debug = request.args.get('debug', 'false').lower() == 'true'

    # 可选自定义权重
    w_cf = request.args.get('w_cf', type=float)
    w_graph = request.args.get('w_graph', type=float)
    w_semantic = request.args.get('w_semantic', type=float)
    weights = None
    if all(w is not None for w in [w_cf, w_graph, w_semantic]):
        weights = {'cf': w_cf, 'graph': w_graph, 'semantic': w_semantic}

    try:
        results, debug_info = recommendation_engine.recommend_with_debug(
            user_id,
            top_n=top_n,
            enable_llm=enable_llm,
            enable_hot=enable_hot,
            weights=weights,
        )

        # 附带帖子详情
        for item in results:
            post = db.session.get(Post, item['post_id'])
            if post:
                item['title'] = post.title
                item['summary'] = post.summary
                item['author_id'] = post.author_id

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

    w_cf = request.args.get('w_cf', type=float)
    w_graph = request.args.get('w_graph', type=float)
    w_semantic = request.args.get('w_semantic', type=float)
    weights = None
    if all(w is not None for w in [w_cf, w_graph, w_semantic]):
        weights = {'cf': w_cf, 'graph': w_graph, 'semantic': w_semantic}

    try:
        results, debug_info = recommendation_engine.recommend_with_debug(
            user_id,
            top_n=top_n,
            enable_llm=enable_llm,
            enable_hot=enable_hot,
            weights=weights,
        )
        for item in results:
            post = db.session.get(Post, item['post_id'])
            if post:
                item['title'] = post.title
                item['summary'] = post.summary
                item['author_id'] = post.author_id

        payload = {"user_id": user_id, "recommendations": results}
        if debug:
            payload["debug"] = debug_info
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@rec_bp.route('/recommend/<int:user_id>/reason/<int:post_id>', methods=['GET'])
def get_recommendation_reason(user_id, post_id):
    """LLM 生成推荐理由"""
    from app.models.user import User

    user = db.session.get(User, user_id)
    post = db.session.get(Post, post_id)
    if not user or not post:
        return jsonify({"error": "用户或帖子不存在"}), 404

    prompt = (
        f"你是推荐系统的解释模块。\n"
        f"用户兴趣：{user.interest_profile or user.bio or '未知'}\n"
        f"推荐文章：{post.title}\n"
        f"文章摘要：{post.summary or '无'}\n"
        f"请用一句简洁的中文说明为什么向该用户推荐这篇文章。"
    )

    try:
        reason = qwen_service.chat(prompt)
        return jsonify({"reason": reason})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@rec_bp.route('/precompute', methods=['POST'])
def precompute():
    """触发离线预计算"""
    try:
        recommendation_engine.precompute()
        return jsonify({"status": "预计算完成"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
