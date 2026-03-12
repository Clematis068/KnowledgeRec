"""
模拟数据生成脚本
用法: cd backend && uv run python -m scripts.generate_mock_data

生成规模: 10领域 / 100标签 / 500用户 / 2000帖子 / ~50000行为 / ~3000关注
"""
import sys
import os
import random
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from faker import Faker
import numpy as np

from app import create_app, db
from app.models import User, Post, Tag, Domain, UserBehavior, UserFollow, post_tag
from app.taxonomy import FIXED_DOMAINS

fake = Faker('zh_CN')


def count_rows(model):
    return db.session.scalar(db.select(db.func.count()).select_from(model))

# ============================================================
# 领域与标签定义
# ============================================================
DOMAINS_AND_TAGS = {
    item["name"]: item["keywords"]
    for item in FIXED_DOMAINS
}

# 帖子标题模板
POST_TITLE_TEMPLATES = [
    "深入理解{tag}的核心概念",
    "{tag}入门指南：从零开始",
    "关于{tag}的几点思考",
    "{tag}领域最新研究进展",
    "如何学好{tag}？分享我的学习经验",
    "{tag}中的常见误区与澄清",
    "{tag}实践案例分析",
    "浅谈{tag}在{domain}中的应用",
    "{tag}的前沿问题探讨",
    "一文读懂{tag}的基本原理",
    "{domain}视角下的{tag}研究",
    "{tag}学习路线图推荐",
]

# 帖子内容模板
POST_CONTENT_TEMPLATES = [
    "本文将从基础概念出发，系统性地介绍{tag}的核心理论框架。{tag}作为{domain}的重要分支，"
    "近年来受到了广泛关注。首先，我们需要理解{tag}的基本定义和发展历程。"
    "其次，本文将深入分析{tag}的关键方法论和技术路线。"
    "最后，我们将讨论{tag}在实际场景中的应用前景和未来发展方向。"
    "希望这篇文章能够帮助读者建立对{tag}的系统认知。",

    "在{domain}研究中，{tag}一直是一个核心话题。本文基于最新的研究成果，"
    "从理论和实践两个维度对{tag}进行深入分析。"
    "我们首先回顾了{tag}的经典理论，然后介绍了近年来的新方法和新思路。"
    "通过对比分析，我们发现传统方法和新方法各有优劣，具体选择需要根据应用场景来决定。"
    "文末提供了详细的参考文献和学习资源，供感兴趣的读者进一步研究。",

    "作为一名{domain}领域的学习者，我在学习{tag}的过程中积累了不少经验和体会。"
    "今天想和大家分享一下我对{tag}的理解。"
    "首先，{tag}的核心在于掌握其基本原理，而不是死记硬背公式和结论。"
    "其次，动手实践非常重要，只有通过大量的练习才能真正理解{tag}的精髓。"
    "最后，建议大家多阅读经典文献，站在巨人的肩膀上看问题。",

    "最近在学习{tag}的过程中，我发现了一些有趣的问题值得探讨。"
    "{tag}是{domain}中的一个活跃研究方向，每年都有大量的新成果发表。"
    "本文尝试梳理{tag}的关键问题和主要研究方向，帮助初学者建立清晰的知识框架。"
    "文中还穿插了一些个人的思考和见解，欢迎大家批评指正。"
    "如果你对{tag}感兴趣，不妨从这篇文章开始，逐步深入学习。",
]

# 评论模板
COMMENT_TEMPLATES = [
    "写得非常好，学到了很多！",
    "感谢分享，收藏了慢慢看",
    "这个观点很新颖，值得思考",
    "请问有推荐的参考书目吗？",
    "文章很有深度，期待更多",
    "有一处小疑问：这里的推导是否有误？",
    "总结得很全面，适合入门",
    "正好在学这个，太及时了",
    "分析得很到位，赞一个",
    "能否展开讲讲实际应用场景？",
]

BIO_ROLE_MAP = {
    "计算机科学": ["后端开发", "算法工程师", "计算机专业学生", "独立开发者"],
    "数学": ["数学系学生", "数据分析师", "竞赛爱好者", "研究助理"],
    "物理学": ["物理系学生", "科研助理", "实验室成员"],
    "化学": ["化学专业学生", "实验室成员", "材料方向研究生"],
    "生物学": ["生物专业学生", "科研助理", "实验记录党"],
    "医学与健康": ["医学生", "临床科研助理", "健康内容学习者"],
    "心理学": ["心理学学生", "咨询方向学习者", "行为观察爱好者"],
    "经济学": ["经济学学生", "政策观察者", "研究生"],
    "金融学": ["金融从业者", "量化学习者", "投资研究爱好者"],
    "管理学": ["产品经理", "运营同学", "创业观察者"],
    "法学": ["法学生", "法律从业者", "案例研究爱好者"],
    "教育学": ["一线教师", "教育学学生", "课程设计爱好者"],
    "新闻传播学": ["内容运营", "媒体观察者", "传播学学生"],
}

BIO_GOALS = [
    "最近在补基础，也会记一些学习笔记。",
    "主要把这里当成整理资料和交流想法的地方。",
    "平时会关注新进展，也会记录自己的理解。",
    "希望把零散知识慢慢串成体系。",
    "欢迎交流入门资料、实践经验和踩坑记录。",
]

BIO_STYLE_TEMPLATES = [
    "{role}，主要关注{tags}，{goal}",
    "{role}，最近在看{tags}，也会持续学习{domains}相关内容。",
    "目前在做{domains}方向的学习和积累，重点关注{tags}。",
    "{role}，平时会记录{domains}的学习心得，最近更关注{tags}。",
    "长期关注{domains}，最近在系统补{tags}这块内容。",
]


def generate_domains_and_tags():
    """生成领域和标签"""
    print("生成领域和标签...")
    for domain_name, tag_names in DOMAINS_AND_TAGS.items():
        description = next(
            (item["description"] for item in FIXED_DOMAINS if item["name"] == domain_name),
            f"{domain_name}相关的知识内容",
        )
        domain = Domain(name=domain_name, description=description)
        db.session.add(domain)
        db.session.flush()  # get domain.id

        for tag_name in tag_names:
            tag = Tag(name=tag_name, domain_id=domain.id)
            db.session.add(tag)

    db.session.commit()
    print(f"  领域: {count_rows(Domain)}, 标签: {count_rows(Tag)}")


def _pick_interest_tags(interests, max_tags=3):
    selected_tags = []
    shuffled_interests = interests[:]
    random.shuffle(shuffled_interests)

    for domain in shuffled_interests:
        domain_tags = domain.tags.all()
        if not domain_tags:
            continue
        selected_tags.append(random.choice(domain_tags).name)
        if len(selected_tags) >= max_tags:
            break

    return selected_tags


def build_realistic_bio(interests):
    main_domain = interests[0].name
    domain_names = [domain.name for domain in interests[:2]]
    focus_tags = _pick_interest_tags(interests, max_tags=min(3, len(interests) + 1))

    role_pool = BIO_ROLE_MAP.get(main_domain, ["学习者", "从业者", "研究爱好者"])
    role = random.choice(role_pool)
    tags_text = "、".join(focus_tags) if focus_tags else main_domain
    domains_text = "、".join(domain_names)
    goal = random.choice(BIO_GOALS)
    template = random.choice(BIO_STYLE_TEMPLATES)

    return template.format(
        role=role,
        tags=tags_text,
        domains=domains_text,
        goal=goal,
    )


def generate_users(n=500):
    """生成用户，每个用户分配2-4个兴趣领域"""
    print(f"生成 {n} 个用户...")
    domains = db.session.scalars(db.select(Domain)).all()
    users_data = []

    for i in range(n):
        interests = random.sample(domains, k=random.randint(2, 4))
        user = User(
            username=fake.user_name() + str(i),
            email=f"user{i}@example.com",
            bio=build_realistic_bio(interests),
            created_at=fake.date_time_between(start_date='-180d', end_date='-30d'),
        )
        db.session.add(user)
        users_data.append({
            'user': user,
            'interests': interests,
        })

    db.session.commit()
    print(f"  用户: {count_rows(User)}")
    return users_data


def generate_posts(users_data, n=2000):
    """生成帖子，按用户兴趣领域分配"""
    print(f"生成 {n} 个帖子...")
    domains = db.session.scalars(db.select(Domain)).all()
    all_tags = {d.id: list(d.tags) for d in domains}

    for i in range(n):
        # 随机选一个用户及其兴趣领域
        ud = random.choice(users_data)
        domain = random.choice(ud['interests'])
        domain_tags = all_tags.get(domain.id, [])
        if not domain_tags:
            continue

        # 选1-3个标签
        selected_tags = random.sample(domain_tags, k=min(random.randint(1, 3), len(domain_tags)))
        main_tag = selected_tags[0]

        title = random.choice(POST_TITLE_TEMPLATES).format(tag=main_tag.name, domain=domain.name)
        content = random.choice(POST_CONTENT_TEMPLATES).format(tag=main_tag.name, domain=domain.name)

        post = Post(
            title=title,
            content=content,
            summary=f"关于{main_tag.name}的{domain.name}领域探讨",
            author_id=ud['user'].id,
            domain_id=domain.id,
            created_at=fake.date_time_between(start_date='-90d', end_date='now'),
        )
        db.session.add(post)
        db.session.flush()

        # 关联标签
        for tag in selected_tags:
            stmt = post_tag.insert().values(post_id=post.id, tag_id=tag.id)
            db.session.execute(stmt)

    db.session.commit()
    print(f"  帖子: {count_rows(Post)}")


def generate_behaviors(users_data, avg_per_user=100):
    """生成用户行为：60% browse, 20% like, 10% favorite, 10% comment"""
    print(f"生成用户行为(每人约{avg_per_user}条)...")
    all_posts = db.session.scalars(db.select(Post)).all()
    posts_by_domain = {}
    for p in all_posts:
        posts_by_domain.setdefault(p.domain_id, []).append(p)

    total = 0
    for ud in users_data:
        user = ud['user']
        interest_domain_ids = [d.id for d in ud['interests']]
        n_behaviors = random.randint(avg_per_user - 30, avg_per_user + 30)

        for _ in range(n_behaviors):
            # 90% 交互兴趣领域的帖子，10% 随机
            if random.random() < 0.9:
                did = random.choice(interest_domain_ids)
                pool = posts_by_domain.get(did, all_posts)
            else:
                pool = all_posts

            post = random.choice(pool)

            # 行为类型分布
            r = random.random()
            if r < 0.60:
                btype = 'browse'
            elif r < 0.80:
                btype = 'like'
            elif r < 0.90:
                btype = 'favorite'
            else:
                btype = 'comment'

            behavior = UserBehavior(
                user_id=user.id,
                post_id=post.id,
                behavior_type=btype,
                duration=random.randint(5, 300) if btype == 'browse' else None,
                comment_text=random.choice(COMMENT_TEMPLATES) if btype == 'comment' else None,
                created_at=fake.date_time_between(start_date='-90d', end_date='now'),
            )
            db.session.add(behavior)
            total += 1

            # 更新帖子计数
            if btype == 'like':
                post.like_count = (post.like_count or 0) + 1
            elif btype == 'browse':
                post.view_count = (post.view_count or 0) + 1

        # 每100个用户提交一次
        if total % 10000 == 0:
            db.session.commit()

    db.session.commit()
    print(f"  行为记录: {count_rows(UserBehavior)}")


def generate_follows(users_data, avg_per_user=6):
    """生成关注关系，优先关注相同兴趣的用户"""
    print("生成关注关系...")
    users = [ud['user'] for ud in users_data]
    interest_map = {ud['user'].id: set(d.id for d in ud['interests']) for ud in users_data}

    total = 0
    existing = set()

    for ud in users_data:
        user = ud['user']
        n_follows = random.randint(3, 10)
        candidates = [u for u in users if u.id != user.id]

        # 按兴趣重叠排序
        my_interests = interest_map[user.id]
        candidates.sort(
            key=lambda u: len(my_interests & interest_map.get(u.id, set())),
            reverse=True,
        )

        # 前70%从兴趣相近的人选，30%随机
        top_pool = candidates[:len(candidates) // 3]
        for _ in range(n_follows):
            pool = top_pool if random.random() < 0.7 and top_pool else candidates
            target = random.choice(pool)
            pair = (user.id, target.id)
            if pair not in existing:
                existing.add(pair)
                db.session.add(UserFollow(follower_id=user.id, followed_id=target.id))
                total += 1

    db.session.commit()
    print(f"  关注关系: {total}")


def generate_embeddings():
    """调用千问API生成帖子和标签的Embedding向量"""
    from app.services.qwen_service import qwen_service

    # 标签 embedding
    tags = db.session.scalars(db.select(Tag).filter(Tag.embedding.is_(None))).all()
    if tags:
        print(f"生成标签Embedding ({len(tags)}个)...")
        for i, tag in enumerate(tags):
            try:
                tag.embedding = qwen_service.get_embedding(tag.name)
                if (i + 1) % 20 == 0:
                    db.session.commit()
                    print(f"  标签进度: {i + 1}/{len(tags)}")
                time.sleep(0.1)  # 限流
            except Exception as e:
                print(f"  标签 {tag.name} 失败: {e}")
        db.session.commit()

    # 帖子 embedding
    posts = db.session.scalars(db.select(Post).filter(Post.content_embedding.is_(None))).all()
    if posts:
        print(f"生成帖子Embedding ({len(posts)}个)...")
        for i, post in enumerate(posts):
            try:
                text = post.title + " " + (post.content[:200] if post.content else "")
                post.content_embedding = qwen_service.get_embedding(text)
                if (i + 1) % 50 == 0:
                    db.session.commit()
                    print(f"  帖子进度: {i + 1}/{len(posts)}")
                time.sleep(0.1)
            except Exception as e:
                print(f"  帖子 {post.id} 失败: {e}")
        db.session.commit()

    print("Embedding生成完成")


def compute_user_interest_embeddings():
    """根据用户行为计算兴趣向量（liked/favorited帖子的加权平均）"""
    print("计算用户兴趣向量...")
    users = db.session.scalars(db.select(User)).all()

    for user in users:
        stmt = (db.select(UserBehavior)
                .filter_by(user_id=user.id)
                .filter(UserBehavior.behavior_type.in_(['like', 'favorite'])))
        behaviors = db.session.scalars(stmt).all()

        if not behaviors:
            continue

        embeddings = []
        weights = []
        for b in behaviors:
            post = db.session.get(Post, b.post_id)
            if post and post.content_embedding:
                emb = post.content_embedding
                w = 2.0 if b.behavior_type == 'favorite' else 1.0
                embeddings.append(np.array(emb))
                weights.append(w)

        if embeddings:
            weights = np.array(weights)
            weighted_avg = np.average(embeddings, axis=0, weights=weights)
            user.interest_embedding = weighted_avg.tolist()

    db.session.commit()
    print(f"  已为 {sum(1 for u in users if u.interest_embedding)} 个用户生成兴趣向量")


def generate_interest_profiles(sample_size=50):
    """LLM生成用户兴趣画像（仅抽样，节省API调用）"""
    from app.services.qwen_service import qwen_service

    print(f"生成用户兴趣画像(抽样{sample_size}个)...")
    stmt = db.select(User).filter(User.interest_embedding.isnot(None)).limit(sample_size)
    users = db.session.scalars(stmt).all()

    for i, user in enumerate(users):
        # 获取该用户最常交互的标签
        stmt = (db.select(UserBehavior)
                .filter_by(user_id=user.id)
                .filter(UserBehavior.behavior_type.in_(['like', 'favorite', 'comment'])))
        behaviors = db.session.scalars(stmt).all()

        post_ids = list(set(b.post_id for b in behaviors))[:20]
        posts = db.session.scalars(db.select(Post).filter(Post.id.in_(post_ids))).all()
        titles = [p.title for p in posts[:10]]

        if not titles:
            continue

        prompt = (
            "根据以下用户近期感兴趣的文章标题，用2-3句话概括该用户的兴趣画像：\n"
            + "\n".join(f"- {t}" for t in titles)
        )

        try:
            user.interest_profile = qwen_service.chat(prompt)
            if (i + 1) % 10 == 0:
                db.session.commit()
                print(f"  画像进度: {i + 1}/{len(users)}")
            time.sleep(0.2)
        except Exception as e:
            print(f"  用户 {user.id} 画像生成失败: {e}")

    db.session.commit()
    print("兴趣画像生成完成")


def sync_to_neo4j():
    """将 MySQL 数据同步到 Neo4j 图数据库"""
    from app.services.neo4j_service import neo4j_service

    print("同步数据到 Neo4j...")

    # 领域
    domains = db.session.scalars(db.select(Domain)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (d:Domain {id: item.id}) SET d.name = item.name",
        {"items": [{"id": d.id, "name": d.name} for d in domains]},
    )
    print("  领域节点已同步")

    # 标签
    tags = db.session.scalars(db.select(Tag)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (t:Tag {id: item.id}) SET t.name = item.name",
        {"items": [{"id": t.id, "name": t.name} for t in tags]},
    )
    # Tag -> Domain
    neo4j_service.run_write(
        "UNWIND $items AS item "
        "MATCH (t:Tag {id: item.tag_id}), (d:Domain {id: item.domain_id}) "
        "MERGE (t)-[:BELONGS_TO]->(d)",
        {"items": [{"tag_id": t.id, "domain_id": t.domain_id} for t in tags]},
    )
    print("  标签节点和关系已同步")

    # 用户
    users = db.session.scalars(db.select(User)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (u:User {id: item.id}) SET u.username = item.username",
        {"items": [{"id": u.id, "username": u.username} for u in users]},
    )
    print("  用户节点已同步")

    # 帖子
    posts = db.session.scalars(db.select(Post)).all()
    neo4j_service.run_write(
        "UNWIND $items AS item MERGE (p:Post {id: item.id}) "
        "SET p.title = item.title, p.summary = item.summary",
        {"items": [{"id": p.id, "title": p.title, "summary": p.summary} for p in posts]},
    )
    # Post -> Author
    neo4j_service.run_write(
        "UNWIND $items AS item "
        "MATCH (u:User {id: item.author_id}), (p:Post {id: item.post_id}) "
        "MERGE (u)-[:AUTHORED]->(p)",
        {"items": [{"author_id": p.author_id, "post_id": p.id} for p in posts]},
    )
    print("  帖子节点和作者关系已同步")

    # Post -> Tag
    pt_rows = db.session.execute(post_tag.select()).fetchall()
    neo4j_service.run_write(
        "UNWIND $items AS item "
        "MATCH (p:Post {id: item.post_id}), (t:Tag {id: item.tag_id}) "
        "MERGE (p)-[:TAGGED_WITH]->(t)",
        {"items": [{"post_id": r[0], "tag_id": r[1]} for r in pt_rows]},
    )
    print("  帖子-标签关系已同步")

    # 用户行为关系（分批处理）
    for btype, rel_type in [('like', 'LIKED'), ('favorite', 'FAVORITED'),
                             ('comment', 'COMMENTED'), ('browse', 'BROWSED')]:
        behaviors = db.session.scalars(db.select(UserBehavior).filter_by(behavior_type=btype)).all()
        if not behaviors:
            continue
        # 分批，每批1000
        batch_size = 1000
        for start in range(0, len(behaviors), batch_size):
            batch = behaviors[start:start + batch_size]
            neo4j_service.run_write(
                f"UNWIND $items AS item "
                f"MATCH (u:User {{id: item.user_id}}), (p:Post {{id: item.post_id}}) "
                f"MERGE (u)-[:{rel_type}]->(p)",
                {"items": [{"user_id": b.user_id, "post_id": b.post_id} for b in batch]},
            )
        print(f"  {rel_type} 关系已同步 ({len(behaviors)}条)")

    # 关注关系
    follows = db.session.scalars(db.select(UserFollow)).all()
    if follows:
        neo4j_service.run_write(
            "UNWIND $items AS item "
            "MATCH (a:User {id: item.follower}), (b:User {id: item.followed}) "
            "MERGE (a)-[:FOLLOWS]->(b)",
            {"items": [{"follower": f.follower_id, "followed": f.followed_id} for f in follows]},
        )
        print(f"  FOLLOWS 关系已同步 ({len(follows)}条)")

    # 派生: INTERESTED_IN (用户对标签的兴趣权重)
    neo4j_service.run_write(
        "MATCH (u:User)-[r:LIKED|FAVORITED|COMMENTED]->(p:Post)-[:TAGGED_WITH]->(t:Tag) "
        "WITH u, t, count(r) AS cnt WHERE cnt >= 2 "
        "MERGE (u)-[rel:INTERESTED_IN]->(t) SET rel.weight = cnt"
    )
    print("  INTERESTED_IN 关系已派生")

    print("Neo4j 同步完成!")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--small', action='store_true', help='小样本模式: 20用户/50帖子/500行为')
    args = parser.parse_args()

    if args.small:
        n_users, n_posts, avg_behaviors, n_profiles = 20, 50, 25, 5
        print("===== 小样本模式 =====")
    else:
        n_users, n_posts, avg_behaviors, n_profiles = 500, 2000, 100, 50

    app = create_app()
    with app.app_context():
        # 清空旧数据
        print("清空旧数据...")
        db.drop_all()
        db.create_all()

        # 基础数据
        generate_domains_and_tags()
        users_data = generate_users(n_users)
        generate_posts(users_data, n_posts)
        generate_behaviors(users_data, avg_behaviors)
        generate_follows(users_data, 6)

        # Embedding（需要千问API，可跳过）
        try:
            generate_embeddings()
            compute_user_interest_embeddings()
            generate_interest_profiles(n_profiles)
        except Exception as e:
            print(f"Embedding/画像生成跳过（API不可用）: {e}")

        # 同步 Neo4j（需要Neo4j运行，可跳过）
        try:
            sync_to_neo4j()
        except Exception as e:
            print(f"Neo4j同步跳过（未启动）: {e}")

        print("\n===== 数据生成完成 =====")
        print(f"领域: {count_rows(Domain)}")
        print(f"标签: {count_rows(Tag)}")
        print(f"用户: {count_rows(User)}")
        print(f"帖子: {count_rows(Post)}")
        print(f"行为: {count_rows(UserBehavior)}")
        print(f"关注: {count_rows(UserFollow)}")


if __name__ == '__main__':
    main()
