import numpy as np

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User


BEHAVIOR_PROFILE_WEIGHTS = {
    'favorite': 2.5,
    'like': 1.8,
    'comment': 1.5,
    'browse': 0.6,
}


class UserInterestService:
    """根据用户近期行为刷新兴趣向量和简易兴趣画像。"""

    def refresh_user_interest_state(self, user_id, recent_limit=100):
        user = db.session.get(User, user_id)
        if not user:
            return None

        behaviors = (
            db.select(UserBehavior)
            .filter_by(user_id=user_id)
            .filter(UserBehavior.behavior_type.in_(['favorite', 'like', 'comment', 'browse']))
            .order_by(UserBehavior.created_at.desc())
            .limit(recent_limit)
        )
        behaviors = db.session.scalars(behaviors).all()

        embeddings = []
        embedding_weights = []
        tag_scores = {}
        domain_scores = {}

        for behavior in behaviors:
            post = db.session.get(Post, behavior.post_id)
            if not post:
                continue

            weight = self._behavior_weight(behavior)

            if post.content_embedding:
                embeddings.append(np.array(post.content_embedding))
                embedding_weights.append(weight)

            if post.domain:
                domain_scores[post.domain.name] = domain_scores.get(post.domain.name, 0.0) + weight

            for tag in post.tags:
                tag_scores[tag.name] = tag_scores.get(tag.name, 0.0) + weight

        if embeddings:
            weights = np.array(embedding_weights)
            weighted_avg = np.average(embeddings, axis=0, weights=weights)
            user.interest_embedding = weighted_avg.tolist()
        else:
            user.interest_embedding = None

        user.interest_profile = self._build_interest_profile(user, domain_scores, tag_scores)
        db.session.commit()
        return user

    def _behavior_weight(self, behavior):
        weight = BEHAVIOR_PROFILE_WEIGHTS.get(behavior.behavior_type, 1.0)
        if behavior.behavior_type == 'browse':
            weight *= min((behavior.duration or 30) / 60.0, 2.0)
        return weight

    def _build_interest_profile(self, user, domain_scores, tag_scores):
        top_domains = sorted(domain_scores.items(), key=lambda item: -item[1])[:3]
        top_tags = sorted(tag_scores.items(), key=lambda item: -item[1])[:6]

        if top_domains or top_tags:
            domain_text = '、'.join(name for name, _ in top_domains) or '暂无'
            tag_text = '、'.join(name for name, _ in top_tags) or '暂无'
            return f'偏好领域：{domain_text}；近期关注主题：{tag_text}。'

        selected_tags = [tag.name for tag in user.interest_tags[:6]]
        if selected_tags:
            return f'注册兴趣：{"、".join(selected_tags)}。'

        return None


user_interest_service = UserInterestService()
