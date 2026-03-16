"""
社区帖子爬取脚本（Playwright 版）
数据源: CSDN博客 + arXiv
爬完自动为每篇帖子生成 2-4 条随机评论

用法: cd backend && uv run python -m scripts.crawl_community_posts
     cd backend && uv run python -m scripts.crawl_community_posts --per-tag 3
"""
import sys
import os
import re
import time
import random
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import feedparser
from playwright.sync_api import sync_playwright

from app import create_app, db
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.domain import Domain
from app.models.user import User
from app.models.behavior import UserBehavior

# arXiv 关键词映射
ARXIV_KEYWORDS = {
    '机器学习': 'machine learning',
    '深度学习': 'deep learning',
    '自然语言处理': 'natural language processing',
    '计算机视觉': 'computer vision',
    '强化学习': 'reinforcement learning',
    '生成对抗网络': 'generative adversarial network',
    '卷积神经网络': 'convolutional neural network',
    '循环神经网络': 'recurrent neural network',
    '目标检测': 'object detection',
    '图像分割': 'image segmentation',
    '数据库': 'database systems',
    '分布式系统': 'distributed systems',
    '网络安全': 'cybersecurity',
    '算法设计': 'algorithm design',
    '编程语言': 'programming languages',
    '操作系统': 'operating system',
    '线性代数': 'linear algebra',
    '概率论': 'probability theory',
    '数论': 'number theory',
    '统计学': 'statistics',
    '最优化': 'optimization',
    '图论': 'graph theory',
    '量子力学': 'quantum mechanics',
    '相对论': 'general relativity',
    '粒子物理': 'particle physics',
    '天体物理': 'astrophysics',
    '神经科学': 'neuroscience',
    '基因工程': 'gene editing CRISPR',
    '博弈论': 'game theory',
    '密码学': 'cryptography',
    '电磁学': 'electromagnetism',
    '热力学': 'thermodynamics',
    '流体力学': 'fluid mechanics',
    '凝聚态物理': 'condensed matter physics',
    '量子信息': 'quantum information',
    '生态学': 'ecology',
    '进化论': 'evolutionary biology',
    '遗传学': 'genetics',
    '免疫学': 'immunology',
    '蛋白质组学': 'proteomics',
    '基因组学': 'genomics',
}

# 评论模板 —— {tag} 会被替换为标签名
COMMENT_TEMPLATES = [
    "写得很清晰，终于搞懂{tag}这块了",
    "总结得不错，收藏了",
    "补充一下，{tag}这个方向最近进展挺快的",
    "有没有推荐的{tag}入门资料？",
    "图文并茂，赞一个",
    "请问{tag}和相关领域有什么区别？",
    "正好在学{tag}，很有帮助",
    "分析得很到位，期待后续",
    "关于{tag}的第三部分能否展开讲讲？",
    "同领域，这篇确实讲得比较透彻",
    "学到了，之前一直没想明白这一点",
    "能否分享一下参考文献？",
    "这个角度很新颖",
    "对初学者很友好",
    "干货满满，已转发给同学",
    "第二段的推导过程有一步没看懂，能解释一下吗？",
    "太棒了，{tag}这块的文章不多见",
    "实践中{tag}确实是这样的，有共鸣",
]


def count_rows(model):
    return db.session.scalar(db.select(db.func.count()).select_from(model))


def get_random_author(users):
    return random.choice(users).id


def insert_post(title, content, summary, author_id, domain_id, tag_ids):
    """插入帖子，标题去重。返回 post_id 或 None"""
    if not content or len(content) < 80:
        return None
    title = title.strip()[:200]
    if db.session.scalar(db.select(Post).filter_by(title=title)):
        return None

    post = Post(
        title=title,
        content=content,
        summary=(summary or content[:200])[:500],
        author_id=author_id,
        domain_id=domain_id,
        view_count=random.randint(50, 2000),
        like_count=random.randint(5, 200),
        created_at=datetime.now() - timedelta(days=random.randint(1, 180)),
    )
    db.session.add(post)
    db.session.flush()

    for tid in tag_ids:
        db.session.execute(post_tag.insert().values(post_id=post.id, tag_id=tid))
    return post.id


def generate_comments(post_id, tag_name, users, n=None):
    """为帖子生成 n 条随机评论"""
    if n is None:
        n = random.randint(2, 4)
    templates = random.sample(COMMENT_TEMPLATES, k=min(n, len(COMMENT_TEMPLATES)))
    for tpl in templates:
        text = tpl.replace('{tag}', tag_name)
        comment = UserBehavior(
            user_id=get_random_author(users),
            post_id=post_id,
            behavior_type='comment',
            comment_text=text,
            created_at=datetime.now() - timedelta(
                days=random.randint(0, 90),
                hours=random.randint(0, 23),
            ),
        )
        db.session.add(comment)


# ────────────────────── CSDN ──────────────────────


def crawl_csdn(page, keyword, max_results=2):
    """用 Playwright 爬 CSDN 博客搜索，返回文章列表"""
    results = []
    try:
        page.goto(
            f'https://so.csdn.net/so/search?q={keyword}&t=blog',
            timeout=15000,
        )
        page.wait_for_timeout(4000)

        links = page.eval_on_selector_all(
            'a[href*="blog.csdn.net/"][href*="/article/details/"]',
            'els => els.map(e => ({href: e.href, text: e.innerText.trim()}))',
        )
        seen = set()
        blog_links = []
        for link in links:
            href = link['href'].split('?')[0]
            if href in seen or not link['text'] or len(link['text']) < 5:
                continue
            seen.add(href)
            blog_links.append(link)

        for link in blog_links[:max_results]:
            try:
                page.goto(link['href'], timeout=12000)
                page.wait_for_timeout(2000)

                title_sel = '#articleContentId, .title-article h1, h1'
                title = page.eval_on_selector(
                    title_sel, 'el => el.innerText.trim()',
                ) if page.query_selector(title_sel) else link['text']

                content_sel = '#content_views, .article_content'
                content = page.eval_on_selector(
                    content_sel, 'el => el.innerText.trim()',
                ) if page.query_selector(content_sel) else ''

                if len(content) < 100:
                    continue
                if len(content) > 3000:
                    content = content[:3000]

                results.append({
                    'title': title,
                    'content': content,
                    'summary': content[:200],
                })
            except Exception:
                continue

    except Exception as e:
        print(f'    [CSDN] {keyword}: {e}')

    return results


# ────────────────────── arXiv ──────────────────────


def crawl_arxiv(keyword_en, max_results=2):
    """通过 arXiv API 搜索论文"""
    results = []
    try:
        resp = requests.get(
            'http://export.arxiv.org/api/query',
            params={
                'search_query': f'all:{keyword_en}',
                'max_results': max_results,
                'sortBy': 'relevance',
            },
            timeout=15,
        )
        feed = feedparser.parse(resp.text)
        for entry in feed.entries:
            title = f'[论文] {entry.title.replace(chr(10), " ").strip()}'
            abstract = entry.summary.replace('\n', ' ').strip()
            if len(abstract) > 50:
                results.append({
                    'title': title[:200],
                    'content': abstract,
                    'summary': abstract[:300],
                })
    except Exception as e:
        print(f'    [arXiv] {keyword_en}: {e}')
    return results


# ────────────────────── Neo4j 同步 ──────────────────────


def sync_new_posts_to_neo4j():
    """将新帖子同步到 Neo4j"""
    try:
        from app.services.neo4j_service import neo4j_service

        stmt = db.select(Post).filter(Post.content_embedding.is_(None))
        new_posts = db.session.scalars(stmt).all()
        if not new_posts:
            print("  没有需要同步的新帖子")
            return

        neo4j_service.run_write(
            "UNWIND $items AS item MERGE (p:Post {id: item.id}) "
            "SET p.title = item.title, p.summary = item.summary",
            {"items": [{"id": p.id, "title": p.title, "summary": p.summary} for p in new_posts]},
        )
        neo4j_service.run_write(
            "UNWIND $items AS item "
            "MATCH (u:User {id: item.author_id}), (p:Post {id: item.post_id}) "
            "MERGE (u)-[:AUTHORED]->(p)",
            {"items": [{"author_id": p.author_id, "post_id": p.id} for p in new_posts]},
        )
        pt_rows = db.session.execute(
            post_tag.select().where(post_tag.c.post_id.in_([p.id for p in new_posts]))
        ).fetchall()
        if pt_rows:
            neo4j_service.run_write(
                "UNWIND $items AS item "
                "MATCH (p:Post {id: item.post_id}), (t:Tag {id: item.tag_id}) "
                "MERGE (p)-[:TAGGED_WITH]->(t)",
                {"items": [{"post_id": r[0], "tag_id": r[1]} for r in pt_rows]},
            )
        print(f"  Neo4j 同步完成: {len(new_posts)} 篇")
    except Exception as e:
        print(f"  Neo4j 同步失败: {e}")


# ────────────────────── main ──────────────────────


def main():
    parser = argparse.ArgumentParser(description='社区帖子爬取')
    parser.add_argument('--per-tag', type=int, default=2, help='每个标签目标篇数 (default: 2)')
    parser.add_argument('--skip-arxiv', action='store_true', help='跳过 arXiv')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        users = db.session.scalars(db.select(User)).all()
        if not users:
            print("错误: 数据库中没有用户，请先运行 generate_mock_data.py")
            return

        domains = db.session.scalars(db.select(Domain)).all()
        domain_map = {d.id: d.name for d in domains}

        tags = db.session.scalars(db.select(Tag)).all()
        total_inserted = 0
        total_comments = 0
        source_counts = {'csdn': 0, 'arxiv': 0}

        print(f"===== 社区帖子爬取 =====")
        print(f"标签数: {len(tags)}, 每标签目标: {args.per_tag} 篇")
        print(f"数据源: CSDN{' + arXiv' if not args.skip_arxiv else ''}")
        print()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            for i, tag in enumerate(tags):
                tag_count = 0

                # ── CSDN（所有标签都搜）──
                if tag_count < args.per_tag:
                    posts = crawl_csdn(page, tag.name, max_results=args.per_tag)
                    for p in posts:
                        if tag_count >= args.per_tag:
                            break
                        post_id = insert_post(
                            p['title'], p['content'], p['summary'],
                            get_random_author(users), tag.domain_id, [tag.id],
                        )
                        if post_id:
                            n_comments = random.randint(2, 4)
                            generate_comments(post_id, tag.name, users, n=n_comments)
                            tag_count += 1
                            total_inserted += 1
                            total_comments += n_comments
                            source_counts['csdn'] += 1
                            print(f"  [{total_inserted:>4}] CSDN  | {tag.name} | {p['title'][:45]}")
                    time.sleep(0.5)

                # ── arXiv（有映射的标签补充）──
                arxiv_kw = ARXIV_KEYWORDS.get(tag.name)
                if arxiv_kw and not args.skip_arxiv and tag_count < args.per_tag:
                    posts = crawl_arxiv(arxiv_kw, max_results=args.per_tag - tag_count)
                    for p in posts:
                        if tag_count >= args.per_tag:
                            break
                        post_id = insert_post(
                            p['title'], p['content'], p['summary'],
                            get_random_author(users), tag.domain_id, [tag.id],
                        )
                        if post_id:
                            n_comments = random.randint(1, 3)
                            generate_comments(post_id, tag.name, users, n=n_comments)
                            tag_count += 1
                            total_inserted += 1
                            total_comments += n_comments
                            source_counts['arxiv'] += 1
                            print(f"  [{total_inserted:>4}] arXiv | {tag.name} | {p['title'][:45]}")
                    time.sleep(0.3)

                # 定期提交
                if (i + 1) % 20 == 0:
                    db.session.commit()
                    print(f"\n  --- 进度: {i + 1}/{len(tags)} 标签, "
                          f"帖子 {total_inserted}, 评论 {total_comments} ---\n")

            browser.close()

        db.session.commit()

        # Neo4j 同步
        print("\n同步到 Neo4j...")
        sync_new_posts_to_neo4j()

        print(f"\n===== 爬取完成 =====")
        print(f"新增帖子: {total_inserted}")
        print(f"生成评论: {total_comments}")
        print(f"  CSDN:  {source_counts['csdn']}")
        print(f"  arXiv: {source_counts['arxiv']}")
        print(f"数据库帖子总数: {count_rows(Post)}")


if __name__ == '__main__':
    main()
