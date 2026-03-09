from app.models.behavior import UserBlockedAuthor, UserBlockedDomain
from app.models.post import Post


def get_blocked_author_ids(user_id):
    if not user_id:
        return set()
    rows = UserBlockedAuthor.query.filter_by(user_id=user_id).all()
    return {row.author_id for row in rows}


def get_blocked_domain_ids(user_id):
    if not user_id:
        return set()
    rows = UserBlockedDomain.query.filter_by(user_id=user_id).all()
    return {row.domain_id for row in rows}


def apply_post_visibility_query(query, user_id):
    blocked_author_ids = get_blocked_author_ids(user_id)
    blocked_domain_ids = get_blocked_domain_ids(user_id)

    if blocked_author_ids:
        query = query.filter(~Post.author_id.in_(blocked_author_ids))
    if blocked_domain_ids:
        query = query.filter(~Post.domain_id.in_(blocked_domain_ids))

    return query


def is_post_visible_to_user(post, user_id):
    if not user_id:
        return True
    if post.author_id == user_id:
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
