#!/bin/bash

# Parameters
MODEL_NAME="$1"
CAPACITY="$2"

if [ -z "$MODEL_NAME" ] || [ -z "$CAPACITY" ]; then
    echo "❌ ERROR: Model name and capacity must be provided as arguments."
    exit 1
fi

echo "🔄 Using Model: $MODEL_NAME with Minimum Capacity: $CAPACITY"

# Authenticate using Managed Identity
echo "Authentication using Managed Identity..."
if ! az login --use-device-code; then
   echo "❌ Error: Failed to login using Managed Identity."
   exit 1
fi

# Fetch the default subscription ID dynamically
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

# Set Azure subscription
echo "🔄 Setting Azure subscription..."
if ! az account set --subscription "$SUBSCRIPTION_ID"; then
    echo "❌ ERROR: Invalid subscription ID or insufficient permissions."
    exit 1
fi
echo "✅ Azure subscription set successfully."

# List of regions to check
REGIONS=("eastus" "uksouth" "eastus2" "northcentralus" "swedencentral" "westus" "westus2" "southcentralus" "canadacentral")

echo "✅ Retrieved Azure regions. Checking availability..."

VALID_REGIONS=()
for REGION in "${REGIONS[@]}"; do
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    # Fetch quota information
    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)
    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    # Extract model quota using awk
    MODEL_INFO=$(echo "$QUOTA_INFO" | awk -v model="\"value\": \"OpenAI.Standard.$MODEL_NAME\"" '
        BEGIN { RS="},"; FS="," }
        $0 ~ model { print $0 }
    ')

    if [ -z "$MODEL_INFO" ]; then
        echo "⚠️ WARNING: No quota information found for model: OpenAI.Standard.$MODEL_NAME in $REGION. Skipping."
        continue
    fi

    CURRENT_VALUE=$(echo "$MODEL_INFO" | awk -F': ' '/"currentValue"/ {print $2}' | tr -d ',' | tr -d ' ')
    LIMIT=$(echo "$MODEL_INFO" | awk -F': ' '/"limit"/ {print $2}' | tr -d ',' | tr -d ' ')

    CURRENT_VALUE=${CURRENT_VALUE:-0}
    LIMIT=${LIMIT:-0}

    CURRENT_VALUE=$(echo "$CURRENT_VALUE" | cut -d'.' -f1)
    LIMIT=$(echo "$LIMIT" | cut -d'.' -f1)

    AVAILABLE=$((LIMIT - CURRENT_VALUE))

    echo "✅ Model: OpenAI.Standard.$MODEL_NAME | Used: $CURRENT_VALUE | Limit: $LIMIT | Available: $AVAILABLE"

    # Check if quota is sufficient
    if [ "$AVAILABLE" -ge "$CAPACITY" ]; then
        echo "✅ Model 'OpenAI.Standard.$MODEL_NAME' has enough quota in $REGION."
        VALID_REGIONS+=("$REGION")
    else
        echo "❌ ERROR: 'OpenAI.Standard.$MODEL_NAME' in $REGION has insufficient quota. Required: $CAPACITY, Available: $AVAILABLE"
    fi
done

# Determine final result
if [ ${#VALID_REGIONS[@]} -eq 0 ]; then
    echo "❌ No region with sufficient quota found. Blocking deployment."
    exit 0
else
    echo "✅ Suggested Regions: ${VALID_REGIONS[*]}"
    exit 0
fi
