#!/bin/bash

# Parameters
IFS=',' read -r -a MODEL_CAPACITY_PAIRS <<< "$1"  # Split the comma-separated model and capacity pairs into an array
USER_REGION="$2"

if [ ${#MODEL_CAPACITY_PAIRS[@]} -lt 1 ]; then
    echo "❌ ERROR: At least one model and capacity pair must be provided."
    exit 1
fi

# Extract model names and required capacities into arrays
declare -a MODEL_NAMES
declare -a CAPACITIES

for PAIR in "${MODEL_CAPACITY_PAIRS[@]}"; do
    MODEL_NAME=$(echo "$PAIR" | cut -d':' -f1)
    CAPACITY=$(echo "$PAIR" | cut -d':' -f2)

    if [ -z "$MODEL_NAME" ] || [ -z "$CAPACITY" ]; then
        echo "❌ ERROR: Invalid model and capacity pair '$PAIR'."
        exit 1
    fi

    MODEL_NAMES+=("$MODEL_NAME")
    CAPACITIES+=("$CAPACITY")
done

echo "🔄 Using Models: ${MODEL_NAMES[*]} with Capacities: ${CAPACITIES[*]}"

# Fetch available Azure subscriptions
echo "🔄 Fetching Azure subscriptions..."
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
            echo "❌ Invalid selection. Please enter a valid number."
        fi
    done
fi

# Set the selected subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
echo "🎯 Active Subscription: $(az account show --query '[name, id]' --output table)"

# List of regions
DEFAULT_REGIONS=("eastus" "uksouth" "eastus2" "northcentralus" "swedencentral" "westus" "westus2" "southcentralus" "canadacentral")
if [ -n "$USER_REGION" ]; then
    REGIONS=("$USER_REGION" "${DEFAULT_REGIONS[@]}")
else
    REGIONS=("${DEFAULT_REGIONS[@]}")
fi

echo "✅ Checking quota availability in regions..."

# Table Header
echo "-------------------------------------------------------------------------------------------------"
printf "| %-15s | %-40s | %-10s | %-10s | %-10s |\n" "Region" "Model" "Used" "Limit" "Available"
echo "-------------------------------------------------------------------------------------------------"

for REGION in "${REGIONS[@]}"; do
    echo "🔍 Checking region: $REGION"
    
    # Fetch quota information
    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)

    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    for index in "${!MODEL_NAMES[@]}"; do
        MODEL_NAME="${MODEL_NAMES[$index]}"
        REQUIRED_CAPACITY="${CAPACITIES[$index]}"

        # Extract quota information from JSON
        MODEL_INFO=$(echo "$QUOTA_INFO" | jq -c ".[] | select(.name.value | contains(\"$MODEL_NAME\"))")

        if [ -z "$MODEL_INFO" ]; then
            printf "| %-15s | %-40s | %-10s | %-10s | %-10s |\n" "$REGION" "$MODEL_NAME" "N/A" "N/A" "N/A"
            continue
        fi

        CURRENT_VALUE=$(echo "$MODEL_INFO" | jq -r '.currentValue // "0"')
        LIMIT=$(echo "$MODEL_INFO" | jq -r '.limit // "0"')

        # Convert floating point to integer
        CURRENT_VALUE=${CURRENT_VALUE%%.*}
        LIMIT=${LIMIT%%.*}

        AVAILABLE=$((LIMIT - CURRENT_VALUE))

        printf "| %-15s | %-40s | %-10s | %-10s | %-10s |\n" "$REGION" "$MODEL_NAME" "$CURRENT_VALUE" "$LIMIT" "$AVAILABLE"
    done
done

echo "-------------------------------------------------------------------------------------------------"
