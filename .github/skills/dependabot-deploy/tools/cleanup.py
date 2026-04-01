"""Resource cleanup: deletes Azure Resource Group and purges soft-deleted resources."""

import os
import sys
from dataclasses import dataclass
from typing import Optional

from .utils import logger, print_phase, run_cmd


@dataclass
class CleanupResult:
    rg_name: str
    rg_deleted: bool
    acr_rg_deleted: bool
    purged_keyvaults: list[str]
    purged_ai_services: list[str]
    env_deleted: bool
    success: bool
    message: str


def run(
    rg_name: str,
    env_name: str = "",
    repo_root: str = "",
    location: str = "eastus2",
    acr_rg_name: str = "",
    acr_name: str = "",
) -> CleanupResult:
    """Delete Azure Resource Group, ACR, and purge soft-deleted resources."""
    print_phase("Resource Cleanup")

    purged_kv = []
    purged_ai = []

    rg_deleted = _delete_resource_group(rg_name)

    # Delete ACR resource group (if it was created by us)
    acr_rg_deleted = False
    if acr_rg_name and acr_rg_name != rg_name:
        logger.info("Deleting ACR resource group: %s", acr_rg_name)
        acr_rg_deleted = _delete_resource_group(acr_rg_name)
    
    purged_kv = _purge_keyvaults(env_name)
    purged_ai = _purge_ai_services(rg_name, location)

    env_deleted = False
    if env_name and repo_root:
        env_deleted = _delete_azd_env(env_name, repo_root)

    msg_parts = [f"RG {rg_name}: {'deleted' if rg_deleted else 'deletion initiated'}"]
    if acr_rg_name and acr_rg_name != rg_name:
        msg_parts.append(f"ACR RG {acr_rg_name}: {'deleted' if acr_rg_deleted else 'deletion initiated'}")
    if purged_kv:
        msg_parts.append(f"Purged {len(purged_kv)} Key Vault(s)")
    if purged_ai:
        msg_parts.append(f"Purged {len(purged_ai)} AI Service(s)")
    if env_deleted:
        msg_parts.append(f"AZD env {env_name} deleted")

    return CleanupResult(
        rg_name=rg_name, rg_deleted=rg_deleted, acr_rg_deleted=acr_rg_deleted,
        purged_keyvaults=purged_kv, purged_ai_services=purged_ai,
        env_deleted=env_deleted, success=rg_deleted,
        message="; ".join(msg_parts),
    )


def _delete_resource_group(rg_name: str) -> bool:
    logger.info("Deleting resource group: %s", rg_name)
    exists = run_cmd(f"az group exists --name {rg_name}", check=False)
    if exists.stdout.strip().lower() != "true":
        logger.info("Resource group %s does not exist, skipping", rg_name)
        return True
    result = run_cmd(f"az group delete --name {rg_name} --yes --no-wait", check=False)
    if result.returncode == 0:
        logger.info("✔ Resource group deletion initiated: %s (async)", rg_name)
        return True
    logger.error("✘ Failed to delete resource group: %s", rg_name)
    return False


def _purge_keyvaults(env_name: str) -> list[str]:
    purged = []
    if not env_name:
        return purged
    logger.info("Checking for soft-deleted Key Vaults matching: %s", env_name)
    result = run_cmd("az keyvault list-deleted -o json", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return purged
    try:
        import json
        for vault in json.loads(result.stdout):
            vault_name = vault.get("name", "")
            if env_name.lower() in vault_name.lower():
                vault_location = vault.get("properties", {}).get("location", "")
                logger.info("  Purging Key Vault: %s", vault_name)
                r = run_cmd(f"az keyvault purge --name {vault_name} --location {vault_location} --no-wait", check=False)
                if r.returncode == 0:
                    purged.append(vault_name)
    except Exception as e:
        logger.warning("⚠ Could not parse deleted Key Vaults: %s", e)
    return purged


def _purge_ai_services(rg_name: str, location: str) -> list[str]:
    purged = []
    logger.info("Checking for soft-deleted AI Services...")
    result = run_cmd("az cognitiveservices account list-deleted -o json", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return purged
    try:
        import json
        for svc in json.loads(result.stdout):
            svc_rg = svc.get("properties", {}).get("resourceGroup", "")
            if svc_rg.lower() == rg_name.lower():
                svc_name = svc.get("name", "")
                svc_loc = svc.get("location", location)
                logger.info("  Purging AI Service: %s", svc_name)
                r = run_cmd(f"az cognitiveservices account purge --name {svc_name} --resource-group {rg_name} --location {svc_loc}", check=False)
                if r.returncode == 0:
                    purged.append(svc_name)
    except Exception as e:
        logger.warning("⚠ Could not parse deleted AI Services: %s", e)
    return purged


def _delete_azd_env(env_name: str, repo_root: str) -> bool:
    logger.info("Deleting azd environment: %s", env_name)
    result = run_cmd(f"azd env delete {env_name} --no-prompt --purge", cwd=repo_root, check=False)
    if result.returncode == 0:
        logger.info("✔ AZD environment deleted: %s", env_name)
        return True
    logger.warning("⚠ Could not delete azd environment: %s", env_name)
    return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Azure resource cleanup")
    parser.add_argument("--rg-name", required=True)
    parser.add_argument("--env-name", default="")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--location", default="eastus2")
    parser.add_argument("--acr-rg-name", default="", help="ACR resource group to delete")
    parser.add_argument("--acr-name", default="")
    args = parser.parse_args()
    result = run(args.rg_name, args.env_name, args.repo_root, args.location, args.acr_rg_name, args.acr_name)
    print(f"\n{'✔' if result.success else '✘'} {result.message}")
    sys.exit(0 if result.success else 1)
