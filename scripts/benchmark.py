"""
Runs every business query in sql/03_business_queries.sql through
EXPLAIN (ANALYZE, FORMAT JSON), records execution time + whether the
plan used a sequential scan or an index scan / partition pruning, and
writes results/<label>.json.

Usage:
    python benchmark.py --label before
    ... run sql/02_indexes_and_partitioning.sql ...
    python benchmark.py --label after
    python benchmark.py --compare   # prints a before/after table
"""
import argparse
import json
import os
import re

import psycopg2
from dotenv import load_dotenv

load_dotenv()

QUERIES_FILE = os.path.join(os.path.dirname(__file__), "..", "sql", "03_business_queries.sql")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def parse_queries(path):
    """Splits the tagged SQL file into {name: sql_text}."""
    with open(path) as f:
        content = f.read()

    parts = re.split(r"-- @query:\s*(\w+)", content)
    # parts[0] is header comments before the first tag; then alternating name, sql
    queries = {}
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        sql = parts[i + 1].strip().rstrip(";")
        queries[name] = sql
    return queries


def contains_seq_scan(plan_node, found=None):
    if found is None:
        found = []
    if isinstance(plan_node, dict):
        if plan_node.get("Node Type") == "Seq Scan":
            found.append(plan_node.get("Relation Name"))
        for v in plan_node.values():
            contains_seq_scan(v, found)
    elif isinstance(plan_node, list):
        for item in plan_node:
            contains_seq_scan(item, found)
    return found


def run_query(conn, name, sql):
    with conn.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON, TIMING true) {sql}")
        plan_json = cur.fetchone()[0][0]

    exec_time_ms = plan_json["Execution Time"]
    planning_time_ms = plan_json["Planning Time"]
    seq_scans = contains_seq_scan(plan_json["Plan"])

    return {
        "query": name,
        "execution_time_ms": round(exec_time_ms, 2),
        "planning_time_ms": round(planning_time_ms, 2),
        "seq_scans_on": seq_scans,
    }


def run_benchmark(label):
    queries = parse_queries(QUERIES_FILE)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])

    results = []
    for name, sql in queries.items():
        print(f"Running {name} ...")
        try:
            result = run_query(conn, name, sql)
        except Exception as e:
            conn.rollback()
            result = {"query": name, "error": str(e)}
        results.append(result)
        print(f"  -> {result}")

    conn.close()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"{label}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {out_path}")


def compare():
    before_path = os.path.join(RESULTS_DIR, "before.json")
    after_path = os.path.join(RESULTS_DIR, "after.json")
    if not (os.path.exists(before_path) and os.path.exists(after_path)):
        print("Need both results/before.json and results/after.json — run both labels first.")
        return

    with open(before_path) as f:
        before = {r["query"]: r for r in json.load(f)}
    with open(after_path) as f:
        after = {r["query"]: r for r in json.load(f)}

    print(f"\n{'Query':<28}{'Before (ms)':>14}{'After (ms)':>14}{'Speedup':>12}")
    print("-" * 68)
    for name in before:
        b = before[name].get("execution_time_ms")
        a = after.get(name, {}).get("execution_time_ms")
        if b is None or a is None:
            print(f"{name:<28}{'error':>14}")
            continue
        speedup = f"{b / a:.1f}x" if a > 0 else "n/a"
        print(f"{name:<28}{b:>14.1f}{a:>14.1f}{speedup:>12}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", help="e.g. before / after")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if args.compare:
        compare()
    elif args.label:
        run_benchmark(args.label)
    else:
        parser.error("pass --label <name> or --compare")
