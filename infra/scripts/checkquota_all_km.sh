#!/bin/bash

# Parameters
IFS=',' read -r -a MODEL_NAMES <<< "$1"
USER_REGION="$2"

if [ ${#MODEL_NAMES[@]} -lt 1 ]; then
    echo "❌ ERROR: At least one model must be provided as an argument."
    exit 1
fi

echo "🔄 Using Models: ${MODEL_NAMES[*]}"

echo "🔄 Fetching available Azure subscriptions..."
SUBSCRIPTIONS=$(az account list --query "[?state=='Enabled'].{Name:name, ID:id}" --output tsv)
SUB_COUNT=$(echo "$SUBSCRIPTIONS" | wc -l)

if [ "$SUB_COUNT" -eq 1 ]; then
    AZURE_SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | awk '{print $2}')
    echo "✅ Using the only available subscription: $AZURE_SUBSCRIPTION_ID"
else
    echo "Multiple subscriptions found:"
    echo "$SUBSCRIPTIONS" | awk '{print NR")", $1, "-", $2}'

    while true; do
        echo "Enter the number of the subscription to use:"
        read SUB_INDEX

        if [[ "$SUB_INDEX" =~ ^[0-9]+$ ]] && [ "$SUB_INDEX" -ge 1 ] && [ "$SUB_INDEX" -le "$SUB_COUNT" ]; then
            AZURE_SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | awk -v idx="$SUB_INDEX" 'NR==idx {print $2}')
            echo "✅ Selected Subscription: $AZURE_SUBSCRIPTION_ID"
            break
        else
            echo "❌ Invalid selection. Please enter a valid number from the list."
        fi
    done
fi

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
echo "🎯 Active Subscription: $(az account show --query '[name, id]' --output table)"

# List of regions to check
DEFAULT_REGIONS=("eastus" "uksouth" "eastus2" "northcentralus" "swedencentral" "westus" "westus2" "southcentralus" "canadacentral")

if [ -n "$USER_REGION" ]; then
    REGIONS=("$USER_REGION" "${DEFAULT_REGIONS[@]}")
else
    REGIONS=("${DEFAULT_REGIONS[@]}")
fi

echo "✅ Retrieved Azure regions. Checking availability..."

# Print table header
echo "-----------------------------------------------------------------------"
printf "| %-15s | %-35s | %-10s | %-10s | %-10s |\n" "Region" "Model" "Used" "Limit" "Available"
echo "-----------------------------------------------------------------------"

for REGION in "${REGIONS[@]}"; do
    echo "🔍 Checking region: $REGION"

    # Fetch quota information
    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)

    echo "🔍 Quota Info: $QUOTA_INFO"

    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION."
        continue
    fi

     for index in "${!MODEL_NAMES[@]}"; do
        MODEL_NAME="${MODEL_NAMES[$index]}"
        REQUIRED_CAPACITY="${CAPACITIES[$index]}"
        
        echo "🔍 Checking model: $MODEL_NAME with required capacity: $REQUIRED_CAPACITY"

        # Extract model quota information
        MODEL_INFO=$(echo "$QUOTA_INFO" | awk -v model="\"value\": \"OpenAI.Standard.$MODEL_NAME\"" '
            BEGIN { RS="},"; FS="," }
            $0 ~ model { print $0 }
        ')

        if [ -z "$MODEL_INFO" ]; then
            echo "⚠️ WARNING: No quota information found for model: OpenAI.Standard.$MODEL_NAME in $REGION. Skipping."
            BOTH_MODELS_AVAILABLE=false
            break  # If any model is not available, no need to check further for this region
        fi

        CURRENT_VALUE=$(echo "$MODEL_INFO" | awk -F': ' '/"currentValue"/ {print $2}' | tr -d ',' | tr -d ' ')
        LIMIT=$(echo "$MODEL_INFO" | awk -F': ' '/"limit"/ {print $2}' | tr -d ',' | tr -d ' ')

        CURRENT_VALUE=${CURRENT_VALUE:-0}
        LIMIT=${LIMIT:-0}

        CURRENT_VALUE=$(echo "$CURRENT_VALUE" | cut -d'.' -f1)
        LIMIT=$(echo "$LIMIT" | cut -d'.' -f1)

        AVAILABLE=$((LIMIT - CURRENT_VALUE))

        echo "✅ Model: OpenAI.Standard.$MODEL_NAME | Used: $CURRENT_VALUE | Limit: $LIMIT | Available: $AVAILABLE"

        printf "| %-15s | %-35s | %-10s | %-10s | %-10s |\n" "$REGION" "$MODEL_KEY" "$CURRENT_VALUE" "$LIMIT" "$AVAILABLE"
    done
done

echo "-----------------------------------------------------------------------"
