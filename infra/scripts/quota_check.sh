#!/bin/bash

# Pre-defined list of models to check
MODEL_NAMES=("gpt-4o" "gpt-4o-mini" "text-embedding-ada-002" "gpt-3.5-turbo" "gpt-4")

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
echo "🎯 Active Subscription: $(az account show --query '[name, id]' --output tsv)"

echo "🔄 Fetching Azure regions..."
REGIONS=$(az account list-locations --query "[].name" --output tsv)

echo "✅ Retrieved Azure regions. Checking availability..."

# Array to store table data
declare -a TABLE_ROWS
INDEX=1

# Loop through all regions
for REGION in $REGIONS; do
    REGION=$(echo "$REGION" | xargs)
    echo "----------------------------------------"
    echo "🔍 Checking region: $REGION"

    QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json)

    if [ -z "$QUOTA_INFO" ]; then
        echo "⚠️ WARNING: Failed to retrieve quota for region $REGION. Skipping."
        continue
    fi

    for MODEL_NAME in "${MODEL_NAMES[@]}"; do
        for MODEL_PREFIX in "OpenAI.Standard" "OpenAI.GlobalStandard"; do
            FULL_MODEL_NAME="${MODEL_PREFIX}.$MODEL_NAME"

            MODEL_INFO=$(echo "$QUOTA_INFO" | awk -v model="\"value\": \"$FULL_MODEL_NAME\"" '
                BEGIN { RS="},"; FS="," }
                $0 ~ model { print $0 }
            ')

            if [ -z "$MODEL_INFO" ]; then
                continue
            fi

            CURRENT_VALUE=$(echo "$MODEL_INFO" | awk -F': ' '/"currentValue"/ {print $2}' | tr -d ',' | tr -d ' ')
            LIMIT=$(echo "$MODEL_INFO" | awk -F': ' '/"limit"/ {print $2}' | tr -d ',' | tr -d ' ')

            CURRENT_VALUE=${CURRENT_VALUE:-0}
            LIMIT=${LIMIT:-0}

            CURRENT_VALUE=$(echo "$CURRENT_VALUE" | cut -d'.' -f1)
            LIMIT=$(echo "$LIMIT" | cut -d'.' -f1)

            AVAILABLE=$((LIMIT - CURRENT_VALUE))

            TABLE_ROWS+=("$(printf "| %-4s | %-20s | %-49s | %-9s | %-9s | %-9s |" "$INDEX" "$REGION" "$FULL_MODEL_NAME" "$LIMIT" "$CURRENT_VALUE" "$AVAILABLE")")
            INDEX=$((INDEX + 1))
        done
    done
    echo "----------------------------------------"
done

# Print table header
echo "----------------------------------------------------------------------------------------------------------"
printf "| %-4s | %-20s | %-49s | %-9s | %-9s | %-9s |\n" "No." "Region" "Model Name" "Limit" "Used" "Available"
echo "----------------------------------------------------------------------------------------------------------"

for ROW in "${TABLE_ROWS[@]}"; do
    echo "$ROW"
done

echo "----------------------------------------------------------------------------------------------------------"
echo "✅ Script completed."