#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Temporarily enable / restore public network access on data-plane resources so
    the post-provision scripts (image build/push, SQL role grant, data seeding)
    can reach them when the environment was deployed with private endpoints
    (enablePrivateNetworking = true).
.DESCRIPTION
    The post-provision hooks run from the deployer's machine, which has no network
    path into the VNet's private endpoints. Container Registry, SQL Server, Storage
    Account, Cosmos DB (when deployed), and the backend API App Service can have
    public network access disabled.

    -Action Enable:  inspects each resource's *current* publicNetworkAccess state
                     and flips any that are Disabled to Enabled.
    -Action Disable: for a private-networking (WAF) deployment — detected from the
                     ENABLE_PRIVATE_NETWORKING azd output — unconditionally restores
                     private-only access on every data-plane resource. No state file
                     is required, so lock-down still works even if Enable ran in a
                     different session (or not at all).

    For a non-private deployment (enablePrivateNetworking = false) the resources are
    meant to stay public, so Disable leaves them untouched (it only clears any
    leftover temporary SQL firewall rule).

    ACR and Storage also enforce a separate network rule set (defaultAction
    Allow/Deny) on top of publicNetworkAccess — both are toggled together. SQL
    Server has no such ruleset; instead a temporary named firewall rule
    (azd-postprovision-temp, 0.0.0.0-255.255.255.255) is added and later removed.
.EXAMPLE
    ./infra/scripts/post-provision/manage-network-access.ps1 -Action Enable
    ./infra/scripts/post-provision/manage-network-access.ps1 -Action Disable
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Enable", "Disable")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

function Get-AzdValue([string]$key) {
    $val = (azd env get-value $key 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $val -or $val -match 'ERROR|not found') { return "" }
    return $val.Trim()
}

$resourceGroup = Get-AzdValue "RESOURCE_GROUP_NAME"
if (-not $resourceGroup) {
    Write-Host "  [SKIP] RESOURCE_GROUP_NAME not found in azd env — nothing to do." -ForegroundColor Yellow
    exit 0
}

$acrName       = Get-AzdValue "ACR_NAME"
$storageName   = Get-AzdValue "AZURE_STORAGE_ACCOUNT"
$sqlServerFqdn = Get-AzdValue "AZURE_SQL_SERVER"
$sqlServerName = if ($sqlServerFqdn) { $sqlServerFqdn.Split('.')[0] } else { "" }
$cosmosEndpoint = Get-AzdValue "AZURE_COSMOS_ENDPOINT"
$cosmosName    = ""
if ($cosmosEndpoint -match 'https://([^.]+)\.') { $cosmosName = $Matches[1] }
$apiAppName    = Get-AzdValue "API_APP_NAME"
$frontendAppName = Get-AzdValue "FRONTEND_APP_NAME"

$envName   = Get-AzdValue "AZURE_ENV_NAME"
$stateFile = Join-Path ([System.IO.Path]::GetTempPath()) "km-network-access-state-$envName-$resourceGroup.json"

# ── Resource-specific helpers: get / set publicNetworkAccess ──
function Get-AcrPublicAccess([string]$name) {
    (az acr show --name $name --resource-group $resourceGroup --query "publicNetworkAccess" -o tsv 2>$null)
}
function Set-AcrPublicAccess([string]$name, [string]$enabled) {
    az acr update --name $name --resource-group $resourceGroup --public-network-enabled $enabled --output none
}
function Get-StoragePublicAccess([string]$name) {
    (az storage account show --name $name --resource-group $resourceGroup --query "publicNetworkAccess" -o tsv 2>$null)
}
function Set-StoragePublicAccess([string]$name, [string]$value) {
    az storage account update --name $name --resource-group $resourceGroup --public-network-access $value --output none
}
function Get-SqlPublicAccess([string]$name) {
    (az sql server show --name $name --resource-group $resourceGroup --query "publicNetworkAccess" -o tsv 2>$null)
}
function Set-SqlPublicAccess([string]$name, [string]$enabled) {
    az sql server update --name $name --resource-group $resourceGroup --enable-public-network $enabled --output none
}
function Get-CosmosPublicAccess([string]$name) {
    (az cosmosdb show --name $name --resource-group $resourceGroup --query "publicNetworkAccess" -o tsv 2>$null)
}
function Set-CosmosPublicAccess([string]$name, [string]$value) {
    az cosmosdb update --name $name --resource-group $resourceGroup --public-network-access $value --output none
}
function Get-ApiAppPublicAccess([string]$name) {
    (az webapp show --name $name --resource-group $resourceGroup --query "publicNetworkAccess" -o tsv 2>$null)
}
function Set-ApiAppPublicAccess([string]$name, [string]$value) {
    az webapp update --name $name --resource-group $resourceGroup --set publicNetworkAccess=$value --output none
}

# ── vnetRouteAllEnabled: routes the app's outbound traffic (incl. ACR image pulls)
# through the VNet so it can reach private-endpoint resources. Toggled true only
# for the enable window per user request; reverted to false on Disable. ──
function Get-VnetRouteAll([string]$name) {
    (az webapp show --name $name --resource-group $resourceGroup --query "siteConfig.vnetRouteAllEnabled" -o tsv 2>$null)
}
function Set-VnetRouteAll([string]$name, [string]$value) {
    # `az webapp update --set siteConfig.vnetRouteAllEnabled=...` silently no-ops (property
    # lives under /config/web, not the top-level site resource) — PATCH the config/web
    # sub-resource directly instead.
    $siteId = (az webapp show --name $name --resource-group $resourceGroup --query id -o tsv 2>$null)
    if (-not $siteId) { $global:LASTEXITCODE = 1; return }
    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) "vnetroute-$name-$([guid]::NewGuid()).json"
    "{`"properties`":{`"vnetRouteAllEnabled`":$value}}" | Out-File -FilePath $tempFile -Encoding ascii -NoNewline
    try {
        az rest --method patch --uri "https://management.azure.com$siteId/config/web?api-version=2022-03-01" --body "@$tempFile" --headers "Content-Type=application/json" --output none
    } finally {
        Remove-Item -Force $tempFile -ErrorAction SilentlyContinue
    }
}

# ── ACR / Storage also enforce a network rule set (defaultAction) independent of publicNetworkAccess ──
function Get-AcrDefaultAction([string]$name) {
    (az acr show --name $name --resource-group $resourceGroup --query "networkRuleSet.defaultAction" -o tsv 2>$null)
}
function Set-AcrDefaultAction([string]$name, [string]$value) {
    az acr update --name $name --resource-group $resourceGroup --default-action $value --output none
}
function Get-StorageDefaultAction([string]$name) {
    (az storage account show --name $name --resource-group $resourceGroup --query "networkRuleSet.defaultAction" -o tsv 2>$null)
}
function Set-StorageDefaultAction([string]$name, [string]$value) {
    az storage account update --name $name --resource-group $resourceGroup --default-action $value --output none
}

# ── SQL Server has no defaultAction ruleset — use a temporary named firewall rule instead ──
$sqlTempRuleName = "azd-postprovision-temp"
function Test-SqlTempFirewallRule([string]$server) {
    $rule = (az sql server firewall-rule show --resource-group $resourceGroup --server $server --name $sqlTempRuleName -o tsv 2>$null)
    return [bool]$rule
}
function Add-SqlTempFirewallRule([string]$server) {
    az sql server firewall-rule create --resource-group $resourceGroup --server $server --name $sqlTempRuleName --start-ip-address "0.0.0.0" --end-ip-address "255.255.255.255" --output none
}
function Remove-SqlTempFirewallRule([string]$server) {
    az sql server firewall-rule delete --resource-group $resourceGroup --server $server --name $sqlTempRuleName --output none
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Network Access: $Action" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($Action -eq "Enable") {
    # Only private-networking (WAF) deployments need public access temporarily opened.
    # For a public deployment the resources are already reachable — skip entirely.
    $privateNetworking = Get-AzdValue "ENABLE_PRIVATE_NETWORKING"
    if ($privateNetworking -notmatch '^(?i:true)$') {
        Write-Host "  Skipping network configuration: this is not a private-networking (WAF) deployment. Resources are already publicly reachable." -ForegroundColor DarkGray
        Write-Host ""
        exit 0
    }

    $toggled = @()

    $candidates = @(
        @{ Name = "acr";     ResourceName = $acrName;       Get = { Get-AcrPublicAccess $acrName };           Set = { param($v) Set-AcrPublicAccess $acrName $v };       OnValue = "true";      OffValue = "false";     DisabledMatch = "Disabled" }
        @{ Name = "storage"; ResourceName = $storageName;   Get = { Get-StoragePublicAccess $storageName };   Set = { param($v) Set-StoragePublicAccess $storageName $v }; OnValue = "Enabled";   OffValue = "Disabled";  DisabledMatch = "Disabled" }
        @{ Name = "sql";     ResourceName = $sqlServerName; Get = { Get-SqlPublicAccess $sqlServerName };     Set = { param($v) Set-SqlPublicAccess $sqlServerName $v };   OnValue = "true";      OffValue = "false";     DisabledMatch = "Disabled" }
        @{ Name = "cosmos";  ResourceName = $cosmosName;    Get = { Get-CosmosPublicAccess $cosmosName };     Set = { param($v) Set-CosmosPublicAccess $cosmosName $v };   OnValue = "Enabled";   OffValue = "Disabled";  DisabledMatch = "Disabled" }
        @{ Name = "apiapp";  ResourceName = $apiAppName;    Get = { Get-ApiAppPublicAccess $apiAppName };     Set = { param($v) Set-ApiAppPublicAccess $apiAppName $v };   OnValue = "Enabled";   OffValue = "Disabled";  DisabledMatch = "Disabled" }
        @{ Name = "frontendapp"; ResourceName = $frontendAppName; Get = { Get-ApiAppPublicAccess $frontendAppName }; Set = { param($v) Set-ApiAppPublicAccess $frontendAppName $v }; OnValue = "Enabled"; OffValue = "Disabled"; DisabledMatch = "Disabled" }
        @{ Name = "api-vnetroute"; ResourceName = $apiAppName;      Get = { Get-VnetRouteAll $apiAppName };      Set = { param($v) Set-VnetRouteAll $apiAppName $v };      OnValue = "true"; OffValue = "false"; DisabledMatch = "false" }
        @{ Name = "app-vnetroute"; ResourceName = $frontendAppName; Get = { Get-VnetRouteAll $frontendAppName };  Set = { param($v) Set-VnetRouteAll $frontendAppName $v }; OnValue = "true"; OffValue = "false"; DisabledMatch = "false" }
    )

    foreach ($c in $candidates) {
        if (-not $c.ResourceName) {
            Write-Host "  [SKIP] $($c.Name): not deployed in this environment." -ForegroundColor DarkGray
            continue
        }
        $current = & $c.Get
        if (-not $current) {
            Write-Host "  [SKIP] $($c.Name) '$($c.ResourceName)': could not read current state (resource not found?)." -ForegroundColor Yellow
            continue
        }
        if ($current -eq $c.DisabledMatch) {
            Write-Host "  Enabling public network access on $($c.Name) '$($c.ResourceName)'..." -ForegroundColor Yellow
            & $c.Set $c.OnValue
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    [OK] Enabled." -ForegroundColor Green
                $toggled += $c.Name
            } else {
                Write-Host "    [WARN] Failed to enable public access on $($c.Name)." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [OK] $($c.Name) '$($c.ResourceName)' already public (state: $current) — no change needed." -ForegroundColor DarkGray
        }
    }

    # Give Azure time to propagate the publicNetworkAccess changes above before
    # attempting dependent operations (e.g. SQL rejects firewall-rule writes
    # while it still considers the public network interface disabled). SQL in
    # particular can take a couple of minutes, so poll its actual state rather
    # than using a fixed sleep.
    if ($toggled.Count -gt 0) {
        Write-Host ""
        Write-Host "Waiting for publicNetworkAccess changes to propagate..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        if ($sqlServerName -and ($toggled -contains "sql")) {
            $deadline = (Get-Date).AddMinutes(5)
            while ((Get-Date) -lt $deadline) {
                $sqlState = Get-SqlPublicAccess $sqlServerName
                if ($sqlState -eq "Enabled") { break }
                Write-Host "  ...sql still reports '$sqlState', waiting 15s more..." -ForegroundColor DarkGray
                Start-Sleep -Seconds 15
            }
        }
    }

    # ── ACR / Storage network rule set (defaultAction) — separate gate from publicNetworkAccess ──
    $ruleCandidates = @(
        @{ Name = "acr-rule";     ResourceName = $acrName;     Get = { Get-AcrDefaultAction $acrName };         Set = { param($v) Set-AcrDefaultAction $acrName $v } }
        @{ Name = "storage-rule"; ResourceName = $storageName; Get = { Get-StorageDefaultAction $storageName }; Set = { param($v) Set-StorageDefaultAction $storageName $v } }
    )
    foreach ($c in $ruleCandidates) {
        if (-not $c.ResourceName) { continue }
        $current = & $c.Get
        if ($current -eq "Deny") {
            Write-Host "  Opening firewall (default-action) on $($c.Name -replace '-rule','') '$($c.ResourceName)'..." -ForegroundColor Yellow
            & $c.Set "Allow"
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    [OK] Allowed." -ForegroundColor Green
                $toggled += $c.Name
            } else {
                Write-Host "    [WARN] Failed to open firewall on $($c.Name)." -ForegroundColor Yellow
            }
        }
    }

    # ── SQL Server: add a temporary broad firewall rule (no defaultAction concept on SQL) ──
    if ($sqlServerName) {
        if (-not (Test-SqlTempFirewallRule $sqlServerName)) {
            Write-Host "  Adding temporary firewall rule on sql '$sqlServerName'..." -ForegroundColor Yellow
            $sqlRetries = 0
            do {
                Add-SqlTempFirewallRule $sqlServerName
                if ($LASTEXITCODE -ne 0 -and $sqlRetries -lt 4) {
                    Write-Host "    ...not ready yet, retrying in 20s..." -ForegroundColor DarkGray
                    Start-Sleep -Seconds 20
                }
                $sqlRetries++
            } while ($LASTEXITCODE -ne 0 -and $sqlRetries -le 4)
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    [OK] Temporary firewall rule added." -ForegroundColor Green
                $toggled += "sql-firewall"
            } else {
                Write-Host "    [WARN] Failed to add temporary SQL firewall rule." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [OK] Temporary SQL firewall rule already present." -ForegroundColor DarkGray
        }
    }

    if ($toggled.Count -gt 0) {
        ConvertTo-Json -InputObject @{ resourceGroup = $resourceGroup; toggled = $toggled } | Set-Content -Path $stateFile -Encoding utf8
    } else {
        Write-Host "  No resources needed a network change." -ForegroundColor DarkGray
        Remove-Item -Force $stateFile -ErrorAction SilentlyContinue
    }
}
else {
    # Disable: lock down based on whether this is a private-networking (WAF) deployment,
    # not on a state file — so revert works regardless of how/where Enable ran.
    $privateNetworking = Get-AzdValue "ENABLE_PRIVATE_NETWORKING"
    Remove-Item -Force $stateFile -ErrorAction SilentlyContinue

    if ($privateNetworking -notmatch '^(?i:true)$') {
        Write-Host "  Skipping network lockdown: this is not a private-networking (WAF) deployment. Resources are intended to remain public." -ForegroundColor DarkGray
        # Best-effort: clear any leftover temporary SQL firewall rule from an Enable run.
        if ($sqlServerName -and (Test-SqlTempFirewallRule $sqlServerName)) {
            Write-Host "  Removing leftover temporary SQL firewall rule on SQL server '$sqlServerName'..." -ForegroundColor Yellow
            Remove-SqlTempFirewallRule $sqlServerName
        }
        Write-Host ""
        exit 0
    }

    Write-Host "  Private-networking (WAF) deployment detected. Enforcing private-only access on all data-plane resources." -ForegroundColor Yellow

    # publicNetworkAccess → Disabled/false. vnetRouteAllEnabled is intentionally left
    # true (required for the App Services to reach private-endpoint resources).
    $reverts = @(
        @{ Name = "Container Registry";      ResourceName = $acrName;         Action = { Set-AcrPublicAccess $acrName "false" } }
        @{ Name = "Storage account";         ResourceName = $storageName;     Action = { Set-StoragePublicAccess $storageName "Disabled" } }
        @{ Name = "SQL server";              ResourceName = $sqlServerName;    Action = { Set-SqlPublicAccess $sqlServerName "false" } }
        @{ Name = "Cosmos DB";               ResourceName = $cosmosName;      Action = { Set-CosmosPublicAccess $cosmosName "Disabled" } }
        @{ Name = "API app";                 ResourceName = $apiAppName;      Action = { Set-ApiAppPublicAccess $apiAppName "Disabled" } }
        # Frontend app is intentionally left public — it's the user-facing UI and must stay reachable.
        @{ Name = "Container Registry firewall"; ResourceName = $acrName;     Action = { Set-AcrDefaultAction $acrName "Deny" } }
        @{ Name = "Storage account firewall";    ResourceName = $storageName; Action = { Set-StorageDefaultAction $storageName "Deny" } }
    )
    foreach ($r in $reverts) {
        if (-not $r.ResourceName) { continue }
        Write-Host "  Disabling public network access on $($r.Name) '$($r.ResourceName)'..." -ForegroundColor Yellow
        & $r.Action
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] Public access disabled." -ForegroundColor Green
        } else {
            Write-Host "    [WARN] Could not disable public access on $($r.Name). Please disable it manually in the Azure portal." -ForegroundColor Yellow
        }
    }

    # SQL has no defaultAction ruleset — remove the temporary broad firewall rule if present.
    if ($sqlServerName -and (Test-SqlTempFirewallRule $sqlServerName)) {
        Write-Host "  Removing temporary SQL firewall rule on SQL server '$sqlServerName'..." -ForegroundColor Yellow
        Remove-SqlTempFirewallRule $sqlServerName
        if ($LASTEXITCODE -eq 0) { Write-Host "    [OK] Temporary SQL firewall rule removed." -ForegroundColor Green }
        else { Write-Host "    [WARN] Could not remove the temporary SQL firewall rule. Please remove it manually in the Azure portal." -ForegroundColor Yellow }
    }
}

Write-Host ""
exit 0
