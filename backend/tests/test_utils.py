"""工具函数单元测试：余弦相似度、归一化、内容过滤。"""
import pytest

from app.utils.helpers import cosine_similarity, min_max_normalize


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1, 2, 3], [-1, -2, -3]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_different_magnitudes_same_direction(self):
        assert cosine_similarity([1, 0], [100, 0]) == pytest.approx(1.0)


class TestMinMaxNormalize:
    def test_empty_dict(self):
        assert min_max_normalize({}) == {}

    def test_all_same_values(self):
        result = min_max_normalize({'a': 5, 'b': 5, 'c': 5})
        assert result == {'a': 0.5, 'b': 0.5, 'c': 0.5}

    def test_normal_distribution(self):
        result = min_max_normalize({'a': 0, 'b': 5, 'c': 10})
        assert result['a'] == pytest.approx(0.0)
        assert result['b'] == pytest.approx(0.5)
        assert result['c'] == pytest.approx(1.0)

    def test_negative_values(self):
        result = min_max_normalize({'a': -10, 'b': 0, 'c': 10})
        assert result['a'] == pytest.approx(0.0)
        assert result['c'] == pytest.approx(1.0)

    def test_single_entry(self):
        result = min_max_normalize({'a': 42})
        assert result == {'a': 0.5}


class TestContentFilter:
    def test_block_helpers_return_set(self, app, seed_users):
        from app.utils.content_filter import get_blocked_author_ids, get_blocked_domain_ids
        result_author = get_blocked_author_ids(seed_users[0].id)
        result_domain = get_blocked_domain_ids(seed_users[0].id)
        assert isinstance(result_author, set)
        assert isinstance(result_domain, set)

    def test_filter_posts_none_user(self, app, seed_posts):
        from app.utils.content_filter import filter_posts
        result = filter_posts(seed_posts, None)
        assert len(result) == len(seed_posts)
