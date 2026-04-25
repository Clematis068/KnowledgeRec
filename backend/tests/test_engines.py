"""六路召回引擎测试：在 mock Neo4j / Qwen 下验证返回格式与分数范围。"""
import pytest


@pytest.fixture(autouse=True)
def _auto_mock_external(mock_neo4j, mock_qwen):
    yield


def _assert_recall_shape(result):
    """召回结果应是 dict[int, float]，分数在 [0, 1]（min-max 归一化后）。"""
    assert isinstance(result, dict)
    for pid, score in result.items():
        assert isinstance(pid, int)
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0 + 1e-6


class TestHotEngine:
    def test_returns_dict(self, app, seed_posts):
        from app.services.recommendation.hot_engine import HotEngine
        result = HotEngine().recommend(user_id=None, top_n=10)
        _assert_recall_shape(result)
        assert len(result) >= 1

    def test_excludes_seen(self, app, seed_posts):
        from app.services.recommendation.hot_engine import HotEngine
        excl = {seed_posts[0].id}
        result = HotEngine().recommend(user_id=None, top_n=10, exclude_post_ids=excl)
        assert seed_posts[0].id not in result


class TestCFEngine:
    def test_no_behavior_returns_empty(self, app, seed_users):
        from app.services.recommendation.cf_engine import CFEngine
        result = CFEngine().recommend(user_id=seed_users[0].id, top_n=10)
        assert result == {}


class TestSwingEngine:
    def test_no_behavior_returns_empty(self, app, seed_users):
        from app.services.recommendation.swing_engine import SwingEngine
        result = SwingEngine().recommend(user_id=seed_users[0].id, top_n=10)
        assert result == {}


class TestGraphEngine:
    def test_with_mock_neo4j_returns_dict(self, app, seed_users):
        from app.services.recommendation.graph_engine import GraphEngine
        result = GraphEngine().recommend(user_id=seed_users[0].id, top_n=10)
        assert isinstance(result, dict)


class TestSemanticEngine:
    def test_returns_dict(self, app, seed_users, seed_posts):
        from app.services.recommendation.semantic_engine import SemanticEngine
        result = SemanticEngine().recommend(
            user_id=seed_users[0].id, top_n=10, enable_llm_rerank=False,
        )
        assert isinstance(result, dict)


class TestLogicEngine:
    def test_recall_returns_dict(self, app, seed_users):
        from app.services.recommendation.logic_constraint_engine import LogicConstraintEngine
        result = LogicConstraintEngine().recall(user_id=seed_users[0].id, top_n=10)
        assert isinstance(result, dict)

    def test_apply_empty_results(self, app, seed_users):
        from app.services.recommendation.logic_constraint_engine import LogicConstraintEngine
        out = LogicConstraintEngine().apply(user_id=seed_users[0].id, results=[])
        assert out == []
