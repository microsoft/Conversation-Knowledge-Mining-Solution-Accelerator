# Get all environment values
$envValues = azd env get-values --output json | ConvertFrom-Json

# Validate and fetch required parameters from azd env if missing
function Get-AzdEnvValueOrDefault {
    param (
        [Parameter(Mandatory = $true)]
        [string]$KeyName,

        [Parameter(Mandatory = $false)]
        [string]$DefaultValue = "",

        [Parameter(Mandatory = $false)]
        [bool]$Required = $false
    )

    # Check if key exists
    if ($envValues.PSObject.Properties.Name -contains $KeyName) {
        return $envValues.$KeyName
    }

    # Key doesn't exist
    if ($Required) {
        Write-Error "Required environment key '$KeyName' not found in azd environment."
        exit 1
    } else {
        return $DefaultValue
    }
}

# Read the required details from Bicep deployment output
$AZURE_SUBSCRIPTION_ID = Get-AzdEnvValueOrDefault -KeyName "AZURE_SUBSCRIPTION_ID" -Required $true
$SOLUTION_NAME = Get-AzdEnvValueOrDefault -KeyName "SOLUTION_NAME" -Required $true
$WEB_APP_IDENTITY_PRINCIPAL_ID = Get-AzdEnvValueOrDefault -KeyName "FRONTEND_MANAGED_IDENTITY_PRINCIPAL_ID" -Required $true
$API_APP_IDENTITY_PRINCIPAL_ID = Get-AzdEnvValueOrDefault -KeyName "BACKEND_MANAGED_IDENTITY_PRINCIPAL_ID" -Required $true
$AZURE_RESOURCE_GROUP = Get-AzdEnvValueOrDefault -KeyName "AZURE_RESOURCE_GROUP" -Required $true
$AZURE_ENV_IMAGETAG = Get-AzdEnvValueOrDefault -KeyName "AZURE_ENV_IMAGETAG" -DefaultValue "latest"
$WEB_APP_NAME=Get-AzdEnvValueOrDefault -KeyName "FRONTEND_APP_NAME" -Required $true
$API_APP_NAME=Get-AzdEnvValueOrDefault -KeyName "BACKEND_APP_NAME" -Required $true

# Export the variables for later use
Write-Host "Using the following parameters:"
Write-Host "AZURE_SUBSCRIPTION_ID = $AZURE_SUBSCRIPTION_ID"
Write-Host "SOLUTION_NAME = $SOLUTION_NAME"
Write-Host "AZURE_RESOURCE_GROUP = $AZURE_RESOURCE_GROUP"
Write-Host "AZURE_ENV_IMAGETAG = $AZURE_ENV_IMAGETAG"
Write-Host "WEB_APP_NAME = $WEB_APP_NAME"
Write-Host "API_APP_NAME = $API_APP_NAME"

Write-Output "`nStarting build process..."

# STEP 1: Ensure user is logged into Azure
Write-Host "`nChecking Azure login status..."
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

# STEP 3: Get current script directory
$ScriptDir = $PSScriptRoot

# STEP 4: Deploy container registry
Write-Host "`nDeploying container registry"
$TemplateFile = Join-Path $ScriptDir "..\deploy_container_registry.bicep" | Resolve-Path
$OUTPUTS = az deployment group create --resource-group $AZURE_RESOURCE_GROUP --template-file $TemplateFile --parameters solutionName=$SOLUTION_NAME acrPullPrincipalIds="['$WEB_APP_IDENTITY_PRINCIPAL_ID', '$API_APP_IDENTITY_PRINCIPAL_ID']" --query "properties.outputs" --output json | ConvertFrom-Json

# Extract ACR name and endpoint
$ACR_NAME = $OUTPUTS.createdAcrName.value

Write-Host "ACR Name: $ACR_NAME"

# STEP 5: Login to Azure Container Registry
Write-Host "Logging into Azure Container Registry: $ACR_NAME"
az acr login -n $ACR_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to log in to ACR"
    exit 1
}

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

Write-Host "`nAll Docker images built and pushed successfully with tag: $AZURE_ENV_IMAGETAG`n"

# STEP 9: Define Function to Update Web App settings to use Managed Identity for ACR pull
function Update-WebApp-Settings {
    param (
        [string]$WebAppName,
        [string]$ResourceGroup
    )

    Write-Host "Updating Web App settings for $WebAppName"
    $webAppConfig = az webapp config show --resource-group $ResourceGroup --name $WebAppName --query id --output tsv
    if (-not $webAppConfig) {
        Write-Error "Error: Web App configuration not found for $WebAppName"
        exit 1
    }
    az resource update --ids $webAppConfig --set properties.acrUseManagedIdentityCreds=True --output none --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to update Web App settings for $WebAppName"
        exit 1
    }
    Write-Host "Web App settings updated successfully for $WebAppName"
}

# STEP 10: Update Web App settings to use the new image
Update-WebApp-Settings -WebAppName $WEB_APP_NAME -ResourceGroup $AZURE_RESOURCE_GROUP
Update-WebApp-Settings -WebAppName $API_APP_NAME -ResourceGroup $AZURE_RESOURCE_GROUP

# STEP 11: Define function to update Web App to use new image
function Update-WebApp-Image {
    param (
        [string]$WebAppName,
        [string]$ResourceGroup,
        [string]$Image
    )

    Write-Host "`nUpdating Web App $WebAppName to use image: $Image"
    az webapp config container set --name $WebAppName --resource-group $ResourceGroup --container-image-name $Image --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to update Web App $WebAppName to use image: $Image"
        exit 1
    }
    Write-Host "Web App $WebAppName updated successfully to use image: $Image"

    Write-Host "`nRestarting Web App $WebAppName to apply changes"
    az webapp restart --name $WebAppName --resource-group $ResourceGroup --output none --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to restart Web App $WebAppName"
        exit 1
    }
    Write-Host "Web App $WebAppName restarted successfully"
}

# STEP 12: Update Web Apps to use new images
Update-WebApp-Image -WebAppName $WEB_APP_NAME -ResourceGroup $AZURE_RESOURCE_GROUP -Image "$ACR_NAME.azurecr.io/km-app:$AZURE_ENV_IMAGETAG"
Update-WebApp-Image -WebAppName $API_APP_NAME -ResourceGroup $AZURE_RESOURCE_GROUP -Image "$ACR_NAME.azurecr.io/km-api:$AZURE_ENV_IMAGETAG"

Write-Host "`nWeb Apps updated successfully to use new images"

Write-Host "`nIt might take a few minutes for the changes to take effect.`n"