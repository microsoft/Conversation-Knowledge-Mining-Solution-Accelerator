"""Configuration for the deploy-test-cleanup skill.

All values are configurable — nothing is hardcoded to a specific accelerator.
Values are resolved in this priority order:
  1. Explicit constructor arguments
  2. Environment variables
  3. Auto-detected from the repository (azure.yaml, Dockerfiles, etc.)
  4. Sensible defaults
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ImageDef:
    """Definition for a single Docker image to build."""

    name: str
    dockerfile: str  # relative to repo_root
    context: str     # relative to repo_root

    def full_tag(self, acr_hostname: str, tag: str) -> str:
        return f"{acr_hostname}/{self.name}:{tag}"


@dataclass
class Config:
    """Central configuration for all deployment phases.

    Designed to be accelerator-agnostic. Supply values via constructor,
    environment variables, or let them be auto-detected from the repo.
    """

    # ── Repository ──
    repo_root: str = ""
    source_branch: str = os.environ.get("SOURCE_BRANCH", "dependabotchanges")
    merge_branch: str = os.environ.get("MERGE_BRANCH", "dev")

    # ── ACR ──
    acr_name: str = os.environ.get("ACR_NAME", "")
    acr_hostname: str = os.environ.get("ACR_HOSTNAME", "")
    acr_rg_name: str = os.environ.get("ACR_RG_NAME", "")
    create_acr: bool = os.environ.get("CREATE_ACR", "true").lower() == "true"

    # ── Docker images (auto-detected if empty) ──
    images: list = field(default_factory=list)

    # ── Azure ──
    subscription_id: str = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    location: str = os.environ.get("AZURE_LOCATION", "eastus2")
    ai_service_location: str = os.environ.get("AZURE_ENV_AI_SERVICE_LOCATION", "eastus2")
    use_case: str = os.environ.get("USE_CASE", "")
    solution_prefix: str = os.environ.get("SOLUTION_PREFIX", "")
    fallback_locations: list = field(default_factory=lambda: [
        loc.strip()
        for loc in os.environ.get(
            "FALLBACK_LOCATIONS", "eastus2,australiaeast,eastus,francecentral,uksouth"
        ).split(",")
    ])
    extra_azd_env: dict = field(default_factory=dict)

    # ── Post-deploy scripts (auto-detected if empty) ──
    post_deploy_scripts: list = field(default_factory=list)

    # ── Testing ──
    test_dir: str = os.environ.get("TEST_DIR", "")
    test_suites: list = field(default_factory=list)
    test_max_retries: int = int(os.environ.get("TEST_MAX_RETRIES", "3"))
    test_retry_delays: list = field(default_factory=lambda: [30, 60, 120])
    app_readiness_attempts: int = int(os.environ.get("APP_READINESS_ATTEMPTS", "10"))
    app_readiness_interval: int = int(os.environ.get("APP_READINESS_INTERVAL", "30"))

    # ── Generated at runtime ──
    timestamp: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d-%H%M"))
    image_tag: str = os.environ.get("IMAGE_TAG", "")
    branch_name: str = os.environ.get("BRANCH_NAME", "")
    env_name: str = os.environ.get("AZD_ENV_NAME", "")
    rg_name: str = os.environ.get("RESOURCE_GROUP_NAME", "")
    web_app_url: str = ""
    api_app_url: str = ""

    def __post_init__(self):
        import random
        import string

        if not self.repo_root:
            # .github/skills/dependabot-deploy → repo root is 3 levels up
            self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

        suffix = "".join(random.choices(string.ascii_lowercase, k=4))

        if not self.image_tag:
            self.image_tag = f"deploy-test-{self.timestamp}"
        if not self.branch_name:
            self.branch_name = f"deploy-test-{self.source_branch}-{self.timestamp}"
        if not self.solution_prefix:
            self.solution_prefix = _detect_solution_prefix(self.repo_root)
        if not self.env_name:
            self.env_name = f"{self.solution_prefix[:6]}{suffix}"
        if not self.rg_name:
            self.rg_name = f"rg-{self.solution_prefix}-test-{suffix}"

        # Auto-detect from repo if not explicitly set
        if not self.acr_name or not self.acr_hostname:
            if self.create_acr:
                # Generate a unique ACR name (must be globally unique, alphanumeric only)
                if not self.acr_name:
                    self.acr_name = f"acr{self.solution_prefix}{suffix}"
                if not self.acr_hostname:
                    self.acr_hostname = f"{self.acr_name}.azurecr.io"
                if not self.acr_rg_name:
                    self.acr_rg_name = f"rg-{self.solution_prefix}-acr-{suffix}"
            else:
                detected_acr, detected_host = _detect_acr(self.repo_root)
                if not self.acr_name:
                    self.acr_name = detected_acr
                if not self.acr_hostname:
                    self.acr_hostname = detected_host or (f"{self.acr_name}.azurecr.io" if self.acr_name else "")

        if not self.images:
            self.images = _detect_images(self.repo_root)

        if not self.post_deploy_scripts:
            self.post_deploy_scripts = _detect_post_deploy_scripts(self.repo_root)

        if not self.test_dir:
            self.test_dir = _detect_test_dir(self.repo_root)

        if not self.use_case:
            self.use_case = _detect_use_case(self.repo_root)


# ── Auto-detection helpers ──

def _detect_solution_prefix(repo_root: str) -> str:
    """Detect solution prefix from azure.yaml or directory name."""
    for yaml_name in ("azure.yaml", "azure_custom.yaml"):
        yaml_path = os.path.join(repo_root, yaml_name)
        if os.path.exists(yaml_path):
            with open(yaml_path, "r") as f:
                for line in f:
                    match = re.match(r"^name:\s*(.+)", line.strip())
                    if match:
                        name = match.group(1).strip()
                        parts = name.split("-")
                        if len(parts) > 2:
                            return "".join(p[0] for p in parts[:4])
                        return name[:16]
    return os.path.basename(repo_root)[:16].lower()


def _detect_acr(repo_root: str) -> tuple:
    """Detect ACR name/hostname from Bicep parameters or main.bicep."""
    params_path = os.path.join(repo_root, "infra", "main.parameters.json")
    if os.path.exists(params_path):
        try:
            with open(params_path, "r") as f:
                params = json.load(f)
            p = params.get("parameters", {})
            for key in ("containerRegistryHostname", "backendContainerRegistryHostname",
                        "frontendContainerRegistryHostname", "acrLoginServer"):
                val = p.get(key, {}).get("value", "")
                if val and not val.startswith("${"):
                    hostname = val
                    name = hostname.replace(".azurecr.io", "")
                    return name, hostname
        except (json.JSONDecodeError, KeyError):
            pass

    bicep_path = os.path.join(repo_root, "infra", "main.bicep")
    if os.path.exists(bicep_path):
        try:
            with open(bicep_path, "r") as f:
                content = f.read()
            match = re.search(r"param\s+\w*[Cc]ontainer[Rr]egistry\w*\s+string\s*=\s*'([^']+)'", content)
            if match:
                hostname = match.group(1)
                name = hostname.replace(".azurecr.io", "")
                return name, hostname
        except OSError:
            pass

    return "", ""


def _detect_images(repo_root: str) -> list:
    """Detect Docker images by finding Dockerfiles in the repo."""
    images = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".venv", "__pycache__")]
        for fname in files:
            if fname.endswith("Dockerfile") or fname.endswith(".Dockerfile"):
                rel_path = os.path.relpath(os.path.join(root, fname), repo_root)
                context = os.path.relpath(root, repo_root)

                if "devcontainer" in rel_path.lower():
                    continue

                if "api" in fname.lower() or "api" in context.lower():
                    name = "api"
                elif "app" in fname.lower() or ("app" in context.lower()):
                    name = "app"
                elif "web" in fname.lower() or "web" in context.lower():
                    name = "app"
                else:
                    name = os.path.splitext(fname)[0].lower().replace("dockerfile", "").strip(".-_") or os.path.basename(root).lower()

                images.append(ImageDef(name=name, dockerfile=rel_path, context=context))

    return images


def _detect_post_deploy_scripts(repo_root: str) -> list:
    """Detect post-deploy scripts from azure.yaml hooks (deduplicated)."""
    seen = set()
    scripts = []
    # Prefer azure_custom.yaml if it exists, else azure.yaml
    for yaml_name in ("azure_custom.yaml", "azure.yaml"):
        yaml_path = os.path.join(repo_root, yaml_name)
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, "r") as f:
                    content = f.read()
                for match in re.finditer(r'bash\s+(\./[^\s"]+\.sh)', content):
                    script = match.group(1).lstrip("./")
                    if script not in seen and os.path.exists(os.path.join(repo_root, script)):
                        scripts.append(script)
                        seen.add(script)
            except OSError:
                pass
            break  # Use only the first yaml found
    return scripts


def _detect_test_dir(repo_root: str) -> str:
    """Detect the E2E test directory."""
    candidates = ["tests/e2e-test", "tests/e2e", "test/e2e", "e2e", "tests"]
    for candidate in candidates:
        path = os.path.join(repo_root, candidate)
        if os.path.isdir(path):
            for f in os.listdir(path):
                if f.startswith("test") or f == "conftest.py" or f == "pytest.ini":
                    return candidate
            for sub in os.listdir(path):
                subpath = os.path.join(path, sub)
                if os.path.isdir(subpath):
                    for f in os.listdir(subpath):
                        if f.startswith("test") or f == "conftest.py":
                            return candidate
    return "tests"


def _detect_use_case(repo_root: str) -> str:
    """Detect use case from parameters or return empty string."""
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
    return ""
