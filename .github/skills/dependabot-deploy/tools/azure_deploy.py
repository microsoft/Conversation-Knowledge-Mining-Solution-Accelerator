"""Azure deployment: provisions infrastructure and deploys via azd.

Works with any accelerator that uses Azure Developer CLI for deployment.
All configuration is passed explicitly — no hardcoded accelerator values.
"""

import os
import platform
import sys
import time
from dataclasses import dataclass
from typing import Optional

from .utils import SkillError, logger, print_phase, run_cmd


@dataclass
class DeployResult:
    env_name: str
    rg_name: str
    web_app_url: str
    api_app_url: str
    location: str
    image_tag: str
    success: bool
    message: str


def run(
    repo_root: str,
    subscription_id: str,
    env_name: str,
    rg_name: str,
    image_tag: str,
    location: str = "eastus2",
    ai_service_location: str = "eastus2",
    use_case: str = "",
    acr_hostname: str = "",
    fallback_locations: Optional[list[str]] = None,
    extra_azd_env: Optional[dict[str, str]] = None,
    post_deploy_scripts: Optional[list[str]] = None,
) -> DeployResult:
    """Deploy the solution to Azure using azd."""
    print_phase("Azure Deployment")

    if not subscription_id:
        raise SkillError("deploy", "subscription_id is required", recoverable=False)

    if fallback_locations is None:
        fallback_locations = ["eastus2", "australiaeast", "eastus", "francecentral"]

    locations_to_try = [location] + [loc for loc in fallback_locations if loc != location]

    for loc in locations_to_try:
        logger.info("Attempting deployment in region: %s", loc)
        try:
            result = _deploy_to_region(
                repo_root=repo_root,
                subscription_id=subscription_id,
                env_name=env_name,
                rg_name=rg_name,
                image_tag=image_tag,
                location=loc,
                ai_service_location=ai_service_location,
                use_case=use_case,
                acr_hostname=acr_hostname,
                extra_azd_env=extra_azd_env,
                post_deploy_scripts=post_deploy_scripts,
            )
            return result
        except SkillError as e:
            if "quota" in str(e).lower() or "capacity" in str(e).lower():
                logger.warning("⚠ Quota issue in %s, trying next region...", loc)
                run_cmd(f"azd env delete {env_name} --no-prompt --purge", check=False, cwd=repo_root)
                continue
            raise

    raise SkillError("deploy", f"Deployment failed in all regions: {locations_to_try}", recoverable=False)


def _deploy_to_region(
    repo_root: str,
    subscription_id: str,
    env_name: str,
    rg_name: str,
    image_tag: str,
    location: str,
    ai_service_location: str,
    use_case: str,
    acr_hostname: str,
    extra_azd_env: Optional[dict[str, str]],
    post_deploy_scripts: Optional[list[str]],
) -> DeployResult:
    """Deploy to a specific Azure region."""
    logger.info("Creating azd environment: %s", env_name)
    run_cmd(f"azd env new {env_name} --no-prompt", cwd=repo_root)

    # Auto-resolve ALL parameters (quota check, defaults from repo, etc.)
    from .param_resolver import resolve as resolve_params
    resolved = resolve_params(
        repo_root=repo_root,
        subscription_id=subscription_id,
        env_name=env_name,
        rg_name=rg_name,
        image_tag=image_tag,
        acr_hostname=acr_hostname,
        preferred_region=location,
        use_case=use_case,
        extra_env=extra_azd_env,
        skip_quota_check=False,
    )

    # Use quota-validated region
    location = resolved.region
    ai_service_location = resolved.ai_service_region

    run_cmd(f"azd config set defaults.subscription {subscription_id}", cwd=repo_root)
    for key, value in resolved.azd_env.items():
        run_cmd(f'azd env set {key} "{value}"', cwd=repo_root)

    # Run azd up
    logger.info("Running azd up (this may take 15-30 minutes)...")
    deploy_result = run_cmd("azd up --no-prompt", cwd=repo_root, check=False, timeout=2400)

    if deploy_result.returncode != 0:
        error = (deploy_result.stdout or "") + (deploy_result.stderr or "")
        if "quota" in error.lower() or "capacity" in error.lower() or "insufficientquota" in error.lower():
            raise SkillError("deploy", f"Quota exceeded in {location}", recoverable=True)
        raise SkillError("deploy", f"azd up failed: {error[-500:]}", recoverable=True)

    logger.info("✔ azd up completed successfully")

    web_url = _get_env_value("WEB_APP_URL", repo_root)
    api_url = _get_env_value("API_APP_URL", repo_root)
    logger.info("Web App URL: %s", web_url)
    logger.info("API App URL: %s", api_url)

    # Run post-deployment scripts
    if post_deploy_scripts:
        _run_post_deploy(repo_root, post_deploy_scripts)

    return DeployResult(
        env_name=env_name, rg_name=rg_name,
        web_app_url=web_url, api_app_url=api_url,
        location=location, image_tag=image_tag,
        success=True, message=f"Deployed to {location} (RG: {rg_name})",
    )


def _get_env_value(key: str, repo_root: str) -> str:
    result = run_cmd(f"azd env get-value {key}", cwd=repo_root, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _run_post_deploy(repo_root: str, scripts: list[str]):
    """Run post-deployment scripts."""
    is_windows = platform.system() == "Windows"

    for script_path in scripts:
        full_path = os.path.join(repo_root, script_path.replace("/", os.sep))
        if not os.path.exists(full_path):
            logger.warning("⚠ Script not found: %s", full_path)
            continue

        logger.info("Running post-deploy script: %s", script_path)

        if is_windows:
            bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                "wsl",
            ]
            bash_cmd = None
            for bp in bash_paths:
                if os.path.exists(bp) or bp == "wsl":
                    bash_cmd = bp
                    break
            if bash_cmd:
                cmd = f'"{bash_cmd}" -c "cd {repo_root.replace(os.sep, "/")} && bash {script_path}"'
            else:
                logger.warning("⚠ No bash available on Windows. Skipping: %s", script_path)
                continue
        else:
            cmd = f"bash {script_path}"

        result = run_cmd(cmd, cwd=repo_root, check=False, timeout=600)
        if result.returncode != 0:
            logger.warning("⚠ Script failed (exit %d). Retrying after 20s...", result.returncode)
            time.sleep(20)
            result = run_cmd(cmd, cwd=repo_root, check=False, timeout=600)
            if result.returncode != 0:
                logger.error("✘ Script failed on retry: %s", script_path)
            else:
                logger.info("✔ Script completed on retry: %s", script_path)
        else:
            logger.info("✔ Script completed: %s", script_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Azure deployment tool")
    parser.add_argument("--repo-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--env-name", required=True)
    parser.add_argument("--rg-name", required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--location", default="eastus2")
    parser.add_argument("--ai-service-location", default="eastus2")
    parser.add_argument("--use-case", default="")
    parser.add_argument("--acr-hostname", default="")
    args = parser.parse_args()
    result = run(
        args.repo_root, args.subscription_id, args.env_name, args.rg_name,
        args.image_tag, args.location, args.ai_service_location, args.use_case, args.acr_hostname,
    )
    print(f"\n{'✔' if result.success else '✘'} {result.message}")
    sys.exit(0 if result.success else 1)
