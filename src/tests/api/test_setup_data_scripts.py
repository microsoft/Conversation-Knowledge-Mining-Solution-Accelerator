import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

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
