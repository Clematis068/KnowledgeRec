"""
爬取真实帖子数据：百度百科 + arXiv
用法: cd backend && uv run python -m scripts.crawl_real_posts

数据源:
  - 百度百科: 所有10个领域100个标签的词条内容
  - arXiv: 计算机/数学/物理 领域的论文摘要
目标: ~500篇真实帖子
"""
import sys
import os
import re
import time
import random
import urllib.parse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from bs4 import BeautifulSoup
import feedparser

from app import create_app, db
from app.models.post import Post, post_tag
from app.models.tag import Tag
from app.models.domain import Domain
from app.models.user import User

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# arXiv 标签名 -> 搜索关键词映射
ARXIV_KEYWORDS = {
    '机器学习': 'machine learning',
    '深度学习': 'deep learning',
    '自然语言处理': 'natural language processing',
    '计算机视觉': 'computer vision',
    '数据库': 'database systems',
    '分布式系统': 'distributed systems',
    '网络安全': 'cybersecurity',
    '算法设计': 'algorithm design',
    '编程语言': 'programming languages',
    '操作系统': 'operating system kernel',
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
}

# 百度百科关键词扩展（每个标签多搜几个词条）
BAIKE_EXTRA_KEYWORDS = {
    '机器学习': ['支持向量机', '随机森林', '梯度提升'],
    '深度学习': ['卷积神经网络', '循环神经网络', 'Transformer'],
    '自然语言处理': ['词向量', '文本分类', '机器翻译'],
    '计算机视觉': ['目标检测', '图像分割', '人脸识别'],
    '数据库': ['关系数据库', 'MySQL', 'Redis'],
    '操作系统': ['进程管理', '内存管理', 'Linux内核'],
    '算法设计': ['动态规划', '贪心算法', '分治法'],
    '分布式系统': ['CAP定理', '一致性算法', 'MapReduce'],
    '网络安全': ['SQL注入', 'XSS攻击', '密码学'],
    '编程语言': ['Python', 'Rust语言', '函数式编程'],
    '线性代数': ['矩阵分解', '特征值', '奇异值分解'],
    '概率论': ['贝叶斯定理', '马尔可夫链', '大数定律'],
    '数论': ['素数', '费马大定理', '模运算'],
    '微积分': ['泰勒展开', '傅里叶变换', '微分方程'],
    '统计学': ['假设检验', '回归分析', '方差分析'],
    '量子力学': ['薛定谔方程', '量子纠缠', '测不准原理'],
    '电磁学': ['麦克斯韦方程组', '电磁波', '法拉第电磁感应'],
    '热力学': ['熵', '卡诺循环', '热力学第二定律'],
    '相对论': ['时间膨胀', '引力波', '黑洞'],
    '逻辑学': ['命题逻辑', '谓词逻辑', '哥德尔不完备定理'],
    '伦理学': ['功利主义', '义务论', '美德伦理'],
    '微观经济': ['供给需求', '边际效用', '市场均衡'],
    '宏观经济': ['GDP', '通货膨胀', '失业率'],
    '金融学': ['资本资产定价模型', '期权定价', '风险管理'],
    '遗传学': ['DNA双螺旋', '基因突变', '孟德尔遗传'],
    '生态学': ['生态系统', '食物链', '生物多样性'],
    '进化论': ['自然选择', '物种起源', '基因漂变'],
    '认知心理': ['工作记忆', '注意力', '认知偏差'],
    '发展心理': ['皮亚杰', '依恋理论', '道德发展'],
    '社会心理': ['从众效应', '服从实验', '群体极化'],
    '中国古代史': ['秦始皇', '唐朝', '科举制度'],
    '中国近代史': ['鸦片战争', '辛亥革命', '五四运动'],
    '世界史': ['文艺复兴', '工业革命', '法国大革命'],
    '中国古典文学': ['诗经', '红楼梦', '唐诗'],
    '现当代文学': ['鲁迅', '莫言', '余华'],
    '外国文学': ['莎士比亚', '卡夫卡', '百年孤独'],
    '宪法学': ['违宪审查', '基本权利', '宪法修正案'],
    '民法': ['物权法', '合同法', '侵权责任'],
    '刑法': ['犯罪构成', '正当防卫', '刑罚'],
    '知识产权': ['专利法', '著作权', '商标法'],
}


def crawl_baike(keyword):
    """爬取百度百科词条，返回 (title, content, summary) 或 None"""
    url = f'https://baike.baidu.com/item/{urllib.parse.quote(keyword)}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'utf-8'
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'lxml')

        # 标题
        title_el = soup.select_one('h1')
        title = title_el.get_text(strip=True) if title_el else keyword

        # 摘要（第一段）
        summary_el = soup.select_one('.lemma-summary, .lemmaWgt-lemmaSummary')
        summary = ''
        if summary_el:
            summary = summary_el.get_text(strip=True)[:300]

        # 正文内容（多个段落）
        content_parts = []
        # 尝试多种选择器适配百度百科不同版本
        for sel in ['.para-title, .para', '.content-section .J-lemma-content div[class*="para"]',
                    '.main-content .para', '.lemma-main-content .para']:
            paras = soup.select(sel)
            if paras:
                for p in paras:
                    text = p.get_text(strip=True)
                    # 过滤过短或纯数字引用
                    text = re.sub(r'\[\d+\]', '', text)
                    if len(text) > 20:
                        content_parts.append(text)
                break

        if not content_parts:
            # 降级：取所有 class 含 para 的 div
            for div in soup.find_all('div', class_=re.compile(r'para')):
                text = re.sub(r'\[\d+\]', '', div.get_text(strip=True))
                if len(text) > 20:
                    content_parts.append(text)

        content = '\n\n'.join(content_parts[:15])  # 取前15段

        if len(content) < 100:
            return None

        # 截断过长内容
        if len(content) > 3000:
            content = content[:3000] + '...'

        if not summary:
            summary = content[:200]

        return title, content, summary

    except Exception as e:
        print(f'    [百度百科] {keyword} 失败: {e}')
        return None


def crawl_arxiv(query, max_results=5):
    """通过 arXiv API 搜索论文，返回 [(title, abstract)] """
    base_url = 'http://export.arxiv.org/api/query'
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
    }
    try:
        resp = requests.get(base_url, params=params, timeout=15)
        feed = feedparser.parse(resp.text)
        results = []
        for entry in feed.entries:
            title = entry.title.replace('\n', ' ').strip()
            abstract = entry.summary.replace('\n', ' ').strip()
            if len(abstract) > 50:
                results.append((title, abstract))
        return results
    except Exception as e:
        print(f'    [arXiv] {query} 失败: {e}')
        return []


def get_random_author(users):
    """随机选一个已有用户作为作者"""
    return random.choice(users).id


def insert_post(title, content, summary, author_id, domain_id, tag_ids):
    """插入一篇帖子到数据库"""
    # 去重：同标题不重复插入
    if Post.query.filter_by(title=title).first():
        return False

    post = Post(
        title=title,
        content=content,
        summary=summary[:500] if summary else None,
        author_id=author_id,
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
        users = User.query.all()
        if not users:
            print("错误: 数据库中没有用户，请先运行 generate_mock_data.py")
            return

        tags = Tag.query.all()
        tag_map = {t.name: t for t in tags}
        total_inserted = 0

        # ===== 1. 百度百科 =====
        print("===== 百度百科爬取 =====")
        for tag in tags:
            # 先爬标签本身
            keywords = [tag.name]
            # 再加扩展关键词
            extras = BAIKE_EXTRA_KEYWORDS.get(tag.name, [])
            keywords.extend(extras)

            for kw in keywords:
                result = crawl_baike(kw)
                if result:
                    title, content, summary = result
                    # 给标题加上知识社区风格
                    if title == kw and len(title) < 10:
                        title = f'{kw}：核心概念与前沿发展'

                    ok = insert_post(
                        title=title,
                        content=content,
                        summary=summary,
                        author_id=get_random_author(users),
                        domain_id=tag.domain_id,
                        tag_ids=[tag.id],
                    )
                    if ok:
                        total_inserted += 1
                        print(f'  [{total_inserted}] 百科: {title[:40]}')

                time.sleep(0.5)  # 限流

            # 每个标签处理完提交一次
            db.session.commit()

        print(f'\n百度百科爬取完成: {total_inserted} 篇')

        # ===== 2. arXiv =====
        print("\n===== arXiv 爬取 =====")
        arxiv_count = 0
        for tag_name, en_query in ARXIV_KEYWORDS.items():
            tag = tag_map.get(tag_name)
            if not tag:
                continue

            papers = crawl_arxiv(en_query, max_results=5)
            for paper_title, abstract in papers:
                # 给 arXiv 论文加中文前缀方便识别
                title = f'[论文] {paper_title}'
                if len(title) > 200:
                    title = title[:200]

                ok = insert_post(
                    title=title,
                    content=abstract,
                    summary=abstract[:300],
                    author_id=get_random_author(users),
                    domain_id=tag.domain_id,
                    tag_ids=[tag.id],
                )
                if ok:
                    arxiv_count += 1
                    total_inserted += 1
                    print(f'  [{total_inserted}] arXiv: {title[:50]}')

            time.sleep(1)  # arXiv 限流
            db.session.commit()

        print(f'\narXiv爬取完成: {arxiv_count} 篇')

        # ===== 同步到 Neo4j =====
        print("\n===== 同步新帖子到 Neo4j =====")
        try:
            from app.services.neo4j_service import neo4j_service

            # 新帖子节点
            new_posts = Post.query.filter(Post.content_embedding.is_(None)).all()
            if new_posts:
                neo4j_service.run_write(
                    "UNWIND $items AS item MERGE (p:Post {id: item.id}) "
                    "SET p.title = item.title, p.summary = item.summary",
                    {"items": [{"id": p.id, "title": p.title, "summary": p.summary} for p in new_posts]},
                )
                # Author 关系
                neo4j_service.run_write(
                    "UNWIND $items AS item "
                    "MATCH (u:User {id: item.author_id}), (p:Post {id: item.post_id}) "
                    "MERGE (u)-[:AUTHORED]->(p)",
                    {"items": [{"author_id": p.author_id, "post_id": p.id} for p in new_posts]},
                )
                # Tag 关系
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
                print(f"  Neo4j 同步完成: {len(new_posts)} 篇新帖子")
        except Exception as e:
            print(f"  Neo4j 同步跳过: {e}")

        print(f"\n===== 总计新增 {total_inserted} 篇真实帖子 =====")
        print(f"数据库帖子总数: {Post.query.count()}")


if __name__ == '__main__':
    main()
