from app import db
from app.models.behavior import UserBlockedAuthor, UserBlockedDomain
from app.models.post import Post


def get_blocked_author_ids(user_id):
    if not user_id:
        return set()
    stmt = db.select(UserBlockedAuthor).filter_by(user_id=user_id)
    rows = db.session.scalars(stmt).all()
    return {row.author_id for row in rows}


def get_blocked_domain_ids(user_id):
    if not user_id:
        return set()
    stmt = db.select(UserBlockedDomain).filter_by(user_id=user_id)
    rows = db.session.scalars(stmt).all()
    return {row.domain_id for row in rows}


def apply_post_visibility_query(query, user_id):
    # 只展示 published 状态的帖子（管理后台的列表不经过此过滤器）
    query = query.filter(Post.status.in_(('published', None)))

    blocked_author_ids = get_blocked_author_ids(user_id)
    blocked_domain_ids = get_blocked_domain_ids(user_id)

    if blocked_author_ids:
        query = query.filter(~Post.author_id.in_(blocked_author_ids))
    if blocked_domain_ids:
        query = query.filter(~Post.domain_id.in_(blocked_domain_ids))

    return query


def is_post_visible_to_user(post, user_id):
    # 仅发布态帖子可见；审核拒绝内容不对用户展示
    if getattr(post, 'status', 'published') not in ('published', None):
        return False
    if not user_id:
        return True

    blocked_author_ids = get_blocked_author_ids(user_id)
    blocked_domain_ids = get_blocked_domain_ids(user_id)
    return (
        post.author_id not in blocked_author_ids
        and post.domain_id not in blocked_domain_ids
    )


def filter_posts(posts, user_id):
    if not user_id:
        return posts
    return [post for post in posts if is_post_visible_to_user(post, user_id)]
