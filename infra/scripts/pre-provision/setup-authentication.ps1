$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Get-AuthEnvironmentValue {
    param([string]$Name)

    $environmentArgs = @()
    if ($env:AZURE_ENV_NAME) {
        $environmentArgs = @("--environment", $env:AZURE_ENV_NAME)
    }
    $value = azd env get-value $Name @environmentArgs 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace("$value")) {
        return "$value".Trim()
    }
    return [Environment]::GetEnvironmentVariable($Name)
}

function Set-AuthEnvironmentValue {
    param([string]$Name, [string]$Value)

    $environmentArgs = @()
    if ($env:AZURE_ENV_NAME) {
        $environmentArgs = @("--environment", $env:AZURE_ENV_NAME)
    }
    azd env set $Name $Value @environmentArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to save $Name in the selected azd environment."
    }
    [Environment]::SetEnvironmentVariable($Name, $Value)
}

function Test-AuthGuid {
    param([string]$Value)

    $parsed = [guid]::Empty
    return [guid]::TryParseExact($Value, "D", [ref]$parsed) -and $parsed -ne [guid]::Empty
}

function Invoke-AuthAzure {
    param([string[]]$Arguments)

    $output = az @Arguments --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Azure authentication setup failed. Verify Azure sign-in, directory read access and permissions to create app registrations/service principals."
    }
    if ($output) {
        return $output | ConvertFrom-Json
    }
}

function Invoke-AuthGraphWrite {
    param([string]$Method, [string]$Url, [hashtable]$Body)

    $file = [IO.Path]::GetTempFileName()
    try {
        $Body | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $file -Encoding utf8
        return Invoke-AuthAzure @("rest", "--method", $Method, "--url", $Url, "--body", "@$file")
    } finally {
        Remove-Item -LiteralPath $file -Force
    }
}

$subscriptionId = Get-AuthEnvironmentValue "AZURE_SUBSCRIPTION_ID"
if (-not (Test-AuthGuid $subscriptionId)) {
    throw "The azd environment must have a valid AZURE_SUBSCRIPTION_ID."
}
$account = Invoke-AuthAzure @("account", "show", "--subscription", $subscriptionId)
$tenantId = "$($account.tenantId)".ToLowerInvariant()
if (-not (Test-AuthGuid $tenantId)) {
    throw "Could not resolve the selected subscription's Microsoft Entra tenant."
}
$configuredTenant = Get-AuthEnvironmentValue "AZURE_AD_TENANT_ID"
if ($configuredTenant -and $configuredTenant.ToLowerInvariant() -ne $tenantId) {
    throw "AZURE_AD_TENANT_ID conflicts with the selected subscription's tenant."
}
$currentAccount = Invoke-AuthAzure @("account", "show")
if ($currentAccount.tenantId -ne $tenantId) {
    throw "Azure CLI must be signed in to tenant $tenantId before setting up its app registration."
}

$clientId = Get-AuthEnvironmentValue "AZURE_AD_CLIENT_ID"
if ($clientId) {
    if (-not (Test-AuthGuid $clientId)) {
        throw "The configured AZURE_AD_CLIENT_ID must be a real backend application client GUID."
    }
    $application = Invoke-AuthAzure @("ad", "app", "show", "--id", $clientId)
} else {
    $environmentName = Get-AuthEnvironmentValue "AZURE_ENV_NAME"
    if ([string]::IsNullOrWhiteSpace($environmentName)) {
        throw "An azd environment name is required to find or create its backend registration."
    }
    $displayName = "CKM-$environmentName-backend"
    $escapedName = $displayName.Replace("'", "''")
    $matches = @(Invoke-AuthAzure @("ad", "app", "list", "--filter", "displayName eq '$escapedName'"))
    if ($matches.Count -gt 1) {
        throw "Multiple backend registrations named '$displayName' exist. Select one explicitly with AZURE_AD_CLIENT_ID."
    }
    if ($matches.Count -eq 1) {
        $application = $matches[0]
    } else {
        $scopeId = [guid]::NewGuid().ToString()
        $roles = foreach ($role in @("Reader", "Contributor", "Admin")) {
            @{
                id = [guid]::NewGuid().ToString()
                value = $role
                displayName = $role
                description = "CKM $role application access"
                isEnabled = $true
                allowedMemberTypes = @("User", "Application")
            }
        }
        $application = Invoke-AuthGraphWrite "POST" "https://graph.microsoft.com/v1.0/applications" @{
            displayName = $displayName
            signInAudience = "AzureADMyOrg"
            tags = @("ckm-auth-bootstrap")
            appRoles = @($roles)
            optionalClaims = @{
                accessToken = @(@{ name = "idtyp"; essential = $false; additionalProperties = @() })
            }
            api = @{
                requestedAccessTokenVersion = 2
                oauth2PermissionScopes = @(@{
                    id = $scopeId
                    value = "access_as_user"
                    type = "Admin"
                    isEnabled = $true
                    adminConsentDisplayName = "Access the CKM backend API"
                    adminConsentDescription = "Access CKM as the signed-in user with assigned application roles."
                })
                preAuthorizedApplications = @(@{
                    appId = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
                    delegatedPermissionIds = @($scopeId)
                })
            }
        }
        Write-Host "Created backend registration '$displayName'." -ForegroundColor Green
    }
}

if (-not (Test-AuthGuid "$($application.appId)") -or -not (Test-AuthGuid "$($application.id)")) {
    throw "Azure did not return a valid backend registration."
}
$clientId = $application.appId.ToLowerInvariant()
$expectedUri = "api://$clientId"
if ($expectedUri -notin $application.identifierUris -and "ckm-auth-bootstrap" -in $application.tags) {
    # Resume an interrupted bootstrap without changing an operator-supplied registration.
    if (@($application.identifierUris).Count -gt 0) {
        throw "The bootstrapped registration has an unexpected Application ID URI."
    }
    Invoke-AuthGraphWrite "PATCH" "https://graph.microsoft.com/v1.0/applications/$($application.id)" @{
        identifierUris = @($expectedUri)
    } | Out-Null
    $application.identifierUris = @($expectedUri)
}
if ($application.signInAudience -ne "AzureADMyOrg" -or $application.api.requestedAccessTokenVersion -ne 2) {
    throw "The backend registration must be single-tenant and issue v2 access tokens."
}
if ($expectedUri -notin $application.identifierUris) {
    throw "The backend registration requires Application ID URI $expectedUri."
}
$scopes = @($application.api.oauth2PermissionScopes | Where-Object {
    $_.value -ceq "access_as_user" -and $_.isEnabled
})
if ($scopes.Count -ne 1 -or -not (Test-AuthGuid "$($scopes[0].id)")) {
    throw "The backend registration requires one enabled access_as_user scope."
}
foreach ($role in @("Reader", "Contributor", "Admin")) {
    $matchingRoles = @($application.appRoles | Where-Object {
        $_.value -ceq $role -and $_.isEnabled -and "User" -in $_.allowedMemberTypes
    })
    if ($matchingRoles.Count -ne 1) {
        throw "The backend registration requires an enabled $role application role."
    }
}
$principals = @(Invoke-AuthAzure @("ad", "sp", "list", "--filter", "appId eq '$clientId'"))
if ($principals.Count -eq 0) {
    Invoke-AuthAzure @("ad", "sp", "create", "--id", $clientId) | Out-Null
}
Set-AuthEnvironmentValue "AZURE_AD_CLIENT_ID" $clientId
Set-AuthEnvironmentValue "AZURE_AD_TENANT_ID" $tenantId
Write-Host "Backend client/tenant IDs saved. This registration will be reused on later deployments." -ForegroundColor Green
Write-Host "Assign users/groups roles (Admin for deployment data setup) and configure frontend consent/EasyAuth separately; see docs/AppAuthentication.md." -ForegroundColor Yellow
