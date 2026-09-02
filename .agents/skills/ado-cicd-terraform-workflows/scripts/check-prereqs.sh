#!/usr/bin/env bash
# Validate that the tools required by the ado-cicd-terraform-workflows skill are available.
# Portable Bash (macOS Bash 3.2 + Windows Git Bash/WSL). Standard tooling only.
#
# This skill targets Azure DevOps pipelines. It relies on the user's active `az` session; the
# Azure DevOps CLI extension (`az devops`) is only needed for the optional setup/validation steps.
set -eu

missing=0
warn=0

have() { command -v "$1" >/dev/null 2>&1; }

require() {
  if have "$1"; then
    printf 'ok    %-10s %s\n' "$1" "$(command -v "$1")"
  else
    printf 'MISS  %-10s required: %s\n' "$1" "$2"
    missing=$((missing + 1))
  fi
}

recommend() {
  if have "$1"; then
    printf 'ok    %-10s %s\n' "$1" "$(command -v "$1")"
  else
    printf 'warn  %-10s recommended: %s\n' "$1" "$2"
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
recommend az        "Azure sign-in, and resource-group cleanup"
recommend terraform "run terraform fmt/validate locally (the pipeline installs it if absent)"

echo
echo "== Authentication (optional, only for setup steps) =="
if have az; then
  if az account show >/dev/null 2>&1; then
    echo "ok    az signed in"
  else
    echo "warn  az not signed in (run: az login)"
    warn=$((warn + 1))
  fi
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
