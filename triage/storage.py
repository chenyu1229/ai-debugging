from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "triage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  ok INTEGER NOT NULL,
  return_code INTEGER NOT NULL,
  raw_output TEXT NOT NULL,
  triage_json TEXT NOT NULL,
  all_tests_json TEXT NOT NULL,
  failed_tests_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
"""

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

def insert_run(
    created_at: str,
    ok: bool,
    return_code: int,
    raw_output: str,
    triage: Dict[str, Any],
    all_tests: List[str],
    failed_tests: List[str],
) -> int:
    init_db()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO runs(created_at, ok, return_code, raw_output, triage_json, all_tests_json, failed_tests_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                1 if ok else 0,
                int(return_code),
                raw_output,
                json.dumps(triage, ensure_ascii=False),
                json.dumps(all_tests, ensure_ascii=False),
                json.dumps(failed_tests, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()

def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, created_at, ok, return_code, triage_json FROM runs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
        out = []
        for rid, created_at, ok, rc, triage_json in rows:
            out.append(
                {
                    "id": rid,
                    "created_at": created_at,
                    "ok": bool(ok),
                    "return_code": rc,
                    "triage": json.loads(triage_json),
                }
            )
        return out
    finally:
        conn.close()

def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, created_at, ok, return_code, raw_output, triage_json, all_tests_json, failed_tests_json FROM runs WHERE id = ?",
            (int(run_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        rid, created_at, ok, rc, raw_output, triage_json, all_tests_json, failed_tests_json = row
        return {
            "id": rid,
            "created_at": created_at,
            "ok": bool(ok),
            "return_code": rc,
            "raw_output": raw_output,
            "triage": json.loads(triage_json),
            "all_tests": json.loads(all_tests_json),
            "failed_tests": json.loads(failed_tests_json),
        }
    finally:
        conn.close()

def _recent_runs(window: int = 50) -> List[Dict[str, Any]]:
    init_db()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, created_at, all_tests_json, failed_tests_json FROM runs ORDER BY id DESC LIMIT ?",
            (int(window),),
        )
        rows = cur.fetchall()
        out = []
        for rid, created_at, allj, failj in rows:
            out.append(
                {
                    "id": rid,
                    "created_at": created_at,
                    "all_tests": json.loads(allj),
                    "failed_tests": set(json.loads(failj)),
                }
            )
        return out
    finally:
        conn.close()

def compute_flaky_tests(window: int = 30, min_occurrences: int = 3) -> Dict[str, Dict[str, Any]]:
    """
    Very practical flaky heuristic:
    - Look at last `window` runs
    - For each test, count pass/fail occurrences (assuming tests executed)
    - Mark flaky if it has BOTH passes and failures and total >= min_occurrences

    Returns dict: test_nodeid -> {runs, fails, passes, fail_rate, is_flaky}
    """
    runs = _recent_runs(window=window)
    # Universe: union of collected tests across runs
    universe = set()
    for r in runs:
        for t in r["all_tests"]:
            universe.add(t)

    stats: Dict[str, Dict[str, Any]] = {}
    for t in sorted(universe):
        total = 0
        fails = 0
        for r in runs:
            # If a run didn't include this test in its collection list, skip it for that run
            if t not in r["all_tests"]:
                continue
            total += 1
            if t in r["failed_tests"]:
                fails += 1
        if total == 0:
            continue
        passes = total - fails
        fail_rate = fails / total if total else 0.0
        is_flaky = (total >= min_occurrences) and (fails > 0) and (passes > 0)
        stats[t] = {
            "runs": total,
            "fails": fails,
            "passes": passes,
            "fail_rate": round(fail_rate, 3),
            "is_flaky": is_flaky,
        }
    return stats
