import pytest

from src.tests.api.test_setup_data_scripts import run_powershell


MOCK_AZURE = r"""
    $Phase = 'PreProvision'
    $script:Tenant = '11111111-1111-4111-8111-111111111111'
    $script:Subscription = '44444444-4444-4444-8444-444444444444'
    $script:AppId = '22222222-2222-4222-8222-222222222222'
    $script:ObjectId = '55555555-5555-4555-8555-555555555555'
    $script:Values = @{
        AZURE_ENV_NAME = 'testenv'
        AZURE_SUBSCRIPTION_ID = $script:Subscription
        RESOURCE_GROUP_NAME = 'rg-test'
        FRONTEND_APP_NAME = 'app-test'
        API_APP_NAME = 'api-test'
    }
    $env:AZURE_AD_CLIENT_ID = ''
    $env:AZURE_AD_TENANT_ID = ''
    $script:Application = @{
        appId = $script:AppId; id = $script:ObjectId; signInAudience = 'AzureADMyOrg'
        identifierUris = @('api://existing-api')
        spa = @{ redirectUris = @('https://existing.example') }
        appRoles = @()
        api = @{
            oauth2PermissionScopes = @()
            preAuthorizedApplications = @(@{
                appId = '77777777-7777-4777-8777-777777777777'
                delegatedPermissionIds = @('88888888-8888-4888-8888-888888888888')
            })
        }
        optionalClaims = @{
            accessToken = @(@{ name = 'email' })
            idToken = @(@{ name = 'login_hint' })
            saml2Token = @()
        }
    }
    $script:Calls = @()
    $script:Patches = @()
    $script:CreateCount = 0
    $script:SpExists = $false
    $script:FailGraph = $false
    $script:FailAppSettings = $false
    function Test-CommandAvailable { return $true }
    function azd {
        param($Command, $Action, $Name, $Value)
        $global:LASTEXITCODE = 0
        if ($Command -ne 'env') { throw 'Unexpected azd command' }
        if ($Action -eq 'get-value') {
            if (-not $script:Values.ContainsKey($Name)) {
                $global:LASTEXITCODE = 1
                return 'ERROR: missing setting'
            }
            return $script:Values[$Name]
        }
        if ($Action -eq 'set') {
            $script:Values[$Name] = $Value
            return
        }
        throw 'Unexpected azd action'
    }
    function az {
        $script:Calls += ($args -join '|')
        $global:LASTEXITCODE = 0
        if ($args[0] -eq 'account') {
            if ($args[1] -eq 'show') {
                return (@{ id = $script:Subscription; tenantId = $script:Tenant } | ConvertTo-Json)
            }
            if ($args[1] -eq 'set') { $script:Subscription = $args[3]; return }
        }
        if ($args[0] -eq 'ad' -and $args[1] -eq 'app') {
            if ($args[2] -eq 'create') { $script:CreateCount++ }
            if ($args[2] -in @('show', 'create')) { return ($script:Application | ConvertTo-Json -Depth 12) }
            if ($args[2] -eq 'update') { return }
        }
        if ($args[0] -eq 'ad' -and $args[1] -eq 'sp') {
            if ($args[2] -eq 'list') {
                if ($script:SpExists) { return '66666666-6666-4666-8666-666666666666' }
                return ''
            }
            if ($args[2] -eq 'create') { $script:SpExists = $true; return }
        }
        if ($args[0] -eq 'rest') {
            if ($script:FailGraph) { $global:LASTEXITCODE = 1; return }
            $index = [Array]::IndexOf($args, '--body')
            $body = Get-Content -LiteralPath $args[$index + 1].Substring(1) -Raw | ConvertFrom-Json -AsHashtable
            $script:Patches += $body
            foreach ($key in $body.Keys) {
                if ($key -eq 'api') {
                    foreach ($field in $body.api.Keys) { $script:Application.api[$field] = $body.api[$field] }
                } else { $script:Application[$key] = $body[$key] }
            }
            return
        }
        if ($args[0] -eq 'webapp') {
            if ($args[1] -eq 'show') { return 'app-test.azurewebsites.net' }
            if ($args[1] -eq 'list') {
                if (($args -join ' ') -like '*api-*') { return 'api-test' }
                return 'app-test'
            }
            if ($args[1] -eq 'config') {
                if ($script:FailAppSettings) { $global:LASTEXITCODE = 1 }
                return
            }
            if ($args[1] -eq 'restart') { return }
        }
        throw "Unexpected Azure CLI command: $($args -join ' ')"
    }
"""


def run_auth_test(body):
    run_powershell(MOCK_AZURE + body, "configure_auth.ps1")


def test_preprovision_creates_registration_and_persists_all_ids():
    run_auth_test("""
        Invoke-Main
        if ($script:CreateCount -ne 1) { throw 'Registration not created' }
        if ($script:Values.AZURE_AD_CLIENT_ID -ne $script:AppId) { throw 'Client ID not persisted' }
        if ($script:Values.AZURE_AD_TENANT_ID -ne $script:Tenant) { throw 'Tenant ID not persisted' }
        if ($script:Values.AZURE_SUBSCRIPTION_ID -ne $script:Subscription) { throw 'Subscription not persisted' }
        if (-not $script:SpExists) { throw 'Enterprise application not created' }
        if ($script:Calls | Where-Object { $_ -like 'webapp|*' }) { throw 'App Service changed before provisioning' }
    """)


def test_repeated_setup_reuses_registration_scopes_roles_and_permissions():
    run_auth_test("""
        Invoke-Main
        $scopeId = $script:Application.api.oauth2PermissionScopes[0].id
        $roleIds = @($script:Application.appRoles | ForEach-Object id)
        Invoke-Main
        if ($script:CreateCount -ne 1) { throw 'Duplicate app registration created' }
        if ($script:Application.api.oauth2PermissionScopes.Count -ne 1) { throw 'Duplicate scope' }
        if ($script:Application.api.oauth2PermissionScopes[0].id -ne $scopeId) { throw 'Scope ID changed' }
        if ($script:Application.appRoles.Count -ne 3) { throw 'Duplicate roles' }
        if (Compare-Object $roleIds @($script:Application.appRoles | ForEach-Object id)) { throw 'Role IDs changed' }
        if ($script:Application.api.preAuthorizedApplications.Count -ne 2) { throw 'Existing preauthorization lost or duplicated' }
    """)


def test_registration_configuration_uses_ckm_spa_and_access_token_contract():
    run_auth_test("""
        Invoke-Main
        $app = $script:Application
        if ($app.api.requestedAccessTokenVersion -ne 2) { throw 'Wrong access-token version' }
        if ($app.api.oauth2PermissionScopes[0].value -ne 'access_as_user') { throw 'Wrong scope' }
        if ($app.spa.redirectUris -notcontains 'http://localhost:3000') { throw 'Local SPA redirect missing' }
        if ($app.spa.redirectUris -notcontains 'https://existing.example') { throw 'Existing redirect removed' }
        if ($app.optionalClaims.accessToken.name -notcontains 'idtyp') { throw 'App identity claim missing' }
        if ($app.optionalClaims.accessToken.name -notcontains 'email') { throw 'Existing claim removed' }
        if ($app.optionalClaims.idToken[0].name -ne 'login_hint') { throw 'Existing ID token claim removed' }
        if ($script:Calls | Where-Object { $_ -match 'credential|appRoleAssignments|owner.*add|authsettings' }) {
            throw 'A secret, role assignment, or EasyAuth configuration was created'
        }
        $cli = $app.api.preAuthorizedApplications | Where-Object appId -eq '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
        if ($cli.delegatedPermissionIds -notcontains $app.api.oauth2PermissionScopes[0].id) { throw 'CLI scope not authorized' }
    """)


def test_graph_failure_preserves_new_client_id_for_retry():
    run_auth_test("""
        $script:FailGraph = $true
        try { Invoke-Main; throw 'Graph failure accepted' }
        catch { if ($_.Exception.Message -notlike '*Azure CLI command failed*') { throw } }
        if ($script:Values.AZURE_AD_CLIENT_ID -ne $script:AppId) { throw 'Created app ID was lost' }
        $script:FailGraph = $false
        Invoke-Main
        if ($script:CreateCount -ne 1) { throw 'Retry created another registration' }
    """)


def test_tenant_mismatch_stops_before_registration_or_settings_changes():
    run_auth_test("""
        $TenantId = '99999999-9999-4999-8999-999999999999'
        try { Invoke-Main; throw 'Tenant mismatch accepted' }
        catch { if ($_.Exception.Message -notlike '*tenant differs*') { throw } }
        if ($script:CreateCount -ne 0 -or $script:Patches.Count -ne 0) { throw 'Registration changed despite mismatch' }
        if ($script:Values.ContainsKey('AZURE_AD_CLIENT_ID')) { throw 'Client ID persisted despite mismatch' }
    """)


def test_postprovision_sets_spa_redirect_and_correct_app_service_settings():
    run_auth_test(r"""
        $Phase = 'PostProvision'
        Invoke-Main
        if ($script:Application.spa.redirectUris -notcontains 'https://app-test.azurewebsites.net') { throw 'Deployed SPA redirect missing' }
        $updates = @($script:Calls | Where-Object { $_ -like 'webapp|config|appsettings|set|*' })
        if ($updates.Count -ne 2) { throw 'Both App Services were not configured' }
        if ($updates[0] -notlike "*--name|api-test|*AZURE_AD_TENANT_ID=$script:Tenant*AZURE_AD_CLIENT_ID=$script:AppId*") { throw 'Wrong backend settings' }
        if ($updates[1] -notlike "*--name|app-test|*APP_AZURE_AD_TENANT_ID=$script:Tenant*APP_AZURE_AD_CLIENT_ID=$script:AppId*") { throw 'Wrong frontend settings' }
        if ($updates -match '\|AZURE_CLIENT_ID=') { throw 'Managed identity client ID overwritten' }
        if (@($script:Calls | Where-Object { $_ -like 'webapp|restart|*' }).Count -ne 2) { throw 'Apps not restarted' }
    """)


def test_existing_registration_is_used_without_creation():
    run_auth_test("""
        $script:Values.AZURE_AD_CLIENT_ID = $script:AppId
        $script:SpExists = $true
        Invoke-Main
        if ($script:CreateCount -ne 0) { throw 'Existing app was not reused' }
    """)


def test_disabled_role_is_not_reenabled_implicitly():
    run_auth_test("""
        $script:Application.appRoles = @(@{
            id = '99999999-9999-4999-8999-999999999999'
            value = 'Admin'; isEnabled = $false; allowedMemberTypes = @('User')
        })
        try { Invoke-Main; throw 'Disabled role accepted' }
        catch { if ($_.Exception.Message -notlike "*'Admin' role must be enabled*") { throw } }
        if ($script:Patches.Count -ne 0) { throw 'Disabled authorization policy changed' }
    """)


@pytest.mark.parametrize("setting", ["AZURE_SUBSCRIPTION_ID", "AZURE_AD_CLIENT_ID"])
def test_invalid_configured_ids_are_rejected(setting):
    run_auth_test(f"""
        $script:Values.{setting} = 'not-a-guid'
        try {{ Invoke-Main; throw 'Invalid ID accepted' }}
        catch {{ if ($_.Exception.Message -notlike '*must be a non-empty GUID*') {{ throw }} }}
        if ($script:CreateCount -ne 0) {{ throw 'Registration created with invalid configuration' }}
    """)


def test_missing_azd_is_reported_before_any_azure_change():
    run_auth_test("""
        function Test-CommandAvailable { param($Name); return $Name -ne 'azd' }
        try { Invoke-Main; throw 'Missing azd accepted' }
        catch { if ($_.Exception.Message -notlike "*'azd' is required*") { throw } }
        if ($script:Calls.Count -ne 0) { throw 'Azure accessed without azd' }
    """)


def test_selected_azd_subscription_takes_precedence_over_cli_default():
    run_auth_test("""
        $target = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        $script:Values.AZURE_SUBSCRIPTION_ID = $target
        Invoke-Main
        if ($script:Subscription -ne $target) { throw 'CLI subscription was not selected' }
        if ($script:Values.AZURE_SUBSCRIPTION_ID -ne $target) { throw 'CLI default replaced azd subscription' }
    """)


def test_existing_role_identifiers_and_cli_permissions_are_preserved():
    run_auth_test("""
        $adminId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
        $script:Application.appRoles = @(@{
            id = $adminId; value = 'Admin'; isEnabled = $true; allowedMemberTypes = @('User')
        }, @{
            id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
            value = 'Custom'; isEnabled = $false; allowedMemberTypes = @('Application')
        })
        $permission = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
        $script:Application.api.preAuthorizedApplications += @{
            appId = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
            delegatedPermissionIds = @($permission)
        }
        Invoke-Main
        $roles = $script:Application.appRoles
        if (($roles | Where-Object value -eq 'Admin').id -ne $adminId) { throw 'Existing role ID changed' }
        if (-not ($roles | Where-Object value -eq 'Custom')) { throw 'Custom role removed' }
        $cli = $script:Application.api.preAuthorizedApplications | Where-Object appId -eq '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
        if ($cli.delegatedPermissionIds -notcontains $permission) { throw 'Existing CLI permission removed' }
    """)


def test_app_service_access_failure_stops_finalization():
    run_auth_test("""
        $Phase = 'PostProvision'
        $script:FailAppSettings = $true
        try { Invoke-Main; throw 'App Service permission failure accepted' }
        catch { if ($_.Exception.Message -notlike '*Azure CLI command failed*') { throw } }
        if (@($script:Calls | Where-Object { $_ -like 'webapp|config|appsettings|set|*' }).Count -ne 1) {
            throw 'Settings changes continued after failure'
        }
        if ($script:Calls | Where-Object { $_ -like 'webapp|restart|*' }) { throw 'Apps restarted after failed configuration' }
    """)


def test_failed_azd_persistence_stops_before_app_registration_creation():
    run_auth_test("""
        function azd { $global:LASTEXITCODE = 1; return 'ERROR: cannot save environment' }
        try { Invoke-Main; throw 'Persistence failure accepted' }
        catch { if ($_.Exception.Message -notlike '*Could not save AZURE_SUBSCRIPTION_ID*') { throw } }
        if ($script:CreateCount -ne 0 -or $script:Patches.Count -ne 0) { throw 'Entra changed despite persistence failure' }
    """)


def test_authentication_hooks_run_in_required_order_and_fail_closed():
    import yaml

    from src.tests.api.test_setup_data_scripts import ROOT

    hooks = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))["hooks"]
    for platform in ("windows", "posix"):
        before = hooks["preprovision"][platform]["run"]
        after = hooks["postprovision"][platform]["run"]
        assert "-Phase PreProvision" in before
        assert after.index("-Phase PostProvision") < after.index("build_and_push_images.ps1")
        assert after.index("-Phase PostProvision") < after.index("setup-data.ps1")
        if platform == "posix":
            assert "-Phase PreProvision || exit 1" in before
            assert "-Phase PostProvision || exit 1" in after
            assert 'azd env set ADMIN_API_KEY "$key" || exit 1' in before
            assert "-AllowDeployedFallback || exit 1" in after
        else:
            assert 'throw "Authentication preparation failed."' in before
            assert 'throw "Authentication configuration failed."' in after
            assert 'throw "Could not persist ADMIN_API_KEY."' in before
            assert 'throw "Data setup failed."' in after
