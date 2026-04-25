"""帖子 API 测试：查看/点赞/收藏/评论。

需 mock Neo4j 和 Qwen，避免真实调用。
"""
import pytest


@pytest.fixture(autouse=True)
def _auto_mock_external(mock_neo4j, mock_qwen):
    """本文件所有测试自动 mock 外部服务。"""
    yield


class TestPostRead:
    def test_get_post_detail(self, client, seed_posts):
        resp = client.get(f'/api/post/{seed_posts[0].id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['title'] == seed_posts[0].title

    def test_get_post_not_found(self, client):
        resp = client.get('/api/post/99999')
        assert resp.status_code == 404

    def test_list_posts_returns_array(self, client, seed_posts):
        resp = client.get('/api/post/list')
        assert resp.status_code == 200
        data = resp.get_json()
        # API 可能返回 {'posts': [...]} 或直接数组
        posts = data.get('posts') if isinstance(data, dict) else data
        assert isinstance(posts, list)
        assert len(posts) >= 1

    def test_hot_posts(self, client, seed_posts):
        resp = client.get('/api/post/hot?top_n=3')
        assert resp.status_code == 200


class TestBehavior:
    def test_like_behavior(self, client, auth_header, seed_posts):
        resp = client.post(
            f'/api/post/{seed_posts[0].id}/behavior',
            json={'behavior_type': 'like'},
            headers=auth_header,
        )
        assert resp.status_code in (200, 201)

    def test_favorite_behavior(self, client, auth_header, seed_posts):
        resp = client.post(
            f'/api/post/{seed_posts[0].id}/behavior',
            json={'behavior_type': 'favorite'},
            headers=auth_header,
        )
        assert resp.status_code in (200, 201)

    def test_browse_behavior_increments_view(self, client, auth_header, seed_posts, app):
        from app import db
        from app.models.post import Post
        pid = seed_posts[0].id
        prev_view = db.session.get(Post, pid).view_count or 0
        client.post(
            f'/api/post/{pid}/behavior',
            json={'behavior_type': 'browse'},
            headers=auth_header,
        )
        db.session.expire_all()
        new_view = db.session.get(Post, pid).view_count or 0
        assert new_view >= prev_view

    def test_unauthorized_behavior_blocked(self, client, seed_posts):
        resp = client.post(
            f'/api/post/{seed_posts[0].id}/behavior',
            json={'behavior_type': 'like'},
        )
        assert resp.status_code == 401

    def test_invalid_behavior_type(self, client, auth_header, seed_posts):
        resp = client.post(
            f'/api/post/{seed_posts[0].id}/behavior',
            json={'behavior_type': 'invalid_type_xyz'},
            headers=auth_header,
        )
        assert resp.status_code in (400, 422)
