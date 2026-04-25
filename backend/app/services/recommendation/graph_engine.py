"""Pipeline B: 知识图谱多跳涟漪传播"""
from app.services.neo4j_service import neo4j_service
from app.utils.helpers import min_max_normalize


class GraphEngine:

    def recommend(self, user_id, top_n=200, exclude_post_ids=None):
        """
        基于 Neo4j 知识图谱的多跳传播推荐
        三路合并: 标签传播 + 纯社交召回 + 冷启动回退
        返回 {post_id: normalized_score}
        """
        exclude_post_ids = list(exclude_post_ids or [])
        try:
            tag_scores = self._behavior_based(user_id, top_n, exclude_post_ids)
            social_scores = self._social_recall(user_id, top_n, exclude_post_ids)

            if not tag_scores and not social_scores:
                return self._tag_based_fallback(user_id, top_n, exclude_post_ids)

            merged = dict(tag_scores)
            for pid, score in social_scores.items():
                merged[pid] = merged.get(pid, 0) + score
            ranked = dict(sorted(merged.items(), key=lambda x: -x[1])[:top_n])
            return min_max_normalize(ranked)
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

    def _social_recall(self, user_id, top_n, exclude_post_ids):
        """纯社交召回：直接推荐朋友（及朋友的朋友）喜欢的帖子，不经过标签传播。"""
        cypher = """
        MATCH (u:User {id: $uid})

        // 一阶：直接关注的人 like/favorite 的帖子
        OPTIONAL MATCH (u)-[:FOLLOWS]->(f1:User)-[r1:LIKED|FAVORITED]->(p1:Post)
        WHERE NOT p1.id IN $exclude_ids
          AND NOT (u)-[:LIKED|FAVORITED|BROWSED]->(p1)
        WITH u, collect(DISTINCT {
            pid: p1.id,
            score: CASE type(r1) WHEN 'FAVORITED' THEN 0.35 WHEN 'LIKED' THEN 0.25 ELSE 0 END
        }) AS hop1

        // 二阶：朋友的朋友 like/favorite 的帖子（衰减）
        OPTIONAL MATCH (u)-[:FOLLOWS]->(:User)-[:FOLLOWS]->(f2:User)-[r2:LIKED|FAVORITED]->(p2:Post)
        WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
          AND NOT p2.id IN $exclude_ids
          AND NOT (u)-[:LIKED|FAVORITED|BROWSED]->(p2)
        WITH hop1, collect(DISTINCT {
            pid: p2.id,
            score: CASE type(r2) WHEN 'FAVORITED' THEN 0.14 WHEN 'LIKED' THEN 0.10 ELSE 0 END
        }) AS hop2

        // 合并两跳结果
        WITH [x IN hop1 WHERE x.pid IS NOT NULL] + [x IN hop2 WHERE x.pid IS NOT NULL] AS all_items
        UNWIND all_items AS item
        WITH item.pid AS post_id, sum(item.score) AS raw_score
        WHERE post_id IS NOT NULL
        RETURN post_id, raw_score
        ORDER BY raw_score DESC
        LIMIT $limit
        """
        results = neo4j_service.run_query(cypher, {
            "uid": user_id, "limit": top_n, "exclude_ids": exclude_post_ids,
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

    # 路径优先级：数字越小越优先（与原 or 顺序一致）
    _PATH_PRIORITY = {
        'social_1hop': 1,
        'social_2hop': 2,
        'shared_tag': 3,
        'interest_tag': 4,
        'interest_domain': 5,
    }

    def explain_paths(self, user_id, post_ids):
        """对一批帖子批量生成解释路径。

        原实现为每条帖子最多 5 次 Cypher 查询（N+1 问题）。
        现改为 5 次批量查询（每种路径类型一次 UNWIND $pids），
        然后按优先级取最优路径。总 roundtrip 从 5N 降到 5。
        """
        pids = [int(pid) for pid in (post_ids or []) if pid is not None]
        if not pids:
            return {}

        candidates = {}

        def _collect(rows, priority, make_explanation):
            for row in rows:
                pid = row.get('post_id')
                if pid is None:
                    continue
                existing = candidates.get(pid)
                if existing is None or existing[0] > priority:
                    candidates[pid] = (priority, make_explanation(row))

        # ── 路径 1：一阶社交（直接关注的用户互动） ──
        _collect(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[:FOLLOWS]->(f:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: pid})
                WITH pid, f, r,
                     CASE type(r) WHEN 'FAVORITED' THEN 2 WHEN 'LIKED' THEN 1 ELSE 0 END AS rank
                ORDER BY pid, rank DESC
                WITH pid, collect({friend_id: f.id, friend_name: f.username, behavior: type(r)})[0] AS best
                RETURN pid AS post_id, best.friend_id AS friend_id,
                       best.friend_name AS friend_name, best.behavior AS behavior
                """,
                {"uid": user_id, "pids": pids},
            ),
            self._PATH_PRIORITY['social_1hop'],
            self._make_social_explanation('social_1hop', '你关注的用户'),
        )

        # ── 路径 2：二阶社交（朋友的朋友互动） ──
        remaining = [pid for pid in pids if pid not in candidates]
        if remaining:
            _collect(
                neo4j_service.run_query(
                    """
                    UNWIND $pids AS pid
                    MATCH (u:User {id: $uid})-[:FOLLOWS]->(:User)-[:FOLLOWS]->(f2:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: pid})
                    WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
                    WITH pid, f2, r,
                         CASE type(r) WHEN 'FAVORITED' THEN 2 WHEN 'LIKED' THEN 1 ELSE 0 END AS rank
                    ORDER BY pid, rank DESC
                    WITH pid, collect({friend_id: f2.id, friend_name: f2.username, behavior: type(r)})[0] AS best
                    RETURN pid AS post_id, best.friend_id AS friend_id,
                           best.friend_name AS friend_name, best.behavior AS behavior
                    """,
                    {"uid": user_id, "pids": remaining},
                ),
                self._PATH_PRIORITY['social_2hop'],
                self._make_social_explanation('social_2hop', '你关注链路中的用户'),
            )

        # ── 路径 3：共享标签（历史交互帖与候选同标签） ──
        remaining = [pid for pid in pids if pid not in candidates]
        if remaining:
            _collect(
                neo4j_service.run_query(
                    """
                    UNWIND $pids AS pid
                    MATCH (u:User {id: $uid})-[r:LIKED|FAVORITED|COMMENTED|BROWSED]->(seed:Post)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                    WITH pid, seed, t, r,
                         CASE type(r) WHEN 'FAVORITED' THEN 4 WHEN 'COMMENTED' THEN 3
                                       WHEN 'LIKED' THEN 2 WHEN 'BROWSED' THEN 1 ELSE 0 END AS rank
                    ORDER BY pid, rank DESC
                    WITH pid, collect({seed_id: seed.id, seed_title: seed.title,
                                       tag_name: t.name, behavior: type(r)})[0] AS best
                    RETURN pid AS post_id, best.seed_id AS seed_id, best.seed_title AS seed_title,
                           best.tag_name AS tag_name, best.behavior AS behavior
                    """,
                    {"uid": user_id, "pids": remaining},
                ),
                self._PATH_PRIORITY['shared_tag'],
                self._make_shared_tag_explanation,
            )

        # ── 路径 4：兴趣标签命中 ──
        remaining = [pid for pid in pids if pid not in candidates]
        if remaining:
            _collect(
                neo4j_service.run_query(
                    """
                    UNWIND $pids AS pid
                    MATCH (u:User {id: $uid})-[:INTERESTED_IN]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                    WITH pid, collect(t.name)[0] AS tag_name
                    RETURN pid AS post_id, tag_name
                    """,
                    {"uid": user_id, "pids": remaining},
                ),
                self._PATH_PRIORITY['interest_tag'],
                lambda row: {
                    "type": "interest_tag",
                    "text": f"这篇帖子命中了你的兴趣标签「{row['tag_name']}」",
                },
            )

        # ── 路径 5：兴趣领域回退 ──
        remaining = [pid for pid in pids if pid not in candidates]
        if remaining:
            _collect(
                neo4j_service.run_query(
                    """
                    UNWIND $pids AS pid
                    MATCH (u:User {id: $uid})-[:INTERESTED_DOMAIN]->(d:Domain)<-[:BELONGS_TO]-(:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                    WITH pid, collect(d.name)[0] AS domain_name
                    RETURN pid AS post_id, domain_name
                    """,
                    {"uid": user_id, "pids": remaining},
                ),
                self._PATH_PRIORITY['interest_domain'],
                lambda row: {
                    "type": "interest_domain",
                    "text": f"这篇帖子属于你持续关注的领域「{row['domain_name']}」",
                },
            )

        return {pid: explanation for pid, (_, explanation) in candidates.items()}

    def _make_social_explanation(self, path_type, prefix):
        def builder(row):
            friend_name = row.get('friend_name') or f"用户 #{row.get('friend_id')}"
            return {
                "type": path_type,
                "text": f"{prefix}「{friend_name}」{self._behavior_phrase(row['behavior'])}这篇帖子",
            }
        return builder

    def _make_shared_tag_explanation(self, row):
        seed_title = row.get('seed_title') or f"帖子 #{row.get('seed_id')}"
        return {
            "type": "shared_tag",
            "text": f"你{self._behavior_past_phrase(row['behavior'])}《{seed_title}》，"
                    f"与这篇共享标签「{row['tag_name']}」",
        }

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

    # ════════════════════════════════════════════════════════════════
    # Graph-RAG 检索端：为每个候选帖子返回多条结构化路径证据
    # 与 explain_paths() 的区别：
    #   - explain_paths 只保留「最优」一条路径（用于前端卡片展示）；
    #   - retrieve_paths_context 保留多种路径类型各一条，形成"检索结果集"，
    #     供 LLM 做跨路径推理（Graph-RAG 的 R 端）
    # ════════════════════════════════════════════════════════════════

    def retrieve_paths_context(self, user_id, post_ids, max_per_post=3):
        """为一批候选帖子批量检索多类图路径，作为 Graph-RAG 的检索证据。

        返回:
            {
                post_id: {
                    "paths": [   # 按优先级排序的多条路径
                        {"type": "social_1hop", "text": "...", "metadata": {...}},
                        {"type": "shared_tag", "text": "...", "metadata": {...}},
                        ...
                    ]
                }
            }
        """
        pids = [int(pid) for pid in (post_ids or []) if pid is not None]
        if not pids:
            return {}

        # 每个 post_id 维护一个按 priority 排序的 path 列表
        bucket = {pid: [] for pid in pids}

        def _push(rows, path_type, make_path):
            priority = self._PATH_PRIORITY[path_type]
            for row in rows:
                pid = row.get('post_id')
                if pid is None:
                    continue
                path = make_path(row)
                path['type'] = path_type
                bucket.setdefault(pid, []).append((priority, path))

        # ── 路径 1：一阶社交 ──
        _push(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[:FOLLOWS]->(f:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: pid})
                WITH pid, f, r,
                     CASE type(r) WHEN 'FAVORITED' THEN 2 WHEN 'LIKED' THEN 1 ELSE 0 END AS rank
                ORDER BY pid, rank DESC
                WITH pid, collect({friend_id: f.id, friend_name: f.username, behavior: type(r)})[0] AS best
                RETURN pid AS post_id, best.friend_id AS friend_id,
                       best.friend_name AS friend_name, best.behavior AS behavior
                """,
                {"uid": user_id, "pids": pids},
            ),
            'social_1hop',
            lambda row: {
                'text': f"你关注的用户「{row.get('friend_name') or ('用户#' + str(row.get('friend_id')))}」"
                        f"{self._behavior_phrase(row['behavior'])}这篇帖子",
                'metadata': {
                    'friend_id': row.get('friend_id'),
                    'friend_name': row.get('friend_name'),
                    'behavior': row.get('behavior'),
                },
            },
        )

        # ── 路径 2：二阶社交 ──
        _push(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[:FOLLOWS]->(:User)-[:FOLLOWS]->(f2:User)-[r:LIKED|FAVORITED]->(candidate:Post {id: pid})
                WHERE f2 <> u AND NOT (u)-[:FOLLOWS]->(f2)
                WITH pid, f2, r,
                     CASE type(r) WHEN 'FAVORITED' THEN 2 WHEN 'LIKED' THEN 1 ELSE 0 END AS rank
                ORDER BY pid, rank DESC
                WITH pid, collect({friend_id: f2.id, friend_name: f2.username, behavior: type(r)})[0] AS best
                RETURN pid AS post_id, best.friend_id AS friend_id,
                       best.friend_name AS friend_name, best.behavior AS behavior
                """,
                {"uid": user_id, "pids": pids},
            ),
            'social_2hop',
            lambda row: {
                'text': f"你关注链路中的用户「{row.get('friend_name') or ('用户#' + str(row.get('friend_id')))}」"
                        f"{self._behavior_phrase(row['behavior'])}这篇帖子",
                'metadata': {
                    'friend_id': row.get('friend_id'),
                    'friend_name': row.get('friend_name'),
                    'behavior': row.get('behavior'),
                },
            },
        )

        # ── 路径 3：共享标签（带种子帖信息） ──
        _push(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[r:LIKED|FAVORITED|COMMENTED|BROWSED]->(seed:Post)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                WITH pid, seed, t, r,
                     CASE type(r) WHEN 'FAVORITED' THEN 4 WHEN 'COMMENTED' THEN 3
                                   WHEN 'LIKED' THEN 2 WHEN 'BROWSED' THEN 1 ELSE 0 END AS rank
                ORDER BY pid, rank DESC
                WITH pid, collect({seed_id: seed.id, seed_title: seed.title,
                                   tag_name: t.name, behavior: type(r)})[0] AS best
                RETURN pid AS post_id, best.seed_id AS seed_id, best.seed_title AS seed_title,
                       best.tag_name AS tag_name, best.behavior AS behavior
                """,
                {"uid": user_id, "pids": pids},
            ),
            'shared_tag',
            lambda row: {
                'text': f"你{self._behavior_past_phrase(row['behavior'])}《"
                        f"{row.get('seed_title') or ('帖子#' + str(row.get('seed_id')))}》，"
                        f"与这篇共享标签「{row['tag_name']}」",
                'metadata': {
                    'seed_id': row.get('seed_id'),
                    'seed_title': row.get('seed_title'),
                    'tag_name': row.get('tag_name'),
                    'behavior': row.get('behavior'),
                },
            },
        )

        # ── 路径 4：兴趣标签命中 ──
        _push(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[:INTERESTED_IN]->(t:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                WITH pid, collect(t.name)[0] AS tag_name
                RETURN pid AS post_id, tag_name
                """,
                {"uid": user_id, "pids": pids},
            ),
            'interest_tag',
            lambda row: {
                'text': f"命中你的兴趣标签「{row['tag_name']}」",
                'metadata': {'tag_name': row.get('tag_name')},
            },
        )

        # ── 路径 5：兴趣领域回退 ──
        _push(
            neo4j_service.run_query(
                """
                UNWIND $pids AS pid
                MATCH (u:User {id: $uid})-[:INTERESTED_DOMAIN]->(d:Domain)<-[:BELONGS_TO]-(:Tag)<-[:TAGGED_WITH]-(candidate:Post {id: pid})
                WITH pid, collect(d.name)[0] AS domain_name
                RETURN pid AS post_id, domain_name
                """,
                {"uid": user_id, "pids": pids},
            ),
            'interest_domain',
            lambda row: {
                'text': f"属于你持续关注的领域「{row['domain_name']}」",
                'metadata': {'domain_name': row.get('domain_name')},
            },
        )

        # 每个 post 按 priority 排序，取前 max_per_post 条
        result = {}
        for pid, entries in bucket.items():
            if not entries:
                continue
            entries.sort(key=lambda x: x[0])
            result[pid] = {'paths': [p for _, p in entries[:max_per_post]]}
        return result
