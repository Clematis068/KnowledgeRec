"""Pipeline B: 知识图谱多跳涟漪传播"""
from app.services.neo4j_service import neo4j_service
from app.utils.helpers import min_max_normalize


class GraphEngine:

    def recommend(self, user_id, top_n=200):
        """
        基于 Neo4j 知识图谱的多跳传播推荐
        冷启动回退: 无行为时用兴趣标签匹配帖子
        返回 {post_id: normalized_score}
        """
        try:
            scores = self._behavior_based(user_id, top_n)
            if scores:
                return scores
            return self._tag_based_fallback(user_id, top_n)
        except Exception as e:
            print(f"[GraphEngine] Neo4j查询失败: {e}")
            return {}

    def _behavior_based(self, user_id, top_n):
        """正常三跳涟漪传播（需要用户有行为数据）"""
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

        UNWIND seeds AS s
        MATCH (sp:Post {id: s.pid})-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post)
        WHERE NOT candidate.id IN interacted_ids
        WITH u, candidate, sum(s.w * 0.4) AS tag_score

        OPTIONAL MATCH (u)-[:FOLLOWS]->(friend:User)-[fr:LIKED|FAVORITED]->(candidate)
        WITH candidate, tag_score,
             COALESCE(sum(CASE type(fr)
                 WHEN 'FAVORITED' THEN 0.15
                 WHEN 'LIKED' THEN 0.10
                 ELSE 0
             END), 0) AS social_score
        WITH candidate.id AS post_id, tag_score + social_score AS raw_score

        RETURN post_id, raw_score
        ORDER BY raw_score DESC
        LIMIT $limit
        """
        results = neo4j_service.run_query(cypher, {"uid": user_id, "limit": top_n})
        scores = {r["post_id"]: r["raw_score"] for r in results}
        return min_max_normalize(scores)

    def _tag_based_fallback(self, user_id, top_n):
        """冷启动回退：用兴趣标签找帖子 + 社交信号加分"""
        cypher = """
        MATCH (u:User {id: $uid})-[it:INTERESTED_IN]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post)
        WITH u, candidate, sum(COALESCE(it.weight, 1) * 0.5) AS tag_score

        OPTIONAL MATCH (u)-[:FOLLOWS]->(friend:User)-[fr:LIKED|FAVORITED]->(candidate)
        WITH candidate, tag_score,
             COALESCE(sum(CASE type(fr)
                 WHEN 'FAVORITED' THEN 0.15
                 WHEN 'LIKED' THEN 0.10
                 ELSE 0
             END), 0) AS social_score
        WITH candidate.id AS post_id, tag_score + social_score AS raw_score

        RETURN post_id, raw_score
        ORDER BY raw_score DESC
        LIMIT $limit
        """
        results = neo4j_service.run_query(cypher, {"uid": user_id, "limit": top_n})
        scores = {r["post_id"]: r["raw_score"] for r in results}
        return min_max_normalize(scores)
