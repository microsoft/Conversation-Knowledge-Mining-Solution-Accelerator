#!/bin/bash
# =============================================================================
# build_and_push_images.sh
#
# Post-deployment script that builds the backend (km-api) and frontend (km-app)
# container images remotely in the Azure Container Registry (ACR) that was
# provisioned during `azd up` (using `az acr build`, so no local Docker is
# required). It then updates the backend and frontend App Services to run the
# newly pushed images (pulled via managed identity).
#
# Usage:
#   bash ./infra/scripts/build_and_push_images.sh [ResourceGroupName]
#
# When no arguments are provided, values are resolved from the azd environment.
# When a resource group name is provided, values are resolved from the
# deployment outputs of that resource group.
# =============================================================================

set -e

# Get the directory where this script is located and the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
resourceGroupName=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        *)
            if [ -z "$resourceGroupName" ]; then
                resourceGroupName="$1"
            fi
            shift
            ;;
    esac
done

# Backend (km-api) and frontend (km-app) build contexts and Dockerfiles
backendContext="$REPO_ROOT/src/api"
backendDockerfile="$REPO_ROOT/src/api/ApiApp.Dockerfile"
frontendContext="$REPO_ROOT/src/App"
frontendDockerfile="$REPO_ROOT/src/App/WebApp.Dockerfile"

# Variables resolved below
acrName=""
acrLoginServer=""
backendImageName=""
backendImageTag=""
frontendImageName=""
frontendImageTag=""
backendAppName=""
frontendAppName=""

# Track original ACR public access state to restore on exit
original_acr_public_access=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
check_azd_installed() {
    command -v azd >/dev/null 2>&1
}

get_values_from_azd_env() {
    echo "Getting values from azd environment..."
    resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
    acrName=$(azd env get-value ACR_NAME 2>&1 | grep -E '^[a-zA-Z0-9]+$')
    acrLoginServer=$(azd env get-value ACR_LOGIN_SERVER 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
    backendImageName=$(azd env get-value BACKEND_CONTAINER_IMAGE_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
    backendImageTag=$(azd env get-value BACKEND_CONTAINER_IMAGE_TAG 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
    frontendImageName=$(azd env get-value FRONTEND_CONTAINER_IMAGE_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
    frontendImageTag=$(azd env get-value FRONTEND_CONTAINER_IMAGE_TAG 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
    backendAppName=$(azd env get-value API_APP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
    frontendAppName=$(azd env get-value FRONTEND_APP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')

    if [ -z "$resourceGroupName" ] || [ -z "$acrName" ] || [ -z "$backendAppName" ] || [ -z "$frontendAppName" ]; then
        echo "Error: One or more required values could not be retrieved from azd environment."
        return 1
    fi
    return 0
}

get_values_from_az_deployment() {
    echo "Getting values from Azure deployment outputs..."

    deploymentName=$(az group show --name "$resourceGroupName" --query "tags.DeploymentName" -o tsv)
    echo "Deployment Name (from tag): $deploymentName"

    echo "Fetching deployment outputs..."
    deploymentOutputs=$(az deployment group show \
        --name "$deploymentName" \
        --resource-group "$resourceGroupName" \
        --query "properties.outputs" -o json)

    # Helper function to extract value from deployment outputs
    # Usage: extract_value "primaryKey" "fallbackKey"
    extract_value() {
        local primary_key="$1"
        local fallback_key="$2"
        local value

        value=$(echo "$deploymentOutputs" | grep -i -A 3 "\"$primary_key\"" | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')

        if [ -z "$value" ] && [ -n "$fallback_key" ]; then
            value=$(echo "$deploymentOutputs" | grep -i -A 3 "\"$fallback_key\"" | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
        fi

        echo "$value"
    }

    # Extract deployment outputs
    acrName=$(extract_value "acR_NAME" "ACR_NAME")
    acrLoginServer=$(extract_value "acR_LOGIN_SERVER" "ACR_LOGIN_SERVER")
    backendImageName=$(extract_value "backenD_CONTAINER_IMAGE_NAME" "BACKEND_CONTAINER_IMAGE_NAME")
    backendImageTag=$(extract_value "backenD_CONTAINER_IMAGE_TAG" "BACKEND_CONTAINER_IMAGE_TAG")
    frontendImageName=$(extract_value "frontenD_CONTAINER_IMAGE_NAME" "FRONTEND_CONTAINER_IMAGE_NAME")
    frontendImageTag=$(extract_value "frontenD_CONTAINER_IMAGE_TAG" "FRONTEND_CONTAINER_IMAGE_TAG")
    backendAppName=$(extract_value "apI_APP_NAME" "API_APP_NAME")
    frontendAppName=$(extract_value "frontenD_APP_NAME" "FRONTEND_APP_NAME")

    # Define required values with their display names
    declare -A required_values=(
        ["acrName"]="ACR_NAME"
        ["acrLoginServer"]="ACR_LOGIN_SERVER"
        ["backendImageName"]="BACKEND_CONTAINER_IMAGE_NAME"
        ["backendImageTag"]="BACKEND_CONTAINER_IMAGE_TAG"
        ["frontendImageName"]="FRONTEND_CONTAINER_IMAGE_NAME"
        ["frontendImageTag"]="FRONTEND_CONTAINER_IMAGE_TAG"
        ["backendAppName"]="API_APP_NAME"
        ["frontendAppName"]="FRONTEND_APP_NAME"
    )

    # Validate required values
    missing_values=()
    for var_name in "${!required_values[@]}"; do
        if [ -z "${!var_name}" ]; then
            missing_values+=("${required_values[$var_name]}")
        fi
    done
    if [ ${#missing_values[@]} -gt 0 ]; then
        echo "Error: The following required values could not be retrieved from Azure deployment outputs:"
        printf '  - %s\n' "${missing_values[@]}" | sort
        return 1
    fi
    return 0
}

# Enable public network access on ACR temporarily (needed for remote builds on WAF deployments)
enable_acr_public_access() {
    original_acr_public_access=$(az acr show \
        --name "$acrName" \
        --resource-group "$resourceGroupName" \
        --query "publicNetworkAccess" -o tsv 2>/dev/null)

    if [ -z "$original_acr_public_access" ]; then
        echo "[WARN] Could not retrieve ACR network access status"
    fi

    if [ "$original_acr_public_access" != "Enabled" ]; then
        echo "[OK] Temporarily enabling ACR public network access"
        az acr update \
            --name "$acrName" \
            --resource-group "$resourceGroupName" \
            --public-network-enabled true \
            --default-action Allow \
            --output none
        # Wait a bit for the change to take effect
        sleep 20
    fi
    return 0
}

# Restore original ACR public network access state
restore_acr_public_access() {
    if [ -n "$original_acr_public_access" ] && [ "$original_acr_public_access" != "Enabled" ]; then
        echo "[OK] Restoring ACR public network access to '$original_acr_public_access'"
        case "$original_acr_public_access" in
            "enabled"|"Enabled") restore_value=true ;;
            "disabled"|"Disabled") restore_value=false ;;
            *) restore_value="$original_acr_public_access" ;;
        esac
        az acr update \
            --name "$acrName" \
            --resource-group "$resourceGroupName" \
            --public-network-enabled $restore_value \
            --default-action Deny \
            --output none 2>/dev/null || echo "[WARN] Failed to restore ACR public network access - please check the Azure portal"
    fi
}

cleanup_on_exit() {
    exit_code=$?
    restore_acr_public_access
    echo ""
    if [ $exit_code -ne 0 ]; then
        echo "[FAILED] Script failed"
    else
        echo "[SUCCESS] Script completed successfully"
    fi
    exit $exit_code
}
trap cleanup_on_exit EXIT

# Build and push a single image
# Args: <context> <dockerfile> <imageName> <imageTag>
build_and_push_image() {
    local context="$1"
    local dockerfile="$2"
    local imageName="$3"
    local imageTag="$4"
    local imageRef="${imageName}:${imageTag}"

    if [ ! -f "$dockerfile" ]; then
        echo "[ERROR] Dockerfile not found: $dockerfile"
        return 1
    fi

    echo "Building '$imageRef' remotely in ACR '$acrName'..."
    az acr build \
        --registry "$acrName" \
        --image "$imageRef" \
        --file "$dockerfile" \
        --platform linux \
        "$context"
}

# Update an App Service to run an ACR image using managed identity credentials
# Args: <appName> <imageName> <imageTag>
update_web_app_image() {
    local appName="$1"
    local imageName="$2"
    local imageTag="$3"
    local fullImage="${acrLoginServer}/${imageName}:${imageTag}"

    echo "Updating App Service '$appName' to use image '$fullImage'..."
    az webapp config container set \
        --name "$appName" \
        --resource-group "$resourceGroupName" \
        --container-image-name "$fullImage" \
        --container-registry-url "https://${acrLoginServer}" \
        --only-show-errors \
        --output none

    # Ensure the app pulls the image using its managed identity (no admin credentials)
    az resource update \
        --resource-group "$resourceGroupName" \
        --namespace Microsoft.Web \
        --resource-type sites \
        --name "$appName" \
        --set properties.siteConfig.acrUseManagedIdentityCreds=true \
        --output none 2>/dev/null || true

    echo "Restarting App Service '$appName'..."
    az webapp restart --name "$appName" --resource-group "$resourceGroupName" --output none
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo "==============================================="
echo "Build & Push Container Images"
echo "==============================================="

# Check Azure authentication
echo "Checking Azure authentication..."
if az account show &>/dev/null; then
    echo "Already authenticated with Azure."
else
    echo "Authenticating with Azure CLI..."
    if ! az login --use-device-code; then
        echo "[ERROR] Failed to authenticate with Azure"
        exit 1
    fi
fi

# Resolve configuration values
if [ -z "$resourceGroupName" ]; then
    if ! get_values_from_azd_env; then
        echo ""
        echo "Failed to get values from azd environment."
        echo "Provide a resource group name to resolve values from deployment outputs instead:"
        echo "  Usage: $0 [ResourceGroupName]"
        exit 1
    fi
else
    if ! get_values_from_az_deployment; then
        echo "Failed to get values from deployment outputs."
        exit 1
    fi
fi

# Fallbacks / defaults
acrLoginServer="${acrLoginServer:-${acrName}.azurecr.io}"
backendImageName="${backendImageName:-km-api}"
backendImageTag="${backendImageTag:-latest}"
frontendImageName="${frontendImageName:-km-app}"
frontendImageTag="${frontendImageTag:-latest}"

echo ""
echo "==============================================="
echo "Values to be used:"
echo "==============================================="
echo "Resource Group:      $resourceGroupName"
echo "ACR Name:            $acrName"
echo "ACR Login Server:    $acrLoginServer"
echo "Backend Image:       $backendImageName:$backendImageTag"
echo "Frontend Image:      $frontendImageName:$frontendImageTag"
echo "Backend App:         $backendAppName"
echo "Frontend App:        $frontendAppName"
echo "==============================================="
echo ""

# Ensure ACR is reachable for build (temporarily enable public access if needed)
enable_acr_public_access

# Build & push backend
build_and_push_image "$backendContext" "$backendDockerfile" "$backendImageName" "$backendImageTag"

# Build & push frontend
build_and_push_image "$frontendContext" "$frontendDockerfile" "$frontendImageName" "$frontendImageTag"

# Update the web apps to use the freshly pushed images
update_web_app_image "$backendAppName" "$backendImageName" "$backendImageTag"
update_web_app_image "$frontendAppName" "$frontendImageName" "$frontendImageTag"

echo ""
echo "Images built and pushed, and App Services updated."
