"""Parameter resolver: auto-resolves all azd deployment parameters.

Reads Bicep param declarations and main.parameters.json to discover what
env vars are needed, applies sensible defaults, runs quota checks, and
returns a complete dict of azd env vars — zero user input required.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from .utils import logger, print_phase, run_cmd


@dataclass
class ResolvedParams:
    """All resolved parameters ready to pass to azd env set."""
    azd_env: dict[str, str]
    region: str
    ai_service_region: str
    use_case: str
    success: bool
    message: str


# Default parameter values when nothing else is available
_DEFAULTS = {
    "AZURE_ENV_MODEL_DEPLOYMENT_TYPE": "GlobalStandard",
    "AZURE_ENV_GPT_MODEL_NAME": "gpt-4o-mini",
    "AZURE_ENV_GPT_MODEL_VERSION": "2024-07-18",
    "AZURE_ENV_GPT_MODEL_CAPACITY": "150",
    "AZURE_ENV_EMBEDDING_MODEL_NAME": "text-embedding-3-small",
    "AZURE_ENV_EMBEDDING_DEPLOYMENT_CAPACITY": "80",
    "AZURE_ENV_CU_LOCATION": "swedencentral",
    "AZURE_ENV_SECONDARY_LOCATION": "eastus2",
    "AZURE_ENV_ENABLE_TELEMETRY": "true",
}


def resolve(
    repo_root: str,
    subscription_id: str,
    env_name: str,
    rg_name: str,
    image_tag: str,
    acr_hostname: str = "",
    preferred_region: str = "",
    use_case: str = "",
    extra_env: Optional[dict[str, str]] = None,
    skip_quota_check: bool = False,
) -> ResolvedParams:
    """Auto-resolve all deployment parameters with zero user input.

    Resolution order for each parameter:
      1. Explicit arg (extra_env overrides)
      2. Detected from repo (main.parameters.json defaults, main.bicep defaults)
      3. Quota-check-determined region
      4. Hardcoded sensible defaults

    Args:
        repo_root: Repository root.
        subscription_id: Azure subscription ID.
        env_name: AZD environment name.
        rg_name: Resource group name.
        image_tag: Docker image tag.
        acr_hostname: ACR hostname (if any).
        preferred_region: Preferred Azure region (quota-checked first).
        use_case: Use case (auto-detected from repo if empty).
        extra_env: Additional env vars that override everything.
        skip_quota_check: If True, use preferred_region without checking quota.
    """
    print_phase("Parameter Resolution")

    env = {}

    # Step 1: Load defaults from repo
    repo_defaults = _load_repo_defaults(repo_root)
    logger.info("Loaded %d defaults from repo", len(repo_defaults))

    # Step 2: Apply hardcoded defaults (lowest priority)
    for k, v in _DEFAULTS.items():
        env[k] = v

    # Step 3: Apply repo-detected defaults (override hardcoded)
    for k, v in repo_defaults.items():
        if v:
            env[k] = v

    # Step 4: Detect use case
    if not use_case:
        use_case = _detect_use_case_from_repo(repo_root) or "telecom"
        logger.info("Auto-detected use case: %s", use_case)

    # Step 5: Determine region via quota check
    region = preferred_region or env.get("AZURE_LOCATION", "eastus2")

    if not skip_quota_check:
        logger.info("Running quota check to find valid region...")
        from .quota_check import auto_select_region

        gpt_model = env.get("AZURE_ENV_GPT_MODEL_NAME", "gpt-4o-mini")
        deployment_type = env.get("AZURE_ENV_MODEL_DEPLOYMENT_TYPE", "GlobalStandard")
        embedding_model = env.get("AZURE_ENV_EMBEDDING_MODEL_NAME", "text-embedding-3-small")

        try:
            gpt_capacity = int(env.get("AZURE_ENV_GPT_MODEL_CAPACITY", "100"))
        except ValueError:
            gpt_capacity = 100
        try:
            emb_capacity = int(env.get("AZURE_ENV_EMBEDDING_DEPLOYMENT_CAPACITY", "80"))
        except ValueError:
            emb_capacity = 80

        try:
            region = auto_select_region(
                subscription_id=subscription_id,
                preferred_region=preferred_region,
                deployment_type=deployment_type,
                gpt_model=gpt_model,
                gpt_min_capacity=gpt_capacity,
                embedding_model=embedding_model,
                embedding_min_capacity=emb_capacity,
            )
            logger.info("✔ Quota check selected region: %s", region)
        except Exception as e:
            logger.warning("⚠ Quota check failed: %s. Using fallback: %s", e, region)
    else:
        logger.info("Skipping quota check, using region: %s", region)

    ai_service_region = region  # Same region for AI services

    # Step 6: Build final env dict
    env["AZURE_SUBSCRIPTION_ID"] = subscription_id
    env["AZURE_LOCATION"] = region
    env["AZURE_ENV_AI_SERVICE_LOCATION"] = ai_service_region
    env["AZURE_RESOURCE_GROUP"] = rg_name
    env["AZURE_ENV_NAME"] = env_name
    env["AZURE_ENV_IMAGE_TAG"] = image_tag
    env["USE_CASE"] = use_case

    if acr_hostname:
        env["AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT"] = acr_hostname

    # Step 7: Apply explicit overrides (highest priority)
    if extra_env:
        env.update(extra_env)

    # Log resolved params
    logger.info("Resolved %d parameters:", len(env))
    for k in sorted(env.keys()):
        v = env[k]
        if "secret" in k.lower() or "password" in k.lower() or "key" in k.lower():
            v = "***"
        logger.info("  %s = %s", k, v)

    return ResolvedParams(
        azd_env=env,
        region=region,
        ai_service_region=ai_service_region,
        use_case=use_case,
        success=True,
        message=f"Resolved {len(env)} params, region={region}, use_case={use_case}",
    )


def _load_repo_defaults(repo_root: str) -> dict[str, str]:
    """Extract default values from main.parameters.json and main.bicep."""
    defaults = {}

    # From main.parameters.json: extract ${VAR=default} patterns
    params_path = os.path.join(repo_root, "infra", "main.parameters.json")
    if os.path.exists(params_path):
        try:
            with open(params_path, "r") as f:
                params = json.load(f)
            for _key, param in params.get("parameters", {}).items():
                val = param.get("value", "")
                if isinstance(val, str) and val.startswith("${"):
                    # Parse ${VAR_NAME=default_value} pattern
                    match = re.match(r"\$\{([^}=]+)=([^}]*)\}", val)
                    if match:
                        env_var = match.group(1)
                        default_val = match.group(2)
                        if default_val:
                            defaults[env_var] = default_val
        except (json.JSONDecodeError, KeyError):
            pass

    # From main.bicep: extract param defaults for key values
    bicep_path = os.path.join(repo_root, "infra", "main.bicep")
    if os.path.exists(bicep_path):
        try:
            with open(bicep_path, "r") as f:
                content = f.read()

            # Map bicep param names to env var names
            bicep_to_env = {
                "gptModelName": "AZURE_ENV_GPT_MODEL_NAME",
                "gptModelVersion": "AZURE_ENV_GPT_MODEL_VERSION",
                "gptDeploymentCapacity": "AZURE_ENV_GPT_MODEL_CAPACITY",
                "embeddingModel": "AZURE_ENV_EMBEDDING_MODEL_NAME",
                "embeddingDeploymentCapacity": "AZURE_ENV_EMBEDDING_DEPLOYMENT_CAPACITY",
                "deploymentType": "AZURE_ENV_MODEL_DEPLOYMENT_TYPE",
                "contentUnderstandingLocation": "AZURE_ENV_CU_LOCATION",
                "secondaryLocation": "AZURE_ENV_SECONDARY_LOCATION",
            }

            for bicep_param, env_var in bicep_to_env.items():
                # Match: param gptModelName string = 'gpt-4o-mini'
                pattern = rf"param\s+{bicep_param}\s+\w+\s*=\s*'([^']+)'"
                match = re.search(pattern, content)
                if match and env_var not in defaults:
                    defaults[env_var] = match.group(1)

                # Match: param gptDeploymentCapacity int = 150
                pattern_int = rf"param\s+{bicep_param}\s+int\s*=\s*(\d+)"
                match_int = re.search(pattern_int, content)
                if match_int and env_var not in defaults:
                    defaults[env_var] = match_int.group(1)

        except OSError:
            pass

    return defaults


def _detect_use_case_from_repo(repo_root: str) -> str:
    """Detect use case from repo parameters."""
    params_path = os.path.join(repo_root, "infra", "main.parameters.json")
    if os.path.exists(params_path):
        try:
            with open(params_path, "r") as f:
                params = json.load(f)
            val = params.get("parameters", {}).get("usecase", {}).get("value", "")
            if val and not val.startswith("${"):
                return val
        except (json.JSONDecodeError, KeyError):
            pass

    # Check for test data to infer use case
    test_data_dir = os.path.join(repo_root, "tests", "e2e-test", "testdata")
    if os.path.isdir(test_data_dir):
        files = os.listdir(test_data_dir)
        if any("telecom" in f.lower() for f in files):
            return "telecom"
        if any("helpdesk" in f.lower() or "ithelpdesk" in f.lower() for f in files):
            return "IT_helpdesk"

    return ""
