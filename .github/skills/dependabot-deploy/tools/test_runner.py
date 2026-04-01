"""Playwright E2E test runner with retries and report generation."""

import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from .utils import logger, print_phase, run_cmd


@dataclass
class TestSuiteResult:
    name: str
    passed: int
    failed: int
    skipped: int
    total: int
    report_path: str
    success: bool


@dataclass
class TestResult:
    suites: list[TestSuiteResult] = field(default_factory=list)
    overall_success: bool = False
    report_dir: str = ""
    summary: str = ""


def run(
    repo_root: str,
    web_app_url: str,
    api_app_url: str,
    test_dir: str = "tests/e2e-test",
    use_case: str = "",
    test_suites: Optional[list[str]] = None,
    max_retries: int = 3,
    retry_delays: Optional[list[int]] = None,
    readiness_attempts: int = 10,
    readiness_interval: int = 30,
) -> TestResult:
    """Run Playwright E2E tests against the deployed application."""
    print_phase("Playwright E2E Testing")

    if retry_delays is None:
        retry_delays = [30, 60, 120]

    abs_test_dir = os.path.join(repo_root, test_dir)
    report_dir = os.path.join(abs_test_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)

    _setup_test_env(abs_test_dir, web_app_url, api_app_url)
    _wait_for_app(web_app_url, readiness_attempts, readiness_interval)

    if test_suites is None:
        test_suites = _auto_detect_test_suites(abs_test_dir, use_case)

    result = TestResult(report_dir=report_dir)

    for suite_file in test_suites:
        suite_name = os.path.splitext(os.path.basename(suite_file))[0]
        report_path = os.path.join(report_dir, f"{suite_name}_report.html")

        logger.info("Running test suite: %s", suite_name)
        suite_result = _run_suite_with_retries(
            test_dir=abs_test_dir, suite_file=suite_file, suite_name=suite_name,
            report_path=report_path, max_retries=max_retries, retry_delays=retry_delays,
        )
        result.suites.append(suite_result)

    result.overall_success = all(s.success for s in result.suites) if result.suites else False
    result.summary = _generate_summary(result)
    logger.info("\n%s", result.summary)
    return result


def _setup_test_env(test_dir: str, web_app_url: str, api_app_url: str):
    """Set up the test environment."""
    logger.info("Setting up test environment...")
    env_file = os.path.join(test_dir, ".env")
    with open(env_file, "w") as f:
        f.write(f"url = '{web_app_url.rstrip('/')}'\n")
        f.write(f"api_url = '{api_app_url.rstrip('/')}'\n")
    logger.info("✔ Created .env with deployment URLs")

    req_file = os.path.join(test_dir, "requirements.txt")
    if os.path.exists(req_file):
        run_cmd(f"pip install -r {req_file}", cwd=test_dir)

    run_cmd("playwright install chromium", cwd=test_dir, check=False)
    logger.info("✔ Test environment configured")


def _wait_for_app(url: str, max_attempts: int, interval: int):
    """Wait for the application to be ready."""
    import urllib.request
    import urllib.error

    logger.info("Waiting for application readiness: %s", url)
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=30)
            if resp.status == 200:
                logger.info("✔ Application is ready (attempt %d/%d)", attempt, max_attempts)
                return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            logger.info("  Attempt %d/%d: Not ready (%s). Waiting %ds...", attempt, max_attempts, type(e).__name__, interval)
            time.sleep(interval)
    logger.warning("⚠ Application may not be fully ready after %d attempts", max_attempts)


def _auto_detect_test_suites(test_dir: str, use_case: str) -> list[str]:
    """Auto-detect test suite files from the test directory."""
    suites = []

    # Look in tests/ subdirectory first, then test_dir itself
    search_dirs = []
    tests_subdir = os.path.join(test_dir, "tests")
    if os.path.isdir(tests_subdir):
        search_dirs.append(tests_subdir)
    search_dirs.append(test_dir)

    for search_dir in search_dirs:
        for f in sorted(os.listdir(search_dir)):
            if f.startswith("test_") and f.endswith(".py"):
                rel_path = os.path.relpath(os.path.join(search_dir, f), test_dir)
                # If use_case is set, filter by it
                if use_case and use_case.lower().replace("_", "") not in f.lower().replace("_", ""):
                    continue
                suites.append(rel_path)

    if not suites:
        # Fallback: include all test files regardless of use_case
        for search_dir in search_dirs:
            for f in sorted(os.listdir(search_dir)):
                if f.startswith("test_") and f.endswith(".py"):
                    suites.append(os.path.relpath(os.path.join(search_dir, f), test_dir))

    logger.info("Auto-detected %d test suite(s): %s", len(suites), ", ".join(suites))
    return suites


def _run_suite_with_retries(
    test_dir: str, suite_file: str, suite_name: str,
    report_path: str, max_retries: int, retry_delays: list[int],
) -> TestSuiteResult:
    """Run a test suite with retry logic."""
    passed = failed = skipped = total = 0

    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
            logger.info("  Retry %d/%d after %ds delay...", attempt, max_retries, delay)
            time.sleep(delay)

        cmd = f"python -m pytest {suite_file} -v --html={report_path} --self-contained-html --tb=short -q"
        result = run_cmd(cmd, cwd=test_dir, check=False, timeout=600)
        output = (result.stdout or "") + (result.stderr or "")
        passed, failed, skipped, total = _parse_pytest_output(output)

        if result.returncode == 0 or failed == 0:
            logger.info("✔ %s: %d passed, %d failed, %d skipped", suite_name, passed, failed, skipped)
            return TestSuiteResult(name=suite_name, passed=passed, failed=failed, skipped=skipped,
                                  total=total, report_path=report_path, success=True)
        logger.warning("⚠ %s: %d passed, %d failed (attempt %d/%d)", suite_name, passed, failed, attempt + 1, max_retries + 1)

    logger.error("✘ %s: Failed after %d attempts", suite_name, max_retries + 1)
    return TestSuiteResult(name=suite_name, passed=passed, failed=failed, skipped=skipped,
                          total=total, report_path=report_path, success=False)


def _parse_pytest_output(output: str) -> tuple[int, int, int, int]:
    passed = failed = skipped = 0
    m_p = re.search(r"(\d+) passed", output)
    m_f = re.search(r"(\d+) failed", output)
    m_s = re.search(r"(\d+) skipped", output)
    if m_p: passed = int(m_p.group(1))
    if m_f: failed = int(m_f.group(1))
    if m_s: skipped = int(m_s.group(1))
    return passed, failed, skipped, passed + failed + skipped


def _generate_summary(result: TestResult) -> str:
    lines = [
        "### Test Results Summary", "",
        "| Suite | Passed | Failed | Skipped | Total | Status |",
        "|-------|--------|--------|---------|-------|--------|",
    ]
    for s in result.suites:
        status = "✅ PASS" if s.success else "❌ FAIL"
        lines.append(f"| {s.name} | {s.passed} | {s.failed} | {s.skipped} | {s.total} | {status} |")
    tp = sum(s.passed for s in result.suites)
    tf = sum(s.failed for s in result.suites)
    ts = sum(s.skipped for s in result.suites)
    overall = "✅ ALL PASS" if result.overall_success else "❌ FAILURES"
    lines.append(f"| **TOTAL** | **{tp}** | **{tf}** | **{ts}** | **{tp+tf+ts}** | **{overall}** |")
    lines.extend(["", f"Reports: `{result.report_dir}`"])
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="E2E test runner")
    parser.add_argument("--repo-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--test-dir", default="tests/e2e-test")
    parser.add_argument("--use-case", default="")
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()
    result = run(args.repo_root, args.web_url, args.api_url, args.test_dir, args.use_case, max_retries=args.max_retries)
    print(f"\n{'✔' if result.overall_success else '✘'} Testing complete")
    sys.exit(0 if result.overall_success else 1)
