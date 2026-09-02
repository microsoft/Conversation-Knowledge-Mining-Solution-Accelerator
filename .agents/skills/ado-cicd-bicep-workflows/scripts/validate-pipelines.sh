#!/usr/bin/env bash
# Validate rendered Azure DevOps pipeline YAML files.
# Portable Bash (macOS Bash 3.2 + Git Bash/WSL).
#
# Azure DevOps has no offline schema validator equivalent to actionlint. Full server-side
# validation requires `az pipelines` against a real project/pipeline (see the note at the end).
# This script performs the strong offline checks that catch the common breakages:
#   1. Each file is well-formed YAML.
#   2. No unrendered __PLACEHOLDER__ tokens remain.
#   3. Every `template:` reference resolves to a file that exists.
#   4. Basic ADO structure (a trigger/pr/schedules key and stages/jobs/steps) is present.
#
# Usage: validate-pipelines.sh <file-or-dir> [more...]
set -eu

fail=0
tmp_list="$(mktemp 2>/dev/null || echo "/tmp/ado-validate-$$.list")"
: > "$tmp_list"
trap 'rm -f "$tmp_list"' EXIT

collect() {
  if [ -d "$1" ]; then
    find "$1" -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null >> "$tmp_list"
  elif [ -f "$1" ]; then
    echo "$1" >> "$tmp_list"
  else
    echo "warn  not found: $1" >&2
  fi
}

if [ "$#" -eq 0 ]; then
  echo "usage: validate-pipelines.sh <file-or-dir> [more...]" >&2
  exit 2
fi
for arg in "$@"; do collect "$arg"; done

YAML_CHECK=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys' >/dev/null 2>&1; then
    YAML_CHECK="$cand"; break
  fi
done

check_yaml() {
  "$YAML_CHECK" - "$1" <<'PY'
import sys
try:
    import yaml
except Exception:
    sys.exit(3)  # pyyaml not installed
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        list(yaml.safe_load_all(fh))
except Exception as e:
    print(str(e))
    sys.exit(1)
sys.exit(0)
PY
}

# Read the collected file list without a pipe so $fail survives.
while IFS= read -r f; do
  [ -n "$f" ] || continue
  echo "== $f"

  # 1. YAML well-formedness
  if [ -n "$YAML_CHECK" ]; then
    out="$(check_yaml "$f" 2>&1)"; rc=$?
    case "$rc" in
      0) echo "  ok    valid YAML" ;;
      3) echo "  warn  pyyaml not installed; skipped YAML parse" ;;
      *) echo "  ERROR invalid YAML: $out"; fail=1 ;;
    esac
  else
    echo "  warn  python3 not found; skipped YAML parse"
  fi

  # 2. Unrendered placeholders
  if grep -qE '__[A-Z0-9_]+__' "$f"; then
    echo "  ERROR unrendered placeholder(s): $(grep -oE '__[A-Z0-9_]+__' "$f" | sort -u | tr '\n' ' ')"
    fail=1
  else
    echo "  ok    no unrendered placeholders"
  fi

  # 3. template references resolve (skip cross-repo @resource references)
  dir="$(dirname "$f")"
  refs="$(grep -E '^[[:space:]]*-?[[:space:]]*template:[[:space:]]*[^ #]' "$f" | sed -E 's/^[[:space:]]*-?[[:space:]]*template:[[:space:]]*//' | sed -E 's/[[:space:]]*#.*$//' | sed -E 's/@.*$//' || true)"
  if [ -n "$refs" ]; then
    while IFS= read -r r; do
      [ -n "$r" ] || continue
      case "$r" in
        *@*) continue ;;
        /*)  target="$r" ;;
        *)   target="$dir/$r" ;;
      esac
      if [ -f "$target" ]; then
        echo "  ok    template exists: $r"
      else
        echo "  ERROR template not found: $r (looked at $target)"
        fail=1
      fi
    done <<EOF
$refs
EOF
  fi

  # 4. basic ADO structure
  if grep -qE '^(trigger|pr|schedules|resources|extends|stages|jobs|steps):' "$f"; then
    echo "  ok    has pipeline structure"
  else
    echo "  warn  no top-level trigger/stages/jobs/steps found (is this a pipeline?)"
  fi
done < "$tmp_list"

echo
if [ "$fail" -ne 0 ]; then
  echo "FAIL: one or more pipeline files have errors (see above)."
  echo "Note: for full server-side validation, run the pipeline's 'Validate' preview in your"
  echo "Azure DevOps project (Pipelines editor > ... > Validate), or 'az pipelines run --name <p>'."
  exit 1
fi
echo "OK: offline pipeline checks passed."
echo "Note: run a server-side validation in your Azure DevOps project for full schema/task checks."
