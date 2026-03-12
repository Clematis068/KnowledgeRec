import random
import re

from sqlalchemy.exc import IntegrityError
from flask import Blueprint, request, jsonify, g
from app import db
from app.models.user import User
from app.models.post import Post
from app.models.tag import Tag
from app.models.domain import Domain
from app.models.behavior import (
    UserBehavior,
    UserFollow,
    UserBlockedAuthor,
    UserBlockedDomain,
)
from app.services.tag_taxonomy_service import tag_taxonomy_service
from app.services.redis_service import redis_service
from app.services.mail_service import mail_service
from app.utils.auth import login_required, optional_login
from app.utils.content_filter import apply_post_visibility_query, filter_posts

user_bp = Blueprint('user', __name__)

EMAIL_CODE_TTL = 600
EMAIL_VERIFIED_TTL = 1800
EMAIL_SEND_COOLDOWN = 60
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email or ''))


def _generate_email_code():
    return ''.join(str(random.randint(0, 9)) for _ in range(6))


def _profile_email_code_key(user_id, email):
    return f'email_code:profile_update:{user_id}:{email.lower()}'


def _profile_email_verified_key(user_id, email):
    return f'email_verified:profile_update:{user_id}:{email.lower()}'


def _profile_email_cooldown_key(user_id, email):
    return f'email_code_cooldown:profile_update:{user_id}:{email.lower()}'


@user_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """获取用户信息"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify(user.to_dict())


@user_bp.route('/list', methods=['GET'])
def list_users():
    """用户列表(分页)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    stmt = db.select(User)
    pagination = db.paginate(stmt, page=page, per_page=per_page)
    return jsonify({
        "users": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "page": page,
    })


@user_bp.route('/<int:user_id>/behaviors', methods=['GET'])
def get_user_behaviors(user_id):
    """获取用户行为历史"""
    limit = request.args.get('limit', 50, type=int)
    stmt = (db.select(UserBehavior)
            .filter_by(user_id=user_id)
            .order_by(UserBehavior.created_at.desc())
            .limit(limit))
    behaviors = db.session.scalars(stmt).all()
    return jsonify({"behaviors": [b.to_dict() for b in behaviors]})


@user_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """更新个人资料 + 兴趣标签"""
    data = request.get_json() or {}
    user = g.current_user

    if 'bio' in data:
        user.bio = data['bio']
    if 'gender' in data and data['gender'] in ('male', 'female', 'other'):
        user.gender = data['gender']
    updated_email = None
    if 'email' in data:
        incoming_email = (data.get('email') or '').strip().lower()
        if not incoming_email:
            return jsonify({"error": "邮箱不能为空"}), 400
        if not _is_valid_email(incoming_email):
            return jsonify({"error": "邮箱格式不正确"}), 400

        if incoming_email != (user.email or '').strip().lower():
            exists_user = db.session.scalar(db.select(User).filter(
                User.email == incoming_email,
                User.id != user.id,
            ))
            if exists_user:
                return jsonify({"error": "邮箱已被占用"}), 409

            if redis_service.get_value(_profile_email_verified_key(user.id, incoming_email)) != '1':
                return jsonify({"error": "请先完成新邮箱验证码校验"}), 400
            user.email = incoming_email
            updated_email = incoming_email
    if 'tag_ids' in data:
        stmt = db.select(Tag).filter(Tag.id.in_(data['tag_ids']))
        tags = db.session.scalars(stmt).all()
        user.interest_tags = tags
        user.interest_embedding = None
        user.interest_profile = (
            f'注册兴趣：{"、".join(tag.name for tag in tags[:6])}。'
            if tags else None
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "邮箱已被占用"}), 409

    if 'tag_ids' in data:
        tag_taxonomy_service.sync_user_interest_tags(user)
        redis_service.delete_pattern(f'llm_rel:{user.id}:*')
    if updated_email:
        redis_service.delete(_profile_email_verified_key(user.id, updated_email))
        redis_service.delete(_profile_email_code_key(user.id, updated_email))
        redis_service.delete(_profile_email_cooldown_key(user.id, updated_email))
    return jsonify(user.to_dict())


@user_bp.route('/profile/email/send-code', methods=['POST'])
@login_required
def send_profile_email_code():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    user = g.current_user

    if not email:
        return jsonify({"error": "邮箱不能为空"}), 400
    if not _is_valid_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if email == (user.email or '').strip().lower():
        return jsonify({"error": "新邮箱不能与当前邮箱相同"}), 400

    exists_user = db.session.scalar(db.select(User).filter(
        User.email == email,
        User.id != user.id,
    ))
    if exists_user:
        return jsonify({"error": "邮箱已被占用"}), 409

    cooldown_key = _profile_email_cooldown_key(user.id, email)
    if redis_service.get_value(cooldown_key):
        return jsonify({"error": "验证码发送过于频繁，请稍后再试"}), 429

    code = _generate_email_code()
    redis_service.set_value(_profile_email_code_key(user.id, email), code, ttl=EMAIL_CODE_TTL)
    redis_service.set_value(cooldown_key, '1', ttl=EMAIL_SEND_COOLDOWN)
    redis_service.delete(_profile_email_verified_key(user.id, email))

    send_result = mail_service.send_verification_code(email, code)
    payload = {'message': '验证码已发送'}
    if send_result.get('mode') == 'dev':
        payload['dev_code'] = code
    return jsonify(payload)


@user_bp.route('/profile/email/verify-code', methods=['POST'])
@login_required
def verify_profile_email_code():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    user = g.current_user

    if not email or not code:
        return jsonify({"error": "邮箱和验证码不能为空"}), 400
    if not _is_valid_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if email == (user.email or '').strip().lower():
        return jsonify({"error": "新邮箱不能与当前邮箱相同"}), 400

    exists_user = db.session.scalar(db.select(User).filter(
        User.email == email,
        User.id != user.id,
    ))
    if exists_user:
        return jsonify({"error": "邮箱已被占用"}), 409

    cached_code = redis_service.get_value(_profile_email_code_key(user.id, email))
    if not cached_code:
        return jsonify({"error": "验证码已过期，请重新发送"}), 400
    if cached_code != code:
        return jsonify({"error": "验证码错误"}), 400

    redis_service.set_value(_profile_email_verified_key(user.id, email), '1', ttl=EMAIL_VERIFIED_TTL)
    redis_service.delete(_profile_email_code_key(user.id, email))
    return jsonify({'message': '邮箱验证通过', 'verified': True})


@user_bp.route('/follow/<int:target_id>', methods=['POST'])
@login_required
def follow_user(target_id):
    """关注用户（写 MySQL + Neo4j）"""
    if g.current_user.id == target_id:
        return jsonify({"error": "不能关注自己"}), 400

    target = db.session.get(User, target_id)
    if not target:
        return jsonify({"error": "用户不存在"}), 404

    exists = db.session.scalar(db.select(UserFollow).filter_by(
        follower_id=g.current_user.id, followed_id=target_id
    ))
    if exists:
        return jsonify({"message": "已关注"}), 200

    follow = UserFollow(follower_id=g.current_user.id, followed_id=target_id)
    db.session.add(follow)
    db.session.commit()

    # 同步 Neo4j
    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MERGE (a:User {id: $fid}) MERGE (b:User {id: $tid}) "
            "MERGE (a)-[:FOLLOWS]->(b)",
            {'fid': g.current_user.id, 'tid': target_id}
        )
    except Exception:
        pass

    return jsonify({"message": "关注成功"}), 201


@user_bp.route('/follow/<int:target_id>', methods=['DELETE'])
@login_required
def unfollow_user(target_id):
    """取消关注"""
    follow = db.session.scalar(db.select(UserFollow).filter_by(
        follower_id=g.current_user.id, followed_id=target_id
    ))
    if not follow:
        return jsonify({"error": "未关注"}), 404

    db.session.delete(follow)
    db.session.commit()

    # 同步 Neo4j
    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (a:User {id: $fid})-[r:FOLLOWS]->(b:User {id: $tid}) DELETE r",
            {'fid': g.current_user.id, 'tid': target_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消关注"})


@user_bp.route('/<int:user_id>/followers', methods=['GET'])
def get_followers(user_id):
    """粉丝列表"""
    follows = db.session.scalars(db.select(UserFollow).filter_by(followed_id=user_id)).all()
    user_ids = [f.follower_id for f in follows]
    users = db.session.scalars(db.select(User).filter(User.id.in_(user_ids))).all() if user_ids else []
    return jsonify({
        "followers": [u.to_dict() for u in users],
        "count": len(users),
    })


@user_bp.route('/<int:user_id>/following', methods=['GET'])
def get_following(user_id):
    """关注列表"""
    follows = db.session.scalars(db.select(UserFollow).filter_by(follower_id=user_id)).all()
    user_ids = [f.followed_id for f in follows]
    users = db.session.scalars(db.select(User).filter(User.id.in_(user_ids))).all() if user_ids else []
    return jsonify({
        "following": [u.to_dict() for u in users],
        "count": len(users),
    })


@user_bp.route('/<int:user_id>/posts', methods=['GET'])
@optional_login
def get_user_posts(user_id):
    """获取用户发布的帖子"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    stmt = db.select(Post).filter_by(author_id=user_id).order_by(Post.created_at.desc())
    if not g.current_user or g.current_user.id != user_id:
        stmt = apply_post_visibility_query(stmt, g.current_user.id if g.current_user else None)
    pagination = db.paginate(stmt, page=page, per_page=per_page)
    return jsonify({
        "posts": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
    })


@user_bp.route('/<int:user_id>/favorites', methods=['GET'])
@optional_login
def get_user_favorites(user_id):
    """获取用户收藏的帖子"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    stmt = (db.select(UserBehavior)
        .filter_by(user_id=user_id, behavior_type='favorite')
        .order_by(UserBehavior.created_at.desc()))
    fav_behaviors = db.paginate(stmt, page=page, per_page=per_page)

    post_ids = [b.post_id for b in fav_behaviors.items]
    posts = db.session.scalars(db.select(Post).filter(Post.id.in_(post_ids))).all() if post_ids else []
    posts = filter_posts(posts, g.current_user.id if g.current_user else None)
    post_map = {p.id: p for p in posts}
    ordered = [post_map[pid] for pid in post_ids if pid in post_map]

    return jsonify({
        "posts": [p.to_dict() for p in ordered],
        "total": fav_behaviors.total,
    })


@user_bp.route('/<int:user_id>/follow_status', methods=['GET'])
@optional_login
def get_follow_status(user_id):
    """当前用户是否关注了目标用户"""
    if not g.current_user:
        return jsonify({"is_following": False})
    exists = db.session.scalar(db.select(UserFollow).filter_by(
        follower_id=g.current_user.id, followed_id=user_id
    ))
    return jsonify({"is_following": exists is not None})


@user_bp.route('/blocked/authors', methods=['GET'])
@login_required
def get_blocked_authors():
    """获取当前用户已屏蔽的作者列表"""
    stmt = (db.select(UserBlockedAuthor)
            .filter_by(user_id=g.current_user.id)
            .order_by(UserBlockedAuthor.created_at.desc()))
    blocked_rows = db.session.scalars(stmt).all()
    author_ids = [row.author_id for row in blocked_rows]
    authors = db.session.scalars(db.select(User).filter(User.id.in_(author_ids))).all() if author_ids else []
    author_map = {author.id: author for author in authors}

    return jsonify({
        "authors": [author_map[author_id].to_dict() for author_id in author_ids if author_id in author_map],
        "total": len(author_ids),
    })


@user_bp.route('/blocked/domains', methods=['GET'])
@login_required
def get_blocked_domains():
    """获取当前用户已屏蔽的领域列表"""
    stmt = (db.select(UserBlockedDomain)
            .filter_by(user_id=g.current_user.id)
            .order_by(UserBlockedDomain.created_at.desc()))
    blocked_rows = db.session.scalars(stmt).all()
    domain_ids = [row.domain_id for row in blocked_rows]
    domains = db.session.scalars(db.select(Domain).filter(Domain.id.in_(domain_ids))).all() if domain_ids else []
    domain_map = {domain.id: domain for domain in domains}

    return jsonify({
        "domains": [domain_map[domain_id].to_dict() for domain_id in domain_ids if domain_id in domain_map],
        "total": len(domain_ids),
    })


@user_bp.route('/blocked/author/<int:author_id>', methods=['DELETE'])
@login_required
def remove_blocked_author(author_id):
    """取消屏蔽某个作者"""
    blocked = db.session.scalar(db.select(UserBlockedAuthor).filter_by(
        user_id=g.current_user.id,
        author_id=author_id,
    ))
    if not blocked:
        return jsonify({"error": "未屏蔽该作者"}), 404

    db.session.delete(blocked)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $uid})-[r:BLOCKED_AUTHOR]->(a:User {id: $aid}) DELETE r",
            {'uid': g.current_user.id, 'aid': author_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消屏蔽作者"})


@user_bp.route('/blocked/domain/<int:domain_id>', methods=['DELETE'])
@login_required
def remove_blocked_domain(domain_id):
    """取消屏蔽某个领域"""
    blocked = db.session.scalar(db.select(UserBlockedDomain).filter_by(
        user_id=g.current_user.id,
        domain_id=domain_id,
    ))
    if not blocked:
        return jsonify({"error": "未屏蔽该领域"}), 404

    db.session.delete(blocked)
    db.session.commit()

    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MATCH (u:User {id: $uid})-[r:BLOCKED_DOMAIN]->(d:Domain {id: $did}) DELETE r",
            {'uid': g.current_user.id, 'did': domain_id}
        )
    except Exception:
        pass

    return jsonify({"message": "已取消屏蔽领域"})
