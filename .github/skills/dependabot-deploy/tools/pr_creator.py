"""Pull request creation: creates a draft PR after successful testing."""

import os
import sys
from dataclasses import dataclass
from typing import Optional

from .utils import logger, print_phase, run_cmd


@dataclass
class PrResult:
    pr_url: str
    pr_number: int
    branch_name: str
    target_branch: str
    success: bool
    message: str


def create_draft_pr(
    repo_root: str,
    branch_name: str,
    target_branch: str = "dev",
    title: str = "",
    body: str = "",
    report_path: Optional[str] = None,
) -> PrResult:
    """Create a draft pull request on GitHub.

    Args:
        repo_root: Repository root path.
        branch_name: Source branch for the PR.
        target_branch: Target branch (default: dev).
        title: PR title (auto-generated if empty).
        body: PR body (auto-generated from report if empty).
        report_path: Path to deployment report to include in PR body.
    """
    print_phase("Create Draft Pull Request")

    # Ensure branch is pushed
    run_cmd(f"git push origin {branch_name}", cwd=repo_root, check=False)

    # Auto-generate title
    if not title:
        title = f"chore(deps): dependency updates from {branch_name}"

    # Auto-generate body from report
    if not body:
        body = _build_pr_body(branch_name, target_branch, report_path)

    # Create draft PR via GitHub CLI
    logger.info("Creating draft PR: %s → %s", branch_name, target_branch)

    cmd = (
        f'gh pr create '
        f'--base {target_branch} '
        f'--head {branch_name} '
        f'--title "{title}" '
        f'--body "{_escape_for_shell(body)}" '
        f'--draft'
    )

    result = run_cmd(cmd, cwd=repo_root, check=False)

    if result.returncode == 0:
        pr_url = result.stdout.strip()
        pr_number = _extract_pr_number(pr_url)
        logger.info("✔ Draft PR created: %s", pr_url)
        return PrResult(
            pr_url=pr_url,
            pr_number=pr_number,
            branch_name=branch_name,
            target_branch=target_branch,
            success=True,
            message=f"Draft PR #{pr_number} created: {pr_url}",
        )
    else:
        error = (result.stderr or "") + (result.stdout or "")

        # Check if PR already exists
        if "already exists" in error.lower():
            logger.info("PR already exists for this branch, fetching URL...")
            existing = run_cmd(
                f"gh pr view {branch_name} --json url,number -q .url",
                cwd=repo_root, check=False,
            )
            if existing.returncode == 0 and existing.stdout.strip():
                pr_url = existing.stdout.strip()
                pr_number = _extract_pr_number(pr_url)
                logger.info("✔ Existing PR found: %s", pr_url)
                return PrResult(
                    pr_url=pr_url,
                    pr_number=pr_number,
                    branch_name=branch_name,
                    target_branch=target_branch,
                    success=True,
                    message=f"Existing PR #{pr_number}: {pr_url}",
                )

        logger.error("✘ Failed to create PR: %s", error[:300])
        return PrResult(
            pr_url="",
            pr_number=0,
            branch_name=branch_name,
            target_branch=target_branch,
            success=False,
            message=f"Failed to create PR: {error[:200]}",
        )


def _build_pr_body(branch_name: str, target_branch: str, report_path: Optional[str]) -> str:
    """Build PR body from deployment report."""
    lines = [
        "## Dependency Update Validation",
        "",
        f"**Source:** `{branch_name}`",
        f"**Target:** `{target_branch}`",
        "",
        "This PR was auto-generated after validating dependency updates through:",
        "- ✅ Docker image build (API + App)",
        "- ✅ Azure deployment (azd up)",
        "- ✅ Playwright E2E tests",
        "",
    ]

    # Append report if available
    if report_path and os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            lines.append("<details>")
            lines.append("<summary>Deployment Validation Report</summary>")
            lines.append("")
            lines.append(report_content)
            lines.append("")
            lines.append("</details>")
        except OSError:
            pass

    return "\n".join(lines)


def _escape_for_shell(text: str) -> str:
    """Escape text for shell command argument."""
    return text.replace('"', '\\"').replace("\n", "\\n").replace("$", "\\$")


def _extract_pr_number(pr_url: str) -> int:
    """Extract PR number from GitHub URL."""
    import re
    match = re.search(r"/pull/(\d+)", pr_url)
    return int(match.group(1)) if match else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create draft PR")
    parser.add_argument("--repo-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--target-branch", default="dev")
    parser.add_argument("--title", default="")
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args()

    result = create_draft_pr(
        args.repo_root, args.branch_name, args.target_branch,
        args.title, report_path=args.report_path,
    )
    print(f"\n{'✔' if result.success else '✘'} {result.message}")
    sys.exit(0 if result.success else 1)
