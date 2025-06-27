# Define script parameters
param (
    [string]$AZURE_SUBSCRIPTION_ID,
    [string]$ENV_NAME,
    [string]$AZURE_LOCATION,
    [string]$AZURE_RESOURCE_GROUP,
    [string]$USE_LOCAL_BUILD,
    [string]$AZURE_ENV_IMAGETAG
)

# Convert USE_LOCAL_BUILD to Boolean
$USE_LOCAL_BUILD = if ($USE_LOCAL_BUILD -match "^(?i:true)$") { $true } else { $false }

if ([string]::IsNullOrEmpty($AZURE_ENV_IMAGETAG)) {
    $AZURE_ENV_IMAGETAG = "latest"
}

# Validate required parameters
if (-not $AZURE_SUBSCRIPTION_ID -or -not $ENV_NAME -or -not $AZURE_LOCATION -or -not $AZURE_RESOURCE_GROUP) {
    Write-Error "Missing required arguments. Usage: docker-build.ps1 <AZURE_SUBSCRIPTION_ID> <ENV_NAME> <AZURE_LOCATION> <AZURE_RESOURCE_GROUP> <USE_LOCAL_BUILD> <AZURE_ENV_IMAGETAG>"
    exit 1
}

# Exit early if local build is not requested
if ($USE_LOCAL_BUILD -eq $false) {
    Write-Output "Local Build not enabled. Using prebuilt image."
    exit 0
}

Write-Output "Local Build enabled. Starting build process."

# STEP 1: Ensure user is logged into Azure
Write-Host "Checking Azure login status..."
$account = az account show 2>$null | ConvertFrom-Json

if (-not $account) {
    Write-Host "Not logged in. Attempting az login..."
    az login | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Azure login failed."
        exit 1
    }
} else {
    Write-Host "Already logged in to Azure as: $($account.user.name)"
}

# STEP 2: Set Azure subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set Azure subscription."
    exit 1
}

# STEP 3: Deploy container registry
Write-Host "Deploying container registry in location: $AZURE_LOCATION"
$OUTPUTS = az deployment group create --resource-group $AZURE_RESOURCE_GROUP --template-file "./infra/deploy_container_registry.bicep" --parameters environmentName=$ENV_NAME --query "properties.outputs" --output json | ConvertFrom-Json

# Extract ACR name and endpoint
$ACR_NAME = $OUTPUTS.createdAcrName.value

Write-Host "Extracted ACR Name: $ACR_NAME"

# STEP 4: Login to Azure Container Registry
Write-Host "Logging into Azure Container Registry: $ACR_NAME"
az acr login -n $ACR_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to log in to ACR"
    exit 1
}

# STEP 5: Get current script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# STEP 6: Resolve full paths to Dockerfiles and build contexts
$WebAppDockerfilePath = Join-Path $ScriptDir "..\..\src\App\WebApp.Dockerfile" | Resolve-Path
$WebAppContextPath = Join-Path $ScriptDir "..\..\src\App" | Resolve-Path
$ApiAppDockerfilePath = Join-Path $ScriptDir "..\..\src\api\ApiApp.Dockerfile" | Resolve-Path
$ApiAppContextPath = Join-Path $ScriptDir "..\..\src\api" | Resolve-Path

# STEP 7: Define function to build and push Docker images
function Build-And-Push-Image {
    param (
        [string]$IMAGE_NAME,
        [string]$BUILD_PATH,
        [string]$BUILD_CONTEXT,
        [string]$TAG
    )

    $IMAGE_URI = "$ACR_NAME.azurecr.io/$($IMAGE_NAME):$TAG"

    Write-Host "`n--- Building Docker image: $IMAGE_URI ---"
    docker build --no-cache -f $BUILD_PATH -t $IMAGE_URI $BUILD_CONTEXT

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Docker image: $IMAGE_URI"
        exit 1
    }

    Write-Host "--- Pushing Docker image to ACR: $IMAGE_URI ---"
    docker push $IMAGE_URI
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push Docker image: $IMAGE_URI"
        exit 1
    }

    Write-Host "--- Docker image pushed successfully: $IMAGE_URI ---`n"
}

# STEP 8: Build and push images with provided tag
Build-And-Push-Image "km-api" $ApiAppDockerfilePath $ApiAppContextPath $AZURE_ENV_IMAGETAG
Build-And-Push-Image "km-app" $WebAppDockerfilePath $WebAppContextPath $AZURE_ENV_IMAGETAG

Write-Host "`nAll Docker images built and pushed successfully with tag: $AZURE_ENV_IMAGETAG"
