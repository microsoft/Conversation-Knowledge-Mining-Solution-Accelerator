#!/usr/bin/env bash
# ============================================================================
# inspect-post-deploy.sh — GENERIC, read-only discovery of a solution's
# post-deploy layer. Emits one JSON object (app-facts.json). Makes NO repo
# changes and contains NO solution-specific knowledge: every fact is derived
# mechanically from the repo's own azd contract and docs, so it works on any
# azd-based solution accelerator.
#
# Two generic sources (a repo may use either or both):
#   1. azd hooks in azure.yaml  (preprovision/postprovision/predeploy/postdeploy)
#      — the declarative contract azd itself runs. For each hook we record the
#      POSIX variant (CI is Linux), whether it EXECUTES its scripts or only
#      PRINTS instructions, and the ordered scripts it references.
#   2. the README / deployment guide "deployment" / "post-deployment" sections
#      (and docs they link to) — the human step list, which often names scripts
#      to run and/or manual steps a person performs by hand.
#
# Nothing is classified by filename/domain keywords. Script "runner" is derived
# only from the invocation (bash/sh/pwsh/python) or the file extension.
#
# Portable Bash (macOS Bash 3.2 + Windows Git Bash/WSL). Requires: jq.
# Usage: inspect-post-deploy.sh [repo_root] > .agent/tmp/app-facts.json
# ============================================================================
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
cd "$REPO_ROOT"
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required." >&2; exit 1; }

first_existing() { for p in "$@"; do [ -e "$p" ] && { printf '%s' "$p"; return 0; }; done; printf ''; }
SCRIPT_RE='[A-Za-z0-9_./\\-]+\.(sh|ps1|py)'

# ----------------------------------------------------------------------------
# azd detection
# ----------------------------------------------------------------------------
AZURE_YAML="$(first_existing azure.yaml azure.yml)"
AZD_PRESENT=false; AZD_NAME=""; INFRA_PROVIDER=""
if [ -n "$AZURE_YAML" ]; then
  AZD_PRESENT=true
  AZD_NAME="$(grep -E '^name:' "$AZURE_YAML" | head -n1 | sed -E 's/^name:[[:space:]]*//; s/[[:space:]]*$//' | tr -d "\"'")"
  INFRA_PROVIDER="$(awk '/^infra:/{f=1;next} f&&/^[^[:space:]]/{f=0} f&&/provider:/{gsub(/.*provider:[[:space:]]*/,"");gsub(/[[:space:]].*/,"");print;exit}' "$AZURE_YAML")"
  [ -n "$INFRA_PROVIDER" ] || INFRA_PROVIDER="bicep"
fi

# ----------------------------------------------------------------------------
# Parse azd hooks (indent state machine; no YAML library).
# For every hook, use the POSIX variant's run block (CI runs on Linux). Emit
# one TSV row per referenced script:  hook \t invoked(0|1) \t runner \t path
# ----------------------------------------------------------------------------
hook_rows() {
  awk '
    function runner_of(path, line,   r){
      if(line ~ /pwsh([[:space:]]+-File)?[[:space:]]/) return "pwsh"
      if(line ~ /(^|[[:space:]])(bash|sh)[[:space:]]/)  return "bash"
      if(line ~ /(^|[[:space:]])python3?[[:space:]]/)   return "python"
      if(path ~ /\.ps1$/) return "pwsh"
      if(path ~ /\.sh$/)  return "bash"
      if(path ~ /\.py$/)  return "python"
      return "unknown"
    }
    BEGIN{inhooks=0; hook=""; variant=""; inrun=0; runindent=0}
    # leave hooks block on any col-0 key that is not hooks:
    /^[^[:space:]]/{ if($0 ~ /^hooks:/){inhooks=1; next} else {inhooks=0; hook=""; variant=""; inrun=0; next} }
    {
      if(!inhooks) next
      # count leading spaces
      ind=0; while(substr($0,ind+1,1)==" ") ind++
      # hook name at 2-space indent
      if(ind==2 && $0 ~ /^  [A-Za-z]+:[[:space:]]*$/){
        h=$0; sub(/^  /,"",h); sub(/:.*/,"",h)
        if(h=="preprovision"||h=="postprovision"||h=="predeploy"||h=="postdeploy"||h=="preup"||h=="postup"){
          hook=h; variant=""; inrun=0
        } else { hook="" }
        next
      }
      if(hook==""){ next }
      # variant at 4-space indent
      if(ind==4 && $0 ~ /^    (posix|windows):[[:space:]]*$/){
        v=$0; sub(/^    /,"",v); sub(/:.*/,"",v); variant=v; inrun=0; next
      }
      # we only extract from the posix variant (Linux CI)
      if(variant!="posix"){ next }
      # start of a run: | block
      if(!inrun && $0 ~ /^[[:space:]]+run:[[:space:]]*\|?[[:space:]]*$/){
        runindent=ind; inrun=1; next
      }
      if(inrun){
        # a sibling key (shell:/interactive:/continueOnError:) at <= run indent ends the block
        if(ind<=runindent && $0 ~ /^[[:space:]]+[A-Za-z]+:/){ inrun=0 }
        else {
          line=$0
          printed = (line ~ /echo|printf|Write-Host|Write-Output/)
          while(match(line, /[A-Za-z0-9_.\/\\-]+\.(sh|ps1|py)/)){
            ref=substr(line, RSTART, RLENGTH); rest=substr(line, RSTART+RLENGTH)
            r=runner_of(ref, $0)
            gsub(/^\.[\/\\]/,"",ref); gsub(/\\/,"/",ref)
            # skip venv activation noise (generic: virtualenv bootstrap, not a step)
            if(ref !~ /(^|\/)\.?venv\// && ref !~ /[Aa]ctivate\.(ps1|sh)/){
              invoked = (printed?0:1)
              print hook "\t" invoked "\t" r "\t" ref
            }
            line=rest
          }
          next
        }
      }
    }
  ' "$AZURE_YAML"
}

HOOKS_JSON='{}'
if [ "$AZD_PRESENT" = true ]; then
  HOOKS_JSON="$(hook_rows | jq -R -s '
    [ split("\n")[] | select(length>0) | split("\t")
      | {hook:.[0], invoked:(.[1]=="1"), runner:.[2], path:.[3]} ]
    | group_by(.hook)
    | map({ key: .[0].hook,
            value: {
              run_mode: (if any(.[]; .invoked) then "executes" else "prints_only" end),
              scripts: ( [ .[] | {path, runner} ] | unique_by(.path) )
            } })
    | from_entries
  ')"
  [ -n "$HOOKS_JSON" ] || HOOKS_JSON='{}'
fi

# ----------------------------------------------------------------------------
# Deployment guides / README — post-deployment section (mechanical only)
# ----------------------------------------------------------------------------
GUIDES=""
for g in \
  README.md \
  docs/DeploymentGuide.md documents/DeploymentGuide.md DeploymentGuide.md \
  docs/DEPLOYMENT.md DEPLOYMENT.md docs/AZD_DEPLOYMENT.md \
  docs/AVMPostDeploymentGuide.md docs/deployment-guide.md documents/deployment-guide.md ; do
  [ -f "$g" ] && GUIDES="$GUIDES$g"$'\n'
done
GUIDES_JSON="$(printf '%s' "$GUIDES" | { grep -v '^[[:space:]]*$' || true; } | jq -R . | jq -s .)"

# Extract deployment / post-deployment step sections (any level>=2 heading mentioning "deploy",
# e.g. "Deploying with AZD", "Deployment Steps", "Post Deployment Steps") up to the next heading of
# same-or-higher level. Emit referenced scripts and follow links into sibling setup guides.
extract_section() {
  awk '
    BEGIN{insec=0; seclevel=0}
    /^#{1,6}[[:space:]]/{
      lvl=0; for(i=1;i<=length($0);i++){ if(substr($0,i,1)=="#") lvl++; else break }
      title=$0; sub(/^#{1,6}[[:space:]]*/,"",title)
      # Skip the H1 doc title so a "Deployment Guide" heading does not select the whole file.
      if(lvl>=2 && tolower(title) ~ /deploy/){ insec=1; seclevel=lvl; next }
      else if(insec && lvl<=seclevel){ insec=0 }
    }
    insec{ print }
  ' "$1"
}
# Normalize paths, drop URL/venv/activate noise and pre-provision scripts (those run BEFORE
# provisioning, not after), and keep only scripts that exist on disk.
clean_exist() {
  sed -E 's#^\.[/\\]##; s#\\#/#g' \
  | { grep -vE '://|www\.|^//|(^|/)\.?venv/|[Aa]ctivate\.(ps1|sh)|(^|/)pre-?provision/' || true; } \
  | while IFS= read -r p; do
      if [ -n "$p" ] && [ -e "$p" ]; then printf '%s\n' "$p"; fi
    done
}
GUIDE_SCRIPTS=""
for g in $(printf '%s' "$GUIDES" | { grep -v '^[[:space:]]*$' || true; }); do
  sec="$(extract_section "$g" || true)"; [ -n "$sec" ] || continue
  gdir="$(dirname "$g")"
  # (a) scripts referenced directly in the deployment / post-deployment section(s)
  refs="$( { printf '%s\n' "$sec" | grep -oE "$SCRIPT_RE" || true; } | clean_exist)"
  [ -n "$refs" ] && GUIDE_SCRIPTS="$GUIDE_SCRIPTS$refs"$'\n' || true
  # (b) follow relative markdown links from those sections into sibling docs (one level) and
  #     extract the scripts they name — e.g. a step documented in a separate linked guide.
  links="$( { printf '%s\n' "$sec" | grep -oE '\]\([^)]+\.md[^)]*\)' || true; } \
    | sed -E 's/^\]\(//; s/\).*$//; s/#.*$//' | { grep -vE '://|www\.' || true; })"
  for l in $links; do
    lp="${l#./}"; lp="${lp#/}"
    cand="$gdir/$lp"; [ -f "$cand" ] || cand="$lp"
    [ -f "$cand" ] || continue
    lrefs="$( { grep -oE "$SCRIPT_RE" "$cand" || true; } | clean_exist)"
    [ -n "$lrefs" ] && GUIDE_SCRIPTS="$GUIDE_SCRIPTS$lrefs"$'\n' || true
  done
done
guide_scripts_json() {
  printf '%s' "$GUIDE_SCRIPTS" | { grep -v '^[[:space:]]*$' || true; } | awk '!seen[$0]++' \
  | jq -R '{path:., runner:(if test("\\.ps1$") then "pwsh" elif test("\\.sh$") then "bash" elif test("\\.py$") then "python" else "unknown" end)}' \
  | jq -s .
}
GUIDE_SCRIPTS_JSON="$(guide_scripts_json)"

# ----------------------------------------------------------------------------
# Reconciled, ordered post-deploy plan (union of hook + guide script refs).
# Hook scripts come first, in declared order (the POSIX variant is already
# Linux-appropriate). Guide scripts are appended only when they are not an
# OS-variant of a hook script (normalized stem: drop dir/ext, lowercase,
# strip non-alphanumerics) — so the same logical step is never listed twice.
# ----------------------------------------------------------------------------
PLAN_JSON="$(jq -n --argjson hooks "$HOOKS_JSON" --argjson guide "$GUIDE_SCRIPTS_JSON" '
  def stem: (. | sub(".*/";"") | sub("\\.[^.]+$";"") | ascii_downcase | gsub("[^a-z0-9]";""));
  ( [ $hooks | to_entries[]
      | select(.key|test("^post")) as $e
      | .value.scripts[] | {path, runner, source:"hook"} ] ) as $hookscripts
  | ($hookscripts | map(.path|stem)) as $hookstems
  | ( [ $guide[] | {path, runner, source:"guide"}
        | select( ([.path|stem] - $hookstems) | length > 0 ) ] ) as $guidescripts
  | ($hookscripts + $guidescripts)
  | reduce .[] as $s ([]; if any(.[]; (.path|stem)==($s.path|stem)) then . else . + [$s] end)
')"

# ----------------------------------------------------------------------------
# Mechanical execution facts about the referenced scripts on disk.
# ----------------------------------------------------------------------------
# Runtime needs are derived directly from the plan's file extensions.
NEEDS_PWSH=$(printf '%s' "$PLAN_JSON"   | jq 'any(.[]; .path|test("\\.ps1$"))')
NEEDS_BASH=$(printf '%s' "$PLAN_JSON"   | jq 'any(.[]; .path|test("\\.sh$"))')
NEEDS_PYTHON=$(printf '%s' "$PLAN_JSON" | jq 'any(.[]; .path|test("\\.py$"))')

# Content facts: does any script read the azd env, or prompt interactively?
READS_AZD_ENV=false; INTERACTIVE=false
for p in $(printf '%s' "$PLAN_JSON" | jq -r '.[].path'); do
  [ -f "$p" ] || continue
  if grep -qsE 'azd env get-value' "$p" 2>/dev/null; then READS_AZD_ENV=true; fi
  if grep -qsE 'input\(|Read-Host' "$p" 2>/dev/null; then INTERACTIVE=true; fi
done

# requirements.txt near the referenced python scripts (generic path search).
REQS="$(find infra src scripts . -maxdepth 4 -type f -name 'requirements.txt' 2>/dev/null | sed 's#^\./##' | sort | head -n1 || true)"
[ "$NEEDS_PYTHON" = true ] || REQS=""

# ----------------------------------------------------------------------------
# Assemble JSON
# ----------------------------------------------------------------------------
jq -n \
  --arg repo_root "$REPO_ROOT" \
  --arg azure_yaml "$AZURE_YAML" \
  --argjson azd_present "$AZD_PRESENT" \
  --arg azd_name "$AZD_NAME" \
  --arg infra_provider "$INFRA_PROVIDER" \
  --argjson hooks "$HOOKS_JSON" \
  --argjson guides "$GUIDES_JSON" \
  --argjson guide_scripts "$GUIDE_SCRIPTS_JSON" \
  --argjson plan "$PLAN_JSON" \
  --arg requirements "$REQS" \
  --argjson reads_azd_env "$READS_AZD_ENV" \
  --argjson interactive "$INTERACTIVE" \
  --argjson needs_pwsh "$NEEDS_PWSH" \
  --argjson needs_bash "$NEEDS_BASH" \
  --argjson needs_python "$NEEDS_PYTHON" \
  '{
    repo_root: $repo_root,
    infra_kind: (if $azd_present then "azd" else "raw" end),
    azd: {
      present: $azd_present,
      azure_yaml: (if $azure_yaml=="" then null else $azure_yaml end),
      name: (if $azd_name=="" then null else $azd_name end),
      infra_provider: (if $infra_provider=="" then null else $infra_provider end),
      hooks: $hooks
    },
    guides: $guides,
    guide_post_deploy: {
      scripts: $guide_scripts
    },
    post_deploy_plan: {
      scripts: $plan,
      requirements: (if $requirements=="" then null else $requirements end),
      reads_azd_env: $reads_azd_env,
      interactive_prompts: $interactive,
      needs_pwsh: $needs_pwsh,
      needs_bash: $needs_bash,
      needs_python: $needs_python
    },
    notes: [
      (if ($plan|length)==0 then
        "No post-deploy scripts were discovered from azd hooks or the deployment guide; this solution may have no post-provision layer, or its steps are described in prose only — review the guide(s) in `.guides` with the user."
       else empty end),
      (if $reads_azd_env then
        "One or more scripts read config via `azd env get-value`; the pipeline must install azd and hydrate an azd environment (azd env set from the infra deployment outputs) before running them."
       else empty end),
      (if ($hooks | to_entries | any(.[]; .value.run_mode=="prints_only")) then
        "Some azd hooks only PRINT their steps (they do not execute them); the referenced scripts are the real work and are surfaced in post_deploy_plan.scripts."
       else empty end),
      "Manual steps that have no script to invoke are NOT extracted mechanically — open the guide(s) listed in `.guides` and confirm any manual-only steps with the user; emit them as run-summary reminders rather than automating them blindly.",
      (if $interactive then
        "At least one referenced script contains interactive prompts (input()/Read-Host); confirm a non-interactive invocation with the user before running it in CI."
       else empty end)
    ]
  }'
