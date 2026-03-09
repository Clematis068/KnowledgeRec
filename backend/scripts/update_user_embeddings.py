"""
定期更新用户兴趣向量和画像
用法: cd backend && uv run python -m scripts.update_user_embeddings

功能:
  1. 为缺少 embedding 的帖子生成 content_embedding
  2. 根据用户行为加权聚合帖子 embedding → 更新 interest_embedding
  3. LLM 生成用户兴趣画像 → 更新 interest_profile
"""
import sys
import os
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.post import Post
from app.models.behavior import UserBehavior
from app.services.qwen_service import qwen_service

# 行为类型权重：收藏 > 评论 > 点赞 > 浏览
BEHAVIOR_WEIGHTS = {
    'favorite': 3.0,
    'comment': 2.0,
    'like': 1.5,
    'browse': 0.5,
}


def update_post_embeddings():
    """为缺少 embedding 的帖子批量生成向量"""
    posts = Post.query.filter(Post.content_embedding.is_(None)).all()
    if not posts:
        print("  所有帖子已有 embedding，跳过")
        return 0

    count = 0
    for i, post in enumerate(posts):
        text = post.summary or (post.content[:300] if post.content else post.title)
        try:
            emb = qwen_service.get_embedding(text)
            post.content_embedding = emb
            count += 1
        except Exception as e:
            print(f"  帖子 {post.id} embedding 失败: {e}")

        time.sleep(0.1)  # API 限流
        if (i + 1) % 50 == 0:
            db.session.commit()
            print(f"  帖子进度: {i+1}/{len(posts)}, 成功 {count}")

    db.session.commit()
    return count


def update_user_embedding(user):
    """根据行为数据加权聚合帖子 embedding → 用户兴趣向量"""
    behaviors = UserBehavior.query.filter_by(user_id=user.id).all()

    # 聚合每个帖子的最大行为权重
    post_weights = {}
    for b in behaviors:
        w = BEHAVIOR_WEIGHTS.get(b.behavior_type, 0.5)
        # 同一帖子取最高权重行为
        if b.post_id not in post_weights or w > post_weights[b.post_id]:
            post_weights[b.post_id] = w

    if not post_weights:
        # 无行为数据：用兴趣标签生成
        tag_names = [t.name for t in user.interest_tags]
        if not tag_names:
            return False
        try:
            text = "兴趣领域：" + "、".join(tag_names)
            user.interest_embedding = qwen_service.get_embedding(text)
            return True
        except Exception:
            return False

    # 有行为数据：加权平均帖子 embedding
    posts = Post.query.filter(
        Post.id.in_(list(post_weights.keys())),
        Post.content_embedding.isnot(None),
    ).all()

    if not posts:
        return False

    weighted_sum = np.zeros(len(posts[0].content_embedding))
    total_weight = 0.0
    for post in posts:
        w = post_weights[post.id]
        weighted_sum += np.array(post.content_embedding) * w
        total_weight += w

    if total_weight > 0:
        user.interest_embedding = (weighted_sum / total_weight).tolist()
        return True
    return False


def update_user_profile(user):
    """LLM 生成用户兴趣画像描述"""
    behaviors = UserBehavior.query.filter_by(user_id=user.id).order_by(
        UserBehavior.created_at.desc()
    ).limit(30).all()

    # 收集交互过的帖子标题
    post_ids = list({b.post_id for b in behaviors})
    posts = Post.query.filter(Post.id.in_(post_ids)).all() if post_ids else []
    post_titles = [p.title for p in posts[:20]]

    # 注册兴趣标签
    tag_names = [t.name for t in user.interest_tags]

    if not post_titles and not tag_names:
        return False

    parts = []
    if tag_names:
        parts.append(f"注册兴趣标签：{', '.join(tag_names)}")
    if post_titles:
        parts.append(f"近期浏览/点赞的文章：{', '.join(post_titles)}")

    prompt = (
        f"根据以下用户信息，用一段话（50-100字）概括该用户的知识兴趣画像。"
        f"侧重实际行为偏好，直接输出画像描述。\n\n"
        + "\n".join(parts)
    )

    try:
        profile = qwen_service.chat(prompt)
        user.interest_profile = profile.strip()[:500]
        return True
    except Exception:
        return False


def main():
    app = create_app()
    with app.app_context():
        # 阶段1：帖子 embedding
        print("===== 1/3 更新帖子 Embedding =====")
        post_count = update_post_embeddings()
        print(f"  新增 {post_count} 个帖子 embedding\n")

        # 阶段2：用户兴趣向量
        print("===== 2/3 更新用户兴趣向量 =====")
        users = User.query.all()
        emb_count = 0
        for i, user in enumerate(users):
            if update_user_embedding(user):
                emb_count += 1
            if (i + 1) % 20 == 0:
                db.session.commit()
                print(f"  进度: {i+1}/{len(users)}")
        db.session.commit()
        print(f"  更新 {emb_count}/{len(users)} 个用户向量\n")

        # 阶段3：用户兴趣画像
        print("===== 3/3 更新用户兴趣画像 =====")
        profile_count = 0
        for i, user in enumerate(users):
            if update_user_profile(user):
                profile_count += 1
            time.sleep(0.3)
            if (i + 1) % 20 == 0:
                db.session.commit()
                print(f"  进度: {i+1}/{len(users)}")
        db.session.commit()
        print(f"  更新 {profile_count}/{len(users)} 个用户画像\n")

        print("===== 完成 =====")
        print(f"帖子 embedding: +{post_count}")
        print(f"用户兴趣向量: {emb_count}/{len(users)}")
        print(f"用户兴趣画像: {profile_count}/{len(users)}")


if __name__ == '__main__':
    main()
