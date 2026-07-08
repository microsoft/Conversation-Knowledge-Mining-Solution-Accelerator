"""Thin wrapper to run the canonical create-agent script from the repo root."""

import os
import subprocess
import sys


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    target = os.path.join(project_root, "scripts", "create_agent.py")

    if not os.path.exists(target):
        print(f"ERROR: Canonical script not found: {target}")
        return 1

    cmd = [sys.executable, target, *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
