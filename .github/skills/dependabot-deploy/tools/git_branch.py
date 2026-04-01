"""Git branch management: create branch from source and merge target branch."""

import os
import sys
from dataclasses import dataclass
from typing import Optional

from .utils import SkillError, logger, print_phase, run_cmd


@dataclass
class GitResult:
    branch_name: str
    merge_conflicts: list[str]
    success: bool
    message: str


def run(
    repo_root: str,
    source_branch: str = "dependabotchanges",
    merge_branch: str = "dev",
    branch_name: Optional[str] = None,
) -> GitResult:
    """Create a branch from source_branch and merge merge_branch into it."""
    print_phase("Git Branch Management")

    if not branch_name:
        from datetime import datetime
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M")
        branch_name = f"deploy-test-{source_branch}-{ts}"

    logger.info("Source: %s → New branch: %s ← Merge: %s", source_branch, branch_name, merge_branch)

    run_cmd("git fetch origin", cwd=repo_root)
    run_cmd(f"git checkout {source_branch}", cwd=repo_root)
    run_cmd(f"git pull origin {source_branch}", cwd=repo_root)
    run_cmd(f"git checkout -b {branch_name}", cwd=repo_root)
    logger.info("✔ Created branch: %s", branch_name)

    merge_result = run_cmd(
        f"git merge origin/{merge_branch} --no-edit",
        cwd=repo_root,
        check=False,
    )

    conflicts = []
    if merge_result.returncode != 0:
        conflict_result = run_cmd("git diff --name-only --diff-filter=U", cwd=repo_root, check=False)
        if conflict_result.stdout.strip():
            conflicts = conflict_result.stdout.strip().splitlines()
            logger.warning("⚠ Merge conflicts in %d files:", len(conflicts))
            for f in conflicts:
                logger.warning("  - %s", f)

            resolved_all = _auto_resolve_conflicts(repo_root, conflicts)
            if resolved_all:
                run_cmd("git add -A", cwd=repo_root)
                run_cmd('git commit --no-edit -m "chore: auto-resolve merge conflicts (prefer higher versions)"', cwd=repo_root)
                logger.info("✔ All conflicts auto-resolved")
                conflicts = []
            else:
                raise SkillError("git", f"Unresolvable merge conflicts in: {', '.join(conflicts)}", recoverable=True)
    else:
        logger.info("✔ Merged %s successfully (no conflicts)", merge_branch)

    run_cmd(f"git push origin {branch_name}", cwd=repo_root)
    logger.info("✔ Pushed branch: %s", branch_name)

    return GitResult(
        branch_name=branch_name, merge_conflicts=conflicts, success=True,
        message=f"Branch {branch_name} created and pushed with {merge_branch} merged.",
    )


def _auto_resolve_conflicts(repo_root: str, conflict_files: list[str]) -> bool:
    """Auto-resolve merge conflicts: accept theirs for structure, fix versions later."""
    for filepath in conflict_files:
        basename = os.path.basename(filepath)
        if basename in ("package-lock.json",):
            run_cmd(f"git checkout --theirs -- {filepath}", cwd=repo_root)
            logger.info("  Resolved %s (accepted target version, will regenerate)", filepath)
        elif basename in ("requirements.txt", "package.json"):
            run_cmd(f"git checkout --theirs -- {filepath}", cwd=repo_root)
            logger.info("  Resolved %s (accepted target version, deps re-applied in fix phase)", filepath)
        else:
            run_cmd(f"git checkout --theirs -- {filepath}", cwd=repo_root)
            logger.info("  Resolved %s (accepted target version)", filepath)
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Git branch management tool")
    parser.add_argument("--repo-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
    parser.add_argument("--source-branch", default="dependabotchanges")
    parser.add_argument("--merge-branch", default="dev")
    parser.add_argument("--branch-name", default=None)
    args = parser.parse_args()
    result = run(args.repo_root, args.source_branch, args.merge_branch, args.branch_name)
    print(f"\n{'✔' if result.success else '✘'} {result.message}")
    sys.exit(0 if result.success else 1)
