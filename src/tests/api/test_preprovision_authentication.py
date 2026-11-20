import base64
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

TENANT = "11111111-1111-4111-8111-111111111111"
CLIENT = "22222222-2222-4222-8222-222222222222"
OBJECT = "33333333-3333-4333-8333-333333333333"
SUBSCRIPTION = "44444444-4444-4444-8444-444444444444"
SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "scripts" / "pre-provision" / "setup-authentication.ps1"


@pytest.fixture
def application():
    return {
        "id": OBJECT, "appId": CLIENT, "displayName": "CKM-unit-test-backend",
        "signInAudience": "AzureADMyOrg", "identifierUris": [f"api://{CLIENT}"],
        "tags": [],
        "api": {
            "requestedAccessTokenVersion": 2,
            "oauth2PermissionScopes": [{
                "id": SUBSCRIPTION, "value": "access_as_user", "isEnabled": True,
            }],
        },
        "appRoles": [
            {"value": role, "isEnabled": True, "allowedMemberTypes": ["User", "Application"]}
            for role in ("Reader", "Contributor", "Admin")
        ],
    }


def run_setup(apps=None, client=None, tenant=None, failure="", repetitions=1):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 is required for authentication setup")
    values = {"AZURE_ENV_NAME": "unit-test", "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION}
    if client:
        values["AZURE_AD_CLIENT_ID"] = client
    if tenant:
        values["AZURE_AD_TENANT_ID"] = tenant
    data = {
        "values": values, "apps": apps or [], "tenant": TENANT,
        "client": CLIENT, "object": OBJECT, "principals": [],
        "failure": failure, "repetitions": repetitions,
    }
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    command = r"""
$global:state = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('DATA')) | ConvertFrom-Json -AsHashtable
$global:calls = @()
$global:files = @()
foreach ($name in @('AZURE_AD_CLIENT_ID','AZURE_AD_TENANT_ID','AZURE_SUBSCRIPTION_ID')) {
    [Environment]::SetEnvironmentVariable($name, $null)
}
$env:AZURE_ENV_NAME = 'unit-test'
function azd {
    if (($args[0..1] -join ' ') -eq 'env get-value') {
        $value = $global:state.values[$args[2]]
        $global:LASTEXITCODE = if ($value) { 0 } else { 1 }
        return $value
    }
    if (($args[0..1] -join ' ') -eq 'env set') {
        $global:state.values[$args[2]] = $args[3]
        $global:LASTEXITCODE = 0
        return
    }
    throw 'Unexpected azd command'
}
function az {
    $global:calls += ($args -join ' ')
    $global:LASTEXITCODE = 0
    $operation = $args[0..1] -join ' '
    if ($operation -eq 'account show') {
        return @{ tenantId = $global:state.tenant } | ConvertTo-Json -Compress
    }
    $adOperation = $args[0..2] -join ' '
    if ($adOperation -eq 'ad app list' -or $adOperation -eq 'ad app show') {
        if ($global:state.failure -eq 'lookup') { $global:LASTEXITCODE = 1; return }
        if ($adOperation -eq 'ad app show') {
            return $global:state.apps[0] | ConvertTo-Json -Depth 20 -Compress
        }
        return ConvertTo-Json -InputObject @($global:state.apps) -Depth 20 -Compress
    }
    if ($adOperation -eq 'ad sp list') {
        return ConvertTo-Json -InputObject @($global:state.principals) -Compress
    }
    if ($adOperation -eq 'ad sp create') {
        if ($global:state.failure -eq 'principal') { $global:LASTEXITCODE = 1; return }
        $principal = @{ id = $global:state.object }
        $global:state.principals += $principal
        return $principal | ConvertTo-Json -Compress
    }
    if ($args[0] -eq 'rest') {
        $method = $args[[array]::IndexOf($args, '--method') + 1]
        $file = $args[[array]::IndexOf($args, '--body') + 1].Substring(1)
        $global:files += $file
        $body = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json -AsHashtable
        if ($method -eq 'POST') {
            if ($global:state.failure -eq 'create') { $global:LASTEXITCODE = 1; return }
            $body.id = $global:state.object
            $body.appId = $global:state.client
            $body.identifierUris = @()
            $global:state.apps += $body
            return $body | ConvertTo-Json -Depth 20 -Compress
        }
        if ($method -eq 'PATCH') {
            if ($global:state.failure -eq 'patch') { $global:LASTEXITCODE = 1; return }
            $global:state.apps[0].identifierUris = $body.identifierUris
            return
        }
    }
    throw 'Unexpected Azure operation'
}
function Read-Host { throw 'Authentication setup must not prompt' }
try {
    for ($i = 0; $i -lt $global:state.repetitions; $i++) { & 'SCRIPT' }
    $result = @{ success = $true }
} catch {
    $result = @{ success = $false; message = $_.Exception.Message }
}
$result.state = $global:state
$result.calls = $global:calls
$result.files = $global:files
$result | ConvertTo-Json -Depth 25 -Compress
"""
    command = command.replace("DATA", encoded).replace("SCRIPT", str(SCRIPT).replace("'", "''"))
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_registration_is_created_once_and_reused_on_next_deployment():
    result = run_setup(repetitions=2)
    assert result["success"], result.get("message")
    assert len(result["state"]["apps"]) == 1
    assert sum("rest --method POST" in call for call in result["calls"]) == 1
    assert sum("ad sp create" in call for call in result["calls"]) == 1
    assert result["state"]["values"]["AZURE_AD_CLIENT_ID"] == CLIENT
    assert result["state"]["values"]["AZURE_AD_TENANT_ID"] == TENANT
    app = result["state"]["apps"][0]
    assert app["identifierUris"] == [f"api://{CLIENT}"]
    assert app["api"]["requestedAccessTokenVersion"] == 2
    assert {role["value"] for role in app["appRoles"]} == {"Reader", "Contributor", "Admin"}
    assert app["optionalClaims"]["accessToken"][0]["name"] == "idtyp"
    assert all(not Path(path).exists() for path in result["files"])


@pytest.mark.parametrize("supplied_id", [None, CLIENT])
def test_valid_existing_registration_is_reused_without_modification(application, supplied_id):
    result = run_setup(apps=[application], client=supplied_id)
    assert result["success"], result.get("message")
    assert not any(call.startswith("rest") for call in result["calls"])
    assert result["state"]["apps"][0] == application


def test_interrupted_bootstrap_is_resumed_without_duplicate_registration(application):
    application["tags"] = ["ckm-auth-bootstrap"]
    application["identifierUris"] = []
    result = run_setup(apps=[application])
    assert result["success"], result.get("message")
    assert sum("rest --method PATCH" in call for call in result["calls"]) == 1
    assert not any("rest --method POST" in call for call in result["calls"])


def test_ambiguous_registration_name_fails_without_selecting_first(application):
    result = run_setup(apps=[application, copy.deepcopy(application)])
    assert not result["success"]
    assert "Multiple backend registrations" in result["message"]
    assert not any(call.startswith("rest") for call in result["calls"])


def test_conflicting_tenant_fails_before_registration_changes():
    result = run_setup(tenant=SUBSCRIPTION)
    assert not result["success"]
    assert "conflicts" in result["message"]
    assert not any(call.startswith("rest") for call in result["calls"])


@pytest.mark.parametrize("defect", ["version", "roles", "scope", "uri"])
def test_incompatible_supplied_registration_is_not_rewritten(application, defect):
    if defect == "version":
        application["api"]["requestedAccessTokenVersion"] = 1
    elif defect == "roles":
        application["appRoles"] = []
    elif defect == "scope":
        application["api"]["oauth2PermissionScopes"] = []
    else:
        application["identifierUris"] = ["api://another-api"]
    result = run_setup(apps=[application], client=CLIENT)
    assert not result["success"]
    assert not any(call.startswith("rest") for call in result["calls"])


@pytest.mark.parametrize("failure", ["lookup", "create", "patch", "principal"])
def test_directory_permission_failures_are_explicit(failure):
    result = run_setup(failure=failure)
    assert not result["success"]
    assert "Azure authentication setup failed" in result["message"]
    assert "AZURE_AD_CLIENT_ID" not in result["state"]["values"]
    assert all(not Path(path).exists() for path in result["files"])
