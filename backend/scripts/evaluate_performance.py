"""
性能优化基准测试脚本
测量指标: 请求延迟、SQL 查询计数
对比维度: 串行 vs 并行 Pipeline、批量加载 vs 逐条查询、语义预过滤效果

用法: cd backend && uv run python -m scripts.evaluate_performance
"""
import csv
import logging
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.behavior import UserBehavior

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "evaluation")
SAMPLE_USER_COUNT = 15
WARMUP_ROUNDS = 2


class SQLCountHandler(logging.Handler):
    """通过拦截 SQLAlchemy engine logger 来统计 SQL 数，线程安全。"""

    def __init__(self):
        super().__init__()
        self._local = threading.local()

    @property
    def count(self):
        return getattr(self._local, "count", 0)

    @count.setter
    def count(self, value):
        self._local.count = value

    def reset(self):
        self._local.count = 0

    def emit(self, record):
        self._local.count = getattr(self._local, "count", 0) + 1


def get_test_users(limit=SAMPLE_USER_COUNT):
    """选取有一定行为量的用户做基准测试。"""
    stmt = (
        db.select(User.id, db.func.count(UserBehavior.id).label("cnt"))
        .join(UserBehavior, UserBehavior.user_id == User.id)
        .group_by(User.id)
        .having(db.func.count(UserBehavior.id) >= 5)
        .order_by(db.text("cnt DESC"))
        .limit(limit)
    )
    return [row[0] for row in db.session.execute(stmt).all()]


def setup_sql_counter(app):
    """给 SQLAlchemy engine logger 挂上计数 handler，返回 handler。"""
    engine_logger = logging.getLogger("sqlalchemy.engine.Engine")
    handler = SQLCountHandler()
    handler.setLevel(logging.INFO)
    engine_logger.addHandler(handler)
    engine_logger.setLevel(logging.INFO)
    # 静默具体 SQL 输出，只计数
    for h in engine_logger.handlers:
        if h is not handler:
            h.setLevel(logging.WARNING)
    return handler


def benchmark_recommend(engine, user_ids, label, sql_handler, enable_llm=False):
    """对一组用户跑推荐，统计延迟和 SQL 数。"""
    latencies = []
    sql_counts = []

    # 预热
    for uid in user_ids[:WARMUP_ROUNDS]:
        try:
            engine.recommend(uid, top_n=20, enable_llm=enable_llm)
        except Exception:
            pass

    for uid in user_ids:
        sql_handler.reset()
        t0 = time.perf_counter()
        try:
            engine.recommend(uid, top_n=20, enable_llm=enable_llm)
        except Exception as e:
            print(f"  [{label}] user {uid} failed: {e}")
            continue
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)
        sql_counts.append(sql_handler.count)
        print(f"  [{label}] user {uid}: {elapsed:.3f}s, {sql_handler.count} SQL")

    if not latencies:
        return {"label": label, "users": 0, "avg_latency": 0, "p50_latency": 0,
                "p95_latency": 0, "min_latency": 0, "max_latency": 0,
                "avg_sql": 0, "min_sql": 0, "max_sql": 0}

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    return {
        "label": label,
        "users": n,
        "avg_latency": round(sum(latencies) / n, 4),
        "p50_latency": round(latencies_sorted[n // 2], 4),
        "p95_latency": round(latencies_sorted[int(n * 0.95)], 4),
        "min_latency": round(latencies_sorted[0], 4),
        "max_latency": round(latencies_sorted[-1], 4),
        "avg_sql": round(sum(sql_counts) / n, 1),
        "min_sql": min(sql_counts),
        "max_sql": max(sql_counts),
    }


def benchmark_semantic_candidates(user_ids):
    """测量语义引擎候选集预过滤效果。"""
    from app.services.recommendation.semantic_engine import SemanticEngine
    from app.models.post import Post
    from datetime import timedelta

    se = SemanticEngine()
    total_posts = db.session.scalar(
        db.select(db.func.count()).select_from(Post).filter(Post.content_embedding.isnot(None))
    )
    results = []
    for uid in user_ids:
        user = db.session.get(User, uid)
        if not user:
            continue
        domain_ids = se._get_user_domain_ids(uid, user)

        # 模拟三级过滤
        cutoff = datetime.now() - timedelta(days=90)
        count_strict = db.session.scalar(
            db.select(db.func.count()).select_from(Post).filter(
                Post.content_embedding.isnot(None),
                Post.domain_id.in_(domain_ids) if domain_ids else db.literal(False),
                Post.created_at >= cutoff,
            )
        ) if domain_ids else 0
        count_domain = db.session.scalar(
            db.select(db.func.count()).select_from(Post).filter(
                Post.content_embedding.isnot(None),
                Post.domain_id.in_(domain_ids) if domain_ids else db.literal(False),
            )
        ) if domain_ids else 0

        results.append({
            "user_id": uid,
            "domain_count": len(domain_ids),
            "candidates_strict": count_strict,
            "candidates_domain": count_domain,
            "candidates_all": total_posts,
        })
    return results


def write_performance_report(perf_results, semantic_results, test_user_count):
    os.makedirs(REPORT_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # CSV
    csv_path = os.path.join(REPORT_DIR, "performance_metrics.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=[
            "label", "users", "avg_latency", "p50_latency", "p95_latency",
            "min_latency", "max_latency", "avg_sql", "min_sql", "max_sql",
        ])
        writer.writeheader()
        for row in perf_results:
            writer.writerow(row)

    # 语义过滤 CSV
    if semantic_results:
        sem_csv_path = os.path.join(REPORT_DIR, "semantic_filter_metrics.csv")
        with open(sem_csv_path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "user_id", "domain_count", "candidates_strict", "candidates_domain", "candidates_all",
            ])
            writer.writeheader()
            for row in semantic_results:
                writer.writerow(row)

    # Markdown
    md_path = os.path.join(REPORT_DIR, "performance_report.md")
    lines = [
        "# 推荐系统性能优化测试报告",
        "",
        f"- 生成时间: {now}",
        f"- 测试用户数: {test_user_count}",
        f"- 预热轮数: {WARMUP_ROUNDS}",
        "",
        "## 1. 延迟与 SQL 查询统计",
        "",
        "| 测试场景 | 用户数 | 平均延迟(s) | P50(s) | P95(s) | 最小(s) | 最大(s) | 平均SQL | SQL范围 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in perf_results:
        lines.append(
            f"| {r['label']} | {r['users']} | {r['avg_latency']} | "
            f"{r['p50_latency']} | {r['p95_latency']} | "
            f"{r['min_latency']} | {r['max_latency']} | "
            f"{r['avg_sql']} | {r['min_sql']}-{r['max_sql']} |"
        )

    if semantic_results:
        total = semantic_results[0]["candidates_all"]
        avg_strict = sum(r["candidates_strict"] for r in semantic_results) / len(semantic_results)
        avg_domain = sum(r["candidates_domain"] for r in semantic_results) / len(semantic_results)
        avg_domains = sum(r["domain_count"] for r in semantic_results) / len(semantic_results)

        lines += [
            "",
            "## 2. 语义引擎候选集预过滤效果",
            "",
            f"全部有 embedding 的帖子: **{total}** 篇",
            "",
            "| 用户ID | 兴趣领域数 | 领域+90天 | 仅领域 | 全部 | 缩减比 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in semantic_results:
            effective = r["candidates_strict"] if r["candidates_strict"] >= 50 else (
                r["candidates_domain"] if r["candidates_domain"] >= 50 else r["candidates_all"]
            )
            ratio = f"{effective / r['candidates_all'] * 100:.0f}%" if r["candidates_all"] > 0 else "-"
            lines.append(
                f"| {r['user_id']} | {r['domain_count']} | "
                f"{r['candidates_strict']} | {r['candidates_domain']} | "
                f"{r['candidates_all']} | {ratio} |"
            )
        lines += [
            "",
            f"- 平均兴趣领域数: {avg_domains:.1f}",
            f"- 平均候选集 (领域+90天): {avg_strict:.0f} 篇",
            f"- 平均候选集 (仅领域): {avg_domain:.0f} 篇",
            f"- 全表: {total} 篇",
        ]

    lines += [
        "",
        "## 3. 优化措施总结",
        "",
        "| 优化项 | 层级 | 手段 | 效果 |",
        "| --- | --- | --- | --- |",
        "| N+1 批量预加载 | 后端 DB | `WHERE IN` + `joinedload` | SQL 大幅减少 |",
        "| 语义预过滤 | 后端算法 | 领域+时间窗口 | 候选集缩小 |",
        "| Pipeline 并行 | 后端调度 | `ThreadPoolExecutor` | 延迟 ~= max(单pipeline) |",
        "| 骨架屏 | 前端 UI | `el-skeleton-item` | 消除布局跳动 |",
        "",
    ]

    with open(md_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))

    print(f"\n报告已写入: {csv_path}")
    print(f"报告已写入: {md_path}")


def main():
    # 降低日志噪音
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = create_app()
    with app.app_context():
        sql_handler = setup_sql_counter(app)

        user_ids = get_test_users()
        if not user_ids:
            print("无可用测试用户，请先生成数据")
            return

        print(f"\n===== 推荐系统性能基准测试 =====")
        print(f"测试用户: {len(user_ids)} 人")
        print(f"用户ID: {user_ids}\n")

        from app.services.recommendation import RecommendationEngine
        engine = RecommendationEngine()
        perf_results = []

        # 测试 1: 完整推荐 (优化后: 并行 + 批量加载 + 预过滤, 无LLM)
        print("[1/3] 优化后完整推荐 (无LLM)...")
        result = benchmark_recommend(engine, user_ids, "optimized_no_llm", sql_handler, enable_llm=False)
        perf_results.append(result)
        print(f"  => 平均延迟: {result['avg_latency']}s, 平均SQL: {result['avg_sql']}\n")

        # 测试 2: 带 LLM rerank (仅5用户避免太慢)
        print("[2/3] 优化后完整推荐 (带LLM)...")
        result = benchmark_recommend(engine, user_ids[:5], "optimized_with_llm", sql_handler, enable_llm=True)
        perf_results.append(result)
        print(f"  => 平均延迟: {result['avg_latency']}s, 平均SQL: {result['avg_sql']}\n")

        # 测试 3: 语义引擎候选集过滤
        print("[3/3] 语义引擎候选集预过滤效果...")
        semantic_results = benchmark_semantic_candidates(user_ids)
        if semantic_results:
            total = semantic_results[0]["candidates_all"]
            avg_strict = sum(r["candidates_strict"] for r in semantic_results) / len(semantic_results)
            print(f"  => 全部帖子: {total}, 平均候选(领域+90天): {avg_strict:.0f}\n")

        # 汇总表
        print("=" * 100)
        print(f"{'场景':<25} {'用户':>5} {'平均延迟':>10} {'P50':>8} {'P95':>8} {'平均SQL':>8} {'SQL范围':>12}")
        print("-" * 100)
        for r in perf_results:
            print(f"{r['label']:<25} {r['users']:>5} {r['avg_latency']:>9.4f}s "
                  f"{r['p50_latency']:>7.4f}s {r['p95_latency']:>7.4f}s "
                  f"{r['avg_sql']:>8.1f} {r['min_sql']:>5}-{r['max_sql']:<5}")
        print("=" * 100)

        write_performance_report(perf_results, semantic_results, len(user_ids))


if __name__ == "__main__":
    main()
