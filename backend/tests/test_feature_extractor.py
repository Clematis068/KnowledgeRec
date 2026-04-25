"""18 维特征提取器测试：验证输出维度、类型、默认值。"""
import pytest


@pytest.fixture(autouse=True)
def _auto_mock(mock_neo4j, mock_qwen):
    yield


class TestFeatureExtractor:
    def test_output_shape_is_18_dim(self, app, seed_users, seed_posts):
        from app.services.recommendation.feature_extractor import FeatureExtractor
        fe = FeatureExtractor()
        fe.warm_user_cache(seed_users[0].id)

        post_ids = [p.id for p in seed_posts[:3]]
        post_cache = {p.id: p for p in seed_posts[:3]}
        recall_scores = {
            pid: {'cf': 0.5, 'swing': 0.3, 'graph': 0.2,
                  'semantic': 0.8, 'knowledge': 0.1, 'hot': 0.4}
            for pid in post_ids
        }
        context = {'region_code': None, 'time_slot': None}

        feats = fe.extract_batch(seed_users[0].id, post_ids, recall_scores, context, post_cache)

        assert len(feats) == 3
        for row in feats:
            assert len(row) == 18
            assert all(isinstance(v, (int, float)) for v in row)

    def test_missing_scores_default_zero(self, app, seed_users, seed_posts):
        from app.services.recommendation.feature_extractor import FeatureExtractor
        fe = FeatureExtractor()
        fe.warm_user_cache(seed_users[0].id)

        post_ids = [seed_posts[0].id]
        post_cache = {seed_posts[0].id: seed_posts[0]}
        feats = fe.extract_batch(
            seed_users[0].id, post_ids, {post_ids[0]: {}},
            {'region_code': None, 'time_slot': None}, post_cache,
        )
        # 前6维（6路召回分）应全 0
        assert feats[0][:6] == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # source_count 也应为 0
        assert feats[0][6] == 0.0

    def test_max_recall_is_max_of_six(self, app, seed_users, seed_posts):
        from app.services.recommendation.feature_extractor import FeatureExtractor
        fe = FeatureExtractor()
        fe.warm_user_cache(seed_users[0].id)

        scores = {'cf': 0.2, 'swing': 0.9, 'graph': 0.1, 'semantic': 0.5, 'knowledge': 0.3, 'hot': 0.4}
        feats = fe.extract_batch(
            seed_users[0].id, [seed_posts[0].id],
            {seed_posts[0].id: scores},
            {'region_code': None, 'time_slot': None},
            {seed_posts[0].id: seed_posts[0]},
        )
        assert feats[0][17] == pytest.approx(0.9)
