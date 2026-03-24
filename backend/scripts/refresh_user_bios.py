"""
批量修复不合适的用户简介。

规则：
1. 空简介、占位简介、模拟数据简介 -> 替换
2. 明显的随机拼接/低质量简介 -> 替换
3. 疑似人工填写且可读的简介 -> 保留

用法：
  cd backend && uv run python -m scripts.refresh_user_bios
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.domain import Domain
from app.models.post import Post
from app.models.user import User

PLACEHOLDER_PREFIXES = (
    "模拟用户",
    "冷启动用户",
    "低活跃用户",
    "Epinions user",
)

GOOD_BIO_HINTS = (
    "我是",
    "关注",
    "喜欢",
    "专注",
    "研究",
    "学习",
    "从事",
    "分享",
    "记录",
    "爱好",
)

GENERIC_TAILS = (
    "偏好从基础概念和方法入手理解问题。",
    "关注系统梳理、案例分析与知识迁移。",
    "更喜欢把理论理解和实际问题结合起来。",
    "习惯先搭建知识框架，再深入具体主题。",
)

PAIR_TEMPLATES = (
    "关注{d1}、{d2}，{tail}",
    "主要阅读{d1}与{d2}相关内容，{tail}",
    "长期关注{d1}、{d2}方向，{tail}",
)

TRIPLE_TEMPLATES = (
    "关注{d1}、{d2}和{d3}，{tail}",
    "主要围绕{d1}、{d2}、{d3}展开阅读，{tail}",
)

SINGLE_TEMPLATES = (
    "主要关注{d1}，{tail}",
    "长期阅读{d1}相关内容，{tail}",
)


def should_replace_bio(user: User, domain_names: list[str]) -> bool:
    bio = (user.bio or "").strip()
    if not bio:
        return True
    if bio.startswith(PLACEHOLDER_PREFIXES):
        return True
    if bio.lower().startswith("epinions user"):
        return True

    if any(hint in bio for hint in GOOD_BIO_HINTS):
        return False
    if any(domain_name in bio for domain_name in domain_names):
        return False

    # 明显的模拟/随机简介：只有短词堆砌，没有中文逗号句式
    condensed = re.sub(r"\s+", "", bio)
    if "，" not in condensed and "。" not in condensed and len(condensed) <= 18:
        return True
    if "，" not in condensed and bio.endswith("."):
        return True
    if re.search(r"sim_user_|cold_eval_|test_chat_|gangqiao|taochen|dyi|qwan|liao\d*$", user.username):
        return True

    return False


def top_behavior_domains(user_id: int, limit: int = 3) -> list[Domain]:
    rows = db.session.execute(
        db.select(Post.domain_id, db.func.count().label("cnt"))
        .join(UserBehavior, UserBehavior.post_id == Post.id)
        .filter(UserBehavior.user_id == user_id)
        .group_by(Post.domain_id)
        .order_by(db.desc("cnt"))
        .limit(limit)
    ).all()
    domain_ids = [row[0] for row in rows if row[0]]
    if not domain_ids:
        return []
    domains = db.session.scalars(
        db.select(Domain).filter(Domain.id.in_(domain_ids))
    ).all()
    domain_map = {domain.id: domain for domain in domains}
    return [domain_map[domain_id] for domain_id in domain_ids if domain_id in domain_map]


def generate_bio(user: User) -> str:
    domains = top_behavior_domains(user.id, limit=3)
    domain_names = [domain.name for domain in domains]

    if not domain_names:
        tag_names = [tag.name for tag in user.interest_tags[:3]]
        if tag_names:
            return f"关注{'、'.join(tag_names)}等主题，偏好系统梳理核心概念与问题。"
        return "关注知识社区中的高质量讨论，偏好从核心概念和实际问题切入。"

    tail = GENERIC_TAILS[user.id % len(GENERIC_TAILS)]
    if len(domain_names) >= 3:
        template = TRIPLE_TEMPLATES[user.id % len(TRIPLE_TEMPLATES)]
        return template.format(d1=domain_names[0], d2=domain_names[1], d3=domain_names[2], tail=tail)
    if len(domain_names) == 2:
        template = PAIR_TEMPLATES[user.id % len(PAIR_TEMPLATES)]
        return template.format(d1=domain_names[0], d2=domain_names[1], tail=tail)
    template = SINGLE_TEMPLATES[user.id % len(SINGLE_TEMPLATES)]
    return template.format(d1=domain_names[0], tail=tail)


def main():
    app = create_app()
    with app.app_context():
        users = db.session.scalars(db.select(User).order_by(User.id)).all()
        updated = 0
        preserved = 0
        reason_counter = Counter()

        domain_names = [name for _, name in db.session.execute(db.select(Domain.id, Domain.name)).all()]

        for user in users:
            if should_replace_bio(user, domain_names):
                old_bio = user.bio
                user.bio = generate_bio(user)
                updated += 1
                if not old_bio:
                    reason_counter["empty"] += 1
                elif old_bio.startswith(PLACEHOLDER_PREFIXES) or old_bio.lower().startswith("epinions user"):
                    reason_counter["placeholder"] += 1
                else:
                    reason_counter["low_quality"] += 1
            else:
                preserved += 1

        db.session.commit()

        print(f"updated={updated} preserved={preserved}")
        for key, value in sorted(reason_counter.items()):
            print(f"{key}={value}")


if __name__ == "__main__":
    main()
