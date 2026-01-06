from __future__ import annotations

import json
from datetime import datetime, timezone
from triage.collect import run_pytest
from triage.decision import analyze_with_openai, analyze_with_rules
from triage.storage import insert_run, compute_flaky_tests

def run_once() -> int:
    result = run_pytest()
    created_at = datetime.now(timezone.utc).isoformat()

    if result.ok:
        triage = {
            "classification": "Unknown",
            "action": "Ignore",
            "block_ci": False,
            "confidence": 1.0,
            "reason": "All tests passed."
        }
        run_id = insert_run(
            created_at, True, result.return_code, result.raw_output, triage,
            all_tests=result.all_tests, failed_tests=result.failed_tests
        )
        print(json.dumps({"run_id": run_id, "ok": True, "triage": triage}, indent=2))
        return 0

    # Try LLM first, fall back to rules.
    try:
        triage = analyze_with_openai(result.raw_output)
        triage["engine"] = "genai"
    except Exception as e:
        triage = analyze_with_rules(result.raw_output)
        triage["engine"] = "rules"
        triage["llm_error"] = str(e)

    # Store run (includes test lists for flaky detection)
    run_id = insert_run(
        created_at, False, result.return_code, result.raw_output, triage,
        all_tests=result.all_tests, failed_tests=result.failed_tests
    )

    # Compute flaky stats from history and annotate current run for convenience
    flaky_stats = compute_flaky_tests(window=30, min_occurrences=3)
    flaky_failed = [t for t in result.failed_tests if flaky_stats.get(t, {}).get("is_flaky")]

    payload = {
        "run_id": run_id,
        "ok": False,
        "failed_tests": result.failed_tests,
        "triage": triage,
        "flaky_failed_tests": flaky_failed,
    }
    print(json.dumps(payload, indent=2))

    # CI decision point:
    # If failures are ONLY flaky, you might choose not to block. Here we keep it simple:
    # - keep triage decision as the source of truth
    return 1 if triage.get("block_ci") else 0

if __name__ == "__main__":
    raise SystemExit(run_once())
