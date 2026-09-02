#!/usr/bin/env bash
# Validate that the tools required by the ado-cicd-bicep-workflows skill are available.
# Portable Bash (macOS Bash 3.2 + Windows Git Bash/WSL). Standard tooling only.
#
# This skill targets Azure DevOps pipelines. It relies on the user's
# active `az` session; the Azure DevOps CLI extension (`az devops`) is only needed for the
# optional setup steps (service connection / variable group guidance and pipeline validation).
set -eu

missing=0
warn=0

have() { command -v "$1" >/dev/null 2>&1; }

require() {
  # require <cmd> <purpose>
  if have "$1"; then
    printf 'ok    %-8s %s\n' "$1" "$(command -v "$1")"
  else
    printf 'MISS  %-8s required: %s\n' "$1" "$2"
    missing=$((missing + 1))
  fi
}

recommend() {
  # recommend <cmd> <purpose>
  if have "$1"; then
    printf 'ok    %-8s %s\n' "$1" "$(command -v "$1")"
  else
    printf 'warn  %-8s recommended: %s\n' "$1" "$2"
    warn=$((warn + 1))
  fi
}

echo "== Required tools =="
require bash "run the skill scripts"
require jq   "parse and emit JSON"
require git  "detect the repository root"
require grep "scan files during discovery"
require find "scan files during discovery"

echo
echo "== Recommended tools =="
recommend az   "Azure sign-in, deployment, and cleanup steps"

echo
echo "== Authentication (optional, only for setup steps) =="
if have az; then
  if az account show >/dev/null 2>&1; then
    echo "ok    az signed in"
  else
    echo "warn  az not signed in (run: az login)"
    warn=$((warn + 1))
  fi
  # The Azure DevOps CLI extension is only needed to validate pipelines / manage the project.
  if az extension show --name azure-devops >/dev/null 2>&1; then
    echo "ok    az devops extension installed"
  else
    echo "warn  az devops extension not installed (run: az extension add --name azure-devops) — only needed for pipeline validation/setup"
    warn=$((warn + 1))
  fi
fi

echo
if [ "$missing" -gt 0 ]; then
  echo "FAIL: $missing required tool(s) missing."
  exit 1
fi
if [ "$warn" -gt 0 ]; then
  echo "OK with $warn warning(s): discovery works; some setup steps need the missing tools."
  exit 0
fi
echo "OK: all tools present."
