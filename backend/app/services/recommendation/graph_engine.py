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

        UNWIND seeds AS s
        MATCH (sp:Post {id: s.pid})
        MATCH (sp)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post)
        WHERE NOT candidate.id IN interacted_ids AND NOT candidate.id IN $exclude_ids
        WITH u, candidate, interacted_ids,
             sum(s.w * 0.35) AS tag_score,
             sum(CASE WHEN candidate.domain_id = sp.domain_id THEN s.w * 0.18 ELSE 0 END) AS domain_score

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
        results = neo4j_service.run_query(cypher, {"uid": user_id, "limit": top_n, "exclude_ids": exclude_post_ids})
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
