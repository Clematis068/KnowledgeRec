"""Pytest 共享 fixture。

使用 SQLite in-memory 作为测试数据库，mock 掉 Neo4j / Qwen / Aliyun 等外部服务，
保证测试快速、可重复、无外部依赖。
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 强制使用 SQLite in-memory，避免测试连接真实 MySQL ──
os.environ['MYSQL_URI'] = 'sqlite:///:memory:'
os.environ['REDIS_URL'] = 'redis://localhost:6379/15'  # DB 15 作为测试库
os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
os.environ['DASHSCOPE_API_KEY'] = 'test-key'
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret'


@pytest.fixture(scope='session')
def app():
    """测试用 Flask app，全局只创建一次。"""
    from app import create_app, db
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    """每个测试独立的 session，结束回滚。"""
    from app import db
    connection = db.engine.connect()
    transaction = connection.begin()
    yield db.session
    db.session.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def mock_neo4j(monkeypatch):
    """Mock Neo4j，默认所有查询返回空列表。"""
    from app.services import neo4j_service

    calls = []

    def fake_run_query(cypher, params=None):
        calls.append((cypher, params))
        return []

    def fake_run_write(cypher, params=None):
        calls.append(('WRITE', cypher, params))
        return None

    monkeypatch.setattr(neo4j_service.neo4j_service, 'run_query', fake_run_query)
    monkeypatch.setattr(neo4j_service.neo4j_service, 'run_write', fake_run_write)
    return calls


@pytest.fixture()
def mock_qwen(monkeypatch):
    """Mock 千问 API，embedding 返回固定 4 维向量；chat 返回定长文本。"""
    from app.services import qwen_service

    monkeypatch.setattr(
        qwen_service.qwen_service, 'get_embedding',
        lambda text: [0.1, 0.2, 0.3, 0.4],
    )
    monkeypatch.setattr(
        qwen_service.qwen_service, 'chat',
        lambda *args, **kwargs: 'mocked response',
    )
    monkeypatch.setattr(
        qwen_service.qwen_service, 'chat_json',
        lambda *args, **kwargs: {},
    )


@pytest.fixture(scope='session')
def seed_domain(app):
    from app import db
    from app.models.domain import Domain
    d = Domain(name='测试领域', description='测试用')
    db.session.add(d)
    db.session.commit()
    return d


@pytest.fixture(scope='session')
def seed_tags(app, seed_domain):
    from app import db
    from app.models.tag import Tag
    tags = [
        Tag(name='Python', domain_id=seed_domain.id, embedding=[0.1] * 4),
        Tag(name='推荐系统', domain_id=seed_domain.id, embedding=[0.2] * 4),
        Tag(name='机器学习', domain_id=seed_domain.id, embedding=[0.3] * 4),
    ]
    db.session.add_all(tags)
    db.session.commit()
    return tags


@pytest.fixture(scope='session')
def seed_users(app):
    from app import db
    from app.models.user import User
    users = []
    for i in range(3):
        u = User(
            username=f'testuser{i}',
            email=f'test{i}@example.com',
        )
        u.set_password('password123')
        users.append(u)
    db.session.add_all(users)
    db.session.commit()
    return users


@pytest.fixture(scope='session')
def seed_posts(app, seed_users, seed_domain, seed_tags):
    from app import db
    from app.models.post import Post
    posts = []
    for i in range(5):
        p = Post(
            title=f'测试帖子{i}',
            content=f'内容{i}' * 20,
            author_id=seed_users[i % 3].id,
            domain_id=seed_domain.id,
            status='published',
            content_embedding=[0.1 * (i + 1)] * 4,
        )
        p.tags = [seed_tags[i % 3]]
        posts.append(p)
    db.session.add_all(posts)
    db.session.commit()
    return posts


@pytest.fixture(scope='session')
def auth_token(seed_users):
    """为 seed_users[0] 生成可用 JWT。"""
    from app.utils.auth import generate_token
    return generate_token(seed_users[0].id)


@pytest.fixture(scope='session')
def auth_header(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}
