import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "infra" / "scripts" / "post-provision"
PWSH = shutil.which("pwsh")


def run_powershell(body, filename="setup-data.ps1"):
    if not PWSH:
        pytest.skip("PowerShell is required for deployment script tests")
    loader = """
        $ErrorActionPreference = 'Stop'
        $tokens = $null; $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile(
            $env:SETUP_SCRIPT, [ref]$tokens, [ref]$errors)
        if ($errors) { throw ($errors | Out-String) }
        foreach ($statement in $ast.EndBlock.Statements) {
            if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
                . ([scriptblock]::Create($statement.Extent.Text))
            }
        }
        $azdAvailable = $false
        $script:RgAppSettingsCache = $null
        $script:RgApiAppName = ''
        function az { throw 'Unexpected Azure CLI call' }
        function azd { throw 'Unexpected azd call' }
        function Start-Sleep {}
    """
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", loader + body + "\nexit 0\n"],
        env={**os.environ, "SETUP_SCRIPT": str(SCRIPTS / filename)},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_backend_probe_uses_anonymous_root():
    run_powershell("""
        function Invoke-RestMethod {
            param($Uri, $Method, $TimeoutSec, [switch]$SkipHttpErrorCheck)
            if ($Uri -ne 'http://localhost:8000/') { throw 'Protected endpoint probed' }
        }
        if (-not (Test-BackendReachable 'http://localhost:8000')) { throw 'Local API rejected' }
    """)


def test_skip_data_loading_preserves_existing_data():
    run_powershell("""
        $menuSwitch = $ast.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.SwitchStatementAst] -and
                $node.Condition.Extent.Text -eq '$selected.type'
        }, $true) | Select-Object -First 1
        $skipClause = $menuSwitch.Clauses | Where-Object { $_.Item1.Value -eq 'skip' }
        if (-not $skipClause) { throw 'Skip menu option missing' }
        $cleanup = $skipClause.Item2.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.CommandAst] -and
                $node.GetCommandName() -eq 'Invoke-DataCleanup'
        }, $true)
        if ($cleanup.Count -gt 0) { throw 'Skipping data loading clears existing data' }
    """)


def test_audio_uploads_use_single_file_requests_with_a_deadline():
    run_powershell("""
        $BackendUrl = 'https://backend.example'
        $headers = @{}
        $audioFiles = @(1..3 | ForEach-Object {
            [pscustomobject]@{ Name = "audio-$_.wav"; FullName = "audio-$_.wav" }
        })
        $uploadFailures = 0
        $script:UploadCalls = 0
        function Get-Item { param($Path); return $Path }
        function Invoke-RestMethod {
            param($Uri, $Method, $Form, $Headers, $TimeoutSec)
            if (@($Form.files).Count -ne 1) { throw 'Audio request contains multiple files' }
            if ($TimeoutSec -ne 180) { throw 'Audio upload deadline missing' }
            $script:UploadCalls++
        }
        $audioBlock = $ast.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.IfStatementAst] -and
                $node.Extent.Text.StartsWith('if ($audioFiles.Count -gt 0)') -and
                $node.Extent.Text.Contains('$batchSize =')
        }, $true) | Select-Object -First 1
        if (-not $audioBlock) { throw 'Audio upload block missing' }
        . ([scriptblock]::Create($audioBlock.Extent.Text))
        if ($script:UploadCalls -ne 3 -or $audioUploaded -ne 3 -or $uploadFailures -ne 0) {
            throw 'Audio upload counts incorrect'
        }
    """)


def test_resource_group_credentials_ignore_stale_azd_and_process_values():
    run_powershell("""
        $ResourceGroupName = 'target-rg'
        $env:ADMIN_API_KEY = 'stale-key'
        $azdAvailable = $true
        $script:RgAppSettingsCache = @{ ADMIN_API_KEY = 'target-key' }
        $headers = Get-ApiHeaders
        if ($headers['X-Admin-Api-Key'] -ne 'target-key') { throw 'Wrong deployment key' }
        $script:RgAppSettingsCache = @{}
        try { Get-ApiHeaders; throw 'Missing target credentials accepted' }
        catch { if ($_.Exception.Message -notlike '*Configure AZURE_AD_CLIENT_ID*') { throw } }
    """)


def test_credentials_support_quoted_env_without_azd(tmp_path):
    (tmp_path / ".env").write_text('ADMIN_API_KEY="env-file-key"\n')
    run_powershell(f"""
        $projectRoot = '{tmp_path}'
        $env:ADMIN_API_KEY = ''
        $headers = Get-ApiHeaders
        if ($headers['X-Admin-Api-Key'] -ne 'env-file-key') {{ throw 'Quoted key not resolved' }}
    """)


@pytest.mark.parametrize("source", ["process", "azd"])
def test_seed_data_prefers_admin_key_without_requesting_a_token(source):
    run_powershell(f"""
        $env:ADMIN_API_KEY = '{'test-key' if source == 'process' else ''}'
        function azd {{
            if (($args -join ' ') -ne 'env get-value ADMIN_API_KEY') {{
                throw 'Token configuration requested despite admin key'
            }}
            return 'test-key'
        }}
        $headers = Get-ApiHeaders
        if ($headers['X-Admin-Api-Key'] -ne 'test-key' -or $headers.ContainsKey('Authorization')) {{
            throw 'Admin key not preferred'
        }}
    """, filename="seed-data.ps1")


def test_seed_data_uses_token_only_without_an_admin_key():
    run_powershell("""
        $env:ADMIN_API_KEY = ''
        $env:AZURE_AD_CLIENT_ID = 'target-client'
        function azd { return '' }
        function az {
            if (($args -join ' ') -notlike '*--resource api://target-client*') {
                throw 'Wrong token target'
            }
            $global:LASTEXITCODE = 0
            return 'test-token'
        }
        if ((Get-ApiHeaders).Authorization -ne 'Bearer test-token') { throw 'Token missing' }
        function az { $global:LASTEXITCODE = 1; return '' }
        try { Get-ApiHeaders; throw 'Token acquisition failure accepted' }
        catch { if ($_.Exception.Message -notlike '*API access token or ADMIN_API_KEY*') { throw } }
    """, filename="seed-data.ps1")


def test_access_token_uses_target_tenant_and_failed_cli_output_is_rejected():
    run_powershell("""
        function Get-DeployValue {
            param($Name)
            switch ($Name) {
                AZURE_AD_CLIENT_ID { return 'target-client' }
                AZURE_AD_TENANT_ID { return 'target-tenant' }
            }
            return ''
        }
        function az {
            if (($args -join ' ') -notlike '*--tenant target-tenant --resource api://target-client*') {
                throw 'Wrong token target'
            }
            $global:LASTEXITCODE = 0
            return 'valid-token'
        }
        if ((Get-ApiHeaders).Authorization -ne 'Bearer valid-token') { throw 'Token missing' }
        function az { $global:LASTEXITCODE = 1; return 'ERROR: failed acquisition' }
        try { Get-ApiHeaders; throw 'CLI failure accepted' }
        catch { if ($_.Exception.Message -notlike '*Could not obtain an API access token*') { throw } }
    """)


@pytest.mark.parametrize("status", [401, 403, 503])
def test_authentication_preflight_reports_access_failures(status):
    run_powershell(f"""
        function Invoke-RestMethod {{
            param($StatusCodeVariable)
            Set-Variable -Name $StatusCodeVariable -Value {status} -Scope 1
            return @{{}}
        }}
        try {{ Test-ApiAccess -Url 'https://backend.example' -Headers @{{}}; throw 'Failure accepted' }}
        catch {{ if ($_.Exception.Message -notlike '*HTTP {status}*') {{ throw }} }}
    """)


def test_preflight_preserves_contributor_uploads_but_rejects_reader_and_admin_operations():
    run_powershell("""
        $script:Roles = @('Reader')
        function Invoke-RestMethod {
            param($StatusCodeVariable)
            Set-Variable -Name $StatusCodeVariable -Value 200 -Scope 1
            return @{ roles = $script:Roles }
        }
        try { Test-ApiAccess -Url 'https://backend.example' -Headers @{}; throw 'Reader accepted' }
        catch { if ($_.Exception.Message -notlike "*requires the 'contributor'*") { throw } }
        $script:Roles = @('Contributor')
        Test-ApiAccess -Url 'https://backend.example' -Headers @{}
        try { Assert-ApiRole -RequiredRole admin; throw 'Contributor accepted as admin' }
        catch { if ($_.Exception.Message -notlike "*requires the 'admin'*") { throw } }
        $script:Roles = @('Admin')
        Test-ApiAccess -Url 'https://backend.example' -Headers @{}
        Assert-ApiRole -RequiredRole admin
    """)


def test_sql_readiness_retries_503_and_forwards_credentials():
    run_powershell("""
        $script:Calls = 0
        function Invoke-RestMethod {
            param($Headers, $StatusCodeVariable)
            if ($Headers['X-Admin-Api-Key'] -ne 'test-key') { throw 'Credentials not forwarded' }
            $script:Calls++
            Set-Variable -Name $StatusCodeVariable -Value $(if ($script:Calls -eq 1) { 503 } else { 200 }) -Scope 1
            return @{ checks = @{ sql = $(if ($script:Calls -eq 1) { 'unavailable' } else { 'ok' }) } }
        }
        if (-not (Wait-ForBackendSqlHealthy -BackendUrl 'https://backend.example' `
            -Headers @{ 'X-Admin-Api-Key' = 'test-key' } -TimeoutSec 2 -PollIntervalSec 1)) {
            throw 'SQL never became ready'
        }
        if ($script:Calls -ne 2) { throw 'Readiness was not retried' }
    """)


@pytest.mark.parametrize("status", [401, 403])
def test_sql_readiness_stops_immediately_on_access_denial(status):
    run_powershell(f"""
        $script:Calls = 0
        function Invoke-RestMethod {{
            param($StatusCodeVariable)
            $script:Calls++
            Set-Variable -Name $StatusCodeVariable -Value {status} -Scope 1
        }}
        try {{
            Wait-ForBackendSqlHealthy -BackendUrl 'https://backend.example' -Headers @{{}} `
                -TimeoutSec 2 -PollIntervalSec 1
            throw 'Denied health accepted'
        }} catch {{ if ($_.Exception.Message -notlike '*HTTP {status}*') {{ throw }} }}
        if ($script:Calls -ne 1) {{ throw 'Access denial was retried' }}
    """)


def test_sql_readiness_timeout_is_fatal():
    run_powershell("""
        function Invoke-RestMethod {
            param($StatusCodeVariable)
            Set-Variable -Name $StatusCodeVariable -Value 503 -Scope 1
            return @{ checks = @{ sql = 'unavailable' } }
        }
        try {
            Wait-ForBackendSqlHealthy -BackendUrl 'https://backend.example' -Headers @{} `
                -TimeoutSec 2 -PollIntervalSec 1
            throw 'SQL failure accepted'
        } catch { if ($_.Exception.Message -notlike '*Setup stopped before changing data*') { throw } }
    """)


def test_setup_stops_before_data_changes_when_sql_is_unavailable():
    run_powershell("""
        $projectRoot = (Get-Item $env:SETUP_SCRIPT).Directory.Parent.Parent.Parent.FullName
        $BackendUrl = 'https://backend.example'
        $UseSampleData = $true
        function Get-DeployValue {
            param($Name)
            if ($Name -eq 'ADMIN_API_KEY') { return 'test-key' }
            return ''
        }
        function Invoke-RestMethod {
            param($Uri, $StatusCodeVariable)
            if ($Uri -like '*/api/auth/me') {
                Set-Variable -Name $StatusCodeVariable -Value 200 -Scope 1
                return @{ roles = @('Admin') }
            }
            if ($Uri -notlike '*/api/health') { throw 'Data mutation attempted before SQL ready' }
            Set-Variable -Name $StatusCodeVariable -Value 503 -Scope 1
            return @{ checks = @{ sql = 'unavailable' } }
        }
        try {
            foreach ($statement in $ast.EndBlock.Statements) {
                if ($statement -isnot [System.Management.Automation.Language.FunctionDefinitionAst] -and
                    -not $statement.Extent.Text.StartsWith('$projectRoot =')) {
                    . ([scriptblock]::Create($statement.Extent.Text))
                }
                if ($statement.Extent.Text.StartsWith('if ($requiresDatabaseReadiness)')) { break }
            }
            throw 'SQL failure accepted'
        } catch { if ($_.Exception.Message -notlike '*Setup stopped before changing data*') { throw } }
    """)


def test_cosmos_readiness_does_not_require_sql():
    run_powershell("""
        function Invoke-RestMethod {
            param($StatusCodeVariable)
            Set-Variable -Name $StatusCodeVariable -Value 503 -Scope 1
            return @{ checks = @{ sql = 'unavailable'; cosmos = 'ok' } }
        }
        if (-not (Wait-ForBackendSqlHealthy -BackendUrl 'https://backend.example' -Headers @{} `
            -DatabaseProvider cosmos -TimeoutSec 1 -PollIntervalSec 1)) { throw 'Cosmos rejected' }
    """)


@pytest.mark.parametrize(
    ("url", "provider", "configured", "expected"),
    [
        ("http://localhost:8000", "sql", False, False),
        ("http://127.0.0.1:8000", "sql", False, False),
        ("http://[::1]:8000", "sql", False, False),
        ("http://localhost:8000", "sql", True, True),
        ("http://localhost:8000", "cosmos", False, False),
        ("http://localhost:8000", "cosmos", True, True),
        ("https://backend.example", "sql", False, True),
        ("https://backend.example", "cosmos", False, True),
    ],
)
def test_database_readiness_gate_preserves_memory_only_local_runs(url, provider, configured, expected):
    run_powershell(f"""
        $BackendUrl = '{url}'
        $backendUri = [Uri]$BackendUrl
        $headers = @{{}}
        $script:ReadinessCalls = 0
        function Get-DeployValue {{
            param($Name)
            if ($Name -eq 'DATABASE_PROVIDER') {{ return '{provider}' }}
            if ($Name -eq '{'AZURE_SQL_SERVER' if provider == 'sql' else 'AZURE_COSMOS_ENDPOINT'}') {{
                return '{'configured-endpoint' if configured else ''}'
            }}
            return ''
        }}
        function Wait-ForBackendSqlHealthy {{
            param($BackendUrl, $Headers, $DatabaseProvider)
            if ($DatabaseProvider -ne '{provider}') {{ throw 'Wrong provider checked' }}
            $script:ReadinessCalls++
        }}
        $started = $false
        foreach ($statement in $ast.EndBlock.Statements) {{
            if ($statement.Extent.Text.StartsWith('$databaseProvider =')) {{ $started = $true }}
            if ($started) {{ . ([scriptblock]::Create($statement.Extent.Text)) }}
            if ($started -and $statement.Extent.Text.StartsWith('if ($requiresDatabaseReadiness)')) {{ break }}
        }}
        if ($script:ReadinessCalls -ne {int(expected)}) {{ throw 'Incorrect readiness gate' }}
    """)


def test_incomplete_upload_registration_is_fatal():
    run_powershell("""
        function Invoke-RestMethod { return @{ files = 0 } }
        try {
            Confirm-UploadRegistered -BackendUrl 'https://backend.example' -Headers @{} `
                -ExpectedFiles @('file.pdf') -TimeoutSec 1 -PollIntervalSec 1
            throw 'Incomplete upload accepted'
        } catch { if ($_.Exception.Message -notlike '*Setup did not complete*') { throw } }
    """)


def load_seed_main():
    path = SCRIPTS / "seed-sample-data.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    namespace = {
        "os": os, "sys": sys,
        "SEARCH_ENDPOINT": "https://search.example", "SQL_SERVER": "",
        "COSMOS_ENDPOINT": "", "SEARCH_DATA_FILE": "search.json",
        "PROCESSED_DATA_FILE": "processed.json", "KEY_PHRASES_FILE": "phrases.json",
        "INDEX_NAME": "index", "COSMOS_DATABASE": "database",
        "upload_search_data": Mock(),
    }
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("credential", ["ADMIN_API_KEY", "KM_API_ACCESS_TOKEN"])
def test_seed_backend_notification_uses_selected_credentials(credential, monkeypatch):
    import urllib.request

    namespace = load_seed_main()
    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("KM_API_ACCESS_TOKEN", "")
    monkeypatch.setenv(credential, "test-credential")
    with patch("os.path.exists", return_value=True), patch.object(urllib.request, "urlopen") as urlopen:
        namespace["main"]()
    request = urlopen.call_args.args[0]
    header = "X-admin-api-key" if credential == "ADMIN_API_KEY" else "Authorization"
    value = "test-credential" if credential == "ADMIN_API_KEY" else "Bearer test-credential"
    assert request.get_header(header) == value


def test_seed_search_permission_failure_exits_unsuccessfully():
    namespace = load_seed_main()
    namespace["upload_search_data"].side_effect = PermissionError("Access denied")
    with patch("os.path.exists", return_value=True), pytest.raises(SystemExit) as error:
        namespace["main"]()
    assert error.value.code == 1


@pytest.mark.parametrize("partial_failure", [False, True])
def test_seed_search_document_results_control_completion(partial_failure):
    import urllib.request

    namespace = load_seed_main()
    path = SCRIPTS / "seed-sample-data.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upload = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upload_search_data"
    )
    search_client = Mock()
    search_client.upload_documents.return_value = [
        Mock(succeeded=True, key="first"),
        Mock(succeeded=not partial_failure, key="second", error_message="Invalid document"),
    ]
    namespace.update({
        "load_json": Mock(return_value=[{"id": "first"}, {"id": "second"}]),
        "SearchClient": Mock(return_value=search_client), "credential": Mock(),
        "COSMOS_ENDPOINT": "https://cosmos.example",
        "upload_processed_data": Mock(), "upload_key_phrases": Mock(),
    })
    exec(compile(ast.Module(body=[upload], type_ignores=[]), str(path), "exec"), namespace)
    with patch("os.path.exists", return_value=True), patch.dict(os.environ, {"ADMIN_API_KEY": "test-key"}):
        with patch.object(urllib.request, "urlopen") as refresh:
            if partial_failure:
                with pytest.raises(SystemExit) as error:
                    namespace["main"]()
                assert error.value.code == 1
                namespace["upload_processed_data"].assert_not_called()
                namespace["upload_key_phrases"].assert_not_called()
                refresh.assert_not_called()
            else:
                namespace["main"]()
                namespace["upload_processed_data"].assert_called_once()
                namespace["upload_key_phrases"].assert_called_once()
                refresh.assert_called_once()


def test_seed_sql_permission_failure_stops_before_search_upload():
    namespace = load_seed_main()
    namespace["SQL_SERVER"] = "mock-server"
    namespace["SQL_DATABASE"] = "mock-database"
    namespace["credential"] = Mock()
    namespace["credential"].get_token.return_value.token = "test-sql-token"
    pyodbc = Mock()
    pyodbc.connect.side_effect = PermissionError("SQL permission denied")
    with patch("os.path.exists", return_value=True), patch.dict("sys.modules", {"pyodbc": pyodbc}):
        with pytest.raises(SystemExit) as error:
            namespace["main"]()
    assert error.value.code == 1
    namespace["upload_search_data"].assert_not_called()


def test_seed_notification_access_denial_exits_unsuccessfully(monkeypatch):
    import urllib.error
    import urllib.request

    namespace = load_seed_main()
    monkeypatch.setenv("ADMIN_API_KEY", "test-key")
    denial = urllib.error.HTTPError("https://backend.example", 403, "Forbidden", {}, None)
    with patch("os.path.exists", return_value=True):
        with patch.object(urllib.request, "urlopen", side_effect=denial):
            with pytest.raises(SystemExit) as error:
                namespace["main"]()
    assert error.value.code == 1


@pytest.mark.parametrize("filename", ["connect-data.py", "seed-sample-data.py"])
def test_targeted_child_scripts_do_not_reload_stale_local_env(filename, tmp_path, monkeypatch):
    path = SCRIPTS / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))
    load_env = next(node for node in tree.body if isinstance(node, ast.If))
    env_file = tmp_path / ".env"
    env_file.write_text("AZURE_SQL_SERVER=wrong-server\n")
    monkeypatch.delenv("AZURE_SQL_SERVER", raising=False)
    monkeypatch.setenv("KM_SKIP_LOCAL_ENV", "1")
    namespace = {"os": os, "env_path": str(env_file)}
    exec(compile(ast.Module(body=[load_env], type_ignores=[]), str(path), "exec"), namespace)
    assert "AZURE_SQL_SERVER" not in os.environ


@pytest.mark.parametrize("filename", ["setup-agent.ps1", "connect-data.ps1"])
def test_child_agent_settings_access_failure_is_not_reset_to_success(filename, tmp_path):
    run_powershell(f"""
        $projectRoot = '{tmp_path}'
        $resourceGroup = 'target-rg'
        $apiAppName = 'api-target'
        $script:Values = @{{
            RESOURCE_GROUP_NAME = $resourceGroup; API_APP_NAME = $apiAppName
            AGENT_NAME_CHAT = 'chat'; AGENT_NAME_TITLE = 'title'; USE_SQL = 'true'
        }}
        function Get-AzdEnvValue {{ param($Name); return $script:Values[$Name] }}
        function az {{ $global:LASTEXITCODE = 1 }}
        try {{
            if (Get-Command Sync-AgentSettingsToApi -ErrorAction SilentlyContinue) {{
                Sync-AgentSettingsToApi -ProjectRoot $projectRoot
            }} else {{
                $global:LASTEXITCODE = 0
                $sync = $ast.EndBlock.Statements | Where-Object {{
                    $_.Extent.Text.StartsWith('if ($LASTEXITCODE -eq 0)')
                }}
                if (-not $sync) {{ throw 'Agent settings block not found' }}
                . ([scriptblock]::Create($sync.Extent.Text))
            }}
            throw 'Permission failure accepted'
        }} catch {{ if ($_.Exception.Message -notlike '*App Service configuration permissions*') {{ throw }} }}
    """, filename)


def notify_connected_backend():
    path = SCRIPTS / "connect-data.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    start = next(
        i for i, node in enumerate(main.body)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "backend_url" for target in node.targets
        )
    )
    namespace = {
        "os": os, "sys": sys, "json": json,
        "config": {"name": "Source", "source_type": "azure_search"},
    }
    exec(compile(ast.Module(body=main.body[start:start + 2], type_ignores=[]), str(path), "exec"), namespace)


@pytest.mark.parametrize("credential", ["ADMIN_API_KEY", "KM_API_ACCESS_TOKEN"])
def test_connected_backend_notification_uses_selected_credentials(credential, monkeypatch):
    import urllib.request

    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("KM_API_ACCESS_TOKEN", "")
    monkeypatch.setenv(credential, "test-credential")
    with patch.object(urllib.request, "urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.status = 200
        notify_connected_backend()
    request = urlopen.call_args.args[0]
    header = "X-admin-api-key" if credential == "ADMIN_API_KEY" else "Authorization"
    value = "test-credential" if credential == "ADMIN_API_KEY" else "Bearer test-credential"
    assert request.get_header(header) == value


def test_connected_backend_notification_denial_is_fatal(monkeypatch):
    import urllib.error
    import urllib.request

    monkeypatch.setenv("ADMIN_API_KEY", "test-key")
    denial = urllib.error.HTTPError("https://backend.example", 401, "Unauthorized", {}, None)
    with patch.object(urllib.request, "urlopen", side_effect=denial):
        with pytest.raises(SystemExit) as error:
            notify_connected_backend()
    assert error.value.code == 1


@pytest.fixture
def sql_role_setup():
    path = SCRIPTS / "add_user_scripts" / "assign_sql_roles.py"
    spec = importlib.util.spec_from_file_location("assign_sql_roles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    conn = Mock()
    module.connect_with_token = Mock(return_value=conn)
    module.AzureCliCredential = Mock()
    return module, conn, conn.cursor.return_value


def sql_assignment():
    return {
        "principalId": "30754929-199a-4262-af83-526893bc80e3",
        "displayName": "api-test",
        "role": "db_datareader",
        "isServicePrincipal": True,
    }


def test_sql_roles_reject_existing_object_id_sid(sql_role_setup, capsys):
    module, conn, cursor = sql_role_setup
    cursor.fetchone.return_value = (
        uuid.UUID("1e4a6cd6-e75a-4dac-ac35-13285ca54ae4").bytes_le, "E",
    )
    assert module.assign_sql_roles("server", "database", [sql_assignment()]) == 1
    assert "wrong SID/type" in capsys.readouterr().err
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    assert cursor.execute.call_count == 1
    conn.close.assert_called_once()


@pytest.mark.parametrize("failure_statement", ["CREATE USER", "ALTER ROLE"])
def test_sql_grant_failures_roll_back_and_exit_unsuccessfully(sql_role_setup, failure_statement):
    module, conn, cursor = sql_role_setup
    cursor.fetchone.side_effect = [None, (0,)]

    def execute(statement, *parameters):
        if statement.startswith(failure_statement):
            raise module.pyodbc.Error("42000", "SQL permission denied")

    cursor.execute.side_effect = execute
    assert module.assign_sql_roles("server", "database", [sql_assignment()]) == 1
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_sql_roles_create_client_id_mapping_and_commit(sql_role_setup):
    module, conn, cursor = sql_role_setup
    assignment = sql_assignment()
    cursor.fetchone.side_effect = [None, (0,)]
    assert module.assign_sql_roles("server", "database", [assignment]) == 0
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert (
        f"CREATE USER [api-test] WITH SID = {module.client_id_to_sid(assignment['principalId'])}, TYPE = E"
    ) in statements
    assert "ALTER ROLE [db_datareader] ADD MEMBER [api-test]" in statements
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_sql_roles_accept_correct_existing_identity_idempotently(sql_role_setup):
    module, conn, cursor = sql_role_setup
    assignment = sql_assignment()
    cursor.fetchone.side_effect = [
        (uuid.UUID(assignment["principalId"]).bytes_le, "E"), (1,),
    ]
    assert module.assign_sql_roles("server", "database", [assignment]) == 0
    assert not any(
        call.args[0].startswith(("CREATE USER", "ALTER ROLE"))
        for call in cursor.execute.call_args_list
    )
    conn.commit.assert_called_once()


def test_sql_roles_reject_incomplete_assignments(sql_role_setup):
    module, conn, cursor = sql_role_setup
    assert module.assign_sql_roles("server", "database", [{"displayName": "api-test"}]) == 1
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


@pytest.mark.parametrize("sqlstate", ["28000", "42000", "08001"])
def test_sql_connection_preserves_login_permission_and_network_errors(monkeypatch, sqlstate):
    path = SCRIPTS / "add_user_scripts" / "assign_sql_roles.py"
    spec = importlib.util.spec_from_file_location("sql_connection", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    credential = Mock()
    credential.get_token.return_value.token = "test-token"
    error = module.pyodbc.Error(sqlstate, "original SQL diagnostic")
    connect = Mock(side_effect=error)
    monkeypatch.setattr(module.pyodbc, "connect", connect)
    with pytest.raises(module.pyodbc.Error, match="original SQL diagnostic"):
        module.connect_with_token("server", "database", credential)
    connect.assert_called_once()


def test_sql_identity_resolution_uses_system_identity_client_id():
    run_powershell("""
        function az {
            $global:LASTEXITCODE = 0
            $command = $args -join ' '
            if ($command -like 'webapp config appsettings*') { return '' }
            if ($command -like 'webapp identity show*') {
                return '11111111-1111-1111-1111-111111111111'
            }
            if ($command -like 'ad sp show*') {
                return '22222222-2222-2222-2222-222222222222'
            }
            throw 'Unexpected command'
        }
        $identity = Resolve-SqlIdentity 'api-test' 'target-rg' ''
        if ($identity.ClientId -ne '22222222-2222-2222-2222-222222222222') {
            throw 'Object ID was used as client ID'
        }
    """, "setup-sql-roles.ps1")


@pytest.mark.parametrize("failed_graph", [True, False])
def test_sql_identity_resolution_never_falls_back_to_object_id(failed_graph):
    run_powershell(f"""
        function az {{
            $global:LASTEXITCODE = 0
            if (($args -join ' ') -like 'webapp config appsettings*') {{ return '' }}
            $global:LASTEXITCODE = {1 if failed_graph else 0}
            return ''
        }}
        try {{
            Resolve-SqlIdentity 'api-test' 'target-rg' '11111111-1111-1111-1111-111111111111'
            throw 'Object ID fallback accepted'
        }} catch {{
            if ($_.Exception.Message -notmatch 'Azure CLI command failed|Could not resolve') {{ throw }}
        }}
    """, "setup-sql-roles.ps1")
