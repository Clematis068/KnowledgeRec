"""Pipeline B: 知识图谱多跳涟漪传播"""
from app.services.neo4j_service import neo4j_service
from app.utils.helpers import min_max_normalize


class GraphEngine:

    def recommend(self, user_id, top_n=200, exclude_post_ids=None):
        """
        基于 Neo4j 知识图谱的多跳传播推荐
        冷启动回退: 无行为时用兴趣标签匹配帖子
        返回 {post_id: normalized_score}
        """
        exclude_post_ids = list(exclude_post_ids or [])
        try:
            scores = self._behavior_based(user_id, top_n, exclude_post_ids)
            if scores:
                return scores
            return self._tag_based_fallback(user_id, top_n, exclude_post_ids)
        except Exception as e:
            print(f"[GraphEngine] Neo4j查询失败: {e}")
            return {}

    def _behavior_based(self, user_id, top_n, exclude_post_ids):
        """三跳涟漪传播 + 二阶社交（朋友的朋友）"""
        cypher = """
        MATCH (u:User {id: $uid})-[r:LIKED|FAVORITED|COMMENTED|BROWSED]->(seed:Post)
        WITH u,
             collect(DISTINCT seed.id) AS interacted_ids,
             collect({pid: seed.id, w: CASE type(r)
                WHEN 'FAVORITED' THEN 1.5
                WHEN 'COMMENTED' THEN 1.2
                WHEN 'LIKED' THEN 1.0
                WHEN 'BROWSED' THEN 0.3
             END}) AS seeds

        // 标签传播 + 领域传播
        UNWIND seeds AS s
        MATCH (sp:Post {id: s.pid})-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post)
        WHERE NOT candidate.id IN interacted_ids AND NOT candidate.id IN $exclude_ids
        WITH u, candidate, interacted_ids,
             sum(s.w * 0.35) AS tag_score,
             sum(CASE WHEN candidate.domain_id = sp.domain_id THEN s.w * 0.18 ELSE 0 END) AS domain_score

        // 提前截断：按标签+领域分排序，只保留 top 候选进入社交阶段
        ORDER BY tag_score + domain_score DESC
        LIMIT $candidate_limit

        // 一阶社交：直接关注的朋友
        OPTIONAL MATCH (u)-[:FOLLOWS]->(f1:User)-[fr1:LIKED|FAVORITED]->(candidate)
        WITH u, candidate, interacted_ids, tag_score, domain_score,
             COALESCE(sum(CASE type(fr1)
                 WHEN 'FAVORITED' THEN 0.25
                 WHEN 'LIKED' THEN 0.18
                 ELSE 0
             END), 0) AS social_1hop

        // 二阶社交：朋友的朋友（衰减 0.4×）
        OPTIONAL MATCH (u)-[:FOLLOWS]->(f1:User)-[:FOLLOWS]->(f2:User)-[fr2:LIKED|FAVORITED]->(candidate)
        WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
        WITH candidate, tag_score, domain_score, social_1hop,
             COALESCE(sum(CASE type(fr2)
                 WHEN 'FAVORITED' THEN 0.10
                 WHEN 'LIKED' THEN 0.07
                 ELSE 0
             END), 0) AS social_2hop
        WITH candidate.id AS post_id,
             tag_score + domain_score + social_1hop + social_2hop AS raw_score

        RETURN post_id, raw_score
        ORDER BY raw_score DESC
        LIMIT $limit
        """
        candidate_limit = top_n * 3  # 标签阶段保留 3 倍候选，社交阶段再精选
        results = neo4j_service.run_query(cypher, {
            "uid": user_id, "limit": top_n,
            "candidate_limit": candidate_limit,
            "exclude_ids": exclude_post_ids,
        })
        scores = {r["post_id"]: r["raw_score"] for r in results}
        return min_max_normalize(scores)

    def _tag_based_fallback(self, user_id, top_n, exclude_post_ids):
        """冷启动回退：用兴趣标签找帖子 + 二阶社交信号加分"""
        cypher = """
        MATCH (u:User {id: $uid})-[it:INTERESTED_IN]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post)
        WHERE NOT candidate.id IN $exclude_ids
        WITH u, candidate, sum(COALESCE(it.weight, 1) * 0.45) AS tag_score

        OPTIONAL MATCH (u)-[idom:INTERESTED_DOMAIN]->(d:Domain)
        WHERE candidate.domain_id = d.id
        WITH u, candidate, tag_score,
             COALESCE(sum(COALESCE(idom.weight, 1) * 0.2), 0) AS domain_score

        // 一阶社交
        OPTIONAL MATCH (u)-[:FOLLOWS]->(f1:User)-[fr1:LIKED|FAVORITED]->(candidate)
        WITH u, candidate, tag_score, domain_score,
             COALESCE(sum(CASE type(fr1)
                 WHEN 'FAVORITED' THEN 0.25
                 WHEN 'LIKED' THEN 0.18
                 ELSE 0
             END), 0) AS social_1hop

        // 二阶社交
        OPTIONAL MATCH (u)-[:FOLLOWS]->(f1:User)-[:FOLLOWS]->(f2:User)-[fr2:LIKED|FAVORITED]->(candidate)
        WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
        WITH candidate, tag_score, domain_score, social_1hop,
             COALESCE(sum(CASE type(fr2)
                 WHEN 'FAVORITED' THEN 0.10
                 WHEN 'LIKED' THEN 0.07
                 ELSE 0
             END), 0) AS social_2hop
        WITH candidate.id AS post_id,
             tag_score + domain_score + social_1hop + social_2hop AS raw_score

        RETURN post_id, raw_score
        ORDER BY raw_score DESC
        LIMIT $limit
        """
        results = neo4j_service.run_query(cypher, {"uid": user_id, "limit": top_n, "exclude_ids": exclude_post_ids})
        scores = {r["post_id"]: r["raw_score"] for r in results}
        return min_max_normalize(scores)

    def explain_paths(self, user_id, post_ids):
        explanations = {}
        for post_id in post_ids or []:
            explanation = (
                self._direct_social_path(user_id, post_id)
                or self._second_social_path(user_id, post_id)
                or self._shared_tag_path(user_id, post_id)
                or self._interest_tag_path(user_id, post_id)
                or self._interest_domain_path(user_id, post_id)
            )
            if explanation:
                explanations[post_id] = explanation
        return explanations

    def _direct_social_path(self, user_id, post_id):
        cypher = """
        MATCH (u:User {id: $uid})-[:FOLLOWS]->(f:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: $pid})
        RETURN f.id AS friend_id, f.username AS friend_name, type(r) AS behavior
        ORDER BY CASE type(r)
            WHEN 'FAVORITED' THEN 2
            WHEN 'LIKED' THEN 1
            ELSE 0
        END DESC
        LIMIT 1
        """
        row = self._single_row(cypher, {"uid": user_id, "pid": post_id})
        if not row:
            return None
        friend_name = row.get('friend_name') or f"用户 #{row['friend_id']}"
        return {
            "type": "social_1hop",
            "text": f"你关注的用户「{friend_name}」{self._behavior_phrase(row['behavior'])}这篇帖子",
        }

    def _second_social_path(self, user_id, post_id):
        cypher = """
        MATCH (u:User {id: $uid})-[:FOLLOWS]->(:User)-[:FOLLOWS]->(f2:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: $pid})
        WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
        RETURN f2.id AS friend_id, f2.username AS friend_name, type(r) AS behavior
        ORDER BY CASE type(r)
            WHEN 'FAVORITED' THEN 2
            WHEN 'LIKED' THEN 1
            ELSE 0
        END DESC
        LIMIT 1
        """
        row = self._single_row(cypher, {"uid": user_id, "pid": post_id})
        if not row:
            return None
        friend_name = row.get('friend_name') or f"用户 #{row['friend_id']}"
        return {
            "type": "social_2hop",
            "text": f"你关注链路中的用户「{friend_name}」{self._behavior_phrase(row['behavior'])}这篇帖子",
        }

    def _shared_tag_path(self, user_id, post_id):
        cypher = """
        MATCH (u:User {id: $uid})-[r:LIKED|FAVORITED|COMMENTED|BROWSED]->(seed:Post)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: $pid})
        RETURN seed.id AS seed_id, seed.title AS seed_title, t.name AS tag_name, type(r) AS behavior
        ORDER BY CASE type(r)
            WHEN 'FAVORITED' THEN 4
            WHEN 'COMMENTED' THEN 3
            WHEN 'LIKED' THEN 2
            WHEN 'BROWSED' THEN 1
            ELSE 0
        END DESC
        LIMIT 1
        """
        row = self._single_row(cypher, {"uid": user_id, "pid": post_id})
        if not row:
            return None
        seed_title = row.get('seed_title') or f"帖子 #{row['seed_id']}"
        return {
            "type": "shared_tag",
            "text": f"你{self._behavior_past_phrase(row['behavior'])}《{seed_title}》，与这篇共享标签「{row['tag_name']}」",
        }

    def _interest_tag_path(self, user_id, post_id):
        cypher = """
        MATCH (u:User {id: $uid})-[:INTERESTED_IN]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: $pid})
        RETURN t.name AS tag_name
        LIMIT 1
        """
        row = self._single_row(cypher, {"uid": user_id, "pid": post_id})
        if not row:
            return None
        return {
            "type": "interest_tag",
            "text": f"这篇帖子命中了你的兴趣标签「{row['tag_name']}」",
        }

    def _interest_domain_path(self, user_id, post_id):
        cypher = """
        MATCH (u:User {id: $uid})-[:INTERESTED_DOMAIN]->(d:Domain)<-[:BELONGS_TO]-(:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: $pid})
        RETURN d.name AS domain_name
        LIMIT 1
        """
        row = self._single_row(cypher, {"uid": user_id, "pid": post_id})
        if not row:
            return None
        return {
            "type": "interest_domain",
            "text": f"这篇帖子属于你持续关注的领域「{row['domain_name']}」",
        }

    @staticmethod
    def _single_row(cypher, params):
        rows = neo4j_service.run_query(cypher, params)
        return rows[0] if rows else None

    @staticmethod
    def _behavior_phrase(behavior_type):
        mapping = {
            'FAVORITED': '收藏了',
            'LIKED': '点赞了',
        }
        return mapping.get(behavior_type, '互动过')

    @staticmethod
    def _behavior_past_phrase(behavior_type):
        mapping = {
            'FAVORITED': '收藏过',
            'COMMENTED': '评论过',
            'LIKED': '点赞过',
            'BROWSED': '浏览过',
        }
        return mapping.get(behavior_type, '看过')
