"""
同步用户兴趣标签/领域到 Neo4j

用法:
  cd backend && uv run python -m scripts.sync_user_interest_graph
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.models.user import User
from app.services.tag_taxonomy_service import tag_taxonomy_service


def main():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        for user in users:
            tag_taxonomy_service.sync_user_interest_tags(user)
        print(f"[DONE] 已同步 {len(users)} 个用户的兴趣标签/领域到 Neo4j")


if __name__ == '__main__':
    main()
