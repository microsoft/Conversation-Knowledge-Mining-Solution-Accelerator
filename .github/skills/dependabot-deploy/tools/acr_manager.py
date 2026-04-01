"""ACR lifecycle management: create a temporary ACR, and delete it after use."""

import os
import sys
from dataclasses import dataclass

from .utils import SkillError, logger, print_phase, run_cmd


@dataclass
class AcrCreateResult:
    acr_name: str
    acr_hostname: str
    acr_rg_name: str
    location: str
    success: bool
    message: str


@dataclass
class AcrDeleteResult:
    acr_rg_name: str
    success: bool
    message: str


def create_acr(
    acr_name: str,
    acr_rg_name: str,
    location: str,
    subscription_id: str = "",
    sku: str = "Basic",
) -> AcrCreateResult:
    """Create a new Azure Container Registry in its own resource group.

    Args:
        acr_name: Name for the ACR (must be globally unique, alphanumeric, 5-50 chars).
        acr_rg_name: Resource group name to create for the ACR.
        location: Azure region.
        subscription_id: Azure subscription (uses current default if empty).
        sku: ACR tier — Basic, Standard, or Premium.
    """
    print_phase("Create Azure Container Registry")

    # Validate ACR name
    import re
    if not re.match(r"^[a-zA-Z0-9]{5,50}$", acr_name):
        raise SkillError(
            "acr",
            f"ACR name '{acr_name}' is invalid. Must be 5-50 alphanumeric characters.",
            recoverable=False,
        )

    # Set subscription if provided
    if subscription_id:
        run_cmd(f"az account set --subscription {subscription_id}")

    # Create resource group for ACR
    logger.info("Creating resource group for ACR: %s (location: %s)", acr_rg_name, location)
    rg_result = run_cmd(
        f"az group create --name {acr_rg_name} --location {location} -o json",
        check=False,
    )
    if rg_result.returncode != 0:
        raise SkillError("acr", f"Failed to create resource group: {acr_rg_name}", recoverable=False)
    logger.info("✔ Resource group created: %s", acr_rg_name)

    # Create ACR
    logger.info("Creating ACR: %s (SKU: %s)", acr_name, sku)
    acr_result = run_cmd(
        f"az acr create --name {acr_name} --resource-group {acr_rg_name} "
        f"--location {location} --sku {sku} --admin-enabled true -o json",
        check=False,
        timeout=300,
    )
    if acr_result.returncode != 0:
        error = (acr_result.stdout or "") + (acr_result.stderr or "")
        raise SkillError("acr", f"Failed to create ACR: {error[-300:]}", recoverable=False)

    acr_hostname = f"{acr_name}.azurecr.io"
    logger.info("✔ ACR created: %s", acr_hostname)

    # Login to ACR
    logger.info("Logging in to ACR...")
    login_result = run_cmd(f"az acr login --name {acr_name}", check=False)
    if login_result.returncode != 0:
        logger.warning("⚠ ACR login failed, will retry before push")

    return AcrCreateResult(
        acr_name=acr_name,
        acr_hostname=acr_hostname,
        acr_rg_name=acr_rg_name,
        location=location,
        success=True,
        message=f"ACR {acr_hostname} created in RG {acr_rg_name}",
    )


def delete_acr(
    acr_rg_name: str,
    acr_name: str = "",
) -> AcrDeleteResult:
    """Delete the ACR resource group (which deletes the ACR with it).

    Args:
        acr_rg_name: Resource group containing the ACR.
        acr_name: ACR name (for logging only).
    """
    print_phase("Delete Azure Container Registry")

    logger.info("Deleting ACR resource group: %s", acr_rg_name)

    exists = run_cmd(f"az group exists --name {acr_rg_name}", check=False)
    if exists.stdout.strip().lower() != "true":
        logger.info("ACR resource group %s does not exist, skipping", acr_rg_name)
        return AcrDeleteResult(acr_rg_name=acr_rg_name, success=True, message="Already deleted")

    result = run_cmd(
        f"az group delete --name {acr_rg_name} --yes --no-wait",
        check=False,
    )
    if result.returncode == 0:
        logger.info("✔ ACR resource group deletion initiated: %s (async)", acr_rg_name)
        return AcrDeleteResult(
            acr_rg_name=acr_rg_name,
            success=True,
            message=f"ACR RG {acr_rg_name} deletion initiated",
        )
    else:
        logger.error("✘ Failed to delete ACR resource group: %s", acr_rg_name)
        return AcrDeleteResult(
            acr_rg_name=acr_rg_name,
            success=False,
            message=f"Failed to delete ACR RG {acr_rg_name}",
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACR lifecycle management")
    sub = parser.add_subparsers(dest="action", required=True)

    create_p = sub.add_parser("create", help="Create a new ACR")
    create_p.add_argument("--acr-name", required=True)
    create_p.add_argument("--acr-rg-name", required=True)
    create_p.add_argument("--location", default="eastus2")
    create_p.add_argument("--subscription-id", default="")
    create_p.add_argument("--sku", default="Basic")

    delete_p = sub.add_parser("delete", help="Delete an ACR resource group")
    delete_p.add_argument("--acr-rg-name", required=True)
    delete_p.add_argument("--acr-name", default="")

    args = parser.parse_args()

    if args.action == "create":
        r = create_acr(args.acr_name, args.acr_rg_name, args.location, args.subscription_id, args.sku)
        print(f"\n{'✔' if r.success else '✘'} {r.message}")
        sys.exit(0 if r.success else 1)
    elif args.action == "delete":
        r = delete_acr(args.acr_rg_name, args.acr_name)
        print(f"\n{'✔' if r.success else '✘'} {r.message}")
        sys.exit(0 if r.success else 1)
