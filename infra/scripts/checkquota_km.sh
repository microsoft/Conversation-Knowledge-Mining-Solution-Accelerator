#!/bin/bash

# List of Azure regions to check for quota (update as needed)
IFS=', ' read -ra REGIONS <<< "$AZURE_REGIONS"

GPT_MIN_CAPACITY="${GPT_MIN_CAPACITY}"
TEXT_EMBEDDING_MIN_CAPACITY="${TEXT_EMBEDDING_MIN_CAPACITY}"
AZURE_CLIENT_ID="${AZURE_CLIENT_ID}"
AZURE_TENANT_ID="${AZURE_TENANT_ID}"
AZURE_CLIENT_SECRET="${AZURE_CLIENT_SECRET}"

# 🔄 Fetch available subscriptions
echo "🔍 Fetching available Azure subscriptions..."
SUBSCRIPTIONS=$(az account list --query "[].{id:id, name:name}" --output tsv)

# 🔹 Count available subscriptions
SUBSCRIPTION_COUNT=$(echo "$SUBSCRIPTIONS" | wc -l)

if [ "$SUBSCRIPTION_COUNT" -eq 0 ]; then
    echo "❌ No active Azure subscriptions found. Please check your account."
    exit 1
elif [ "$SUBSCRIPTION_COUNT" -eq 1 ]; then
    # Auto-select if only one subscription exists
    SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | awk '{print $1}')
    echo "✅ Using the only available subscription: $SUBSCRIPTION_ID"
else
    # Prompt user to select a subscription
    echo "📋 Multiple subscriptions found. Please select one:"
    echo "$SUBSCRIPTIONS" | nl -w2 -s'. '

    read -p "Enter the number of the subscription to use: " SUB_CHOICE
    SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | sed -n "${SUB_CHOICE}p" | awk '{print $1}')

    if [ -z "$SUBSCRIPTION_ID" ]; then
        echo "❌ Invalid selection. Exiting."
        exit 1
    fi
    echo "✅ Selected Subscription: $SUBSCRIPTION_ID"
fi

# 🔄 Set the chosen subscription
echo "🔄 Setting Azure subscription..."
if ! az account set --subscription "$SUBSCRIPTION_ID"; then
    echo "❌ ERROR: Invalid subscription ID or insufficient permissions."
    exit 1
fi
echo "✅ Azure subscription set successfully."

# 🔄 Fetch the correct Tenant ID
AZURE_TENANT_ID=$(az account show --query tenantId --output tsv)
echo "✅ Using Tenant ID: $AZURE_TENANT_ID"

# 🔐 Authenticate using Service Principal
echo "🔐 Logging in with Service Principal..."
if ! az login --service-principal -u "$AZURE_CLIENT_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID"; then
   echo "❌ Error: Failed to login using Service Principal."
   exit 1
fi

echo "🔄 Validating required environment variables..."
if [[ -z "$SUBSCRIPTION_ID" || -z "$GPT_MIN_CAPACITY" || -z "$TEXT_EMBEDDING_MIN_CAPACITY" || -z "$REGIONS" ]]; then
    echo "❌ ERROR: Missing required environment variables."
    exit 1
fi

# Define models and their minimum required capacities
declare -A MIN_CAPACITY=(
    ["OpenAI.Standard.gpt-4o-mini"]=$GPT_MIN_CAPACITY
    ["OpenAI.Standard.text-embedding-ada-002"]=$TEXT_EMBEDDING_MIN_CAPACITY
)

VALID_REGION=""
for REGION in "${REGIONS[@]}"; do
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)
    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    INSUFFICIENT_QUOTA=false
    for MODEL in "${!MIN_CAPACITY[@]}"; do
        MODEL_INFO=$(echo "$QUOTA_INFO" | awk -v model="\"value\": \"$MODEL\"" '
            BEGIN { RS="},"; FS="," }
            $0 ~ model { print $0 }
        ')

        if [ -z "$MODEL_INFO" ]; then
            echo "⚠️ WARNING: No quota information found for model: $MODEL in $REGION. Skipping."
            continue
        fi

        CURRENT_VALUE=$(echo "$MODEL_INFO" | awk -F': ' '/"currentValue"/ {print $2}' | tr -d ',' | tr -d ' ')
        LIMIT=$(echo "$MODEL_INFO" | awk -F': ' '/"limit"/ {print $2}' | tr -d ',' | tr -d ' ')

        CURRENT_VALUE=${CURRENT_VALUE:-0}
        LIMIT=${LIMIT:-0}

        CURRENT_VALUE=$(echo "$CURRENT_VALUE" | cut -d'.' -f1)
        LIMIT=$(echo "$LIMIT" | cut -d'.' -f1)

        AVAILABLE=$((LIMIT - CURRENT_VALUE))

        echo "✅ Model: $MODEL | Used: $CURRENT_VALUE | Limit: $LIMIT | Available: $AVAILABLE"

        if [ "$AVAILABLE" -lt "${MIN_CAPACITY[$MODEL]}" ]; then
            echo "❌ ERROR: $MODEL in $REGION has insufficient quota."
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
    echo "QUOTA_FAILED=true" >> "$GITHUB_ENV"
    exit 0
else
    echo "✅ Final Region: $VALID_REGION"
    echo "VALID_REGION=$VALID_REGION" >> "$GITHUB_ENV"
    exit 0
fi
