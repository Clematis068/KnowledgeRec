from flask import Blueprint, request, jsonify, g
from app import db
from app.models.post import Post
from app.models.user import User
from app.utils.auth import optional_login
from app.utils.content_filter import filter_posts
from app.utils.helpers import cosine_similarity

search_bp = Blueprint('search', __name__)


@search_bp.route('', methods=['GET'])
@optional_login
def search():
    """搜索帖子或用户"""
    q = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'post').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if not q:
        if search_type == 'author':
            return jsonify({"users": [], "total": 0, "page": page})
        return jsonify({"posts": [], "total": 0, "page": page})

    if search_type == 'author':
        return _search_authors(q, page, per_page)

    return _search_posts(q, page, per_page)


def _search_authors(q, page, per_page):
    """按用户名搜索用户"""
    like_pattern = f'%{q}%'
    stmt = db.select(User).filter(User.username.like(like_pattern))
    pagination = db.paginate(stmt, page=page, per_page=per_page)
    users = [{
        'id': u.id,
        'username': u.username,
        'bio': u.bio,
    } for u in pagination.items]
    return jsonify({"users": users, "total": pagination.total, "page": page})


def _search_posts(q, page, per_page):
    """搜索帖子：LIKE 筛选 + Embedding 语义排序"""
    # 1. MySQL LIKE 粗筛（title + content）
    like_pattern = f'%{q}%'
    stmt = db.select(Post).filter(
        db.or_(
            Post.title.like(like_pattern),
            Post.content.like(like_pattern),
        )
    )
    candidates = db.session.scalars(stmt).all()
    candidates = filter_posts(candidates, g.current_user.id if g.current_user else None)

    # 2. 千问 Embedding 语义排序
    try:
        from app.services.qwen_service import qwen_service
        query_embedding = qwen_service.get_embedding(q)

        scored = []
        for post in candidates:
            if post.content_embedding:
                sim = cosine_similarity(query_embedding, post.content_embedding)
            else:
                sim = 0.0
            scored.append((post, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
    except Exception:
        # Embedding 服务不可用时按原始顺序
        scored = [(p, 0.0) for p in candidates]

    # 3. 分页
    total = len(scored)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = scored[start:end]

    results = []
    for post, sim in page_items:
        d = post.to_dict()
        d['relevance_score'] = round(sim, 4)
        results.append(d)

    return jsonify({"posts": results, "total": total, "page": page})
