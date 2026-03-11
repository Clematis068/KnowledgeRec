import random
import re

from flask import Blueprint, request, jsonify

from app import db
from app.models.user import User, user_tag
from app.models.tag import Tag
from app.models.domain import Domain
from app.services.mail_service import mail_service
from app.services.redis_service import redis_service
from app.services.tag_taxonomy_service import tag_taxonomy_service
from app.utils.auth import generate_token, login_required

auth_bp = Blueprint('auth', __name__)

EMAIL_CODE_TTL = 600
EMAIL_VERIFIED_TTL = 1800
EMAIL_SEND_COOLDOWN = 60
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _email_code_key(email):
    return f'email_code:register:{email.lower()}'


def _email_verified_key(email):
    return f'email_verified:register:{email.lower()}'


def _email_cooldown_key(email):
    return f'email_code_cooldown:register:{email.lower()}'


def _password_reset_code_key(email):
    return f'email_code:reset_password:{email.lower()}'


def _password_reset_verified_key(email):
    return f'email_verified:reset_password:{email.lower()}'


def _password_reset_cooldown_key(email):
    return f'email_code_cooldown:reset_password:{email.lower()}'


def _is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email or ''))


def _generate_email_code():
    return ''.join(str(random.randint(0, 9)) for _ in range(6))


@auth_bp.route('/register', methods=['POST'])
def register():
    """注册：username + password + gender + email + tag_ids"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    gender = data.get('gender')
    email = data.get('email', '').strip().lower()
    tag_ids = data.get('tag_ids', [])

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400
    if not email:
        return jsonify({'error': '邮箱不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    if gender and gender not in ('male', 'female', 'other'):
        return jsonify({'error': '性别参数不合法'}), 400

    if db.session.scalar(db.select(User).filter_by(username=username)):
        return jsonify({'error': '用户名已存在'}), 409
    if db.session.scalar(db.select(User).filter_by(email=email)):
        return jsonify({'error': '邮箱已被注册'}), 409
    if redis_service.get_value(_email_verified_key(email)) != '1':
        return jsonify({'error': '请先完成邮箱验证'}), 400

    user = User(username=username, gender=gender, email=email)
    user.set_password(password)

    # 绑定兴趣标签
    if tag_ids:
        stmt = db.select(Tag).filter(Tag.id.in_(tag_ids))
        tags = db.session.scalars(stmt).all()
        user.interest_tags = tags

    db.session.add(user)
    db.session.commit()

    tag_taxonomy_service.sync_user_interest_tags(user)
    redis_service.delete(_email_verified_key(email))
    redis_service.delete(_email_code_key(email))
    redis_service.delete(_email_cooldown_key(email))

    token = generate_token(user.id)
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@auth_bp.route('/send-email-code', methods=['POST'])
def send_email_code():
    """发送注册邮箱验证码"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': '邮箱不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    if db.session.scalar(db.select(User).filter_by(email=email)):
        return jsonify({'error': '邮箱已被注册'}), 409

    cooldown_key = _email_cooldown_key(email)
    if redis_service.get_value(cooldown_key):
        return jsonify({'error': '验证码发送过于频繁，请稍后再试'}), 429

    code = _generate_email_code()
    redis_service.set_value(_email_code_key(email), code, ttl=EMAIL_CODE_TTL)
    redis_service.set_value(cooldown_key, '1', ttl=EMAIL_SEND_COOLDOWN)
    redis_service.delete(_email_verified_key(email))

    send_result = mail_service.send_verification_code(email, code)
    payload = {'message': '验证码已发送'}
    if send_result.get('mode') == 'dev':
        payload['dev_code'] = code
    return jsonify(payload)


@auth_bp.route('/send-reset-password-code', methods=['POST'])
def send_reset_password_code():
    """发送找回密码邮箱验证码"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': '邮箱不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user:
        return jsonify({'error': '该邮箱尚未注册'}), 404

    cooldown_key = _password_reset_cooldown_key(email)
    if redis_service.get_value(cooldown_key):
        return jsonify({'error': '验证码发送过于频繁，请稍后再试'}), 429

    code = _generate_email_code()
    redis_service.set_value(_password_reset_code_key(email), code, ttl=EMAIL_CODE_TTL)
    redis_service.set_value(cooldown_key, '1', ttl=EMAIL_SEND_COOLDOWN)
    redis_service.delete(_password_reset_verified_key(email))

    send_result = mail_service.send_password_reset_code(email, code)
    payload = {'message': '验证码已发送'}
    if send_result.get('mode') == 'dev':
        payload['dev_code'] = code
    return jsonify(payload)


@auth_bp.route('/verify-email-code', methods=['POST'])
def verify_email_code():
    """校验注册邮箱验证码"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({'error': '邮箱和验证码不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    cached_code = redis_service.get_value(_email_code_key(email))
    if not cached_code:
        return jsonify({'error': '验证码已过期，请重新发送'}), 400
    if cached_code != code:
        return jsonify({'error': '验证码错误'}), 400

    redis_service.set_value(_email_verified_key(email), '1', ttl=EMAIL_VERIFIED_TTL)
    redis_service.delete(_email_code_key(email))
    return jsonify({'message': '邮箱验证通过', 'verified': True})


@auth_bp.route('/verify-reset-password-code', methods=['POST'])
def verify_reset_password_code():
    """校验找回密码邮箱验证码"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({'error': '邮箱和验证码不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user:
        return jsonify({'error': '该邮箱尚未注册'}), 404

    cached_code = redis_service.get_value(_password_reset_code_key(email))
    if not cached_code:
        return jsonify({'error': '验证码已过期，请重新发送'}), 400
    if cached_code != code:
        return jsonify({'error': '验证码错误'}), 400

    redis_service.set_value(_password_reset_verified_key(email), '1', ttl=EMAIL_VERIFIED_TTL)
    redis_service.delete(_password_reset_code_key(email))
    return jsonify({'message': '邮箱验证通过', 'verified': True})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """通过邮箱验证码重置密码"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': '邮箱和新密码不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400
    if redis_service.get_value(_password_reset_verified_key(email)) != '1':
        return jsonify({'error': '请先完成邮箱验证'}), 400

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user:
        return jsonify({'error': '该邮箱尚未注册'}), 404

    user.set_password(password)
    db.session.commit()

    redis_service.delete(_password_reset_verified_key(email))
    redis_service.delete(_password_reset_code_key(email))
    redis_service.delete(_password_reset_cooldown_key(email))
    return jsonify({'message': '密码重置成功'})


@auth_bp.route('/mail/status', methods=['GET'])
def get_mail_status():
    """查看当前邮件服务配置状态"""
    return jsonify(mail_service.get_status())


@auth_bp.route('/mail/test', methods=['POST'])
def send_test_email():
    """发送测试邮件，用于验证 SMTP 配置是否可用"""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    subject = (data.get('subject') or 'KnowledgeRec 邮件服务测试').strip()
    content = (data.get('content') or '').strip()

    if not email:
        return jsonify({'error': '邮箱不能为空'}), 400
    if not _is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    if not content:
        content = (
            '这是一封来自 KnowledgeRec 的测试邮件。\n\n'
            '如果你收到这封邮件，说明当前 SMTP 配置已经可以正常发送。'
        )

    result = mail_service.send_text_email(email, subject, content)
    payload = {
        'message': '测试邮件已发送',
        'mode': result.get('mode'),
        'email': email,
    }
    return jsonify(payload)


@auth_bp.route('/login', methods=['POST'])
def login():
    """登录，返回 JWT + user"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    user = db.session.scalar(db.select(User).filter_by(username=username))
    if not user or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401

    token = generate_token(user.id)
    return jsonify({'token': token, 'user': user.to_dict()})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    """获取当前用户信息"""
    from flask import g
    return jsonify(g.current_user.to_dict())


@auth_bp.route('/tags', methods=['GET'])
def get_registration_tags():
    """按领域分组的全部标签（注册页用）"""
    domains = db.session.scalars(db.select(Domain).order_by(Domain.id.asc())).all()
    result = []
    for d in domains:
        stmt = db.select(Tag).filter_by(domain_id=d.id).order_by(Tag.name.asc())
        tags = db.session.scalars(stmt).all()
        result.append({
            'domain': d.to_dict(),
            'tags': [t.to_dict() for t in tags],
        })
    return jsonify({'groups': result})


@auth_bp.route('/domains', methods=['GET'])
def get_domains():
    """全部一级领域（发帖、筛选等使用）"""
    domains = db.session.scalars(db.select(Domain).order_by(Domain.id.asc())).all()
    return jsonify({'domains': [domain.to_dict() for domain in domains]})
