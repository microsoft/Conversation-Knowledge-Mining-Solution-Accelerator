#!/usr/bin/env bash
# Discover the ADO-CI/CD-relevant facts of the repository in the current working directory.
# Emits a single JSON document on stdout.
# Portable Bash (macOS Bash 3.2 + Git Bash/WSL).
#
# Detection only — this script never modifies the repo. Always assumes Bicep.
# Variable VALUES are never read or printed; only their names. Secrets are never touched.
#
# Deployment model (no stages, no params folder, no environments): the pipeline creates a fresh
# resource group and deploys the Bicep entrypoint with `az deployment` (no azd/azure.yaml
# dependency), runs post-deploy, tests, then deletes the resource group. Configuration comes from
# an Azure DevOps *variable group*, not per-env files.
#
# Usage: run from the target repository root (or pass --root <path>):
#   inspect-repo.sh [--root <path>]
set -eu

ROOT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

if [ -z "$ROOT" ]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi
cd "$ROOT"

have() { command -v "$1" >/dev/null 2>&1; }

lines_to_json_array() {
  grep -v '^[[:space:]]*$' | LC_ALL=C sort -u | jq -R . | jq -s .
}

find_files() {
  # shellcheck disable=SC2016
  find . \
    \( -name .git -o -name .github -o -name .devcontainer -o -name .agents -o -name node_modules -o -name .terraform -o -name .venv -o -name dist -o -name build \) -prune \
    -o -type f "$@" -print 2>/dev/null | sed 's|^\./||'
}

# ---- default branch ---------------------------------------------------------
default_branch=""
if have git; then
  default_branch="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)"
  [ -n "$default_branch" ] || default_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
fi
[ -n "$default_branch" ] || default_branch="main"

# ---- org/repo slug (GitHub or Azure DevOps remote) --------------------------
org_repo=""
remote_host=""
if have git; then
  remote_url="$(git config --get remote.origin.url 2>/dev/null || true)"
  case "$remote_url" in
    *github.com[:/]*)
      remote_host="github"
      org_repo="$(printf '%s' "$remote_url" | sed -e 's|.*github.com[:/]||' -e 's|\.git$||')"
      ;;
    *dev.azure.com/*|*visualstudio.com/*)
      remote_host="azure-devops"
      org_repo="$(printf '%s' "$remote_url" | sed -e 's|.*dev.azure.com/||' -e 's|.*visualstudio.com/||' -e 's|\.git$||')"
      ;;
  esac
fi

# ---- Bicep discovery (content-based; folder name is only a hint) ------------
# This skill always assumes Bicep. The entrypoint is chosen by content: a main.bicep that is NOT
# under a modules/ tree. Among those content candidates, a path segment literally named `infra` is
# preferred as a common-convention baseline; otherwise the shallowest candidate (fewest path
# segments) wins. Falls back to any main.bicep, then any .bicep. Works whatever the directory is
# called (infra, bicep, or anything else). infra_dir = its dir.
bicep_files="$(find_files -name '*.bicep')"
bicep_entrypoint=""
if [ -n "$bicep_files" ]; then
  _cands="$(printf '%s\n' "$bicep_files" | grep -E '(^|/)main\.bicep$' | grep -vE '(^|/)modules/' || true)"
  [ -n "$_cands" ] || _cands="$(printf '%s\n' "$bicep_files" | grep -E '(^|/)main\.bicep$' || true)"
  _pref="$(printf '%s\n' "$_cands" | grep -E '(^|/)infra/' || true)"
  [ -n "$_pref" ] && _cands="$_pref"
  bicep_entrypoint="$(printf '%s\n' "$_cands" | awk 'NF{n=gsub(/\//,"/"); print n"\t"$0}' | LC_ALL=C sort -k1,1n -k2,2 | head -n 1 | cut -f2-)"
  [ -n "$bicep_entrypoint" ] || bicep_entrypoint="$(printf '%s\n' "$bicep_files" | head -n 1)"
fi

infra_dir=""
[ -n "$bicep_entrypoint" ] && infra_dir="$(dirname "$bicep_entrypoint")"

# Bicep parameters file next to the entrypoint, if any.
bicep_params=""
if [ -n "$bicep_entrypoint" ]; then
  dir="$(dirname "$bicep_entrypoint")"
  for cand in "$dir/main.parameters.json" "$dir/main.bicepparam"; do
    [ -f "$cand" ] && { bicep_params="$cand"; break; }
  done
fi

# Bicep deployment scope (resource group vs subscription).
bicep_scope="resourceGroup"
if [ -n "$bicep_entrypoint" ] && grep -qiE "targetScope[[:space:]]*=[[:space:]]*'subscription'" "$bicep_entrypoint" 2>/dev/null; then
  bicep_scope="subscription"
fi

# ---- azd / azure.yaml presence (informational only) -------------------------
# The deploy pipeline deploys the Bicep entrypoint directly with `az deployment`; it does NOT
# require azure.yaml. We still surface it because, when present, it documents azd pre/postprovision
# hooks a maintainer may want to port into the pipeline.
azure_yaml=""
for cand in azure.yaml azure.yml; do
  [ -f "$cand" ] && { azure_yaml="$cand"; break; }
done

# ---- required pipeline variables --------------------------------------------
# With main.parameters.json, every parameter is supplied via ${VAR} / ${VAR=default}
# tokens (resolved by the pipeline from the environment, the same way azd did). Tokens WITHOUT a
# "=default" are mandatory variables the pipeline's variable group must provide; tokens WITH a
# default are optional overrides. This drives the variable-group setup.
required_vars_json="[]"
optional_vars_json="[]"
if [ -n "$bicep_params" ] && printf '%s' "$bicep_params" | grep -q '\.json$'; then
  # Extract ${...} tokens from the parameters JSON.
  toks="$(grep -oE '\$\{[A-Za-z0-9_]+(=[^}]*)?\}' "$bicep_params" 2>/dev/null | sed -e 's/^\${//' -e 's/}$//' || true)"
  req=""
  opt=""
  while IFS= read -r t; do
    [ -n "$t" ] || continue
    case "$t" in
      *=*) opt="$opt${opt:+$'\n'}${t%%=*}" ;;
      *)   req="$req${req:+$'\n'}$t" ;;
    esac
  done <<EOF
$toks
EOF
  required_vars_json="$(printf '%s' "$req" | lines_to_json_array)"
  optional_vars_json="$(printf '%s' "$opt" | lines_to_json_array)"
fi

# ---- existing Azure DevOps pipeline files -----------------------------------
# Common conventions: azure-pipelines.yml at root, or under .azuredevops/ / .azure-pipelines/ /
# pipelines/. We surface anything that looks like an ADO pipeline so we never silently overwrite.
existing_pipelines="$(find_files \( -name 'azure-pipelines*.yml' -o -name 'azure-pipelines*.yaml' \) 2>/dev/null || true)"
extra_pipelines="$(find . \( -path './.azuredevops/*' -o -path './.azure-pipelines/*' -o -path './pipelines/*' \) -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sed 's|^\./||' || true)"
all_pipelines="$(printf '%s\n%s\n' "$existing_pipelines" "$extra_pipelines")"

# ---- assemble JSON ----------------------------------------------------------
jq -n \
  --arg root "$ROOT" \
  --arg org_repo "$org_repo" \
  --arg remote_host "$remote_host" \
  --arg default_branch "$default_branch" \
  --arg bicep_entrypoint "$bicep_entrypoint" \
  --arg bicep_params "$bicep_params" \
  --arg bicep_scope "$bicep_scope" \
  --arg infra_dir "$infra_dir" \
  --arg azure_yaml "$azure_yaml" \
  --argjson required_vars "$required_vars_json" \
  --argjson optional_vars "$optional_vars_json" \
  --argjson existing_pipelines "$(printf '%s' "$all_pipelines" | lines_to_json_array)" \
  '{
    repo_root: $root,
    org_repo: (if $org_repo == "" then null else $org_repo end),
    remote_host: (if $remote_host == "" then null else $remote_host end),
    default_branch: $default_branch,
    infra: {
      flavor: "bicep",
      bicep_entrypoint: (if $bicep_entrypoint == "" then null else $bicep_entrypoint end),
      bicep_parameters: (if $bicep_params == "" then null else $bicep_params end),
      bicep_scope: $bicep_scope,
      infra_dir: (if $infra_dir == "" then null else $infra_dir end),
      azd: {
        azure_yaml: (if $azure_yaml == "" then null else $azure_yaml end),
        present: ($azure_yaml != ""),
        note: "Informational only — the deploy pipeline uses az deployment, not azd; azure.yaml is not required."
      }
    },
    deployment: {
      deploy_tool: "az deployment",
      resource_group: "created per run (variable prefix + generated unique suffix), deleted after tests",
      required_variables: (["AZURE_SUBSCRIPTION_ID","AZURE_ENV_NAME","AZURE_LOCATION"] + $required_vars | unique),
      optional_variables: $optional_vars,
      schedule_cron_utc: "30 18 * * *",
      schedule_comment: "00:00 IST daily"
    },
    azure_devops: {
      existing_pipelines: $existing_pipelines,
      service_connection_required: true,
      variable_group_required: true
    }
  }'
