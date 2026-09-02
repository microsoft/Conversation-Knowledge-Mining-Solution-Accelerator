#!/usr/bin/env bash
# Discover the ADO-CI/CD-relevant facts of a Terraform repository in the current working directory.
# Emits a single JSON document on stdout. Portable Bash (macOS Bash 3.2 + Git Bash/WSL).
#
# Detection only — this script never modifies the repo. Assumes Terraform (azurerm provider).
# Variable VALUES are never read or printed; only their names. Secrets are never touched.
#
# Deployment model (no stages, no per-env tfvars, no environments): the deploy pipeline generates a
# unique resource-group / solution name, runs `terraform apply` against a runtime LOCAL backend
# (ephemeral state on the agent — no remote state backend to bootstrap), hands off to post-deploy +
# tests, then deletes the resource group. Configuration comes from an Azure DevOps variable group.
#
# Usage: run from the target repository root (or pass --root <path>):
#   inspect-repo-tf.sh [--root <path>]
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

# ---- Terraform root discovery (content-based; folder name is only a hint) ----
# The Terraform root module is chosen by content: a main.tf that is NOT under a modules/ tree.
# Among those content candidates, a path segment literally named `infra` is preferred as a
# common-convention baseline; otherwise the shallowest candidate (fewest path segments) wins.
# Falls back to any main.tf. Works whatever the directory is called (infra, infra_tf, terraform,
# or anything else). Left empty when the repo has no main.tf.
tf_files="$(find_files -name '*.tf')"
tf_root_dir=""
if [ -n "$tf_files" ]; then
  _cands="$(printf '%s\n' "$tf_files" | grep -E '(^|/)main\.tf$' | grep -vE '(^|/)modules/' || true)"
  [ -n "$_cands" ] || _cands="$(printf '%s\n' "$tf_files" | grep -E '(^|/)main\.tf$' || true)"
  _pref="$(printf '%s\n' "$_cands" | grep -E '(^|/)infra/' || true)"
  [ -n "$_pref" ] && _cands="$_pref"
  _mt="$(printf '%s\n' "$_cands" | awk 'NF{n=gsub(/\//,"/"); print n"\t"$0}' | LC_ALL=C sort -k1,1n -k2,2 | head -n 1 | cut -f2-)"
  [ -n "$_mt" ] && tf_root_dir="$(dirname "$_mt")"
fi

tf_entrypoint=""
[ -f "$tf_root_dir/main.tf" ] && tf_entrypoint="$tf_root_dir/main.tf"

# Declared backend in the committed (git-tracked, non-override) .tf. The deploy pipeline overrides
# this with a runtime LOCAL backend for ephemeral runs, so a remote backend here is not a blocker.
tf_backend="none"
if [ -n "$tf_root_dir" ]; then
  _in_git=0
  if have git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then _in_git=1; fi
  for _tf in "$tf_root_dir"/*.tf; do
    [ -e "$_tf" ] || continue
    _base="$(basename "$_tf")"
    _ci_file=1
    case "$_base" in
      *_override.tf|override.tf) _ci_file=0 ;;
    esac
    if [ "$_ci_file" -eq 1 ] && [ "$_in_git" -eq 1 ]; then
      git ls-files --error-unmatch "$_tf" >/dev/null 2>&1 || _ci_file=0
    fi
    [ "$_ci_file" -eq 0 ] && continue
    if grep -qsE 'backend[[:space:]]+"azurerm"' "$_tf"; then
      tf_backend="azurerm"
    elif [ "$tf_backend" = "none" ] && grep -qsE 'backend[[:space:]]+"[a-z]+"' "$_tf"; then
      tf_backend="other"
    fi
  done
fi

# ---- required variables (variable blocks without a default) -----------------
# Parse the root .tf variable blocks; a variable with no `default = ...` must be provided by the
# pipeline's variable group (as TF_VAR_<name>). Names only — values are never read.
required_vars_json="[]"
optional_vars_json="[]"
if [ -d "$tf_root_dir" ]; then
  parsed="$(awk '
    /^[[:space:]]*variable[[:space:]]+"/ {
      name=$0; sub(/^[[:space:]]*variable[[:space:]]+"/,"",name); sub(/".*$/,"",name);
      depth=0; has_default="no";
    }
    {
      # track brace depth to know when a variable block ends
      n=gsub(/{/,"{"); m=gsub(/}/,"}");
      depth += n - m;
      if (name!="" && $0 ~ /^[[:space:]]*default[[:space:]]*=/) has_default="yes";
      if (name!="" && depth<=0 && (n+m)>0) { print name "\t" has_default; name=""; }
    }
  ' "$tf_root_dir"/*.tf 2>/dev/null || true)"
  req=""; opt=""
  while IFS="$(printf '\t')" read -r vname vdef; do
    [ -n "$vname" ] || continue
    # subscription_id is provided from the service connection, not the variable group.
    [ "$vname" = "subscription_id" ] && continue
    if [ "$vdef" = "no" ]; then
      req="$req${req:+$'\n'}$vname"
    else
      opt="$opt${opt:+$'\n'}$vname"
    fi
  done <<EOF
$parsed
EOF
  required_vars_json="$(printf '%s' "$req" | lines_to_json_array)"
  optional_vars_json="$(printf '%s' "$opt" | lines_to_json_array)"
fi

# ---- coexisting Bicep? ------------------------------------------------------
bicep_present="false"
if find_files -name '*.bicep' | grep -q .; then bicep_present="true"; fi

# ---- existing Azure DevOps pipeline files -----------------------------------
existing_pipelines="$(find_files \( -name 'azure-pipelines*.yml' -o -name 'azure-pipelines*.yaml' \) 2>/dev/null || true)"
extra_pipelines="$(find . \( -path './.azuredevops/*' -o -path './.azure-pipelines/*' -o -path './pipelines/*' \) -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sed 's|^\./||' || true)"
all_pipelines="$(printf '%s\n%s\n' "$existing_pipelines" "$extra_pipelines")"

# ---- required terraform version (from required_version, if pinned) ----------
tf_required_version=""
if [ -n "$tf_root_dir" ]; then
  tf_required_version="$(grep -hoE 'required_version[[:space:]]*=[[:space:]]*"[^"]*"' "$tf_root_dir"/*.tf 2>/dev/null | head -n 1 | sed -E 's/.*"([^"]*)".*/\1/' || true)"
fi

# ---- assemble JSON ----------------------------------------------------------
jq -n \
  --arg root "$ROOT" \
  --arg org_repo "$org_repo" \
  --arg remote_host "$remote_host" \
  --arg default_branch "$default_branch" \
  --arg tf_entrypoint "$tf_entrypoint" \
  --arg tf_root_dir "$tf_root_dir" \
  --arg tf_backend "$tf_backend" \
  --arg tf_required_version "$tf_required_version" \
  --arg bicep_present "$bicep_present" \
  --argjson required_vars "$required_vars_json" \
  --argjson optional_vars "$optional_vars_json" \
  --argjson existing_pipelines "$(printf '%s' "$all_pipelines" | lines_to_json_array)" \
  '{
    repo_root: $root,
    org_repo: (if $org_repo == "" then null else $org_repo end),
    remote_host: (if $remote_host == "" then null else $remote_host end),
    default_branch: $default_branch,
    infra: {
      flavor: "terraform",
      tf_entrypoint: (if $tf_entrypoint == "" then null else $tf_entrypoint end),
      tf_root_dir: (if $tf_root_dir == "" then null else $tf_root_dir end),
      backend: $tf_backend,
      required_version: (if $tf_required_version == "" then null else $tf_required_version end),
      bicep_present: ($bicep_present == "true")
    },
    deployment: {
      deploy_tool: "terraform apply (runtime local backend, ephemeral state)",
      resource_group: "created by terraform, deleted after tests; the true name is captured from state for cleanup (some solutions self-name it, e.g. with a random suffix)",
      required_variables: (["AZURE_SUBSCRIPTION_ID","AZURE_LOCATION"] + $required_vars | unique),
      optional_variables: $optional_vars,
      generated_vars: (($required_vars + $optional_vars) | map(select(. == "resource_group_name" or . == "solution_name"))),
      schedule_cron_utc: "30 18 * * *",
      schedule_comment: "00:00 IST daily"
    },
    azure_devops: {
      existing_pipelines: $existing_pipelines,
      service_connection_required: true,
      variable_group_required: true
    }
  }'
