"""性能测试：端到端接口响应时间回归基准。

使用 pytest-benchmark 或简单 time.perf_counter，设置宽松阈值避免 CI 波动误报。
在 SQLite in-memory + mock Neo4j/Qwen 下，响应应显著快于生产环境阈值。
"""
import time

import pytest


@pytest.fixture(autouse=True)
def _auto_mock(mock_neo4j, mock_qwen):
    yield


class TestResponseLatency:
    """关键接口的响应时间上限（测试环境，mock 外部依赖）。"""

    def test_login_under_500ms(self, client, seed_users):
        start = time.perf_counter()
        resp = client.post('/api/auth/login', json={
            'username': 'testuser0', 'password': 'password123',
        })
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f'login took {elapsed:.3f}s'

    def test_post_detail_under_300ms(self, client, seed_posts):
        start = time.perf_counter()
        resp = client.get(f'/api/post/{seed_posts[0].id}')
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.3, f'post detail took {elapsed:.3f}s'

    def test_post_list_under_500ms(self, client, seed_posts):
        start = time.perf_counter()
        resp = client.get('/api/post/list')
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f'post list took {elapsed:.3f}s'

    def test_hot_posts_under_500ms(self, client, seed_posts):
        start = time.perf_counter()
        resp = client.get('/api/post/hot?top_n=10')
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f'hot took {elapsed:.3f}s'


class TestRecallThroughput:
    """召回引擎吞吐量基准（单用户，mock 环境）。"""

    def test_hot_engine_under_200ms(self, app, seed_posts):
        from app.services.recommendation.hot_engine import HotEngine
        start = time.perf_counter()
        HotEngine().recommend(user_id=None, top_n=50)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f'hot engine took {elapsed:.3f}s'

    def test_feature_extract_batch_under_200ms(self, app, seed_users, seed_posts):
        from app.services.recommendation.feature_extractor import FeatureExtractor
        fe = FeatureExtractor()
        fe.warm_user_cache(seed_users[0].id)
        post_ids = [p.id for p in seed_posts]
        post_cache = {p.id: p for p in seed_posts}
        recall = {pid: {'cf': 0.5} for pid in post_ids}

        start = time.perf_counter()
        feats = fe.extract_batch(seed_users[0].id, post_ids, recall,
                                  {'region_code': None, 'time_slot': None}, post_cache)
        elapsed = time.perf_counter() - start
        assert len(feats) == len(post_ids)
        assert elapsed < 0.2, f'feature extract took {elapsed:.3f}s'
