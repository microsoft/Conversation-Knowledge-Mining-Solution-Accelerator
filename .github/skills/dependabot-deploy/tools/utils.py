"""Utility functions shared across tools."""

import logging
import subprocess
import sys
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deploy-test-skill")


class SkillError(Exception):
    """Raised when a skill phase fails."""

    def __init__(self, phase: str, message: str, recoverable: bool = False):
        self.phase = phase
        self.recoverable = recoverable
        super().__init__(f"[{phase}] {message}")


def run_cmd(
    cmd: str | list[str],
    cwd: Optional[str] = None,
    check: bool = True,
    capture: bool = True,
    shell: bool = True,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """Run a shell command with logging."""
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    logger.info("▶ %s", cmd_str)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=capture,
            text=True,
            shell=shell,
            timeout=timeout,
        )
        if capture and result.stdout and result.stdout.strip():
            for line in result.stdout.strip().splitlines()[:20]:
                logger.info("  %s", line)
        if capture and result.stderr and result.stderr.strip():
            for line in result.stderr.strip().splitlines()[:10]:
                logger.warning("  stderr: %s", line)
        return result
    except subprocess.CalledProcessError as exc:
        logger.error("✘ Command failed (exit %d): %s", exc.returncode, cmd_str)
        if exc.stdout:
            logger.error("  stdout: %s", exc.stdout[-500:])
        if exc.stderr:
            logger.error("  stderr: %s", exc.stderr[-500:])
        raise
    except subprocess.TimeoutExpired:
        logger.error("✘ Command timed out after %ds: %s", timeout, cmd_str)
        raise


def print_phase(name: str):
    """Print a phase header."""
    border = "=" * 60
    logger.info(border)
    logger.info("  PHASE: %s", name)
    logger.info(border)


def confirm_tool_available(tool: str) -> bool:
    """Check if a CLI tool is available."""
    # azd uses 'version' subcommand, not '--version'
    version_flag = "version" if tool == "azd" else "--version"
    try:
        result = run_cmd(f"{tool} {version_flag}", check=False, capture=True)
        return result.returncode == 0
    except FileNotFoundError:
        logger.error("✘ Required tool not found: %s", tool)
        return False
