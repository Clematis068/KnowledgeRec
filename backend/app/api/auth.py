from flask import Blueprint, request, jsonify
from app import db
from app.models.user import User, user_tag
from app.models.tag import Tag
from app.models.domain import Domain
from app.utils.auth import generate_token, login_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """注册：username + password + gender + tag_ids"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    gender = data.get('gender')
    tag_ids = data.get('tag_ids', [])

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400
    if gender and gender not in ('male', 'female', 'other'):
        return jsonify({'error': '性别参数不合法'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 409

    user = User(username=username, gender=gender)
    user.set_password(password)

    # 绑定兴趣标签
    if tag_ids:
        tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
        user.interest_tags = tags

    db.session.add(user)
    db.session.commit()

    # 同步到 Neo4j（创建 User 节点 + INTERESTED_IN 标签关系）
    try:
        from app.services.neo4j_service import neo4j_service
        neo4j_service.run_write(
            "MERGE (u:User {id: $uid}) SET u.username = $name",
            {'uid': user.id, 'name': user.username}
        )
        if tag_ids:
            neo4j_service.run_write(
                "MATCH (u:User {id: $uid}) "
                "UNWIND $tids AS tid "
                "MATCH (t:Tag {id: tid}) "
                "MERGE (u)-[:INTERESTED_IN {weight: 1}]->(t)",
                {'uid': user.id, 'tids': tag_ids}
            )
    except Exception:
        pass  # Neo4j 可能未启动

    token = generate_token(user.id)
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """登录，返回 JWT + user"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    user = User.query.filter_by(username=username).first()
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
    domains = Domain.query.all()
    result = []
    for d in domains:
        tags = Tag.query.filter_by(domain_id=d.id).all()
        result.append({
            'domain': d.to_dict(),
            'tags': [t.to_dict() for t in tags],
        })
    return jsonify({'groups': result})
