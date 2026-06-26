#!/bin/bash

# Function to trim leading and trailing whitespace
trim() {
    local var="$*"
    var="${var#"${var%%[![:space:]]*}"}"
    var="${var%"${var##*[![:space:]]}"}"
    printf '%s' "$var"
}

# Get requested regions from the environment variable.
REGIONS=()
if [[ -n "${AZURE_REGIONS:-}" ]]; then
    IFS=',' read -ra REQUESTED_REGIONS <<< "$AZURE_REGIONS"
    for req_region in "${REQUESTED_REGIONS[@]}"; do
        req_region=$(trim "$req_region")
        if [[ -n "$req_region" ]]; then
            REGIONS+=("$req_region")
        fi
    done
fi
if [[ ${#REGIONS[@]} -eq 0 ]]; then
    echo "❌ ERROR: No regions found in AZURE_REGIONS. Please set AZURE_REGIONS."
    exit 1
fi

SUBSCRIPTION_ID=$(trim "${AZURE_SUBSCRIPTION_ID}")
GPT_MIN_CAPACITY="${GPT_MIN_CAPACITY:-50}"
TEXT_EMBEDDING_MIN_CAPACITY="${TEXT_EMBEDDING_MIN_CAPACITY:-10}"

# Azure CLI is expected to be already authenticated via OIDC (federated credentials)
echo "Verifying Azure CLI authentication..."
if ! az account show > /dev/null 2>&1; then
   echo "❌ Error: Not logged in to Azure CLI. Please run 'az login' and try again."
   exit 1
fi
echo "✅ Azure CLI is authenticated."

echo "🔄 Validating required environment variables..."
if [[ -z "$SUBSCRIPTION_ID" ]]; then
    echo "❌ ERROR: Missing required environment variable AZURE_SUBSCRIPTION_ID."
    exit 1
fi

echo "🔄 Setting Azure subscription..."
if ! az account set --subscription "$SUBSCRIPTION_ID"; then
    echo "❌ ERROR: Invalid subscription ID or insufficient permissions."
    exit 1
fi
echo "✅ Azure subscription set successfully."

# Define models and their minimum required capacities
declare -A MIN_CAPACITY=(
    ["OpenAI.GlobalStandard.gpt-4o-mini"]=$GPT_MIN_CAPACITY #km generic
    ["OpenAI.GlobalStandard.text-embedding-3-small"]=$TEXT_EMBEDDING_MIN_CAPACITY #km generic
)

echo "----------------------------------------"
echo "📋 Required quota minimums for this deployment:"
echo "   - OpenAI.GlobalStandard.gpt-4o-mini: ${GPT_MIN_CAPACITY}"
echo "   - OpenAI.GlobalStandard.text-embedding-3-small: ${TEXT_EMBEDDING_MIN_CAPACITY}"

# Iterate through ALL regions and select the one with the highest available GPT quota.
VALID_REGION=""
VALID_REGION_AVAILABLE_CAPACITY=-1
for REGION in "${REGIONS[@]}"; do
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    USAGE_COUNT=$(az cognitiveservices usage list --location "$REGION" --query 'length(@)' -o tsv 2>/dev/null || echo "0")
    if [[ -z "$USAGE_COUNT" || "$USAGE_COUNT" == "0" ]]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    INSUFFICIENT_QUOTA=false
    REGION_GPT_AVAILABLE=""
    for MODEL in "${!MIN_CAPACITY[@]}"; do
        CURRENT_VALUE=$(az cognitiveservices usage list --location "$REGION" --query "[?name.value=='$MODEL'].currentValue | [0]" -o tsv 2>/dev/null)
        LIMIT=$(az cognitiveservices usage list --location "$REGION" --query "[?name.value=='$MODEL'].limit | [0]" -o tsv 2>/dev/null)

        if [[ -z "$CURRENT_VALUE" || -z "$LIMIT" || "$CURRENT_VALUE" == "None" || "$LIMIT" == "None" ]]; then
            echo "⚠️ WARNING: No quota information found for model: $MODEL in $REGION."
            INSUFFICIENT_QUOTA=true
            break
        fi

        CURRENT_VALUE=${CURRENT_VALUE%.*}
        LIMIT=${LIMIT%.*}
        AVAILABLE=$((LIMIT - CURRENT_VALUE))

        echo "✅ Model: $MODEL | Used: $CURRENT_VALUE | Limit: $LIMIT | Available: $AVAILABLE"

        if [[ "$MODEL" == "OpenAI.GlobalStandard.gpt-4o-mini" ]]; then
            REGION_GPT_AVAILABLE="$AVAILABLE"
        fi

        if [ "$AVAILABLE" -lt "${MIN_CAPACITY[$MODEL]}" ]; then
            echo "❌ ERROR: $MODEL in $REGION has insufficient quota."
            echo "   Required: ${MIN_CAPACITY[$MODEL]}, Available: $AVAILABLE"
            INSUFFICIENT_QUOTA=true
            break
        fi
    done

    if [ "$INSUFFICIENT_QUOTA" = false ]; then
        echo "  ✅ $REGION has sufficient quota."
        if [[ -n "$REGION_GPT_AVAILABLE" && "$REGION_GPT_AVAILABLE" -gt "$VALID_REGION_AVAILABLE_CAPACITY" ]]; then
            VALID_REGION="$REGION"
            VALID_REGION_AVAILABLE_CAPACITY="$REGION_GPT_AVAILABLE"
        fi
    fi
done

if [ -z "$VALID_REGION" ]; then
    echo "❌ No region with sufficient quota found. Blocking deployment."
    echo "QUOTA_FAILED=true" >> "$GITHUB_ENV"
    exit 0
else
    echo "---------------------------------------------------------"
    echo "✅ Final Region (highest available quota): $VALID_REGION"
    echo "---------------------------------------------------------"
    echo "VALID_REGION=$VALID_REGION" >> "$GITHUB_ENV"
    exit 0
fi
