import os
import uuid
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from app.utils.auth import login_required

upload_bp = Blueprint('upload', __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route('/image', methods=['POST'])
@login_required
def upload_image():
    """上传图片文件"""
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': '未选择文件'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': '仅支持 jpg/png/gif/webp 格式'}), 400

    # 检查文件大小
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'error': '文件大小不能超过 5MB'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file.save(os.path.join(UPLOAD_DIR, filename))

    url = f"/api/upload/files/{filename}"
    return jsonify({'url': url}), 201


@upload_bp.route('/files/<filename>', methods=['GET'])
def serve_file(filename):
    """静态文件服务"""
    return send_from_directory(UPLOAD_DIR, filename)
