"""
批量抓取多个技术社区帖子标题/正文，并导出为 JSONL。

默认社区:
  - CSDN
  - 博客园
  - 稀土掘金
  - 开源中国
  - 51CTO

默认关键词:
  机器学习、深度学习、自然语言处理、计算机视觉、数据库、
  分布式系统、网络安全、算法设计、操作系统、编程语言

用法:
  cd backend && uv run python -m scripts.bulk_firecrawl_community_scrape
  cd backend && uv run python -m scripts.bulk_firecrawl_community_scrape --limit-per-query 4
  cd backend && uv run python -m scripts.bulk_firecrawl_community_scrape --keywords 机器学习 深度学习 数据库
  cd backend && uv run python -m scripts.bulk_firecrawl_community_scrape --communities csdn cnblogs juejin
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


COMMUNITY_SITES: Dict[str, str] = {
    "csdn": "blog.csdn.net",
    "cnblogs": "www.cnblogs.com",
    "juejin": "juejin.cn",
    "oschina": "my.oschina.net",
    "51cto": "blog.51cto.com",
}

DEFAULT_KEYWORDS = [
    "机器学习",
    "深度学习",
    "自然语言处理",
    "计算机视觉",
    "数据库",
    "分布式系统",
    "网络安全",
    "算法设计",
    "操作系统",
    "编程语言",
]


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip().lower())
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "query"


def ensure_firecrawl() -> None:
    result = subprocess.run(
        ["firecrawl", "--status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("firecrawl CLI 不可用，请先确认已安装并登录。")


def run_search(query: str, output_path: Path, limit: int, country: str) -> dict:
    cmd = [
        "firecrawl",
        "search",
        query,
        "--scrape",
        "--limit",
        str(limit),
        "--json",
        "-o",
        str(output_path),
    ]
    if country:
        cmd.extend(["--country", country])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "firecrawl search 失败")

    with output_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_items(
    payload: dict,
    *,
    community: str,
    keyword: str,
    site: str,
) -> List[dict]:
    web_items = (((payload or {}).get("data") or {}).get("web") or [])
    normalized: List[dict] = []

    for item in web_items:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        description = (item.get("description") or "").strip()
        markdown = (item.get("markdown") or "").strip()
        if not url or not title:
            continue

        normalized.append({
            "community": community,
            "site": site,
            "keyword": keyword,
            "title": title,
            "url": url,
            "description": description,
            "markdown": markdown,
            "markdown_length": len(markdown),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return normalized


def dedupe(records: Iterable[dict]) -> List[dict]:
    seen = set()
    output = []
    for record in records:
        key = record["url"].split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="批量抓取多个社区帖子")
    parser.add_argument(
        "--communities",
        nargs="+",
        default=list(COMMUNITY_SITES.keys()),
        help=f"社区列表，可选: {', '.join(COMMUNITY_SITES.keys())}",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="关键词列表",
    )
    parser.add_argument(
        "--limit-per-query",
        type=int,
        default=4,
        help="每个 社区×关键词 抓取结果数，默认 4",
    )
    parser.add_argument(
        "--country",
        default="cn",
        help="Firecrawl 搜索国家代码，默认 cn",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.8,
        help="每次搜索之间等待秒数，默认 0.8",
    )
    parser.add_argument(
        "--output-dir",
        default="../.firecrawl/community-batch",
        help="输出目录，默认 ../.firecrawl/community-batch",
    )
    args = parser.parse_args()

    invalid = [name for name in args.communities if name not in COMMUNITY_SITES]
    if invalid:
        raise SystemExit(f"不支持的社区: {', '.join(invalid)}")

    ensure_firecrawl()

    output_dir = Path(args.output_dir).resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    all_records: List[dict] = []
    query_stats = []
    total_queries = len(args.communities) * len(args.keywords)
    query_index = 0

    print("===== 批量社区抓取开始 =====")
    print(f"社区: {', '.join(args.communities)}")
    print(f"关键词数: {len(args.keywords)}")
    print(f"每查询抓取: {args.limit_per_query}")
    print(f"预计查询数: {total_queries}")
    print(f"输出目录: {output_dir}")
    print()

    for community in args.communities:
        site = COMMUNITY_SITES[community]
        for keyword in args.keywords:
            query_index += 1
            query = f"site:{site} {keyword}"
            filename = f"{community}__{slugify(keyword)}.json"
            output_path = raw_dir / filename
            print(f"[{query_index:>3}/{total_queries}] {community:<8} | {keyword}")
            try:
                payload = run_search(query, output_path, args.limit_per_query, args.country)
                records = normalize_items(payload, community=community, keyword=keyword, site=site)
                all_records.extend(records)
                query_stats.append({
                    "community": community,
                    "site": site,
                    "keyword": keyword,
                    "query": query,
                    "count": len(records),
                    "raw_file": str(output_path),
                })
                print(f"         -> 命中 {len(records)} 篇")
            except Exception as e:
                query_stats.append({
                    "community": community,
                    "site": site,
                    "keyword": keyword,
                    "query": query,
                    "count": 0,
                    "error": str(e),
                    "raw_file": str(output_path),
                })
                print(f"         -> 失败: {e}")

            time.sleep(max(args.sleep, 0))

    deduped_records = dedupe(all_records)
    posts_path = output_dir / "posts.jsonl"
    summary_path = output_dir / "summary.json"
    write_jsonl(posts_path, deduped_records)

    by_community = {community: 0 for community in args.communities}
    for record in deduped_records:
        by_community[record["community"]] = by_community.get(record["community"], 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "communities": args.communities,
        "keywords": args.keywords,
        "limit_per_query": args.limit_per_query,
        "country": args.country,
        "total_queries": total_queries,
        "total_records_before_dedupe": len(all_records),
        "total_records_after_dedupe": len(deduped_records),
        "by_community": by_community,
        "output_files": {
            "posts_jsonl": str(posts_path),
            "raw_dir": str(raw_dir),
        },
        "query_stats": query_stats,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("===== 抓取完成 =====")
    print(f"去重前: {len(all_records)}")
    print(f"去重后: {len(deduped_records)}")
    for community, count in by_community.items():
        print(f"  {community:<8}: {count}")
    print(f"posts.jsonl: {posts_path}")
    print(f"summary.json: {summary_path}")


if __name__ == "__main__":
    main()
