from flask import Blueprint, request, jsonify, g
from app import db
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.utils.auth import login_required, optional_login

post_bp = Blueprint('post', __name__)


@post_bp.route('/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """获取帖子详情"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    return jsonify(post.to_dict())


@post_bp.route('/list', methods=['GET'])
def list_posts():
    """帖子列表(分页)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    domain_id = request.args.get('domain_id', type=int)

    query = Post.query
    if domain_id:
        query = query.filter_by(domain_id=domain_id)
    query = query.order_by(Post.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page)
    return jsonify({
        "posts": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": page,
    })


@post_bp.route('/hot', methods=['GET'])
def hot_posts():
    """热门帖子(按点赞数)"""
    limit = request.args.get('limit', 20, type=int)
    posts = Post.query.order_by(Post.like_count.desc()).limit(limit).all()
    return jsonify({"posts": [p.to_dict() for p in posts]})


@post_bp.route('/<int:post_id>/behavior', methods=['POST'])
@login_required
def record_behavior(post_id):
    """记录用户行为（browse/like/favorite/comment），同步 Neo4j"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    data = request.get_json() or {}
    behavior_type = data.get('behavior_type')
    if behavior_type not in ('browse', 'like', 'favorite', 'comment'):
        return jsonify({"error": "行为类型不合法"}), 400

    user_id = g.current_user.id

    # 点赞/收藏去重
    if behavior_type in ('like', 'favorite'):
        exists = UserBehavior.query.filter_by(
            user_id=user_id, post_id=post_id, behavior_type=behavior_type
        ).first()
        if exists:
            return jsonify({"message": "已经操作过了"}), 200

    behavior = UserBehavior(
        user_id=user_id,
        post_id=post_id,
        behavior_type=behavior_type,
        comment_text=data.get('comment_text') if behavior_type == 'comment' else None,
        duration=data.get('duration') if behavior_type == 'browse' else None,
    )
    db.session.add(behavior)

    # 更新帖子计数
    if behavior_type == 'like':
        post.like_count = (post.like_count or 0) + 1
    elif behavior_type == 'browse':
        post.view_count = (post.view_count or 0) + 1

    db.session.commit()

    # 同步到 Neo4j（非阻塞，失败不影响主流程）
    try:
        from app.services.neo4j_service import neo4j_service
        relation_map = {
            'browse': 'BROWSED',
            'like': 'LIKED',
            'favorite': 'FAVORITED',
            'comment': 'COMMENTED',
        }
        cypher = (
            f"MERGE (u:User {{id: $user_id}}) "
            f"MERGE (p:Post {{id: $post_id}}) "
            f"MERGE (u)-[:{relation_map[behavior_type]}]->(p)"
        )
        neo4j_service.run_write(cypher, {'user_id': user_id, 'post_id': post_id})
    except Exception:
        pass  # Neo4j 可能未启动

    return jsonify({"message": "行为记录成功", "behavior": behavior.to_dict()}), 201


@post_bp.route('/<int:post_id>/like', methods=['DELETE'])
@login_required
def unlike_post(post_id):
    """取消点赞"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    user_id = g.current_user.id
    behavior = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='like'
    ).first()

    if not behavior:
        return jsonify({"error": "未点赞过"}), 404

    db.session.delete(behavior)
    post.like_count = max((post.like_count or 0) - 1, 0)
    db.session.commit()

    # 同步 Neo4j
    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $user_id})-[r:LIKED]->(p:Post {id: $post_id}) DELETE r",
            {'user_id': user_id, 'post_id': post_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消点赞"})


@post_bp.route('/<int:post_id>/user_status', methods=['GET'])
@optional_login
def get_post_user_status(post_id):
    """当前用户对帖子的交互状态"""
    if not g.current_user:
        return jsonify({"liked": False, "favorited": False})

    user_id = g.current_user.id
    liked = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='like'
    ).first() is not None
    favorited = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='favorite'
    ).first() is not None

    return jsonify({"liked": liked, "favorited": favorited})
