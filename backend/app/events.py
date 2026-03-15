import jwt
from flask_socketio import disconnect
from app.socketio_instance import socketio
from app.config import Config

# sid → user_id 映射
_sid_to_uid = {}
# user_id → set(sid) 映射（一个用户可能开多个标签页）
_uid_to_sids = {}


@socketio.on('connect')
def handle_connect(auth_data=None):
    """WebSocket 连接时验证 JWT"""
    from flask import request as flask_request

    token = None
    # 优先从 auth 参数获取
    if auth_data and isinstance(auth_data, dict):
        token = auth_data.get('token')
    # 其次从 query string 获取
    if not token:
        token = flask_request.args.get('token')

    if not token:
        disconnect()
        return False

    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload['user_id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        disconnect()
        return False

    sid = flask_request.sid
    _sid_to_uid[sid] = user_id
    _uid_to_sids.setdefault(user_id, set()).add(sid)


@socketio.on('disconnect')
def handle_disconnect():
    """清除映射"""
    from flask import request as flask_request

    sid = flask_request.sid
    user_id = _sid_to_uid.pop(sid, None)
    if user_id and user_id in _uid_to_sids:
        _uid_to_sids[user_id].discard(sid)
        if not _uid_to_sids[user_id]:
            del _uid_to_sids[user_id]


def emit_to_user(user_id, event, data):
    """向指定用户的所有连接推送事件"""
    sids = _uid_to_sids.get(user_id, set())
    for sid in sids:
        socketio.emit(event, data, to=sid)
