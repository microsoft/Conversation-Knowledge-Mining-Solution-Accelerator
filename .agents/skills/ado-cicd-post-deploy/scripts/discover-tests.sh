#!/usr/bin/env bash
# ============================================================================
# discover-tests.sh — GENERIC, read-only discovery of a solution's automated
# tests (unit + Playwright/e2e). Emits one JSON object on stdout. Makes NO repo
# changes and contains NO solution-specific knowledge: every fact is derived
# mechanically from the repo's test tooling (package.json scripts, pytest
# config, .csproj test projects, Playwright config / imports).
#
# The post-deploy pipeline uses this to add conditional test stages: a test job
# is only rendered when its category is actually present.
#
# Categories:
#   unit_frontend  — a package.json exposing a `test` script (Jest/Vitest/CRA)
#                    with at least one *.test.* / *.spec.* file or __tests__ dir.
#   unit_backend   — pytest (pytest.ini/pyproject/conftest) with at least one
#                    real test_*.py/*_test.py source, and/or dotnet test
#                    projects (*Tests*.csproj / *.Tests.csproj).
#   playwright     — a Playwright config (JS/TS) or Python Playwright usage
#                    (`from playwright...`) under a tests directory.
#
# Portable Bash (macOS Bash 3.2 + Git Bash/WSL). Requires: jq.
# Usage: discover-tests.sh [repo_root] > .agent/tmp/test-facts.json
# ============================================================================
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
cd "$REPO_ROOT"
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required." >&2; exit 1; }

find_files() {
  find . \
    \( -name .git -o -name .github -o -name .devcontainer -o -name .agents -o -name node_modules -o -name .terraform -o -name .venv -o -name venv -o -name env -o -name .tox -o -name .pytest_cache -o -name .mypy_cache -o -name site-packages -o -name dist -o -name build -o -name bin -o -name obj -o -name __pycache__ \) -prune \
    -o -type f "$@" -print 2>/dev/null | sed 's|^\./||'
}
find_dirs() {
  find . \
    \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name env -o -name .tox -o -name site-packages -o -name .terraform -o -name __pycache__ \) -prune \
    -o -type d "$@" -print 2>/dev/null | sed 's|^\./||'
}

# ---- unit_frontend: package.json with a "test" script -----------------------
fe_present=false; fe_dir=""; fe_manager="npm"; fe_cmd=""
for pj in $(find_files -name 'package.json'); do
  # A "test" script that is not the CRA/react-scripts eject placeholder.
  if jq -e '.scripts.test // empty' "$pj" >/dev/null 2>&1; then
    testscript="$(jq -r '.scripts.test // ""' "$pj")"
    case "$testscript" in
      *"no test specified"*) continue ;;
    esac
    pkgdir="$(dirname "$pj")"
    # A `test` script alone is not a runnable suite: require at least one real
    # test file (or a __tests__ dir) under the package, so a script pointing at
    # absent tests doesn't yield a phantom job.
    has_fe_tests="$(find "$pkgdir" -name node_modules -prune -o -type f \( -name '*.test.*' -o -name '*.spec.*' \) -print 2>/dev/null | head -n 1 || true)"
    if [ -z "$has_fe_tests" ]; then
      has_fe_tests="$(find "$pkgdir" -name node_modules -prune -o -type d -name '__tests__' -print 2>/dev/null | head -n 1 || true)"
    fi
    [ -n "$has_fe_tests" ] || continue
    fe_present=true
    fe_dir="$pkgdir"
    # Prefer the package manager implied by a lockfile in the same dir.
    if [ -f "$fe_dir/pnpm-lock.yaml" ]; then fe_manager="pnpm";
    elif [ -f "$fe_dir/yarn.lock" ]; then fe_manager="yarn";
    else fe_manager="npm"; fi
    fe_cmd="$testscript"
    break
  fi
done

# ---- unit_backend: pytest and/or dotnet test --------------------------------
py_present=false; py_dir=""; py_reqs=""
# pytest markers: pytest.ini / setup.cfg [tool:pytest] / pyproject [tool.pytest] / conftest.py
py_marker="$(find_files \( -name 'pytest.ini' -o -name 'conftest.py' \) | head -n 1 || true)"
if [ -z "$py_marker" ]; then
  for pp in $(find_files -name 'pyproject.toml'); do
    if grep -qsE '\[tool\.pytest' "$pp"; then py_marker="$pp"; break; fi
  done
fi
if [ -n "$py_marker" ]; then
  # A marker (pytest.ini/conftest.py/pyproject) alone is not a runnable suite:
  # require at least one real pytest source file. This prevents a phantom suite
  # from a stale marker or leftover __pycache__/*.pyc when the test sources are
  # not actually in the checkout.
  py_src="$(find_files \( -name 'test_*.py' -o -name '*_test.py' \) | head -n 1 || true)"
  if [ -n "$py_src" ]; then
    py_present=true
    py_dir="$(dirname "$py_marker")"
    # Nearest requirements.txt for installing test deps.
    py_reqs="$(find_files -name 'requirements.txt' | head -n 1 || true)"
  fi
fi

dotnet_present=false; dotnet_dir=""
dotnet_test_proj="$(find_files -name '*.csproj' | grep -iE '(tests?|\.tests)\.csproj$|/tests?/' | head -n 1 || true)"
if [ -n "$dotnet_test_proj" ]; then
  dotnet_present=true
  dotnet_dir="$(dirname "$dotnet_test_proj")"
fi

# ---- playwright -------------------------------------------------------------
pw_present=false; pw_dir=""; pw_lang=""
pw_config="$(find_files \( -name 'playwright.config.ts' -o -name 'playwright.config.js' -o -name 'playwright.config.mjs' \) | head -n 1 || true)"
if [ -n "$pw_config" ]; then
  pw_present=true
  pw_dir="$(dirname "$pw_config")"
  pw_lang="node"
else
  # Python Playwright: `from playwright...` import inside a tests tree.
  pw_py="$(grep -rlsE '^[[:space:]]*from[[:space:]]+playwright' --include='*.py' \
    --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv --exclude-dir=env \
    --exclude-dir=.tox --exclude-dir=site-packages --exclude-dir=__pycache__ \
    . 2>/dev/null | sed 's|^\./||' | head -n 1 || true)"
  if [ -n "$pw_py" ]; then
    pw_present=true
    pw_lang="python"
    # Use the nearest ancestor dir that has a pytest.ini, else the file's dir.
    d="$(dirname "$pw_py")"
    while [ "$d" != "." ] && [ "$d" != "/" ]; do
      if [ -f "$d/pytest.ini" ] || [ -f "$d/conftest.py" ]; then pw_dir="$d"; break; fi
      d="$(dirname "$d")"
    done
    [ -n "$pw_dir" ] || pw_dir="$(dirname "$pw_py")"
  fi
fi
pw_reqs=""
if [ "$pw_present" = true ] && [ "$pw_lang" = "python" ]; then
  [ -f "$pw_dir/requirements.txt" ] && pw_reqs="$pw_dir/requirements.txt"
fi

jq -n \
  --arg repo_root "$REPO_ROOT" \
  --argjson fe_present "$fe_present" \
  --arg fe_dir "$fe_dir" \
  --arg fe_manager "$fe_manager" \
  --arg fe_cmd "$fe_cmd" \
  --argjson py_present "$py_present" \
  --arg py_dir "$py_dir" \
  --arg py_reqs "$py_reqs" \
  --argjson dotnet_present "$dotnet_present" \
  --arg dotnet_dir "$dotnet_dir" \
  --argjson pw_present "$pw_present" \
  --arg pw_dir "$pw_dir" \
  --arg pw_lang "$pw_lang" \
  --arg pw_reqs "$pw_reqs" \
  '{
    repo_root: $repo_root,
    unit_frontend: {
      present: $fe_present,
      directory: (if $fe_dir=="" then null else $fe_dir end),
      package_manager: $fe_manager,
      test_script: (if $fe_cmd=="" then null else $fe_cmd end)
    },
    unit_backend: {
      pytest: {
        present: $py_present,
        directory: (if $py_dir=="" then null else $py_dir end),
        requirements: (if $py_reqs=="" then null else $py_reqs end)
      },
      dotnet: {
        present: $dotnet_present,
        directory: (if $dotnet_dir=="" then null else $dotnet_dir end)
      },
      present: ($py_present or $dotnet_present)
    },
    playwright: {
      present: $pw_present,
      language: (if $pw_lang=="" then null else $pw_lang end),
      directory: (if $pw_dir=="" then null else $pw_dir end),
      requirements: (if $pw_reqs=="" then null else $pw_reqs end)
    },
    any_tests: ($fe_present or $py_present or $dotnet_present or $pw_present)
  }'
