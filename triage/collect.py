import subprocess
import re
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class PytestResult:
    ok: bool
    raw_output: str
    return_code: int
    all_tests: List[str]
    failed_tests: List[str]

_FAILED_RE = re.compile(r"^FAILED\s+([^\s]+)\s+-\s+", re.MULTILINE)

def _run(cmd: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode, raw

def collect_all_tests() -> List[str]:
    """
    Collect all pytest nodeids (test identifiers) via --collect-only.

    This gives us the universe of tests so we can infer "pass" for tests that
    don't appear in the failed list for a given run.
    """
    rc, raw = _run(["pytest", "--collect-only", "-q"])
    # Typical lines contain nodeids like:
    #   app_under_test/test_buggy.py::test_divide_ok
    tests = []
    for line in raw.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("<") and not line.startswith("ERROR"):
            # very lightweight filter
            tests.append(line)
    # If collection fails, degrade gracefully
    return sorted(set(tests))

def extract_failed_tests(pytest_output: str) -> List[str]:
    """
    Extract failed test nodeids from pytest output.
    Works with the standard pytest summary lines:
      FAILED path/to/test.py::test_name - ...
    """
    return sorted(set(_FAILED_RE.findall(pytest_output or "")))

def run_pytest() -> PytestResult:
    """
    Run pytest and capture raw output + derive:
      - all_tests: collected nodeids
      - failed_tests: failed nodeids for this run
    """
    all_tests = collect_all_tests()
    rc, raw = _run(["pytest", "-q"])
    failed = extract_failed_tests(raw)
    ok = (rc == 0)

    # If collection failed, we can still store failed tests.
    return PytestResult(ok=ok, raw_output=raw, return_code=rc, all_tests=all_tests, failed_tests=failed)
