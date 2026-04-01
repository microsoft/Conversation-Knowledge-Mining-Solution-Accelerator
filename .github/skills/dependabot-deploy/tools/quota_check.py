"""Quota checker: auto-discovers a valid Azure region with sufficient quota.

Checks OpenAI model quota (GPT + embedding) across candidate regions and
returns the first region that has enough available capacity. No user input needed.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

from .utils import SkillError, logger, print_phase, run_cmd


@dataclass
class QuotaResult:
    valid_region: str
    checked_regions: dict  # region -> {model: available_capacity}
    success: bool
    message: str


@dataclass
class ModelQuotaReq:
    """A model + minimum capacity requirement."""
    usage_name: str   # e.g. "OpenAI.GlobalStandard.gpt-4o-mini"
    min_capacity: int


def check_quota(
    subscription_id: str = "",
    candidate_regions: Optional[list[str]] = None,
    deployment_type: str = "GlobalStandard",
    gpt_model: str = "gpt-4o-mini",
    gpt_min_capacity: int = 100,
    embedding_model: str = "text-embedding-3-small",
    embedding_min_capacity: int = 80,
) -> QuotaResult:
    """Find the first region with sufficient quota for all required models.

    Args:
        subscription_id: Azure subscription (uses current default if empty).
        candidate_regions: Regions to check, in priority order.
        deployment_type: "Standard" or "GlobalStandard".
        gpt_model: GPT model name.
        gpt_min_capacity: Minimum GPT capacity (TPM in thousands).
        embedding_model: Embedding model name.
        embedding_min_capacity: Minimum embedding capacity.
    """
    print_phase("Quota Check")

    if candidate_regions is None:
        candidate_regions = [
            "eastus2", "eastus", "australiaeast", "uksouth",
            "francecentral", "swedencentral", "westus", "westus3",
            "japaneast", "northeurope",
        ]

    if subscription_id:
        run_cmd(f"az account set --subscription {subscription_id}", check=False)

    requirements = [
        ModelQuotaReq(
            usage_name=f"OpenAI.{deployment_type}.{gpt_model}",
            min_capacity=gpt_min_capacity,
        ),
        ModelQuotaReq(
            usage_name=f"OpenAI.{deployment_type}.{embedding_model}",
            min_capacity=embedding_min_capacity,
        ),
    ]

    logger.info("Checking quota for %d models across %d regions...", len(requirements), len(candidate_regions))
    for req in requirements:
        logger.info("  %s: need %d", req.usage_name, req.min_capacity)

    checked = {}

    for region in candidate_regions:
        logger.info("Checking region: %s", region)
        region_quota = _check_region_quota(region, requirements)
        checked[region] = region_quota

        if region_quota is not None:
            all_sufficient = all(
                region_quota.get(req.usage_name, 0) >= req.min_capacity
                for req in requirements
            )
            if all_sufficient:
                logger.info("✔ Region %s has sufficient quota:", region)
                for req in requirements:
                    avail = region_quota.get(req.usage_name, 0)
                    logger.info("  %s: %d available (need %d)", req.usage_name, avail, req.min_capacity)
                return QuotaResult(
                    valid_region=region,
                    checked_regions=checked,
                    success=True,
                    message=f"Region {region} has sufficient quota for all models",
                )
            else:
                for req in requirements:
                    avail = region_quota.get(req.usage_name, 0)
                    status = "✔" if avail >= req.min_capacity else "✘"
                    logger.info("  %s %s: %d available (need %d)", status, req.usage_name, avail, req.min_capacity)

    logger.error("✘ No region found with sufficient quota")
    return QuotaResult(
        valid_region="",
        checked_regions=checked,
        success=False,
        message=f"No region has sufficient quota. Checked: {', '.join(candidate_regions)}",
    )


def _check_region_quota(region: str, requirements: list[ModelQuotaReq]) -> Optional[dict]:
    """Check quota for all required models in a single region."""
    result = run_cmd(
        f"az cognitiveservices usage list --location {region} -o json",
        check=False,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        logger.warning("  Could not query quota for %s", region)
        return None

    try:
        usages = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("  Invalid quota response for %s", region)
        return None

    quota_map = {}
    for usage in usages:
        name = usage.get("name", {}).get("value", "")
        current = usage.get("currentValue", 0)
        limit = usage.get("limit", 0)
        available = limit - current

        # Check if this matches any of our requirements
        for req in requirements:
            if req.usage_name.lower() == name.lower():
                quota_map[req.usage_name] = available

    # For models not found in usage list, assume 0 available
    for req in requirements:
        if req.usage_name not in quota_map:
            quota_map[req.usage_name] = 0

    return quota_map


def auto_select_region(
    subscription_id: str = "",
    preferred_region: str = "",
    candidate_regions: Optional[list[str]] = None,
    deployment_type: str = "GlobalStandard",
    gpt_model: str = "gpt-4o-mini",
    gpt_min_capacity: int = 100,
    embedding_model: str = "text-embedding-3-small",
    embedding_min_capacity: int = 80,
) -> str:
    """Auto-select a region, checking preferred first then falling back.

    Returns the selected region, or raises SkillError if none found.
    """
    if candidate_regions is None:
        candidate_regions = [
            "eastus2", "eastus", "australiaeast", "uksouth",
            "francecentral", "swedencentral", "westus", "westus3",
        ]

    # Put preferred region first if specified
    if preferred_region:
        regions = [preferred_region] + [r for r in candidate_regions if r != preferred_region]
    else:
        regions = candidate_regions

    result = check_quota(
        subscription_id=subscription_id,
        candidate_regions=regions,
        deployment_type=deployment_type,
        gpt_model=gpt_model,
        gpt_min_capacity=gpt_min_capacity,
        embedding_model=embedding_model,
        embedding_min_capacity=embedding_min_capacity,
    )

    if result.success:
        return result.valid_region

    raise SkillError("quota", result.message, recoverable=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Azure quota checker")
    parser.add_argument("--subscription-id", default="")
    parser.add_argument("--regions", default="eastus2,eastus,australiaeast,uksouth,francecentral")
    parser.add_argument("--gpt-model", default="gpt-4o-mini")
    parser.add_argument("--gpt-capacity", type=int, default=100)
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--embedding-capacity", type=int, default=80)
    parser.add_argument("--deployment-type", default="GlobalStandard")
    args = parser.parse_args()

    regions = [r.strip() for r in args.regions.split(",")]
    result = check_quota(
        subscription_id=args.subscription_id,
        candidate_regions=regions,
        deployment_type=args.deployment_type,
        gpt_model=args.gpt_model,
        gpt_min_capacity=args.gpt_capacity,
        embedding_model=args.embedding_model,
        embedding_min_capacity=args.embedding_capacity,
    )
    if result.success:
        print(f"\n✔ Valid region: {result.valid_region}")
    else:
        print(f"\n✘ {result.message}")
    sys.exit(0 if result.success else 1)
