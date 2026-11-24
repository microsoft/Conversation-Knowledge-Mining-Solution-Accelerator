#!/usr/bin/env pwsh
#Requires -Version 7.0
<#
.SYNOPSIS
    Creates or reuses CKM's Entra registration and configures deployment authentication.
.DESCRIPTION
    PreProvision saves the subscription, tenant, and client IDs in the selected azd
    environment before production startup. PostProvision also adds the frontend SPA
    redirect URI and synchronizes authentication settings on both App Services.
    No client secret is created and no user is automatically assigned an app role.
.EXAMPLE
    ./infra/scripts/post-provision/configure_auth.ps1 -Phase PreProvision
.EXAMPLE
    ./infra/scripts/post-provision/configure_auth.ps1 -Phase PostProvision
#>
[CmdletBinding()]
param(
    [ValidateSet("PreProvision", "PostProvision")]
    [string]$Phase = "PreProvision",
    [string]$ClientId,
    [string]$TenantId,
    [string]$SubscriptionId,
    [string]$ResourceGroupName,
    [string]$FrontendAppName,
    [string]$BackendAppName,
    [string]$AppDisplayName
)

$ErrorActionPreference = "Stop"

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-AzdEnvValue {
    param([string]$Name)
    $value = azd env get-value $Name 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value -or "$value" -match '^ERROR:') { return "" }
    return ($value | Out-String).Trim()
}

function Resolve-Value {
    param([string]$Value, [string[]]$EnvironmentKeys)
    if (-not [string]::IsNullOrWhiteSpace($Value)) { return $Value.Trim() }
    foreach ($key in $EnvironmentKeys) {
        $configured = Get-AzdEnvValue $key
        if ($configured) { return $configured }
        $configured = [Environment]::GetEnvironmentVariable($key)
        if (-not [string]::IsNullOrWhiteSpace($configured)) { return $configured.Trim() }
    }
    return ""
}

function Assert-Guid {
    param([string]$Value, [string]$Name)
    $parsed = [guid]::Empty
    if (-not [guid]::TryParse($Value, [ref]$parsed) -or $parsed -eq [guid]::Empty) {
        throw "$Name must be a non-empty GUID."
    }
}

function Invoke-Az {
    param([string[]]$Arguments)
    $output = az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' '). Check sign-in and permissions."
    }
    return ($output | Out-String).Trim()
}

function Save-AzdValue {
    param([string]$Name, [string]$Value)
    azd env set $Name $Value | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not save $Name to the selected azd environment. Select the deployment environment and retry."
    }
    [Environment]::SetEnvironmentVariable($Name, $Value)
}

function Invoke-GraphPatch {
    param([string]$ApplicationId, [hashtable]$Body)
    $file = New-TemporaryFile
    try {
        $Body | ConvertTo-Json -Depth 12 -Compress | Set-Content -LiteralPath $file.FullName -Encoding utf8 -NoNewline
        Invoke-Az @(
            "rest", "--method", "patch",
            "--url", "https://graph.microsoft.com/v1.0/applications/$ApplicationId",
            "--headers", "Content-Type=application/json", "--body", "@$($file.FullName)", "--output", "none"
        ) | Out-Null
    } finally {
        Remove-Item -LiteralPath $file.FullName -Force
    }
}

function Get-DeploymentAppName {
    param([string]$Name, [string]$EnvironmentKey, [string]$Rg, [string]$Prefix)
    $resolved = Resolve-Value $Name @($EnvironmentKey)
    if ($resolved) { return $resolved }
    $names = Invoke-Az @("webapp", "list", "--resource-group", $Rg, "--query", "[?starts_with(name, '$Prefix')].name", "-o", "tsv")
    $matches = @($names -split "\r?\n" | Where-Object { $_ })
    if ($matches.Count -ne 1) {
        throw "Expected one $Prefix App Service in '$Rg'. Pass its app name explicitly or configure $EnvironmentKey."
    }
    return $matches[0].Trim()
}

function Set-AppRegistration {
    param([psobject]$Application, [string]$FrontendOrigin)
    $appClientId = $Application.appId
    $scopeName = "access_as_user"
    $cliAppId = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
    $identifierUris = @(@($Application.identifierUris) + "api://$appClientId" | Where-Object { $_ } | Sort-Object -Unique -CaseSensitive)
    Invoke-Az (@("ad", "app", "update", "--id", $appClientId, "--identifier-uris") + $identifierUris + @("--output", "none")) | Out-Null

    $scopes = @($Application.api.oauth2PermissionScopes | Where-Object { $_ })
    $scope = $scopes | Where-Object { $_.value -ceq $scopeName } | Select-Object -First 1
    if (-not $scope) {
        if ($scopes | Where-Object { $_.value -eq $scopeName }) {
            throw "The API scope must use the exact value '$scopeName'."
        }
        $scope = @{
            id = [guid]::NewGuid().ToString()
            value = $scopeName
            isEnabled = $true
            type = "User"
            adminConsentDisplayName = "Access the CKM API"
            adminConsentDescription = "Access the CKM API on behalf of the signed-in user."
            userConsentDisplayName = "Access the CKM API"
            userConsentDescription = "Allow access to the CKM API on your behalf."
        }
        $scopes += $scope
    } elseif (-not $scope.isEnabled) {
        throw "The '$scopeName' scope is disabled. Enable it explicitly before configuring authentication."
    }

    $roles = @($Application.appRoles | Where-Object { $_ })
    foreach ($name in @("Reader", "Contributor", "Admin")) {
        $role = $roles | Where-Object { $_.value -ceq $name } | Select-Object -First 1
        if ($role) {
            if (-not $role.isEnabled -or $role.allowedMemberTypes -notcontains "User") {
                throw "The '$name' role must be enabled and support users. Update the existing role explicitly."
            }
        } else {
            if ($roles | Where-Object { $_.value -eq $name }) { throw "App role values must use the exact case '$name'." }
            $roles += @{
                id = [guid]::NewGuid().ToString()
                value = $name
                displayName = $name
                description = "CKM $name access"
                allowedMemberTypes = @("User", "Application")
                isEnabled = $true
            }
        }
    }

    $redirectUris = @(@($Application.spa.redirectUris) + "http://localhost:3000" + $FrontendOrigin |
        Where-Object { $_ } | Sort-Object -Unique -CaseSensitive)
    $accessClaims = @($Application.optionalClaims.accessToken | Where-Object { $_ })
    if (-not ($accessClaims | Where-Object { $_.name -eq "idtyp" })) {
        $accessClaims += @{ name = "idtyp"; essential = $false; additionalProperties = @() }
    }
    Invoke-GraphPatch -ApplicationId $Application.id -Body @{
        api = @{ requestedAccessTokenVersion = 2; oauth2PermissionScopes = $scopes }
        appRoles = $roles
        spa = @{ redirectUris = $redirectUris }
        optionalClaims = @{
            accessToken = $accessClaims
            idToken = @($Application.optionalClaims.idToken | Where-Object { $_ })
            saml2Token = @($Application.optionalClaims.saml2Token | Where-Object { $_ })
        }
    }

    # The scope must exist before Graph accepts Azure CLI preauthorization.
    $authorized = @($Application.api.preAuthorizedApplications | Where-Object { $_ })
    $existingCli = $authorized | Where-Object { $_.appId -eq $cliAppId } | Select-Object -First 1
    $permissionIds = @(@($existingCli.delegatedPermissionIds) + $scope.id | Where-Object { $_ } | Sort-Object -Unique)
    $authorized = @($authorized | Where-Object { $_.appId -ne $cliAppId })
    $authorized += @{ appId = $cliAppId; delegatedPermissionIds = $permissionIds }
    Invoke-GraphPatch -ApplicationId $Application.id -Body @{ api = @{ preAuthorizedApplications = $authorized } }
}

function Invoke-Main {
    foreach ($command in @("az", "azd")) {
        if (-not (Test-CommandAvailable $command)) { throw "'$command' is required for authentication setup." }
    }
    $selectedSubscription = Resolve-Value $SubscriptionId @("AZURE_SUBSCRIPTION_ID")
    if ($selectedSubscription) {
        Assert-Guid $selectedSubscription "SubscriptionId"
        Invoke-Az @("account", "set", "--subscription", $selectedSubscription) | Out-Null
    }
    $account = Invoke-Az @("account", "show", "--output", "json") | ConvertFrom-Json
    Assert-Guid $account.id "Azure subscription ID"
    Assert-Guid $account.tenantId "Azure tenant ID"
    $expectedTenant = Resolve-Value $TenantId @("AZURE_AD_TENANT_ID")
    if ($expectedTenant -and $expectedTenant -ne $account.tenantId) {
        throw "The configured Entra tenant differs from the selected subscription's tenant. Sign in to the correct tenant and select the matching subscription."
    }
    Save-AzdValue "AZURE_SUBSCRIPTION_ID" $account.id
    Save-AzdValue "AZURE_AD_TENANT_ID" $account.tenantId

    $resolvedClientId = Resolve-Value $ClientId @("AZURE_AD_CLIENT_ID")
    if ($resolvedClientId) {
        Assert-Guid $resolvedClientId "ClientId"
        $application = Invoke-Az @("ad", "app", "show", "--id", $resolvedClientId, "--output", "json") | ConvertFrom-Json
    } else {
        $displayName = $AppDisplayName
        if (-not $displayName) {
            $environmentName = Get-AzdEnvValue "AZURE_ENV_NAME"
            if (-not $environmentName) { throw "Select an azd environment before creating an app registration." }
            $displayName = "$environmentName-ckm-auth"
        }
        $application = Invoke-Az @("ad", "app", "create", "--display-name", $displayName, "--sign-in-audience", "AzureADMyOrg", "--output", "json") | ConvertFrom-Json
    }
    Assert-Guid $application.appId "App registration client ID"
    Assert-Guid $application.id "App registration object ID"
    if ($application.signInAudience -ne "AzureADMyOrg") {
        throw "CKM requires a single-tenant app registration (AzureADMyOrg)."
    }
    Write-Host "Using app registration client ID: $($application.appId)"
    # Persist immediately so a failed Graph update does not create another registration on retry.
    Save-AzdValue "AZURE_AD_CLIENT_ID" $application.appId

    $frontendOrigin = ""
    if ($Phase -eq "PostProvision") {
        $rg = Resolve-Value $ResourceGroupName @("RESOURCE_GROUP_NAME", "AZURE_RESOURCE_GROUP")
        if (-not $rg) { throw "ResourceGroupName is required for PostProvision authentication setup." }
        $frontend = Get-DeploymentAppName $FrontendAppName "FRONTEND_APP_NAME" $rg "app-"
        $backend = Get-DeploymentAppName $BackendAppName "API_APP_NAME" $rg "api-"
        $hostName = Invoke-Az @("webapp", "show", "--resource-group", $rg, "--name", $frontend, "--query", "defaultHostName", "--output", "tsv")
        if (-not $hostName -or $hostName -match '[/\s]') { throw "Could not resolve the frontend App Service hostname." }
        $frontendOrigin = "https://$hostName"
    }
    Set-AppRegistration -Application $application -FrontendOrigin $frontendOrigin
    $principal = Invoke-Az @("ad", "sp", "list", "--filter", "appId eq '$($application.appId)'", "--query", "[0].id", "--output", "tsv")
    if (-not $principal) {
        Invoke-Az @("ad", "sp", "create", "--id", $application.appId, "--output", "none") | Out-Null
    }

    if ($Phase -eq "PostProvision") {
        Invoke-Az @(
            "webapp", "config", "appsettings", "set", "--resource-group", $rg, "--name", $backend,
            "--settings", "AZURE_AD_TENANT_ID=$($account.tenantId)", "AZURE_AD_CLIENT_ID=$($application.appId)", "--output", "none"
        ) | Out-Null
        Invoke-Az @(
            "webapp", "config", "appsettings", "set", "--resource-group", $rg, "--name", $frontend,
            "--settings", "APP_AZURE_AD_TENANT_ID=$($account.tenantId)", "APP_AZURE_AD_CLIENT_ID=$($application.appId)", "--output", "none"
        ) | Out-Null
        foreach ($app in @($backend, $frontend)) {
            Invoke-Az @("webapp", "restart", "--resource-group", $rg, "--name", $app) | Out-Null
        }
    }
    Write-Host "Authentication configured ($Phase). Client ID: $($application.appId)" -ForegroundColor Green
    Write-Host "Assign Reader, Contributor, or Admin roles explicitly through the enterprise application. No user roles were assigned."
}

if ($MyInvocation.InvocationName -ne ".") {
    try {
        Invoke-Main
        exit 0
    } catch {
        Write-Error -ErrorAction Continue "configure_auth failed: $($_.Exception.Message)"
        exit 1
    }
}
