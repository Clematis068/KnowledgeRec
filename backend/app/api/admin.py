"""管理后台 API"""
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from app import db
from app.models.user import User
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.utils.auth import admin_required

admin_bp = Blueprint('admin', __name__)


# ─── 数据概览 ────────────────────────────────────────────

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def overview_stats():
    """数据概览：总量 + 今日新增"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.session.scalar(func.count(User.id)) or 0
    total_posts = db.session.scalar(func.count(Post.id)) or 0
    total_behaviors = db.session.scalar(func.count(UserBehavior.id)) or 0

    new_users_today = db.session.scalar(
        db.select(func.count(User.id)).filter(User.created_at >= today)
    ) or 0
    new_posts_today = db.session.scalar(
        db.select(func.count(Post.id)).filter(Post.created_at >= today)
    ) or 0
    new_behaviors_today = db.session.scalar(
        db.select(func.count(UserBehavior.id)).filter(UserBehavior.created_at >= today)
    ) or 0

    banned_users = db.session.scalar(
        db.select(func.count(User.id)).filter(User.status == 'banned')
    ) or 0
    pending_posts = db.session.scalar(
        db.select(func.count(Post.id)).filter(Post.status == 'pending')
    ) or 0

    # 近 7 日每日新增用户/帖子
    trend = []
    for i in range(6, -1, -1):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_users = db.session.scalar(
            db.select(func.count(User.id)).filter(
                User.created_at >= day_start, User.created_at < day_end
            )
        ) or 0
        day_posts = db.session.scalar(
            db.select(func.count(Post.id)).filter(
                Post.created_at >= day_start, Post.created_at < day_end
            )
        ) or 0
        trend.append({
            'date': day_start.strftime('%m-%d'),
            'users': day_users,
            'posts': day_posts,
        })

    return jsonify({
        'total_users': total_users,
        'total_posts': total_posts,
        'total_behaviors': total_behaviors,
        'new_users_today': new_users_today,
        'new_posts_today': new_posts_today,
        'new_behaviors_today': new_behaviors_today,
        'banned_users': banned_users,
        'pending_posts': pending_posts,
        'trend': trend,
    })


# ─── 用户管理 ────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """分页用户列表，支持关键字搜索和状态筛选"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()

    stmt = db.select(User)
    if keyword:
        stmt = stmt.filter(User.username.contains(keyword) | User.email.contains(keyword))
    if status:
        stmt = stmt.filter(User.status == status)
    stmt = stmt.order_by(User.created_at.desc())

    pagination = db.paginate(stmt, page=page, per_page=per_page)
    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
    })


@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    """封禁用户"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    if user.role == 'admin':
        return jsonify({'error': '不能封禁管理员'}), 403
    user.status = 'banned'
    db.session.commit()
    return jsonify({'message': f'用户 {user.username} 已封禁'})


@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    """解封用户"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    user.status = 'active'
    db.session.commit()
    return jsonify({'message': f'用户 {user.username} 已解封'})


# ─── 内容审核 ────────────────────────────────────────────

@admin_bp.route('/posts', methods=['GET'])
@admin_required
def list_posts():
    """分页帖子列表，支持状态筛选和关键字搜索"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()

    stmt = db.select(Post)
    if keyword:
        stmt = stmt.filter(Post.title.contains(keyword))
    if status:
        stmt = stmt.filter(Post.status == status)
    stmt = stmt.order_by(Post.created_at.desc())

    pagination = db.paginate(stmt, page=page, per_page=per_page)
    return jsonify({
        'posts': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'page': page,
    })


@admin_bp.route('/posts/<int:post_id>/approve', methods=['POST'])
@admin_required
def approve_post(post_id):
    """通过审核"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    post.status = 'published'
    post.reject_reason = None
    db.session.commit()
    return jsonify({'message': '帖子已通过审核'})


@admin_bp.route('/posts/<int:post_id>/reject', methods=['POST'])
@admin_required
def reject_post(post_id):
    """拒绝/下架帖子，并通知作者"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    data = request.get_json() or {}
    reason = data.get('reason', '内容不符合社区规范')
    post.status = 'rejected'
    post.reject_reason = reason

    from app.models.notification import create_notification
    create_notification(
        user_id=post.author_id,
        sender_id=g.current_user.id,
        notification_type='system',
        post_id=post.id,
        content=f"您的帖子《{post.title}》未通过管理员审核：{reason}",
    )

    db.session.commit()
    return jsonify({'message': '帖子已下架'})


@admin_bp.route('/posts/<int:post_id>/remove', methods=['POST'])
@admin_required
def remove_post(post_id):
    """彻底删除帖子"""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    db.session.execute(db.delete(UserBehavior).filter_by(post_id=post_id))
    post.tags = []
    db.session.delete(post)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (p:Post {id: $pid}) DETACH DELETE p", {'pid': post_id}
        )
    except Exception:
        pass

    return jsonify({'message': '帖子已删除'})
