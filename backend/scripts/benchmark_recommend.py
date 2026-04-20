"""推荐引擎性能基准测试 — 记录 DB 查询次数与响应时间。"""
import sys
import time
from collections import defaultdict

from sqlalchemy import event


def run_benchmark():
    from app import create_app, db
    app = create_app()

    with app.app_context():
        # ── 注入 SQL 查询计数器 ──
        query_log = defaultdict(int)

        @event.listens_for(db.engine, "before_cursor_execute")
        def _count_query(conn, cursor, statement, parameters, context, executemany):
            # 按语句前缀分类
            stmt = statement.strip().upper()
            if stmt.startswith("SELECT"):
                query_log["SELECT"] += 1
            elif stmt.startswith("INSERT"):
                query_log["INSERT"] += 1
            else:
                query_log["OTHER"] += 1
            query_log["TOTAL"] += 1

        from app.services.recommendation import recommendation_engine

        # 测试用户: 活跃 / 温启动 / 冷启动
        test_users = [
            (1,   "active"),
            (50,  "warm"),
            (299, "cold"),
        ]

        print("=" * 70)
        print(f"{'用户ID':>6} {'阶段':<8} {'结果数':>4} {'耗时(ms)':>9} {'SELECT':>7} {'总SQL':>6}")
        print("-" * 70)

        all_results = []

        for user_id, stage in test_users:
            # 预热一轮（排除首次加载开销）
            recommendation_engine.recommend(user_id, top_n=10, enable_llm=False)

            # 正式测量 3 轮取中位数
            runs = []
            for _ in range(3):
                query_log.clear()
                t0 = time.perf_counter()
                results, debug = recommendation_engine.recommend_with_debug(
                    user_id, top_n=10, enable_llm=False,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                runs.append({
                    "elapsed_ms": elapsed_ms,
                    "result_count": len(results),
                    "select_count": query_log["SELECT"],
                    "total_sql": query_log["TOTAL"],
                    "recall_stats": debug.get("recall_stats", {}),
                })

            # 取中位数
            runs.sort(key=lambda r: r["elapsed_ms"])
            median = runs[1]  # 3 轮取第 2 个

            print(
                f"{user_id:>6} {stage:<8} {median['result_count']:>4} "
                f"{median['elapsed_ms']:>8.0f}ms {median['select_count']:>7} {median['total_sql']:>6}"
            )

            # 各路召回延迟
            for name, stat in median["recall_stats"].items():
                latency = stat.get("latency_ms", 0)
                count = stat.get("count", 0)
                print(f"       ├─ {name:<12} {count:>4} 条  {latency:>7.0f}ms")

            all_results.append({
                "user_id": user_id,
                "stage": stage,
                **{k: median[k] for k in ("elapsed_ms", "result_count", "select_count", "total_sql")},
            })
            print()

        print("=" * 70)

        # 汇总
        total_select = sum(r["select_count"] for r in all_results)
        avg_ms = sum(r["elapsed_ms"] for r in all_results) / len(all_results)
        print(f"平均响应时间: {avg_ms:.0f}ms | 总 SELECT 数(3用户): {total_select}")
        return all_results


if __name__ == "__main__":
    run_benchmark()
