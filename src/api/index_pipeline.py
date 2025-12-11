"""
Standalone orchestrator to run the index creation and processing pipeline
composed of the existing scripts:

 - infra/scripts/index_scripts/01_create_search_index.py
 - infra/scripts/index_scripts/02_create_cu_template_text.py
 - infra/scripts/index_scripts/02_create_cu_template_audio.py
 - infra/scripts/index_scripts/03_cu_process_data_text.py

This module exposes a single callable `run_index_pipeline` that can be invoked
from FastAPI or any Python caller. It runs each script sequentially while
injecting `KEY_VAULT_NAME` and `MANAGED_IDENTITY_CLIENT_ID` at runtime so no
in-file edits are required.

Packages: This file assumes required Azure SDK packages are installed.
You mentioned you will manage venv and installs.
"""

from __future__ import annotations

import os
import sys
import runpy
from pathlib import Path
from typing import Dict, Any


# Workspace-relative paths to the scripts
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = WORKSPACE_ROOT / "infra" / "scripts" / "index_scripts"
DATA_DIR = WORKSPACE_ROOT / "infra" / "data"

SCRIPT_FILES = [
    SCRIPTS_DIR / "01_create_search_index.py",
    SCRIPTS_DIR / "02_create_cu_template_text.py",
    SCRIPTS_DIR / "02_create_cu_template_audio.py",
    SCRIPTS_DIR / "03_cu_process_data_text.py",
]


def _run_script_with_overrides(script_path: Path, kv_name: str, mici: str) -> Dict[str, Any]:
    """Run a Python script file with runtime constant overrides.

    Overrides the global variables `KEY_VAULT_NAME` and `MANAGED_IDENTITY_CLIENT_ID`
    inside the script by supplying them via `init_globals` to `runpy.run_path`.

    Returns the globals dict produced by the script for basic introspection.
    """
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    init_globals: Dict[str, Any] = {
        "KEY_VAULT_NAME": kv_name,
        "MANAGED_IDENTITY_CLIENT_ID": mici,
        # Ensure script can import local helpers by adjusting sys.path-like behavior
        "__name__": "__main__",
        "__file__": str(script_path),
        "__package__": None,
    }

    # Provide absolute paths for analyzer templates to avoid cwd-relative issues
    if script_path.name == "02_create_cu_template_text.py":
        init_globals["ANALYZER_TEMPLATE_FILE"] = str(DATA_DIR / "ckm-analyzer_config_text.json")
    elif script_path.name == "02_create_cu_template_audio.py":
        init_globals["ANALYZER_TEMPLATE_FILE"] = str(DATA_DIR / "ckm-analyzer_config_audio.json")

    # Allow scripts to find sibling modules (e.g., content_understanding_client)
    sys_path_added = False
    scripts_parent = str(SCRIPTS_DIR)
    if scripts_parent not in sys.path:
        sys.path.insert(0, scripts_parent)
        sys_path_added = True

    try:
        result_globals = runpy.run_path(str(script_path), init_globals=init_globals)
        return result_globals
    finally:
        # Clean up sys.path modification to avoid side effects
        if sys_path_added:
            try:
                sys.path.remove(scripts_parent)
            except ValueError:
                pass


def run_index_pipeline(keyvault_name: str, managed_identity_client_id: str) -> Dict[str, Any]:
    """Run the full pipeline: search index creation, CU analyzers, and data processing.

    Parameters
    - keyvault_name: Azure Key Vault name containing required secrets
    - managed_identity_client_id: Client ID of the user-assigned managed identity

    Returns
    - A summary dict with per-script statuses and any returned globals
    """
    summary: Dict[str, Any] = {
        "workspace_root": str(WORKSPACE_ROOT),
        "scripts_dir": str(SCRIPTS_DIR),
        "steps": [],
    }

    for script in SCRIPT_FILES:
        step_info: Dict[str, Any] = {"script": str(script)}
        try:
            result = _run_script_with_overrides(script, keyvault_name, managed_identity_client_id)
            step_info.update({
                "status": "success",
                "result_keys": sorted(list(result.keys())),
            })
        except Exception as e:
            step_info.update({
                "status": "error",
                "error": str(e),
            })
            # Stop at first failing step to make failures obvious to the caller
            summary["steps"].append(step_info)
            break
        summary["steps"].append(step_info)

    return summary


# Optional: minimal FastAPI-compatible callable without importing FastAPI itself
def run_index_pipeline_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """A thin handler suitable for wiring into a FastAPI route.

    Expects a JSON-like dict with keys:
      - keyvault_name
      - managed_identity_client_id

    Returns the pipeline summary dict.
    """
    kv = payload.get("keyvault_name")
    mici = payload.get("managed_identity_client_id")
    if not kv or not mici:
        raise ValueError("Missing required fields: 'keyvault_name' and 'managed_identity_client_id'")
    return run_index_pipeline(kv, mici)


if __name__ == "__main__":
    # Allow quick local testing via CLI:
    # python src/api/index_pipeline.py <keyvault_name> <managed_identity_client_id>
    if len(sys.argv) < 3:
        print("Usage: python index_pipeline.py <keyvault_name> <managed_identity_client_id>")
        sys.exit(2)
    kv_arg = sys.argv[1]
    mici_arg = sys.argv[2]
    out = run_index_pipeline(kv_arg, mici_arg)
    # Print a concise summary
    print("Pipeline result:")
    for step in out.get("steps", []):
        print(f" - {os.path.basename(step['script'])}: {step['status']}")
        if step.get("error"):
            print(f"   error: {step['error']}")