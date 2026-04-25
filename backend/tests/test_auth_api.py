"""认证 API 测试：注册/登录/JWT/封禁检查。"""
import pytest


class TestLogin:
    def test_login_success(self, client, seed_users):
        resp = client.post('/api/auth/login', json={
            'username': 'testuser0',
            'password': 'password123',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'token' in data
        assert data['user']['username'] == 'testuser0'

    def test_login_wrong_password(self, client, seed_users):
        resp = client.post('/api/auth/login', json={
            'username': 'testuser0',
            'password': 'WRONG',
        })
        assert resp.status_code == 401
        assert '错误' in resp.get_json()['error']

    def test_login_nonexistent_user(self, client):
        resp = client.post('/api/auth/login', json={
            'username': 'nobody',
            'password': 'anything',
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post('/api/auth/login', json={})
        assert resp.status_code == 400

    def test_login_banned_user(self, client, seed_users, app):
        from app import db
        seed_users[0].status = 'banned'
        db.session.commit()
        resp = client.post('/api/auth/login', json={
            'username': 'testuser0',
            'password': 'password123',
        })
        assert resp.status_code == 403
        # 还原
        seed_users[0].status = 'active'
        db.session.commit()


class TestMe:
    def test_me_with_valid_token(self, client, auth_header):
        resp = client.get('/api/auth/me', headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['username'] == 'testuser0'

    def test_me_without_token(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401

    def test_me_with_invalid_token(self, client):
        resp = client.get('/api/auth/me', headers={'Authorization': 'Bearer BAD.TOKEN'})
        assert resp.status_code == 401


class TestJWT:
    def test_token_roundtrip(self, seed_users):
        from app.utils.auth import generate_token, _decode_token
        token = generate_token(seed_users[0].id)
        payload = _decode_token(token)
        assert payload['user_id'] == seed_users[0].id

    def test_decode_invalid_returns_none(self):
        from app.utils.auth import _decode_token
        assert _decode_token('bogus.token.string') is None

    def test_password_hash_roundtrip(self, seed_users):
        assert seed_users[0].check_password('password123')
        assert not seed_users[0].check_password('wrong')
