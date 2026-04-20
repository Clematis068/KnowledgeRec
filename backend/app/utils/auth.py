import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, g, jsonify
from app.config import Config


def generate_token(user_id: int) -> str:
    """签发 JWT Token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')


def _decode_token(token: str) -> dict | None:
    """解码 JWT，失败返回 None"""
    try:
        return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _get_current_user():
    """从请求头解析当前用户，成功设置 g.current_user"""
    from app.models.user import User
    from app import db

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    payload = _decode_token(auth_header[7:])
    if not payload:
        return None

    user = db.session.get(User, payload['user_id'])
    return user


def login_required(f):
    """必须登录才能访问的装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = _get_current_user()
        if not user:
            return jsonify({'error': '请先登录'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = _get_current_user()
        if not user:
            return jsonify({'error': '请先登录'}), 401
        if getattr(user, 'role', 'user') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def optional_login(f):
    """可选登录装饰器，未登录时 g.current_user = None"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        g.current_user = _get_current_user()
        return f(*args, **kwargs)
    return wrapper
