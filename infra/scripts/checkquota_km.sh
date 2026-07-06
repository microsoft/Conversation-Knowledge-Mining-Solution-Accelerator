#!/bin/bash

set -u

# List of Azure regions to check for quota (update as needed)
IFS=', ' read -ra REGIONS <<< "$AZURE_REGIONS"

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"
GPT_MIN_CAPACITY="${GPT_MIN_CAPACITY}"
TEXT_EMBEDDING_MIN_CAPACITY="${TEXT_EMBEDDING_MIN_CAPACITY}"

# Safety buffer multiplier: only select a region if available quota is at least
# QUOTA_SAFETY_MULTIPLIER times the required minimum. This guards against race
# conditions where concurrent deployments consume quota between check and deploy.
# Default is 2 (i.e. requires 2x the minimum to be available).
QUOTA_SAFETY_MULTIPLIER="${QUOTA_SAFETY_MULTIPLIER:-2}"

# Azure CLI is expected to be already authenticated via OIDC (federated credentials)
echo "Verifying Azure CLI authentication..."
if ! az account show > /dev/null 2>&1; then
   echo "❌ Error: Not logged in to Azure CLI. Please run 'az login' and try again."
   exit 1
fi

echo "🔄 Validating required environment variables..."
if [[ -z "$SUBSCRIPTION_ID" || -z "$GPT_MIN_CAPACITY" || -z "$TEXT_EMBEDDING_MIN_CAPACITY" || -z "$REGIONS" ]]; then
    echo "❌ ERROR: Missing required environment variables."
    exit 1
fi

echo "🔄 Setting Azure subscription..."
if ! az account set --subscription "$SUBSCRIPTION_ID"; then
    echo "❌ ERROR: Invalid subscription ID or insufficient permissions."
    exit 1
fi
echo "✅ Azure subscription set successfully."

if ! command -v jq >/dev/null 2>&1; then
    echo "❌ ERROR: jq is required for quota parsing but was not found."
    exit 1
fi

# Define models and their minimum required capacities
declare -A MIN_CAPACITY=(
    ["OpenAI.GlobalStandard.gpt-5.4-mini"]=$GPT_MIN_CAPACITY #km generic
    ["OpenAI.GlobalStandard.text-embedding-3-small"]=$TEXT_EMBEDDING_MIN_CAPACITY #km generic
)

VALID_REGION=""
for REGION in "${REGIONS[@]}"; do
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json 2>/dev/null || true)
    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    INSUFFICIENT_QUOTA=false
    for MODEL in "${!MIN_CAPACITY[@]}"; do
        MODEL_INFO=$(echo "$QUOTA_INFO" | jq -r --arg model "$MODEL" '
            [.[]
              | select(.name.value == $model)
              | {
                  currentValue: ((.currentValue // 0) | floor),
                  limit: ((.limit // 0) | floor)
                }
            ] | first // empty
        ')

        if [ -z "$MODEL_INFO" ] || [ "$MODEL_INFO" = "null" ]; then
            echo "⚠️ WARNING: No quota information found for model: $MODEL in $REGION. Skipping."
            INSUFFICIENT_QUOTA=true
            continue
        fi

        CURRENT_VALUE=$(echo "$MODEL_INFO" | jq -r '.currentValue // 0')
        LIMIT=$(echo "$MODEL_INFO" | jq -r '.limit // 0')

        AVAILABLE=$((LIMIT - CURRENT_VALUE))
        REQUIRED_WITH_BUFFER=$(( ${MIN_CAPACITY[$MODEL]} * QUOTA_SAFETY_MULTIPLIER ))

        echo "✅ Model: $MODEL | Used: $CURRENT_VALUE | Limit: $LIMIT | Available: $AVAILABLE | Required (with ${QUOTA_SAFETY_MULTIPLIER}x buffer): $REQUIRED_WITH_BUFFER"

        if [ "$AVAILABLE" -lt "$REQUIRED_WITH_BUFFER" ]; then
            echo "❌ ERROR: $MODEL in $REGION has insufficient quota (available: $AVAILABLE, need $REQUIRED_WITH_BUFFER with safety buffer)."
            INSUFFICIENT_QUOTA=true
            break
        fi
    done

    if [ "$INSUFFICIENT_QUOTA" = false ]; then
        VALID_REGION="$REGION"
        break
    fi

done

if [ -z "$VALID_REGION" ]; then
    echo "❌ No region with sufficient quota found. Blocking deployment."
    if [[ -n "${GITHUB_ENV:-}" ]]; then
        echo "QUOTA_FAILED=true" >> "$GITHUB_ENV"
    fi
    exit 0
else
    echo "✅ Final Region: $VALID_REGION"
    if [[ -n "${GITHUB_ENV:-}" ]]; then
        echo "QUOTA_FAILED=false" >> "$GITHUB_ENV"
        echo "VALID_REGION=$VALID_REGION" >> "$GITHUB_ENV"
    fi
    exit 0
fi
