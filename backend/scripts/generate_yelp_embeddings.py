"""为 Yelp 库生成 embedding（标签 → 帖子 → 用户兴趣向量）。

用法：
    MYSQL_URI=mysql+pymysql://root@localhost:3306/knowledge_community_yelp \
    NEO4J_URI=bolt://localhost:7688 \
    uv run python scripts/generate_yelp_embeddings.py

支持中断后续跑：仅处理 embedding 为 NULL 的记录。
"""
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Tag, Post, User, UserBehavior
from app.services.qwen_service import qwen_service


SLEEP = 0.1
TAG_COMMIT_EVERY = 20
POST_COMMIT_EVERY = 50
USER_COMMIT_EVERY = 200


def gen_tag_embeddings():
    tags = db.session.scalars(db.select(Tag).filter(Tag.embedding.is_(None))).all()
    print(f"\n[1/3] 标签 embedding：待处理 {len(tags)}")
    if not tags:
        return
    for i, tag in enumerate(tags):
        try:
            tag.embedding = qwen_service.get_embedding(tag.name)
        except Exception as e:
            print(f"  标签 {tag.name} 失败: {e}")
            db.session.commit()
            return
        if (i + 1) % TAG_COMMIT_EVERY == 0:
            db.session.commit()
            print(f"  进度 {i + 1}/{len(tags)}")
        time.sleep(SLEEP)
    db.session.commit()
    print(f"  完成 {len(tags)}")


def gen_post_embeddings():
    posts = db.session.scalars(
        db.select(Post).filter(Post.content_embedding.is_(None))
    ).all()
    print(f"\n[2/3] 帖子 embedding：待处理 {len(posts)}")
    if not posts:
        return
    t0 = time.time()
    for i, post in enumerate(posts):
        text = (post.title or '') + ' ' + ((post.content or '')[:500])
        text = text.strip()
        if not text:
            continue
        try:
            post.content_embedding = qwen_service.get_embedding(text)
        except Exception as e:
            print(f"  帖子 {post.id} 失败: {e}")
            db.session.commit()
            return
        if (i + 1) % POST_COMMIT_EVERY == 0:
            db.session.commit()
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(posts) - i - 1) / max(rate, 1e-6)
            print(f"  进度 {i + 1}/{len(posts)}  rate={rate:.1f}/s  ETA={eta/60:.1f} min")
        time.sleep(SLEEP)
    db.session.commit()
    print(f"  完成 {len(posts)}，用时 {(time.time()-t0)/60:.1f} min")


def gen_user_interest_vectors():
    """基于 like/favorite 行为加权平均帖子 embedding。"""
    users = db.session.scalars(
        db.select(User).filter(User.interest_embedding.is_(None))
    ).all()
    print(f"\n[3/3] 用户兴趣向量：待处理 {len(users)}")
    if not users:
        return

    print("  预加载帖子 embedding...")
    post_emb = {}
    for pid, emb in db.session.execute(
        db.select(Post.id, Post.content_embedding).where(Post.content_embedding.isnot(None))
    ):
        if emb is not None:
            post_emb[pid] = np.array(emb)
    print(f"  缓存 {len(post_emb)} 个帖子向量")

    print("  预加载用户行为...")
    user_acts = defaultdict(list)
    for uid, pid, btype in db.session.execute(
        db.select(UserBehavior.user_id, UserBehavior.post_id, UserBehavior.behavior_type)
        .where(UserBehavior.behavior_type.in_(['like', 'favorite']))
    ):
        user_acts[uid].append((pid, btype))

    updated = 0
    for i, user in enumerate(users):
        acts = user_acts.get(user.id, [])
        embs, ws = [], []
        for pid, btype in acts:
            v = post_emb.get(pid)
            if v is None:
                continue
            embs.append(v)
            ws.append(2.0 if btype == 'favorite' else 1.0)
        if embs:
            user.interest_embedding = np.average(embs, axis=0, weights=ws).tolist()
            updated += 1
        if (i + 1) % USER_COMMIT_EVERY == 0:
            db.session.commit()
            print(f"  进度 {i + 1}/{len(users)}  已更新 {updated}")
    db.session.commit()
    print(f"  完成：更新 {updated}/{len(users)} 个用户")


def main():
    app = create_app()
    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print("=" * 60)
        print(f"目标库：{uri}")
        print("=" * 60)
        gen_tag_embeddings()
        gen_post_embeddings()
        gen_user_interest_vectors()
        print("\n全部完成")


if __name__ == '__main__':
    main()
