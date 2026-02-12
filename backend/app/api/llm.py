from flask import Blueprint, request, jsonify
from ..services.qwen_service import qwen_service

llm_bp = Blueprint('llm', __name__)


@llm_bp.route('/chat', methods=['POST'])
def chat():
    """单轮对话接口"""
    data = request.get_json()
    message = data.get('message', '')
    if not message:
        return jsonify({"error": "message 不能为空"}), 400

    try:
        reply = qwen_service.chat(message)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@llm_bp.route('/extract_tags', methods=['POST'])
def extract_tags():
    """内容标签提取接口"""
    data = request.get_json()
    content = data.get('content', '')
    if not content:
        return jsonify({"error": "content 不能为空"}), 400

    try:
        result = qwen_service.extract_tags(content)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
