#!/bin/bash

set -e

get_azd_env_value_or_default() {
    local key="$1"
    local default="$2"
    local required="${3:-false}"

    value=$(azd env get-value "$key" 2>/dev/null || echo "")

    if [ -z "$value" ]; then
        if [ "$required" = true ]; then
            echo "❌ Required environment key '$key' not found." >&2
            exit 1
        else
            value="$default"
        fi
    fi

    echo "$value"
}

# Required env variables
AZURE_SUBSCRIPTION_ID=$(get_azd_env_value_or_default "AZURE_SUBSCRIPTION_ID" "" true)
SOLUTION_NAME=$(get_azd_env_value_or_default "SOLUTION_NAME" "" true)
WEB_APP_IDENTITY_PRINCIPAL_ID=$(get_azd_env_value_or_default "FRONTEND_MANAGED_IDENTITY_PRINCIPAL_ID" "" true)
API_APP_IDENTITY_PRINCIPAL_ID=$(get_azd_env_value_or_default "BACKEND_MANAGED_IDENTITY_PRINCIPAL_ID" "" true)
AZURE_RESOURCE_GROUP=$(get_azd_env_value_or_default "AZURE_RESOURCE_GROUP" "" true)
AZURE_ENV_IMAGETAG=$(get_azd_env_value_or_default "AZURE_ENV_IMAGETAG" "latest" false)
WEB_APP_NAME=$(get_azd_env_value_or_default "FRONTEND_APP_NAME" "" true)
API_APP_NAME=$(get_azd_env_value_or_default "BACKEND_APP_NAME" "" true)

echo "Using the following parameters:"
echo "AZURE_SUBSCRIPTION_ID = $AZURE_SUBSCRIPTION_ID"
echo "SOLUTION_NAME = $SOLUTION_NAME"
echo "AZURE_RESOURCE_GROUP = $AZURE_RESOURCE_GROUP"
echo "AZURE_ENV_IMAGETAG = $AZURE_ENV_IMAGETAG"
echo "WEB_APP_NAME = $WEB_APP_NAME"
echo "API_APP_NAME = $API_APP_NAME"

echo -e "\nStarting build process..."

# STEP 1: Ensure user is logged into Azure
if ! az account show > /dev/null 2>&1; then
    echo "Not logged in to Azure. Attempting az login..."
    az login
    if [[ $? -ne 0 ]]; then
        echo "Azure login failed."
        exit 1
    fi
else
    echo "Already logged in to Azure."
fi

# STEP 2: Set Azure subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
if [[ $? -ne 0 ]]; then
    echo "Failed to set Azure subscription."
    exit 1
fi

# STEP 3: Get current script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# STEP 4: Deploy container registry
TEMPLATE_FILE="$SCRIPT_DIR/../deploy_container_registry.bicep"
echo -e "\nDeploying container registry"
OUTPUTS=$(az deployment group create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --template-file "$TEMPLATE_FILE" \
    --parameters solutionName="$SOLUTION_NAME" acrPullPrincipalIds="['$WEB_APP_IDENTITY_PRINCIPAL_ID', '$API_APP_IDENTITY_PRINCIPAL_ID']" \
    --query "properties.outputs" \
    --output json)

ACR_NAME=$(echo "$OUTPUTS" | grep -o '"createdAcrName"[^}]*"value"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"value"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

echo "ACR Name: $ACR_NAME"

# STEP 5: Login to Azure Container Registry
echo "Logging into Azure Container Registry: $ACR_NAME"
az acr login -n "$ACR_NAME"
if [[ $? -ne 0 ]]; then
    echo "Failed to log in to ACR"
    exit 1
fi

# STEP 6: Resolve full paths to Dockerfiles and build contexts
WEBAPP_DOCKERFILE_PATH="$SCRIPT_DIR/../../src/App/WebApp.Dockerfile"
WEBAPP_CONTEXT_PATH="$SCRIPT_DIR/../../src/App"
APIAPP_DOCKERFILE_PATH="$SCRIPT_DIR/../../src/api/ApiApp.Dockerfile"
APIAPP_CONTEXT_PATH="$SCRIPT_DIR/../../src/api"

# STEP 7: Define function to build and push Docker images
build_and_push_image() {
    IMAGE_NAME="$1"
    BUILD_PATH="$2"
    BUILD_CONTEXT="$3"
    TAG="$4"

    IMAGE_URI="$ACR_NAME.azurecr.io/${IMAGE_NAME}:$TAG"

    echo -e "\n--- Building Docker image: $IMAGE_URI ---"
    docker build --no-cache -f "$BUILD_PATH" -t "$IMAGE_URI" "$BUILD_CONTEXT"
    if [[ $? -ne 0 ]]; then
        echo "Failed to build Docker image: $IMAGE_URI"
        exit 1
    fi

    echo "--- Pushing Docker image to ACR: $IMAGE_URI ---"
    docker push "$IMAGE_URI"
    if [[ $? -ne 0 ]]; then
        echo "Failed to push Docker image: $IMAGE_URI"
        exit 1
    fi

    echo "--- Docker image pushed successfully: $IMAGE_URI ---"
}

# STEP 8: Build and push images with provided tag
build_and_push_image "km-api" "$APIAPP_DOCKERFILE_PATH" "$APIAPP_CONTEXT_PATH" "$AZURE_ENV_IMAGETAG"
build_and_push_image "km-app" "$WEBAPP_DOCKERFILE_PATH" "$WEBAPP_CONTEXT_PATH" "$AZURE_ENV_IMAGETAG"

echo -e "\nAll Docker images built and pushed successfully with tag: $AZURE_ENV_IMAGETAG\n"

# STEP 9: Function to Update Web App settings to use Managed Identity for ACR pull
update_web_app_settings() {
    local webAppName="$1"
    local resourceGroup="$2"

    echo "Updating Web App settings for $webAppName"
    webAppConfig=$(az webapp config show --resource-group "$resourceGroup" --name "$webAppName" --query id --output tsv)
    if [[ -z "$webAppConfig" ]]; then
        echo "Error: Web App configuration not found for $webAppName"
        exit 1
    fi
    az resource update --ids "$webAppConfig" --set properties.acrUseManagedIdentityCreds=True --output none --only-show-errors
    if [[ $? -ne 0 ]]; then
        echo "Failed to update Web App settings for $webAppName"
        exit 1
    fi
    echo "Web App settings updated successfully for $webAppName"
}

# STEP 10: Update Web App settings
update_web_app_settings "$WEB_APP_NAME" "$AZURE_RESOURCE_GROUP"
update_web_app_settings "$API_APP_NAME" "$AZURE_RESOURCE_GROUP"

# STEP 11: Function to Update Web App to use new image
update_web_app_image() {
    local webAppName="$1"
    local resourceGroup="$2"
    local image="$3"

    echo -e "\nUpdating Web App $webAppName to use new image tag: $image"
    az webapp config container set --name "$webAppName" --resource-group "$resourceGroup" --container-image-name "$image" --only-show-errors
    if [[ $? -ne 0 ]]; then
        echo "Failed to update Web App $webAppName to use new image: $image"
        exit 1
    fi
    echo "Web App $webAppName updated successfully to use new image: $image"

    echo -e "\nRestarting Web App $webAppName to apply changes"
    az webapp restart --name "$webAppName" --resource-group "$resourceGroup" --output none --only-show-errors
    if [[ $? -ne 0 ]]; then
        echo "Failed to restart Web App $webAppName"
        exit 1
    fi
    echo "Web App $webAppName restarted successfully"
}

# STEP 12: Update Web Apps to use new images
update_web_app_image "$WEB_APP_NAME" "$AZURE_RESOURCE_GROUP" "$ACR_NAME.azurecr.io/km-app:$AZURE_ENV_IMAGETAG"
update_web_app_image "$API_APP_NAME" "$AZURE_RESOURCE_GROUP" "$ACR_NAME.azurecr.io/km-api:$AZURE_ENV_IMAGETAG"

echo -e "\nWeb Apps updated successfully to use new images"

echo -e "\nIt might take a few minutes for the changes to take effect.\n"
