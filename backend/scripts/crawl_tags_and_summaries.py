"""
从权威知识社区爬取帖子摘要 + 细化标签分类
用法: cd backend && uv run python -m scripts.crawl_tags_and_summaries

数据源:
  - 维基百科 MediaWiki API (全领域，中文摘要)
  - Stack Exchange API (各领域子站高赞问答)
  - arXiv API (STEM论文摘要)
  - 千问 LLM (翻译英文 + 补充缺失标签)
"""
import sys
import os
import re
import json
import time
import random
import html
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import feedparser

from app import create_app, db
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.domain import Domain
from app.models.user import User


def count_rows(model):
    return db.session.scalar(db.select(db.func.count()).select_from(model))

WIKI_API = 'https://zh.wikipedia.org/w/api.php'
WIKI_HEADERS = {'User-Agent': 'KnowledgeRec/1.0 (educational project)'}
SE_API = 'https://api.stackexchange.com/2.3'
ARXIV_API = 'http://export.arxiv.org/api/query'

# Stack Exchange 子站映射
SE_SITES = {
    '计算机科学': 'stackoverflow',
    '数学': 'math',
    '物理学': 'physics',
    '经济学': 'economics',
    '生物学': 'biology',
    '哲学': 'philosophy',
    '心理学': 'psychology',
    '历史学': 'history',
    '文学': 'literature',
    '法学': 'law',
}

# 标签名 -> 英文搜索关键词
TAG_EN_MAP = {
    '机器学习': 'machine learning', '深度学习': 'deep learning',
    '自然语言处理': 'NLP natural language processing',
    '计算机视觉': 'computer vision', '数据库': 'database design',
    '操作系统': 'operating system', '算法设计': 'algorithm',
    '分布式系统': 'distributed system', '网络安全': 'cybersecurity',
    '编程语言': 'programming language design',
    '线性代数': 'linear algebra', '概率论': 'probability',
    '数论': 'number theory', '微积分': 'calculus',
    '统计学': 'statistics', '组合数学': 'combinatorics',
    '最优化': 'optimization', '图论': 'graph theory',
    '离散数学': 'discrete math', '数学建模': 'mathematical modeling',
    '量子力学': 'quantum mechanics', '电磁学': 'electromagnetism',
    '热力学': 'thermodynamics', '光学': 'optics',
    '相对论': 'relativity', '粒子物理': 'particle physics',
    '天体物理': 'astrophysics', '流体力学': 'fluid dynamics',
    '固体物理': 'solid state physics', '核物理': 'nuclear physics',
    '逻辑学': 'formal logic', '伦理学': 'ethics moral philosophy',
    '认识论': 'epistemology', '形而上学': 'metaphysics',
    '美学': 'aesthetics philosophy', '政治哲学': 'political philosophy',
    '科学哲学': 'philosophy of science', '存在主义': 'existentialism',
    '微观经济': 'microeconomics', '宏观经济': 'macroeconomics',
    '金融学': 'finance', '博弈论': 'game theory',
    '行为经济': 'behavioral economics', '国际贸易': 'international trade',
    '遗传学': 'genetics', '生态学': 'ecology',
    '进化论': 'evolution', '神经科学': 'neuroscience',
    '分子生物': 'molecular biology', '免疫学': 'immunology',
    '基因工程': 'genetic engineering', '细胞生物': 'cell biology',
    '认知心理': 'cognitive psychology', '发展心理': 'developmental psychology',
    '社会心理': 'social psychology', '临床心理': 'clinical psychology',
    '中国古代史': 'ancient China history', '世界史': 'world history',
    '中国近代史': 'modern China history',
    '中国古典文学': 'Chinese classical literature',
    '外国文学': 'world literature', '诗歌': 'poetry',
    '民法': 'civil law', '刑法': 'criminal law',
    '宪法学': 'constitutional law', '国际法': 'international law',
    '知识产权': 'intellectual property',
}


def clean_html(text):
    """去除 HTML 标签"""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


# ========== 维基百科 ==========
def wiki_get_summary(keyword):
    """中文维基百科摘要"""
    try:
        resp = requests.get(WIKI_API, params={
            'action': 'query', 'titles': keyword,
            'prop': 'extracts', 'exintro': True, 'explaintext': True,
            'format': 'json',
        }, headers=WIKI_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        pages = resp.json().get('query', {}).get('pages', {})
        for pid, page in pages.items():
            if pid == '-1':
                return None
            extract = page.get('extract', '').strip()
            if len(extract) > 50:
                return extract[:2000]
        return None
    except Exception:
        return None


def wiki_search(keyword, limit=10):
    """搜索维基百科相关词条标题"""
    try:
        resp = requests.get(WIKI_API, params={
            'action': 'query', 'list': 'search',
            'srsearch': keyword, 'srlimit': limit, 'format': 'json',
        }, headers=WIKI_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        return [r['title'] for r in resp.json().get('query', {}).get('search', [])]
    except Exception:
        return []


# ========== Stack Exchange ==========
def se_search(query, site='stackoverflow', pagesize=5):
    """Stack Exchange 搜索高赞问答"""
    try:
        resp = requests.get(f'{SE_API}/search/excerpts', params={
            'order': 'desc', 'sort': 'votes',
            'q': query, 'site': site, 'pagesize': pagesize,
        }, timeout=10)
        if resp.status_code != 200:
            return []
        items = resp.json().get('items', [])
        results = []
        for item in items:
            title = clean_html(item.get('title', ''))
            body = clean_html(item.get('excerpt', ''))
            if len(body) > 30:
                results.append({'title': title, 'body': body, 'type': item.get('item_type')})
        return results
    except Exception:
        return []


# ========== arXiv ==========
def arxiv_search(query, max_results=3):
    """arXiv 论文摘要"""
    try:
        resp = requests.get(ARXIV_API, params={
            'search_query': f'all:{query}',
            'max_results': max_results, 'sortBy': 'relevance',
        }, timeout=15)
        feed = feedparser.parse(resp.text)
        results = []
        for entry in feed.entries:
            title = entry.title.replace('\n', ' ').strip()
            abstract = entry.summary.replace('\n', ' ').strip()
            if len(abstract) > 50:
                results.append({'title': title, 'abstract': abstract})
        return results
    except Exception:
        return []


# ========== LLM ==========
def llm_generate_subtags(domain_name, tag_name):
    """千问生成3个细分子标签"""
    from app.services.qwen_service import qwen_service
    prompt = (
        f"为「{domain_name}」领域的「{tag_name}」列出3个细分子主题关键词。\n"
        f"要求：2-6个汉字，真实专业术语。严格JSON数组，无其他内容。\n"
        f'示例：["子主题A","子主题B","子主题C"]'
    )
    try:
        result = qwen_service.chat(prompt).strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1].rsplit('```', 1)[0]
        tags = json.loads(result)
        return [s.strip() for s in tags if isinstance(s, str) and 2 <= len(s.strip()) <= 12][:3]
    except Exception:
        return []


def llm_translate_and_summarize(title_en, body_en, domain_cn):
    """LLM 翻译英文社区内容为中文摘要"""
    from app.services.qwen_service import qwen_service
    prompt = (
        f"将以下{domain_cn}领域的英文知识社区内容翻译并整理为200-400字的中文知识摘要。\n"
        f"标题：{title_en}\n内容：{body_en[:600]}\n"
        f"要求：学术科普风格，直接输出中文摘要正文。"
    )
    try:
        return qwen_service.chat(prompt)
    except Exception:
        return None


def llm_generate_summary(tag_name, domain_name):
    """LLM 直接生成知识摘要"""
    from app.services.qwen_service import qwen_service
    prompt = (
        f"用200-400字介绍「{tag_name}」（{domain_name}领域）。"
        f"包含定义、核心要点、意义。学术科普风格，直接输出正文。"
    )
    try:
        return qwen_service.chat(prompt)
    except Exception:
        return None


# ========== 数据库操作 ==========
def get_or_create_tag(name, domain_id):
    tag = db.session.scalar(db.select(Tag).filter_by(name=name, domain_id=domain_id))
    if tag:
        return tag, False
    tag = Tag(name=name, domain_id=domain_id)
    db.session.add(tag)
    db.session.flush()
    return tag, True


def insert_post(title, content, summary, author_id, domain_id, tag_ids):
    if db.session.scalar(db.select(Post).filter_by(title=title)):
        return False
    post = Post(
        title=title[:250], content=content or summary,
        summary=(summary or '')[:500], author_id=author_id,
        domain_id=domain_id,
        view_count=random.randint(10, 500),
        like_count=random.randint(0, 50),
        created_at=datetime.now() - timedelta(days=random.randint(1, 180)),
    )
    db.session.add(post)
    db.session.flush()
    for tid in tag_ids:
        db.session.execute(post_tag.insert().values(post_id=post.id, tag_id=tid))
    return True


def main():
    app = create_app()
    with app.app_context():
        users = db.session.scalars(db.select(User)).all()
        if not users:
            print("错误: 数据库中没有用户")
            return

        domains = db.session.scalars(db.select(Domain)).all()
        domain_map = {d.id: d.name for d in domains}
        orig_tags = count_rows(Tag)
        orig_posts = count_rows(Post)
        stats = {'tags': 0, 'wiki': 0, 'se': 0, 'arxiv': 0, 'llm': 0}

        # ===== 1. LLM 生成子标签 =====
        print("===== 1/5 LLM 细化标签 =====")
        all_tags = db.session.scalars(db.select(Tag)).all()
        for i, tag in enumerate(all_tags):
            subtags = llm_generate_subtags(domain_map[tag.domain_id], tag.name)
            for st in subtags:
                _, created = get_or_create_tag(st, tag.domain_id)
                if created:
                    stats['tags'] += 1
            if subtags:
                print(f'  [{i+1}/{len(all_tags)}] {tag.name} → {subtags}')
            time.sleep(0.3)
            if (i + 1) % 20 == 0:
                db.session.commit()
        db.session.commit()
        print(f'  新增 {stats["tags"]} 个子标签 (总计 {count_rows(Tag)})\n')

        # ===== 2. 维基百科 =====
        print("===== 2/5 维基百科知识摘要 =====")
        all_tags = db.session.scalars(db.select(Tag)).all()
        for i, tag in enumerate(all_tags):
            summary = wiki_get_summary(tag.name)
            if summary:
                ok = insert_post(
                    title=f'{tag.name} - 知识百科',
                    content=summary, summary=summary[:300],
                    author_id=random.choice(users).id,
                    domain_id=tag.domain_id, tag_ids=[tag.id],
                )
                if ok:
                    stats['wiki'] += 1

            # 顺便搜相关词条，多抓几篇
            related = wiki_search(tag.name, limit=3)
            for rt in related:
                if rt == tag.name:
                    continue
                rs = wiki_get_summary(rt)
                if rs and len(rs) > 100:
                    ok = insert_post(
                        title=f'{rt} - 知识百科',
                        content=rs, summary=rs[:300],
                        author_id=random.choice(users).id,
                        domain_id=tag.domain_id, tag_ids=[tag.id],
                    )
                    if ok:
                        stats['wiki'] += 1
                time.sleep(0.2)

            time.sleep(0.3)
            if (i + 1) % 20 == 0:
                db.session.commit()
                print(f'  进度: {i+1}/{len(all_tags)}, 已爬 {stats["wiki"]} 篇')
        db.session.commit()
        print(f'  维基百科: {stats["wiki"]} 篇\n')

        # ===== 3. Stack Exchange =====
        print("===== 3/5 Stack Exchange 社区问答 =====")
        for tag in all_tags:
            en_kw = TAG_EN_MAP.get(tag.name)
            if not en_kw:
                continue
            site = SE_SITES.get(domain_map[tag.domain_id], 'stackoverflow')
            items = se_search(en_kw, site=site, pagesize=3)

            for item in items:
                # 用 LLM 翻译成中文摘要
                cn_summary = llm_translate_and_summarize(
                    item['title'], item['body'], domain_map[tag.domain_id]
                )
                if cn_summary:
                    prefix = '[问答]' if item['type'] == 'question' else '[精选回答]'
                    title = f'{prefix} {clean_html(item["title"])}'
                    ok = insert_post(
                        title=title, content=cn_summary, summary=cn_summary[:300],
                        author_id=random.choice(users).id,
                        domain_id=tag.domain_id, tag_ids=[tag.id],
                    )
                    if ok:
                        stats['se'] += 1
                time.sleep(0.5)

            time.sleep(1)  # SE 限流
            if stats['se'] % 10 == 0 and stats['se'] > 0:
                db.session.commit()
                print(f'  SE进度: {stats["se"]} 篇')
        db.session.commit()
        print(f'  Stack Exchange: {stats["se"]} 篇\n')

        # ===== 4. arXiv =====
        print("===== 4/5 arXiv 论文摘要 =====")
        stmt = (db.select(Tag)
                .join(Domain)
                .filter(Domain.name.in_(['计算机科学', '数学', '物理学', '生物学'])))
        stem_tags = db.session.scalars(stmt).all()
        sample = random.sample(stem_tags, min(50, len(stem_tags)))
        for tag in sample:
            papers = arxiv_search(tag.name, max_results=2)
            for p in papers:
                ok = insert_post(
                    title=f'[论文] {p["title"]}',
                    content=p['abstract'], summary=p['abstract'][:300],
                    author_id=random.choice(users).id,
                    domain_id=tag.domain_id, tag_ids=[tag.id],
                )
                if ok:
                    stats['arxiv'] += 1
            time.sleep(1)
        db.session.commit()
        print(f'  arXiv: {stats["arxiv"]} 篇\n')

        # ===== 5. LLM 补缺 =====
        print("===== 5/5 LLM 补充缺失标签 =====")
        covered = {r[1] for r in db.session.execute(post_tag.select()).fetchall()}
        all_tags = db.session.scalars(db.select(Tag)).all()
        missing = [t for t in all_tags if t.id not in covered]
        print(f'  还有 {len(missing)} 个标签无帖子，LLM补充...')
        for tag in missing:
            s = llm_generate_summary(tag.name, domain_map[tag.domain_id])
            if s:
                ok = insert_post(
                    title=f'{tag.name}：概念与要点',
                    content=s, summary=s[:300],
                    author_id=random.choice(users).id,
                    domain_id=tag.domain_id, tag_ids=[tag.id],
                )
                if ok:
                    stats['llm'] += 1
            time.sleep(0.3)
            if stats['llm'] % 20 == 0 and stats['llm'] > 0:
                db.session.commit()
        db.session.commit()
        print(f'  LLM补充: {stats["llm"]} 篇\n')

        # ===== Neo4j 同步 =====
        print("===== 同步 Neo4j =====")
        try:
            from app.services.neo4j_service import neo4j_service
            tags = db.session.scalars(db.select(Tag)).all()
            neo4j_service.run_write(
                "UNWIND $items AS i MERGE (t:Tag {id: i.id}) SET t.name = i.name",
                {"items": [{"id": t.id, "name": t.name} for t in tags]})
            neo4j_service.run_write(
                "UNWIND $items AS i MATCH (t:Tag {id: i.tid}), (d:Domain {id: i.did}) MERGE (t)-[:BELONGS_TO]->(d)",
                {"items": [{"tid": t.id, "did": t.domain_id} for t in tags]})
            posts = db.session.scalars(db.select(Post)).all()
            neo4j_service.run_write(
                "UNWIND $items AS i MERGE (p:Post {id: i.id}) SET p.title = i.title, p.summary = i.summary",
                {"items": [{"id": p.id, "title": p.title, "summary": p.summary} for p in posts]})
            neo4j_service.run_write(
                "UNWIND $items AS i MATCH (u:User {id: i.aid}), (p:Post {id: i.pid}) MERGE (u)-[:AUTHORED]->(p)",
                {"items": [{"aid": p.author_id, "pid": p.id} for p in posts]})
            pt = db.session.execute(post_tag.select()).fetchall()
            neo4j_service.run_write(
                "UNWIND $items AS i MATCH (p:Post {id: i.pid}), (t:Tag {id: i.tid}) MERGE (p)-[:TAGGED_WITH]->(t)",
                {"items": [{"pid": r[0], "tid": r[1]} for r in pt]})
            print('  同步完成')
        except Exception as e:
            print(f'  同步跳过: {e}')

        # ===== 汇总 =====
        total_new = stats['wiki'] + stats['se'] + stats['arxiv'] + stats['llm']
        print(f'\n{"="*50}')
        print(f'标签: {orig_tags} → {count_rows(Tag)} (+{stats["tags"]})')
        print(f'帖子: {orig_posts} → {count_rows(Post)} (+{total_new})')
        print(f'  维基百科: {stats["wiki"]}  |  Stack Exchange: {stats["se"]}')
        print(f'  arXiv: {stats["arxiv"]}  |  LLM补充: {stats["llm"]}')
        print(f'{"="*50}')


if __name__ == '__main__':
    main()
