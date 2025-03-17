#!/bin/bash

# Parameters
IFS=',' read -r -a MODEL_CAPACITY_PAIRS <<< "$1"  # Split the comma-separated model and capacity pairs into an array
USER_REGION="$2"

if [ ${#MODEL_CAPACITY_PAIRS[@]} -lt 1 ]; then
    echo "❌ ERROR: At least one model and capacity pairs must be provided as arguments."
    exit 1
fi

# Extract model names and required capacities into arrays
declare -a MODEL_NAMES
declare -a CAPACITIES

for PAIR in "${MODEL_CAPACITY_PAIRS[@]}"; do
    MODEL_NAME=$(echo "$PAIR" | cut -d':' -f1)
    CAPACITY=$(echo "$PAIR" | cut -d':' -f2)

    if [ -z "$MODEL_NAME" ] || [ -z "$CAPACITY" ]; then
        echo "❌ ERROR: Invalid model and capacity pair '$PAIR'. Both model and capacity must be specified."
        exit 1
    fi

    MODEL_NAMES+=("$MODEL_NAME")
    CAPACITIES+=("$CAPACITY")
done

echo "🔄 Using Models: ${MODEL_NAMES[*]} with respective Capacities: ${CAPACITIES[*]}"

echo "🔄 Fetching available Azure subscriptions..."
SUBSCRIPTIONS=$(az account list --query "[?state=='Enabled'].{Name:name, ID:id}" --output tsv)
SUB_COUNT=$(echo "$SUBSCRIPTIONS" | wc -l)

if [ "$SUB_COUNT" -eq 1 ]; then
    # If only one subscription, automatically select it
    AZURE_SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | awk '{print $2}')
    echo "✅ Using the only available subscription: $AZURE_SUBSCRIPTION_ID"
else
    # If multiple subscriptions exist, prompt the user to choose one
    echo "Multiple subscriptions found:"
    echo "$SUBSCRIPTIONS" | awk '{print NR")", $1, "-", $2}'

    while true; do
        echo "Enter the number of the subscription to use:"
        read SUB_INDEX

        # Validate user input
        if [[ "$SUB_INDEX" =~ ^[0-9]+$ ]] && [ "$SUB_INDEX" -ge 1 ] && [ "$SUB_INDEX" -le "$SUB_COUNT" ]; then
            AZURE_SUBSCRIPTION_ID=$(echo "$SUBSCRIPTIONS" | awk -v idx="$SUB_INDEX" 'NR==idx {print $2}')
            echo "✅ Selected Subscription: $AZURE_SUBSCRIPTION_ID"
            break
        else
            echo "❌ Invalid selection. Please enter a valid number from the list."
        fi
    done
fi

# Set the selected subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
echo "🎯 Active Subscription: $(az account show --query '[name, id]' --output table)"

# List of regions to check
DEFAULT_REGIONS=("eastus" "uksouth" "eastus2" "northcentralus" "swedencentral" "westus" "westus2" "southcentralus" "canadacentral")

# Prioritize user-provided region if given
if [ -n "$USER_REGION" ]; then
    # Ensure the user-provided region is checked first
    REGIONS=("$USER_REGION" "${DEFAULT_REGIONS[@]}")
else
    REGIONS=("${DEFAULT_REGIONS[@]}")
fi

echo "✅ Retrieved Azure regions. Checking availability..."

VALID_REGIONS=()
for REGION in "${REGIONS[@]}"; do
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    # Fetch quota information for the region
    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)
    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    # Initialize a flag to track if both models have sufficient quota in the region
    BOTH_MODELS_AVAILABLE=true

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

        # Check if quota is sufficient
        if [ "$AVAILABLE" -lt "$REQUIRED_CAPACITY" ]; then
            echo "❌ ERROR: 'OpenAI.Standard.$MODEL_NAME' in $REGION has insufficient quota. Required: $REQUIRED_CAPACITY, Available: $AVAILABLE"
            BOTH_MODELS_AVAILABLE=false
            break
        fi
    done

    # If both models have sufficient quota, add region to valid regions
    if [ "$BOTH_MODELS_AVAILABLE" = true ]; then
        echo "✅ All models have sufficient quota in $REGION."
        VALID_REGIONS+=("$REGION")
    fi
done

# Determine final result
if [ ${#VALID_REGIONS[@]} -eq 0 ]; then
    echo "----------------------------------------"
    echo "❌ No region with sufficient quota found for all models. Blocking deployment."
    exit 0
else
    echo "----------------------------------------"
    echo "✅ Suggested Regions: ${VALID_REGIONS[*]}"
    exit 0
fi
