"""推荐引擎并发基准测试。

用法:
  cd backend && uv run python -m scripts.benchmark_recommend_concurrent
  cd backend && uv run python -m scripts.benchmark_recommend_concurrent --workers 8 --top-n 10

说明:
  - 默认使用全部用户
  - 每个 worker 复用一个 RecommendationEngine 实例
  - 采用分片并发，统计端到端延迟与结果数
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.user import User
from app.services.recommendation import RecommendationEngine


REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "evaluation")


def collect_user_rows(min_behaviors=0):
    """返回全部可测用户及其行为数。"""
    stmt = (
        db.select(
            User.id,
            User.username,
            db.func.count(UserBehavior.id).label("behavior_count"),
        )
        .outerjoin(UserBehavior, UserBehavior.user_id == User.id)
        .group_by(User.id)
        .order_by(db.text("behavior_count DESC"), User.id.asc())
    )
    rows = db.session.execute(stmt).all()
    items = []
    for uid, username, behavior_count in rows:
        behavior_count = int(behavior_count or 0)
        if behavior_count < min_behaviors:
            continue
        stage = "cold" if behavior_count == 0 else ("warm" if behavior_count < 15 else "active")
        items.append({
            "user_id": int(uid),
            "username": username,
            "behavior_count": behavior_count,
            "stage": stage,
        })
    return items


def chunk_round_robin(items, workers):
    chunks = [[] for _ in range(workers)]
    for idx, item in enumerate(items):
        chunks[idx % workers].append(item)
    return [chunk for chunk in chunks if chunk]


def run_chunk(app, chunk, top_n, enable_llm, warmup_uid):
    """单 worker 处理一个分片。"""
    results = []
    with app.app_context():
        engine = RecommendationEngine()

        # 预热一次，避免首个请求把模型加载时间计入正式样本。
        try:
            engine.recommend(warmup_uid, top_n=top_n, enable_llm=enable_llm)
        except Exception:
            pass

        for row in chunk:
            t0 = time.perf_counter()
            try:
                recs = engine.recommend(row["user_id"], top_n=top_n, enable_llm=enable_llm)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                results.append({
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "stage": row["stage"],
                    "behavior_count": row["behavior_count"],
                    "result_count": len(recs),
                    "elapsed_ms": elapsed_ms,
                    "status": "ok",
                })
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                results.append({
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "stage": row["stage"],
                    "behavior_count": row["behavior_count"],
                    "result_count": 0,
                    "elapsed_ms": elapsed_ms,
                    "status": f"error: {exc}",
                })

        db.session.remove()

    return results


def summarize(results):
    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]

    if ok:
        latencies = sorted(r["elapsed_ms"] for r in ok)
        n = len(latencies)
        return {
            "count": len(ok),
            "failed": len(failed),
            "avg_ms": mean(latencies),
            "p50_ms": latencies[n // 2],
            "p95_ms": latencies[min(n - 1, math.ceil(n * 0.95) - 1)],
            "min_ms": latencies[0],
            "max_ms": latencies[-1],
            "avg_results": mean(r["result_count"] for r in ok),
        }

    return {
        "count": 0,
        "failed": len(failed),
        "avg_ms": 0,
        "p50_ms": 0,
        "p95_ms": 0,
        "min_ms": 0,
        "max_ms": 0,
        "avg_results": 0,
    }


def write_report(results, workers, top_n, enable_llm, wall_ms):
    os.makedirs(REPORT_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = summarize(results)

    report_path = os.path.join(REPORT_DIR, "concurrent_performance_report.md")
    lines = [
        "# 推荐系统并发性能测试报告",
        "",
        f"- 生成时间: {now}",
        f"- 测试用户数: {summary['count']}",
        f"- 失败用户数: {summary['failed']}",
        f"- 并发 worker 数: {workers}",
        f"- top_n: {top_n}",
        f"- enable_llm: {enable_llm}",
        f"- 总墙钟时间: {wall_ms:.0f}ms",
        f"- 平均吞吐: {summary['count'] / (wall_ms / 1000):.2f} 用户/秒" if wall_ms > 0 else "- 平均吞吐: 0",
        "",
        "## 结果统计",
        "",
        "| 指标 | 数值(ms) |",
        "| --- | ---: |",
        f"| 平均延迟 | {summary['avg_ms']:.1f} |",
        f"| P50 | {summary['p50_ms']:.1f} |",
        f"| P95 | {summary['p95_ms']:.1f} |",
        f"| 最小值 | {summary['min_ms']:.1f} |",
        f"| 最大值 | {summary['max_ms']:.1f} |",
        f"| 平均结果数 | {summary['avg_results']:.1f} |",
        "",
        "## 用户分布",
        "",
        "| 阶段 | 用户数 | 平均耗时(ms) | 平均结果数 |",
        "| --- | ---: | ---: | ---: |",
    ]

    by_stage = {}
    for row in results:
        if row["status"] != "ok":
            continue
        by_stage.setdefault(row["stage"], []).append(row)

    for stage in ("active", "warm", "cold"):
        rows = by_stage.get(stage, [])
        if not rows:
            continue
        lines.append(
            f"| {stage} | {len(rows)} | {mean(r['elapsed_ms'] for r in rows):.1f} | {mean(r['result_count'] for r in rows):.1f} |"
        )

    lines += [
        "",
        "## 样本明细",
        "",
        "| 用户ID | 用户名 | 阶段 | 行为数 | 结果数 | 耗时(ms) | 状态 |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(results, key=lambda r: r["user_id"]):
        lines.append(
            f"| {row['user_id']} | {row['username']} | {row['stage']} | {row['behavior_count']} | "
            f"{row['result_count']} | {row['elapsed_ms']:.1f} | {row['status']} |"
        )

    with open(report_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))

    print(f"报告已写入: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="推荐引擎并发基准测试")
    parser.add_argument("--workers", type=int, default=8, help="并发 worker 数")
    parser.add_argument("--top-n", type=int, default=10, help="推荐条数")
    parser.add_argument("--enable-llm", action="store_true", help="开启 LLM 重排序")
    parser.add_argument("--min-behaviors", type=int, default=0, help="最少行为数过滤")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user_rows = collect_user_rows(min_behaviors=args.min_behaviors)

    if not user_rows:
        print("没有可用用户。")
        return

    workers = max(1, min(args.workers, len(user_rows)))
    chunks = chunk_round_robin(user_rows, workers)
    warmup_uid = user_rows[0]["user_id"]

    print("=" * 90)
    print(f"总用户数: {len(user_rows)} | worker 数: {workers} | top_n: {args.top_n} | enable_llm: {args.enable_llm}")
    print(f"warmup 用户: {warmup_uid}")
    print("=" * 90)

    start = time.perf_counter()
    all_results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(run_chunk, app, chunk, args.top_n, args.enable_llm, warmup_uid)
            for chunk in chunks
        ]
        for fut in as_completed(futures):
            all_results.extend(fut.result())

    wall_ms = (time.perf_counter() - start) * 1000
    summary = summarize(all_results)

    print(f"完成用户数: {summary['count']} | 失败用户数: {summary['failed']}")
    print(
        f"平均延迟: {summary['avg_ms']:.1f}ms | P50: {summary['p50_ms']:.1f}ms | "
        f"P95: {summary['p95_ms']:.1f}ms | 最小: {summary['min_ms']:.1f}ms | 最大: {summary['max_ms']:.1f}ms"
    )
    print(f"平均结果数: {summary['avg_results']:.1f}")
    print(f"总墙钟时间: {wall_ms:.0f}ms | 吞吐: {summary['count'] / (wall_ms / 1000):.2f} 用户/秒")

    stage_counts = {}
    for row in all_results:
        if row["status"] != "ok":
            continue
        stage_counts[row["stage"]] = stage_counts.get(row["stage"], 0) + 1
    print("阶段分布:", stage_counts)

    write_report(all_results, workers, args.top_n, args.enable_llm, wall_ms)


if __name__ == "__main__":
    main()
