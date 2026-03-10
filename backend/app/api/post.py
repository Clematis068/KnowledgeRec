from flask import Blueprint, request, jsonify, g
from app import db
from app.models.post import Post
from app.models.behavior import (
    UserBehavior,
    UserFollow,
    UserBlockedAuthor,
    UserBlockedDomain,
)
from app.models.tag import Tag
from app.services.tag_taxonomy_service import tag_taxonomy_service
from app.services.user_interest_service import user_interest_service
from app.utils.auth import login_required, optional_login
from app.utils.content_filter import apply_post_visibility_query, is_post_visible_to_user

post_bp = Blueprint('post', __name__)


def _sync_post_to_neo4j(post):
    try:
        from app.services.neo4j_service import neo4j_service
        tag_ids_for_graph = [tag.id for tag in post.tags]
        for tag in post.tags:
            tag_taxonomy_service.sync_tag_to_neo4j(tag)
        neo4j_service.run_write(
            "MERGE (p:Post {id: $pid}) "
            "SET p.title = $title, p.domain_id = $did "
            "WITH p "
            "MERGE (u:User {id: $uid}) "
            "MERGE (u)-[:AUTHORED]->(p)",
            {'pid': post.id, 'title': post.title, 'did': post.domain_id, 'uid': post.author_id}
        )
        neo4j_service.run_write(
            "MATCH (p:Post {id: $pid})-[r:TAGGED_WITH]->(:Tag) DELETE r",
            {'pid': post.id}
        )
        if tag_ids_for_graph:
            neo4j_service.run_write(
                "MATCH (p:Post {id: $pid}) "
                "UNWIND $tids AS tid "
                "MATCH (t:Tag {id: tid}) "
                "MERGE (p)-[:TAGGED_WITH]->(t)",
                {'pid': post.id, 'tids': tag_ids_for_graph}
            )
    except Exception:
        pass


def _refresh_post_summary_and_embedding(post):
    try:
        from app.services.qwen_service import qwen_service
        summary = qwen_service.chat(
            post.content[:2000],
            system_prompt="请用一句话总结以下内容，不超过100字："
        )
        post.summary = summary[:500]
    except Exception:
        post.summary = post.content[:200]

    try:
        from app.services.qwen_service import qwen_service
        post.content_embedding = qwen_service.get_embedding(post.title + " " + post.content[:500])
    except Exception:
        pass


def _bind_post_tags(post, domain_id, tag_ids=None, tag_names=None, source_user_id=None):
    tag_ids = tag_ids or []
    tag_names = tag_names or []

    if tag_names:
        tags, resolutions = tag_taxonomy_service.resolve_tag_names(
            tag_names,
            domain_id,
            source_user_id=source_user_id,
            source_post_id=post.id,
        )
        post.tags = tags
        return resolutions
    elif tag_ids:
        post.tags = (
            Tag.query
            .filter(Tag.domain_id == domain_id, Tag.id.in_(tag_ids))
            .all()
        )
    else:
        post.tags = []
    return []


def _delete_post_from_neo4j(post_id):
    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (p:Post {id: $post_id}) DETACH DELETE p",
            {'post_id': post_id}
        )
    except Exception:
        pass


def _delete_comment_relation_if_needed(user_id, post_id):
    remaining = UserBehavior.query.filter_by(
        user_id=user_id,
        post_id=post_id,
        behavior_type='comment',
    ).count()
    if remaining > 0:
        return

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $user_id})-[r:COMMENTED]->(p:Post {id: $post_id}) DELETE r",
            {'user_id': user_id, 'post_id': post_id}
        )
    except Exception:
        pass


def _refresh_user_interest_if_needed(user_id, behavior_type=None, duration=None):
    """行为变更后刷新用户兴趣画像；浏览仅在停留较久时触发。"""
    should_refresh = behavior_type in ('like', 'favorite', 'comment', 'dislike')
    if behavior_type == 'browse' and (duration or 0) >= 30:
        should_refresh = True
    if behavior_type in ('unlike', 'unfavorite', 'undislike', 'delete_comment'):
        should_refresh = True

    if not should_refresh:
        return

    try:
        user_interest_service.refresh_user_interest_state(user_id)
    except Exception:
        pass


@post_bp.route('/create', methods=['POST'])
@login_required
def create_post():
    """创建帖子"""
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    domain_id = data.get('domain_id')
    tag_ids = data.get('tag_ids', [])
    tag_names = data.get('tags', [])

    if not title or not content or not domain_id:
        return jsonify({"error": "标题、正文和领域不能为空"}), 400

    post = Post(
        title=title,
        content=content,
        author_id=g.current_user.id,
        domain_id=domain_id,
    )

    db.session.add(post)
    db.session.flush()
    _bind_post_tags(
        post,
        domain_id,
        tag_ids=tag_ids,
        tag_names=tag_names,
        source_user_id=g.current_user.id,
    )
    _refresh_post_summary_and_embedding(post)
    db.session.commit()
    _sync_post_to_neo4j(post)

    return jsonify(post.to_dict()), 201


@post_bp.route('/<int:post_id>', methods=['GET'])
@optional_login
def get_post(post_id):
    """获取帖子详情"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    if g.current_user and not is_post_visible_to_user(post, g.current_user.id):
        return jsonify({"error": "帖子不存在"}), 404
    return jsonify(post.to_dict())


@post_bp.route('/<int:post_id>', methods=['PUT'])
@login_required
def update_post(post_id):
    """编辑帖子，仅作者本人可操作"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    if post.author_id != g.current_user.id:
        return jsonify({"error": "无权编辑该帖子"}), 403

    data = request.get_json() or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    domain_id = data.get('domain_id')
    tag_ids = data.get('tag_ids', [])
    tag_names = data.get('tags', [])

    if not title or not content or not domain_id:
        return jsonify({"error": "标题、正文和领域不能为空"}), 400

    post.title = title
    post.content = content
    post.domain_id = domain_id
    _bind_post_tags(
        post,
        domain_id,
        tag_ids=tag_ids,
        tag_names=tag_names,
        source_user_id=g.current_user.id,
    )
    _refresh_post_summary_and_embedding(post)

    db.session.commit()
    _sync_post_to_neo4j(post)
    return jsonify(post.to_dict())


@post_bp.route('/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    """删除帖子，仅作者本人可操作"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    if post.author_id != g.current_user.id:
        return jsonify({"error": "无权删除该帖子"}), 403

    UserBehavior.query.filter_by(post_id=post_id).delete()
    post.tags = []
    db.session.delete(post)
    db.session.commit()
    _delete_post_from_neo4j(post_id)

    return jsonify({"message": "帖子已删除"})


@post_bp.route('/list', methods=['GET'])
@optional_login
def list_posts():
    """帖子列表(分页)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    domain_id = request.args.get('domain_id', type=int)

    query = Post.query
    if domain_id:
        query = query.filter_by(domain_id=domain_id)
    query = apply_post_visibility_query(query, g.current_user.id if g.current_user else None)
    query = query.order_by(Post.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page)
    return jsonify({
        "posts": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": page,
    })


@post_bp.route('/hot', methods=['GET'])
@optional_login
def hot_posts():
    """热门帖子(按点赞数)"""
    limit = request.args.get('limit', 20, type=int)
    query = apply_post_visibility_query(Post.query, g.current_user.id if g.current_user else None)
    posts = query.order_by(Post.like_count.desc()).limit(limit).all()
    return jsonify({"posts": [p.to_dict() for p in posts]})


@post_bp.route('/following', methods=['GET'])
@login_required
def following_posts():
    """关注流：按发布时间返回已关注用户的帖子"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    followed_subquery = (
        db.session.query(UserFollow.followed_id)
        .filter_by(follower_id=g.current_user.id)
        .subquery()
    )

    query = (
        apply_post_visibility_query(Post.query, g.current_user.id)
        .filter(Post.author_id.in_(followed_subquery))
        .order_by(Post.created_at.desc())
    )
    pagination = query.paginate(page=page, per_page=per_page)

    return jsonify({
        "posts": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": page,
    })


@post_bp.route('/<int:post_id>/behavior', methods=['POST'])
@login_required
def record_behavior(post_id):
    """记录用户行为（browse/like/favorite/comment/dislike），同步 Neo4j"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    data = request.get_json() or {}
    behavior_type = data.get('behavior_type')
    if behavior_type not in ('browse', 'like', 'favorite', 'comment', 'dislike'):
        return jsonify({"error": "行为类型不合法"}), 400

    user_id = g.current_user.id

    # 点赞/收藏/不感兴趣去重
    if behavior_type in ('like', 'favorite', 'dislike'):
        exists = UserBehavior.query.filter_by(
            user_id=user_id, post_id=post_id, behavior_type=behavior_type
        ).first()
        if exists:
            return jsonify({"message": "已经操作过了"}), 200

    if behavior_type in ('like', 'favorite'):
        dislike_behavior = UserBehavior.query.filter_by(
            user_id=user_id, post_id=post_id, behavior_type='dislike'
        ).first()
        if dislike_behavior:
            db.session.delete(dislike_behavior)
    elif behavior_type == 'dislike':
        positive_behaviors = UserBehavior.query.filter(
            UserBehavior.user_id == user_id,
            UserBehavior.post_id == post_id,
            UserBehavior.behavior_type.in_(['like', 'favorite'])
        ).all()
        for behavior in positive_behaviors:
            if behavior.behavior_type == 'like':
                post.like_count = max((post.like_count or 0) - 1, 0)
            db.session.delete(behavior)

    behavior = UserBehavior(
        user_id=user_id,
        post_id=post_id,
        behavior_type=behavior_type,
        comment_text=data.get('comment_text') if behavior_type == 'comment' else None,
        parent_id=data.get('parent_id') if behavior_type == 'comment' else None,
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
            'dislike': 'DISLIKED',
        }

        if behavior_type in ('like', 'favorite'):
            neo4j_service.run_write(
                "MATCH (u:User {id: $user_id})-[r:DISLIKED]->(p:Post {id: $post_id}) DELETE r",
                {'user_id': user_id, 'post_id': post_id}
            )
        elif behavior_type == 'dislike':
            neo4j_service.run_write(
                "MATCH (u:User {id: $user_id})-[r:LIKED|FAVORITED]->(p:Post {id: $post_id}) DELETE r",
                {'user_id': user_id, 'post_id': post_id}
            )

        cypher = (
            f"MERGE (u:User {{id: $user_id}}) "
            f"MERGE (p:Post {{id: $post_id}}) "
            f"MERGE (u)-[:{relation_map[behavior_type]}]->(p)"
        )
        neo4j_service.run_write(cypher, {'user_id': user_id, 'post_id': post_id})
    except Exception:
        pass  # Neo4j 可能未启动

    _refresh_user_interest_if_needed(
        user_id,
        behavior_type=behavior_type,
        duration=data.get('duration') if behavior_type == 'browse' else None,
    )

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

    _refresh_user_interest_if_needed(user_id, behavior_type='unlike')

    return jsonify({"message": "已取消点赞"})


@post_bp.route('/<int:post_id>/user_status', methods=['GET'])
@optional_login
def get_post_user_status(post_id):
    """当前用户对帖子的交互状态"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    if not g.current_user:
        return jsonify({
            "liked": False,
            "favorited": False,
            "disliked": False,
            "blocked_author": False,
            "blocked_domain": False,
            "is_owner": False,
        })

    user_id = g.current_user.id
    liked = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='like'
    ).first() is not None
    favorited = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='favorite'
    ).first() is not None
    disliked = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='dislike'
    ).first() is not None
    blocked_author = UserBlockedAuthor.query.filter_by(
        user_id=user_id,
        author_id=post.author_id,
    ).first() is not None
    blocked_domain = UserBlockedDomain.query.filter_by(
        user_id=user_id,
        domain_id=post.domain_id,
    ).first() is not None

    return jsonify({
        "liked": liked,
        "favorited": favorited,
        "disliked": disliked,
        "blocked_author": blocked_author,
        "blocked_domain": blocked_domain,
        "is_owner": post.author_id == user_id,
    })


@post_bp.route('/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    """获取帖子评论列表"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = UserBehavior.query.filter_by(
        post_id=post_id, behavior_type='comment'
    ).order_by(UserBehavior.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page)
    return jsonify({
        "comments": [b.to_comment_dict() for b in pagination.items],
        "total": pagination.total,
    })


@post_bp.route('/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(post_id, comment_id):
    """删除自己的评论；若已有回复则保留楼层并标记为已删除。"""
    comment = UserBehavior.query.filter_by(
        id=comment_id,
        post_id=post_id,
        behavior_type='comment',
    ).first()
    if not comment:
        return jsonify({"error": "评论不存在"}), 404
    if comment.user_id != g.current_user.id:
        return jsonify({"error": "无权删除该评论"}), 403

    if comment.replies:
        comment.comment_text = '[该评论已删除]'
        db.session.commit()
        _delete_comment_relation_if_needed(comment.user_id, post_id)
        _refresh_user_interest_if_needed(comment.user_id, behavior_type='delete_comment')
        return jsonify({"message": "评论已删除"}), 200

    db.session.delete(comment)
    db.session.commit()
    _delete_comment_relation_if_needed(comment.user_id, post_id)
    _refresh_user_interest_if_needed(comment.user_id, behavior_type='delete_comment')
    return jsonify({"message": "评论已删除"}), 200


@post_bp.route('/<int:post_id>/favorite', methods=['DELETE'])
@login_required
def unfavorite_post(post_id):
    """取消收藏"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    user_id = g.current_user.id
    behavior = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='favorite'
    ).first()

    if not behavior:
        return jsonify({"error": "未收藏过"}), 404

    db.session.delete(behavior)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $user_id})-[r:FAVORITED]->(p:Post {id: $post_id}) DELETE r",
            {'user_id': user_id, 'post_id': post_id}
        )
    except Exception:
        pass

    _refresh_user_interest_if_needed(user_id, behavior_type='unfavorite')

    return jsonify({"message": "已取消收藏"})


@post_bp.route('/<int:post_id>/dislike', methods=['DELETE'])
@login_required
def undislike_post(post_id):
    """取消不感兴趣"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    user_id = g.current_user.id
    behavior = UserBehavior.query.filter_by(
        user_id=user_id, post_id=post_id, behavior_type='dislike'
    ).first()

    if not behavior:
        return jsonify({"error": "未标记不感兴趣"}), 404

    db.session.delete(behavior)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $user_id})-[r:DISLIKED]->(p:Post {id: $post_id}) DELETE r",
            {'user_id': user_id, 'post_id': post_id}
        )
    except Exception:
        pass

    _refresh_user_interest_if_needed(user_id, behavior_type='undislike')

    return jsonify({"message": "已取消不感兴趣"})


@post_bp.route('/<int:post_id>/block-author', methods=['POST'])
@login_required
def block_post_author(post_id):
    """屏蔽当前帖子的作者"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404
    if post.author_id == g.current_user.id:
        return jsonify({"error": "不能屏蔽自己"}), 400

    exists = UserBlockedAuthor.query.filter_by(
        user_id=g.current_user.id,
        author_id=post.author_id,
    ).first()
    if exists:
        return jsonify({"message": "已屏蔽该作者"}), 200

    db.session.add(UserBlockedAuthor(user_id=g.current_user.id, author_id=post.author_id))
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MERGE (u:User {id: $uid}) "
            "MERGE (a:User {id: $aid}) "
            "MERGE (u)-[:BLOCKED_AUTHOR]->(a)",
            {'uid': g.current_user.id, 'aid': post.author_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已屏蔽该作者"}), 201


@post_bp.route('/<int:post_id>/block-author', methods=['DELETE'])
@login_required
def unblock_post_author(post_id):
    """取消屏蔽当前帖子的作者"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    blocked = UserBlockedAuthor.query.filter_by(
        user_id=g.current_user.id,
        author_id=post.author_id,
    ).first()
    if not blocked:
        return jsonify({"error": "未屏蔽该作者"}), 404

    db.session.delete(blocked)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $uid})-[r:BLOCKED_AUTHOR]->(a:User {id: $aid}) DELETE r",
            {'uid': g.current_user.id, 'aid': post.author_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消屏蔽作者"})


@post_bp.route('/<int:post_id>/block-domain', methods=['POST'])
@login_required
def block_post_domain(post_id):
    """屏蔽当前帖子的领域"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    exists = UserBlockedDomain.query.filter_by(
        user_id=g.current_user.id,
        domain_id=post.domain_id,
    ).first()
    if exists:
        return jsonify({"message": "已屏蔽该领域"}), 200

    db.session.add(UserBlockedDomain(user_id=g.current_user.id, domain_id=post.domain_id))
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MERGE (u:User {id: $uid}) "
            "MERGE (d:Domain {id: $did}) "
            "MERGE (u)-[:BLOCKED_DOMAIN]->(d)",
            {'uid': g.current_user.id, 'did': post.domain_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已屏蔽该领域"}), 201


@post_bp.route('/<int:post_id>/block-domain', methods=['DELETE'])
@login_required
def unblock_post_domain(post_id):
    """取消屏蔽当前帖子的领域"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "帖子不存在"}), 404

    blocked = UserBlockedDomain.query.filter_by(
        user_id=g.current_user.id,
        domain_id=post.domain_id,
    ).first()
    if not blocked:
        return jsonify({"error": "未屏蔽该领域"}), 404

    db.session.delete(blocked)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $uid})-[r:BLOCKED_DOMAIN]->(d:Domain {id: $did}) DELETE r",
            {'uid': g.current_user.id, 'did': post.domain_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消屏蔽领域"})
