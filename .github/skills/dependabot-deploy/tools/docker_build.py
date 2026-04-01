"""Docker build & push: builds images from auto-detected Dockerfiles and pushes to ACR."""

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

from .utils import SkillError, logger, print_phase, run_cmd

# Import ImageDef so callers can construct image lists
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import ImageDef


@dataclass
class DockerResult:
    built_images: list[str]
    success: bool
    message: str
    fixed_packages: list[str]


def run(
    repo_root: str,
    acr_name: str,
    acr_hostname: str,
    image_tag: str,
    images: list[ImageDef],
    auto_fix: bool = True,
) -> DockerResult:
    """Build and push Docker images to ACR.

    Args:
        repo_root: Path to the repository root.
        acr_name: ACR registry name (without .azurecr.io).
        acr_hostname: Full ACR hostname.
        image_tag: Tag for the Docker images.
        images: List of ImageDef describing each image to build.
        auto_fix: If True, attempt to fix package version issues on build failure.
    """
    print_phase("Docker Build & Push")

    if not images:
        raise SkillError("docker", "No Docker images configured. Check Dockerfiles in the repo.", recoverable=False)

    fixed_packages = []
    built_images = []

    # Login to ACR
    logger.info("Logging in to ACR: %s", acr_name)
    run_cmd(f"az acr login --name {acr_name}")

    for img_def in images:
        full_tag = img_def.full_tag(acr_hostname, image_tag)
        context = os.path.join(repo_root, img_def.context)
        dockerfile = os.path.join(repo_root, img_def.dockerfile)

        if not os.path.exists(dockerfile):
            logger.warning("⚠ Dockerfile not found, skipping: %s", img_def.dockerfile)
            continue

        logger.info("Building image: %s (from %s)", full_tag, img_def.dockerfile)
        success, fixes = _build_with_retry(
            image=full_tag,
            context=context,
            dockerfile=dockerfile,
            repo_root=repo_root,
            img_def=img_def,
            auto_fix=auto_fix,
        )
        fixed_packages.extend(fixes)

        if not success:
            raise SkillError("docker", f"Failed to build image after retries: {full_tag}", recoverable=True)

        # Push image
        logger.info("Pushing image: %s", full_tag)
        run_cmd(f"docker push {full_tag}")
        built_images.append(full_tag)

    # Verify images in ACR
    logger.info("Verifying images in ACR...")
    for img_def in images:
        run_cmd(
            f"az acr repository show-tags --name {acr_name} --repository {img_def.name} --top 3 --orderby time_desc",
            check=False,
        )

    logger.info("✔ Docker build and push complete (%d images)", len(built_images))

    return DockerResult(
        built_images=built_images,
        success=True,
        message=f"Built and pushed {len(built_images)} image(s): {', '.join(built_images)}",
        fixed_packages=fixed_packages,
    )


def _build_with_retry(
    image: str,
    context: str,
    dockerfile: str,
    repo_root: str,
    img_def: "ImageDef",
    auto_fix: bool,
    max_retries: int = 2,
) -> tuple[bool, list[str]]:
    """Build a Docker image with automatic package fix retries."""
    fixed = []
    for attempt in range(max_retries + 1):
        build_cmd = f"docker build -t {image} -f {dockerfile} {context}"
        result = run_cmd(build_cmd, check=False, cwd=repo_root)

        if result.returncode == 0:
            logger.info("✔ Build succeeded for %s (attempt %d)", image, attempt + 1)
            return True, fixed

        if attempt < max_retries and auto_fix:
            logger.warning("⚠ Build failed (attempt %d/%d). Attempting auto-fix...", attempt + 1, max_retries + 1)
            error_output = (result.stdout or "") + (result.stderr or "")
            image_type = _detect_image_type(img_def, context)
            fix_result = _auto_fix_packages(repo_root, image_type, error_output, context)
            if fix_result:
                fixed.extend(fix_result)
                # Commit the fix
                run_cmd("git add -A", cwd=repo_root)
                run_cmd(
                    f'git commit -m "fix: auto-fix package versions for {img_def.name} ({", ".join(fix_result)})"',
                    cwd=repo_root,
                )
                logger.info("✔ Applied package fixes: %s", ", ".join(fix_result))
            else:
                logger.error("✘ Could not auto-fix build failure")
                return False, fixed
        else:
            logger.error("✘ Build failed after all attempts")
            return False, fixed

    return False, fixed


def _detect_image_type(img_def: "ImageDef", context: str) -> str:
    """Detect whether the image is Python-based or Node-based."""
    context_lower = context.lower()
    dockerfile_lower = img_def.dockerfile.lower()

    # Check for requirements.txt (Python) or package.json (Node)
    if os.path.exists(os.path.join(context, "requirements.txt")):
        return "python"
    if os.path.exists(os.path.join(context, "package.json")):
        return "node"

    # Infer from Dockerfile content
    try:
        with open(os.path.join(context, os.path.basename(img_def.dockerfile)), "r") as f:
            content = f.read().lower()
        if "pip install" in content or "python" in content:
            return "python"
        if "npm" in content or "node" in content:
            return "node"
    except OSError:
        pass

    return "unknown"


def _auto_fix_packages(repo_root: str, image_type: str, error_output: str, context: str) -> list[str]:
    """Attempt to fix package version issues based on build error output."""
    fixes = []

    if image_type == "python":
        fixes = _fix_python_packages(context, error_output)
    elif image_type == "node":
        fixes = _fix_node_packages(context, error_output)

    return fixes


def _fix_python_packages(context: str, error_output: str) -> list[str]:
    """Fix Python package version issues in requirements.txt."""
    req_file = os.path.join(context, "requirements.txt")
    if not os.path.exists(req_file):
        # Search for requirements.txt in subdirectories
        for root, _, files in os.walk(context):
            if "requirements.txt" in files:
                req_file = os.path.join(root, "requirements.txt")
                break
        else:
            return []

    fixes = []
    error_lower = error_output.lower()

    # Pattern: "No matching distribution found for package==version"
    no_dist_pattern = re.compile(r"no matching distribution found for (\S+)==([\d.]+)", re.IGNORECASE)
    # Pattern: "Could not find a version that satisfies the requirement package==version"
    no_version_pattern = re.compile(r"could not find a version that satisfies the requirement (\S+)==([\d.]+)", re.IGNORECASE)
    # Pattern: "ERROR: package has requirement dep>=X, but you have dep Y"
    conflict_pattern = re.compile(r"(\S+) has requirement (\S+)([><=!]+)([\d.]+)", re.IGNORECASE)

    problem_packages = set()
    for pattern in [no_dist_pattern, no_version_pattern]:
        for match in pattern.finditer(error_output):
            pkg = match.group(1)
            problem_packages.add(pkg)

    if not problem_packages:
        # Check for general build failures with package names
        if "pip install" in error_lower or "requirement" in error_lower:
            logger.warning("Build failed during pip install but couldn't identify specific packages")
        return []

    with open(req_file, "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            pkg_name = re.split(r"[><=!~\[]", stripped)[0].strip()
            if pkg_name.lower() in {p.lower() for p in problem_packages}:
                # Replace exact pin with flexible version
                new_line = f"{pkg_name}\n"
                new_lines.append(new_line)
                fixes.append(f"{pkg_name} (unpinned from {stripped})")
                logger.info("  Fixed: %s → %s", stripped, pkg_name)
                continue
        new_lines.append(line)

    if fixes:
        with open(req_file, "w") as f:
            f.writelines(new_lines)

    return fixes


def _fix_node_packages(context: str, error_output: str) -> list[str]:
    """Fix Node.js package issues by regenerating package-lock.json."""
    app_dir = context
    if not os.path.exists(os.path.join(app_dir, "package.json")):
        # Search for package.json
        for root, _, files in os.walk(context):
            if "package.json" in files:
                app_dir = root
                break
        else:
            return []

    fixes = []

    if "npm ci" in error_output.lower() or "npm ERR!" in error_output:
        logger.info("  Attempting npm install to regenerate package-lock.json...")
        result = run_cmd("npm install", cwd=app_dir, check=False)
        if result.returncode == 0:
            fixes.append("package-lock.json (regenerated)")
        else:
            # Try removing node_modules and retrying
            node_modules = os.path.join(app_dir, "node_modules")
            if os.path.exists(node_modules):
                import shutil
                shutil.rmtree(node_modules)
            lock_file = os.path.join(app_dir, "package-lock.json")
            if os.path.exists(lock_file):
                os.remove(lock_file)
            result = run_cmd("npm install", cwd=app_dir, check=False)
            if result.returncode == 0:
                fixes.append("package-lock.json (clean regenerated)")

    return fixes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Docker build and push tool")
    parser.add_argument("--repo-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
    parser.add_argument("--acr-name", required=True, help="ACR registry name")
    parser.add_argument("--acr-hostname", default=None, help="ACR hostname (default: <acr-name>.azurecr.io)")
    parser.add_argument("--image-tag", default=None)
    parser.add_argument("--no-auto-fix", action="store_true")
    args = parser.parse_args()

    tag = args.image_tag
    if not tag:
        from datetime import datetime
        tag = f"deploy-test-{datetime.utcnow().strftime('%Y-%m-%d_%H%M')}"

    hostname = args.acr_hostname or f"{args.acr_name}.azurecr.io"

    # Auto-detect images
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import _detect_images
    images = _detect_images(args.repo_root)

    result = run(args.repo_root, args.acr_name, hostname, image_tag=tag, images=images, auto_fix=not args.no_auto_fix)
    print(f"\n{'✔' if result.success else '✘'} {result.message}")
    if result.fixed_packages:
        print(f"  Auto-fixed packages: {', '.join(result.fixed_packages)}")
    sys.exit(0 if result.success else 1)
