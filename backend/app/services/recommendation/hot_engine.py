"""热门召回：用热度 + 新鲜度补足冷启动候选池。"""
import math
from datetime import datetime, timedelta

from app import db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User
from app.utils.helpers import min_max_normalize


class HotEngine:
    RECENT_WINDOW_DAYS = 30
    TAG_MATCH_BONUS = 0.0
    DOMAIN_MATCH_BONUS = 0.0

    def recommend(self, user_id=None, candidate_ids=None, top_n=200):
        stmt = db.select(Post)
        if candidate_ids:
            stmt = stmt.filter(Post.id.in_(candidate_ids))

        cutoff = datetime.now() - timedelta(days=self.RECENT_WINDOW_DAYS)
        posts = db.session.scalars(stmt.filter(Post.created_at >= cutoff)).all()
        if not posts:
            posts = db.session.scalars(stmt).all()
        if not posts:
            return {}

        interacted_ids = set()
        interest_tag_ids = set()
        interest_domain_ids = set()

        if user_id:
            interacted_ids = {
                post_id
                for (post_id,) in (
                    db.session.execute(
                        db.select(UserBehavior.post_id)
                    .filter(UserBehavior.user_id == user_id)
                    .distinct()
                    ).all()
                )
            }
            user = db.session.get(User, user_id)
            if user:
                interest_tag_ids = {tag.id for tag in user.interest_tags}
                interest_domain_ids = {tag.domain_id for tag in user.interest_tags}

        scores = {}
        for post in posts:
            if post.id in interacted_ids:
                continue

            age_days = max((datetime.now() - post.created_at).days, 0) if post.created_at else self.RECENT_WINDOW_DAYS
            freshness = max(0.0, 1 - age_days / self.RECENT_WINDOW_DAYS)
            popularity = math.log1p((post.like_count or 0) * 3 + (post.view_count or 0))

            domain_bonus = self.DOMAIN_MATCH_BONUS if post.domain_id in interest_domain_ids else 0.0
            overlap_count = sum(1 for tag in post.tags if tag.id in interest_tag_ids)
            tag_bonus = min(overlap_count * self.TAG_MATCH_BONUS, 0.36)

            scores[post.id] = popularity * 0.65 + freshness * 0.35 + domain_bonus + tag_bonus

        ranked = dict(sorted(scores.items(), key=lambda item: -item[1])[:top_n])
        return min_max_normalize(ranked)
