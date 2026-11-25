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
