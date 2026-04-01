"""
Deploy-Test-Cleanup Orchestrator

Generic, accelerator-agnostic entry point that runs all phases sequentially:
  1. Git branching (create branch from source, merge target)
  2. ACR creation (create a temporary Azure Container Registry)
  3. Docker build & push (auto-detected Dockerfiles → ACR)
  4. Azure deployment (azd up + auto-detected post-deploy scripts)
  5. Playwright E2E testing (with retries)
  6. Report generation + Draft PR to dev (if tests pass)
  7. Cleanup (delete deployment RG, ACR RG, purge soft-deleted resources)

All configuration is auto-detected from the repository or supplied via CLI/env vars.
No values are hardcoded to any specific accelerator.

Usage:
    python orchestrator.py --subscription-id <SUB_ID> --acr-name <ACR>
"""

import argparse
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from tools import utils
from tools.utils import SkillError, logger, print_phase


def main():
    parser = argparse.ArgumentParser(
        description="Generic deploy-test-cleanup orchestrator for Azure accelerators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full workflow — creates temporary ACR, deploys, tests, cleans up everything
  python orchestrator.py --subscription-id <SUB_ID>

  # Use an existing ACR instead of creating a new one
  python orchestrator.py --subscription-id <ID> --acr-name myexistingacr --use-existing-acr

  # Custom branches and region
  python orchestrator.py --subscription-id <ID> \\
    --source-branch dependabotchanges --merge-branch main --location australiaeast

  # Skip cleanup (keep resources for debugging)
  python orchestrator.py --subscription-id <ID> --skip-cleanup

  # Test against an existing deployment
  python orchestrator.py --subscription-id <ID> \\
    --web-url https://myapp.azurewebsites.net --api-url https://myapi.azurewebsites.net \\
    --skip-git --skip-docker

  # Pass extra azd environment variables
  python orchestrator.py --subscription-id <ID> \\
    --azd-env USE_CASE=telecom --azd-env AZURE_ENV_MODEL=gpt-4o
        """,
    )
    # Required
    parser.add_argument("--subscription-id", required=True, help="Azure subscription ID")

    # ACR (auto-detected from repo if not provided)
    parser.add_argument("--acr-name", default="", help="ACR registry name (auto-created if omitted)")
    parser.add_argument("--acr-hostname", default="", help="ACR hostname (default: <acr-name>.azurecr.io)")
    parser.add_argument("--use-existing-acr", action="store_true",
                        help="Use an existing ACR instead of creating a new one")

    # Git
    parser.add_argument("--source-branch", default="dependabotchanges", help="Source branch to create from")
    parser.add_argument("--merge-branch", default="dev", help="Branch to merge into the new branch")
    parser.add_argument("--branch-name", default=None, help="New branch name (auto-generated if omitted)")

    # Azure
    parser.add_argument("--location", default="eastus2", help="Azure region")
    parser.add_argument("--ai-service-location", default="eastus2", help="AI service region")
    parser.add_argument("--use-case", default="", help="Use case identifier (accelerator-specific)")
    parser.add_argument("--image-tag", default=None, help="Docker image tag (auto-generated if omitted)")
    parser.add_argument("--azd-env", action="append", default=[], metavar="KEY=VALUE",
                        help="Extra azd env vars (repeatable)")

    # Phases to skip
    parser.add_argument("--skip-git", action="store_true", help="Skip git branch management")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker build & push")
    parser.add_argument("--skip-deploy", action="store_true", help="Skip Azure deployment")
    parser.add_argument("--skip-tests", action="store_true", help="Skip E2E tests")
    parser.add_argument("--skip-pr", action="store_true", help="Skip draft PR creation")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip resource cleanup")
    parser.add_argument("--pr-target", default="dev", help="PR target branch (default: dev)")

    # Existing deployment
    parser.add_argument("--web-url", default=None, help="Existing web app URL (skips deploy)")
    parser.add_argument("--api-url", default=None, help="Existing API URL (skips deploy)")

    # Overrides
    parser.add_argument("--repo-root", default=None, help="Repository root path")
    parser.add_argument("--test-dir", default="", help="Test directory relative to repo root")

    args = parser.parse_args()

    # Parse extra azd env vars
    extra_azd = {}
    for item in args.azd_env:
        if "=" in item:
            k, v = item.split("=", 1)
            extra_azd[k] = v

    # Initialize config
    cfg = Config(
        subscription_id=args.subscription_id,
        source_branch=args.source_branch,
        merge_branch=args.merge_branch,
        acr_name=args.acr_name,
        acr_hostname=args.acr_hostname,
        create_acr=not args.use_existing_acr,
        location=args.location,
        ai_service_location=args.ai_service_location,
        use_case=args.use_case,
        extra_azd_env=extra_azd,
    )

    if args.image_tag:
        cfg.image_tag = args.image_tag
    if args.branch_name:
        cfg.branch_name = args.branch_name
    if args.repo_root:
        cfg.repo_root = args.repo_root
    if args.test_dir:
        cfg.test_dir = args.test_dir

    from tools.report import ReportData
    report_data = ReportData(
        env_name=cfg.env_name, rg_name=cfg.rg_name,
        location=cfg.location, image_tag=cfg.image_tag, use_case=cfg.use_case,
    )

    logger.info("=" * 60)
    logger.info("  DEPLOY-TEST-CLEANUP ORCHESTRATOR")
    logger.info("=" * 60)
    logger.info("Repo root:      %s", cfg.repo_root)
    logger.info("Source branch:  %s", cfg.source_branch)
    logger.info("Merge branch:   %s", cfg.merge_branch)
    logger.info("New branch:     %s", cfg.branch_name)
    logger.info("ACR:            %s (%s)", cfg.acr_hostname or "(will create)", "existing" if not cfg.create_acr else "temporary")
    if cfg.acr_rg_name:
        logger.info("ACR RG:         %s", cfg.acr_rg_name)
    logger.info("Images:         %s", ", ".join(i.name for i in cfg.images) or "(auto-detect)")
    logger.info("Image tag:      %s", cfg.image_tag)
    logger.info("Environment:    %s", cfg.env_name)
    logger.info("Resource Group: %s", cfg.rg_name)
    logger.info("Location:       %s", cfg.location)
    if cfg.use_case:
        logger.info("Use case:       %s", cfg.use_case)
    if cfg.post_deploy_scripts:
        logger.info("Post-deploy:    %s", ", ".join(cfg.post_deploy_scripts))
    logger.info("Test dir:       %s", cfg.test_dir)
    logger.info("=" * 60)

    _check_prerequisites()

    try:
        # ── Phase 1: Git ──
        if not args.skip_git:
            from tools import git_branch
            git_result = git_branch.run(
                repo_root=cfg.repo_root, source_branch=cfg.source_branch,
                merge_branch=cfg.merge_branch, branch_name=cfg.branch_name,
            )
            report_data.branch_name = git_result.branch_name
            report_data.merge_conflicts = git_result.merge_conflicts
            cfg.branch_name = git_result.branch_name
        else:
            logger.info("⏭ Skipping git branch management")
            report_data.branch_name = cfg.branch_name or "skipped"

        # ── Phase 2: Create ACR (if needed) ──
        if not args.skip_docker and cfg.create_acr:
            from tools import acr_manager
            acr_result = acr_manager.create_acr(
                acr_name=cfg.acr_name,
                acr_rg_name=cfg.acr_rg_name,
                location=cfg.location,
                subscription_id=cfg.subscription_id,
            )
            cfg.acr_name = acr_result.acr_name
            cfg.acr_hostname = acr_result.acr_hostname
            cfg.acr_rg_name = acr_result.acr_rg_name
            logger.info("✔ Temporary ACR ready: %s", cfg.acr_hostname)

        # ── Phase 3: Docker ──
        if not args.skip_docker:
            if not cfg.acr_name:
                raise SkillError("docker", "ACR name is required. Use --acr-name or set ACR_NAME env var.", recoverable=False)
            from tools import docker_build
            docker_result = docker_build.run(
                repo_root=cfg.repo_root, acr_name=cfg.acr_name,
                acr_hostname=cfg.acr_hostname, image_tag=cfg.image_tag,
                images=cfg.images, auto_fix=True,
            )
            report_data.built_images = docker_result.built_images
            report_data.fixed_packages = docker_result.fixed_packages
            if docker_result.fixed_packages:
                from tools.utils import run_cmd
                run_cmd(f"git push origin {cfg.branch_name}", cwd=cfg.repo_root)
        else:
            logger.info("⏭ Skipping Docker build & push")

        # ── Phase 3: Deploy ──
        if not args.skip_deploy and not (args.web_url and args.api_url):
            from tools import azure_deploy
            deploy_result = azure_deploy.run(
                repo_root=cfg.repo_root, subscription_id=cfg.subscription_id,
                env_name=cfg.env_name, rg_name=cfg.rg_name, image_tag=cfg.image_tag,
                location=cfg.location, ai_service_location=cfg.ai_service_location,
                use_case=cfg.use_case, acr_hostname=cfg.acr_hostname,
                fallback_locations=cfg.fallback_locations, extra_azd_env=cfg.extra_azd_env,
                post_deploy_scripts=cfg.post_deploy_scripts,
            )
            cfg.web_app_url = deploy_result.web_app_url
            cfg.api_app_url = deploy_result.api_app_url
            cfg.location = deploy_result.location
            report_data.web_app_url = deploy_result.web_app_url
            report_data.api_app_url = deploy_result.api_app_url
            report_data.location = deploy_result.location
            report_data.deploy_success = deploy_result.success
        elif args.web_url and args.api_url:
            logger.info("⏭ Using existing deployment: %s", args.web_url)
            cfg.web_app_url = args.web_url
            cfg.api_app_url = args.api_url
            report_data.web_app_url = args.web_url
            report_data.api_app_url = args.api_url
            report_data.deploy_success = True
        else:
            logger.info("⏭ Skipping Azure deployment")
            report_data.deploy_success = True

        # ── Phase 4: Test ──
        if not args.skip_tests and cfg.web_app_url and cfg.api_app_url:
            from tools import test_runner
            test_result = test_runner.run(
                repo_root=cfg.repo_root, web_app_url=cfg.web_app_url,
                api_app_url=cfg.api_app_url, test_dir=cfg.test_dir,
                use_case=cfg.use_case, test_suites=cfg.test_suites or None,
                max_retries=cfg.test_max_retries, retry_delays=cfg.test_retry_delays,
                readiness_attempts=cfg.app_readiness_attempts,
                readiness_interval=cfg.app_readiness_interval,
            )
            report_data.test_summary = test_result.summary
            report_data.test_success = test_result.overall_success
        else:
            logger.info("⏭ Skipping E2E tests")
            report_data.test_success = True
            report_data.test_summary = "_Tests skipped_"

    except SkillError as e:
        logger.error("✘ Phase failed: %s", e)
        report_data.errors.append(str(e))
        if not e.recoverable:
            logger.error("✘ Unrecoverable error — skipping to cleanup")
    except Exception as e:
        logger.error("✘ Unexpected error: %s", e)
        traceback.print_exc()
        report_data.errors.append(f"Unexpected: {e}")

    # ── Phase 5: Report ──
    report_path = ""
    try:
        from tools import report
        report_path = os.path.join(cfg.repo_root, cfg.test_dir, "reports", "deployment_report.md")
        report_text = report.generate(report_data, output_path=report_path)
        logger.info("\n%s", report_text)
    except Exception as e:
        logger.error("✘ Report generation failed: %s", e)

    # ── Phase 6: Create Draft PR (only if tests passed) ──
    if not args.skip_pr and report_data.deploy_success and report_data.test_success and cfg.branch_name:
        try:
            from tools import pr_creator
            pr_result = pr_creator.create_draft_pr(
                repo_root=cfg.repo_root,
                branch_name=cfg.branch_name,
                target_branch=args.pr_target,
                report_path=report_path if report_path else None,
            )
            if pr_result.success:
                logger.info("✔ Draft PR: %s", pr_result.pr_url)
            else:
                logger.warning("⚠ PR creation failed: %s", pr_result.message)
        except Exception as e:
            logger.warning("⚠ PR creation failed: %s", e)
    elif not args.skip_pr and not (report_data.deploy_success and report_data.test_success):
        logger.info("⏭ Skipping PR creation (deploy or tests failed)")
    else:
        logger.info("⏭ Skipping PR creation")

    # ── Phase 7: Cleanup ──
    if not args.skip_cleanup:
        try:
            from tools import cleanup
            cleanup_result = cleanup.run(
                rg_name=cfg.rg_name, env_name=cfg.env_name,
                repo_root=cfg.repo_root, location=cfg.location,
                acr_rg_name=cfg.acr_rg_name if cfg.create_acr else "",
                acr_name=cfg.acr_name if cfg.create_acr else "",
            )
            report_data.cleanup_message = cleanup_result.message
            report_data.cleanup_success = cleanup_result.success
        except Exception as e:
            logger.error("✘ Cleanup failed: %s", e)
            report_data.cleanup_message = str(e)
    else:
        logger.info("⏭ Skipping resource cleanup")
        report_data.cleanup_message = "Skipped"
        report_data.cleanup_success = True

    overall = report_data.deploy_success and report_data.test_success
    logger.info("=" * 60)
    logger.info("  %s OVERALL RESULT: %s", "✅" if overall else "❌", "PASS" if overall else "FAIL")
    logger.info("=" * 60)
    return 0 if overall else 1


def _check_prerequisites():
    tools = ["az", "azd", "docker", "git", "python"]
    missing = [t for t in tools if not utils.confirm_tool_available(t)]
    if missing:
        logger.error("✘ Missing required tools: %s", ", ".join(missing))
        sys.exit(1)
    logger.info("✔ All prerequisite tools available")


if __name__ == "__main__":
    sys.exit(main())
