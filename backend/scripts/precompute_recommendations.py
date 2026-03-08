"""
离线预计算：物品相似度矩阵
用法: cd backend && uv run python -m scripts.precompute_recommendations
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.services.recommendation import recommendation_engine

app = create_app()

with app.app_context():
    print("===== 离线预计算 =====")
    recommendation_engine.precompute()
    print("===== 完成 =====")
