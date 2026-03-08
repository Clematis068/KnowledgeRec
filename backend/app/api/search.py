from flask import Blueprint, request, jsonify
from app import db
from app.models.post import Post
from app.utils.helpers import cosine_similarity

search_bp = Blueprint('search', __name__)


@search_bp.route('', methods=['GET'])
def search_posts():
    """搜索帖子：LIKE 筛选 + Embedding 语义排序"""
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if not q:
        return jsonify({"posts": [], "total": 0, "page": page})

    # 1. MySQL LIKE 粗筛（title + content）
    like_pattern = f'%{q}%'
    candidates = Post.query.filter(
        db.or_(
            Post.title.like(like_pattern),
            Post.content.like(like_pattern),
        )
    ).all()

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
