from flask import Blueprint, request, jsonify, g
from sqlalchemy import or_, and_, func, case
from app import db
from app.models.user import User
from app.models.notification import Notification, Message
from app.models.post import Post
from app.utils.auth import login_required

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/list', methods=['GET'])
@login_required
def list_notifications():
    """通知列表（分页，可按 type 筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    filter_type = request.args.get('type')  # system / interaction

    stmt = db.select(Notification).filter_by(user_id=g.current_user.id)

    if filter_type == 'system':
        stmt = stmt.filter(Notification.type == 'system')
    elif filter_type == 'interaction':
        stmt = stmt.filter(Notification.type.in_(['follow', 'like', 'favorite', 'comment']))

    stmt = stmt.order_by(Notification.created_at.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page)

    return jsonify({
        'notifications': [n.to_dict() for n in pagination.items],
        'total': pagination.total,
        'page': page,
    })


@notification_bp.route('/unread-count', methods=['GET'])
@login_required
def unread_count():
    """未读数（分 system/interaction/message 三类）"""
    user_id = g.current_user.id

    system_count = db.session.scalar(
        db.select(func.count()).select_from(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.type == 'system',
        )
    ) or 0

    interaction_count = db.session.scalar(
        db.select(func.count()).select_from(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.type.in_(['follow', 'like', 'favorite', 'comment']),
        )
    ) or 0

    message_count = db.session.scalar(
        db.select(func.count()).select_from(Message).filter(
            Message.receiver_id == user_id,
            Message.is_read == False,
        )
    ) or 0

    return jsonify({
        'system': system_count,
        'interaction': interaction_count,
        'message': message_count,
        'total': system_count + interaction_count + message_count,
    })


@notification_bp.route('/read/<int:notification_id>', methods=['PUT'])
@login_required
def mark_read(notification_id):
    """标记单条通知已读"""
    notification = db.session.scalar(db.select(Notification).filter_by(
        id=notification_id, user_id=g.current_user.id
    ))
    if not notification:
        return jsonify({'error': '通知不存在'}), 404

    notification.is_read = True
    db.session.commit()
    return jsonify({'message': '已标记已读'})


@notification_bp.route('/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """删除单条通知"""
    notification = db.session.scalar(db.select(Notification).filter_by(
        id=notification_id,
        user_id=g.current_user.id,
    ))
    if not notification:
        return jsonify({'error': '通知不存在'}), 404

    db.session.delete(notification)
    db.session.commit()
    return jsonify({'message': '已删除通知'})


@notification_bp.route('/read-all', methods=['PUT'])
@login_required
def mark_all_read():
    """全部已读"""
    filter_type = request.args.get('type')

    stmt = db.update(Notification).where(
        Notification.user_id == g.current_user.id,
        Notification.is_read == False,
    )

    if filter_type == 'system':
        stmt = stmt.where(Notification.type == 'system')
    elif filter_type == 'interaction':
        stmt = stmt.where(Notification.type.in_(['follow', 'like', 'favorite', 'comment']))

    stmt = stmt.values(is_read=True)
    db.session.execute(stmt)
    db.session.commit()
    return jsonify({'message': '已全部标记已读'})


@notification_bp.route('/messages', methods=['GET'])
@login_required
def message_conversations():
    """私信会话列表"""
    user_id = g.current_user.id

    # 找出与当前用户相关的所有对话方
    partner_ids_stmt = db.select(
        case(
            (Message.sender_id == user_id, Message.receiver_id),
            else_=Message.sender_id,
        ).label('partner_id')
    ).filter(
        or_(Message.sender_id == user_id, Message.receiver_id == user_id)
    ).distinct()

    partner_ids = [row[0] for row in db.session.execute(partner_ids_stmt).all()]

    conversations = []
    for pid in partner_ids:
        # 最新一条消息
        last_msg = db.session.scalar(
            db.select(Message).filter(
                or_(
                    and_(Message.sender_id == user_id, Message.receiver_id == pid),
                    and_(Message.sender_id == pid, Message.receiver_id == user_id),
                )
            ).order_by(Message.created_at.desc())
        )

        # 未读数
        unread = db.session.scalar(
            db.select(func.count()).select_from(Message).filter(
                Message.sender_id == pid,
                Message.receiver_id == user_id,
                Message.is_read == False,
            )
        ) or 0

        partner = db.session.get(User, pid)
        if not partner or not last_msg:
            continue

        conversations.append({
            'user_id': pid,
            'username': partner.username,
            'avatar_url': partner.avatar_url,
            'last_message': last_msg.content[:100] if last_msg.msg_type == 'text' else (
                '[图片]' if last_msg.msg_type == 'image' else '[帖子分享]'
            ),
            'last_time': last_msg.created_at.isoformat() if last_msg.created_at else None,
            'unread_count': unread,
        })

    # 按最后消息时间排序
    conversations.sort(key=lambda c: c['last_time'] or '', reverse=True)

    return jsonify({'conversations': conversations})


@notification_bp.route('/messages/<int:target_user_id>', methods=['GET'])
@login_required
def message_detail(target_user_id):
    """与某用户的对话详情"""
    user_id = g.current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 30, type=int)

    target = db.session.get(User, target_user_id)
    if not target:
        return jsonify({'error': '用户不存在'}), 404

    stmt = db.select(Message).filter(
        or_(
            and_(Message.sender_id == user_id, Message.receiver_id == target_user_id),
            and_(Message.sender_id == target_user_id, Message.receiver_id == user_id),
        )
    ).order_by(Message.created_at.desc())

    pagination = db.paginate(stmt, page=page, per_page=per_page)

    # 标记对方发来的消息为已读
    db.session.execute(
        db.update(Message).where(
            Message.sender_id == target_user_id,
            Message.receiver_id == user_id,
            Message.is_read == False,
        ).values(is_read=True)
    )
    db.session.commit()

    return jsonify({
        'messages': [m.to_dict() for m in reversed(pagination.items)],
        'total': pagination.total,
        'page': page,
        'target_user': {
            'id': target.id,
            'username': target.username,
            'avatar_url': target.avatar_url,
        },
    })


@notification_bp.route('/messages/<int:target_user_id>', methods=['POST'])
@login_required
def send_message(target_user_id):
    """发送私信"""
    user_id = g.current_user.id

    if user_id == target_user_id:
        return jsonify({'error': '不能给自己发私信'}), 400

    target = db.session.get(User, target_user_id)
    if not target:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json() or {}
    msg_type = data.get('msg_type', 'text')
    content = (data.get('content') or '').strip()
    image_url = data.get('image_url')
    linked_post_id = data.get('linked_post_id')

    if msg_type == 'image':
        if not image_url:
            return jsonify({'error': '图片消息必须包含图片URL'}), 400
        content = content or '[图片]'
    elif msg_type == 'post_link':
        if not linked_post_id:
            return jsonify({'error': '帖子链接消息必须包含帖子ID'}), 400
        post = db.session.get(Post, linked_post_id)
        if not post:
            return jsonify({'error': '帖子不存在'}), 404
        content = content or f'[分享帖子] {post.title}'
    else:
        msg_type = 'text'
        if not content:
            return jsonify({'error': '消息内容不能为空'}), 400

    msg = Message(
        sender_id=user_id,
        receiver_id=target_user_id,
        content=content,
        msg_type=msg_type,
        image_url=image_url if msg_type == 'image' else None,
        linked_post_id=linked_post_id if msg_type == 'post_link' else None,
    )
    db.session.add(msg)
    db.session.commit()

    msg_data = msg.to_dict()

    # WebSocket 实时推送
    try:
        from app.events import emit_to_user
        emit_to_user(target_user_id, 'new_message', msg_data)
        emit_to_user(user_id, 'message_sent', msg_data)
    except Exception:
        pass

    return jsonify(msg_data), 201
