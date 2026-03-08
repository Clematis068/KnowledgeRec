"""
数据库初始化脚本
用法: cd backend && uv run python -m scripts.init_db
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models import *  # noqa: ensure all models are imported
from app.services.neo4j_service import neo4j_service


def init_mysql():
    """创建所有 MySQL 表"""
    db.create_all()
    print("[MySQL] 所有表创建完成")


def init_neo4j():
    """创建 Neo4j 约束和索引"""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tag) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.id IS UNIQUE",
    ]
    for cypher in constraints:
        try:
            neo4j_service.run_write(cypher)
        except Exception as e:
            print(f"[Neo4j] 跳过已存在的约束: {e}")

    print("[Neo4j] 约束和索引创建完成")


def main():
    app = create_app()
    with app.app_context():
        init_mysql()
        try:
            init_neo4j()
        except Exception as e:
            print(f"[Neo4j] 连接失败（可稍后重试）: {e}")
        print("数据库初始化完成!")


if __name__ == '__main__':
    main()
