"""Run Windows script safety checks without any PostgreSQL installation."""

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/testdb.psm1"
POWERSHELL = (
    Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
)


def run_module(body):
    path = str(MODULE).replace("'", "''")
    command = f"$ErrorActionPreference='Stop'; $m=Import-Module '{path}' -PassThru; & $m {{ {body} }}"
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-EncodedCommand",
            base64.b64encode(command.encode("utf-16-le")).decode(),
        ],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=45,
        check=False,
    )


@pytest.mark.parametrize(
    "name",
    [
        "production",
        "hiatlas_demo",
        "a_test;DROP DATABASE x",
        "../a_test",
        "a_test?host=real",
    ],
)
def test_database_names_fail_closed(name):
    result = run_module(f"Assert-TestDatabaseName '{name}'")
    assert result.returncode != 0
    assert "_test" in result.stderr


def test_valid_disposable_database_name():
    result = run_module("Assert-TestDatabaseName 'hiatlas_foundation_test'; 'accepted'")
    assert result.returncode == 0, result.stderr
    assert "accepted" in result.stdout


@pytest.mark.parametrize("target", ["parent", "wrong-name", "outside", "traversal"])
def test_cleanup_refuses_unowned_or_unsafe_paths(tmp_path, target):
    parent = str(tmp_path).replace("'", "''")
    paths = {
        "parent": tmp_path,
        "wrong-name": tmp_path / "hiatlas-demo",
        "outside": tmp_path.parent / "hiatlas-testdb-00000000000000000000000000000000",
        "traversal": tmp_path
        / ".."
        / "hiatlas-testdb-00000000000000000000000000000000",
    }
    root = str(paths[target]).replace("'", "''")
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("preserve")
    result = run_module(
        f"$s=@{{TempParent='{parent}';Root='{root}';Id='00000000000000000000000000000000'}}; Assert-OwnedTestRoot $s"
    )
    assert result.returncode != 0
    assert sentinel.read_text() == "preserve"
    assert "Unsafe" in result.stderr or "Ownership" in result.stderr


@pytest.mark.parametrize(
    "missing",
    [
        "bin/postgres.exe",
        "bin/initdb.exe",
        "bin/pg_ctl.exe",
        "bin/pg_isready.exe",
        "bin/psql.exe",
        "share/postgres.bki",
    ],
)
def test_incomplete_portable_distribution_is_rejected(tmp_path, missing):
    for name in (
        "bin/postgres.exe",
        "bin/initdb.exe",
        "bin/pg_ctl.exe",
        "bin/pg_isready.exe",
        "bin/psql.exe",
        "share/postgres.bki",
    ):
        if name != missing:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    path = str(tmp_path).replace("'", "''")
    result = run_module(f"Assert-PortableDistribution '{path}'")
    assert result.returncode != 0
    assert "incomplete" in result.stderr.lower()


def test_missing_distribution_does_not_set_env_or_create_cluster(tmp_path):
    path = str(tmp_path / "absent").replace("'", "''")
    result = run_module(
        "$env:TEST_DATABASE_OWNER_URL='sentinel-secret'; "
        f"try {{ Start-HiAtlasTestDb -PostgresRoot '{path}' }} "
        "catch { if($env:TEST_DATABASE_OWNER_URL -ne 'sentinel-secret'){throw 'env changed'}; 'safe refusal' }"
    )
    assert result.returncode == 0, result.stderr
    assert "safe refusal" in result.stdout
    assert "sentinel-secret" not in result.stdout + result.stderr
    assert not list(tmp_path.iterdir())


def test_stop_without_owned_state_preserves_foreign_environment():
    result = run_module(
        "$env:TEST_DATABASE_OWNER_URL='sentinel-secret'; Stop-HiAtlasTestDb; "
        "if($env:TEST_DATABASE_OWNER_URL -ne 'sentinel-secret'){throw 'modified external configuration'}; 'preserved'"
    )
    assert result.returncode == 0, result.stderr
    assert "sentinel-secret" not in result.stdout + result.stderr
    assert "preserved" in result.stdout


def native_ps_body(script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    exe = str(POWERSHELL).replace("'", "''")
    return f"-Executable '{exe}' -NativeArguments @('-NoProfile','-EncodedCommand','{encoded}')"


def test_native_failure_never_prints_output_or_password():
    invocation = native_ps_body("Write-Output 'sentinel-secret'; exit 23")
    result = run_module(f"Invoke-TestDbNative {invocation} -Label 'controlled failure'")
    assert result.returncode != 0
    assert "23" in result.stderr
    assert "sentinel-secret" not in result.stdout + result.stderr


def test_native_connection_environment_cannot_be_redirected():
    invocation = native_ps_body(
        "if($env:PGSERVICE){exit 21}; if($env:PGOPTIONS){exit 22}; 'isolated'"
    )
    result = run_module(
        "$env:PGSERVICE='sentinel-secret'; $env:PGOPTIONS='unsafe'; "
        f"$out=Invoke-TestDbNative {invocation} -Label 'env isolation'; "
        "if($out.Trim() -ne 'isolated'){throw 'wrong output'}; "
        "if($env:PGSERVICE -ne 'sentinel-secret'){throw 'parent env modified'}; 'isolated'"
    )
    assert result.returncode == 0, result.stderr
    assert "isolated" in result.stdout
    assert "sentinel-secret" not in result.stdout + result.stderr


def test_cleanup_refuses_junction_inside_owned_root(tmp_path):
    root = tmp_path / "hiatlas-testdb-00000000000000000000000000000000"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("preserve")
    path = str(root).replace("'", "''")
    destination = str(outside).replace("'", "''")
    result = run_module(
        f"New-Item -ItemType Junction -Path '{path}/link' -Target '{destination}' | Out-Null; Assert-NoReparseTree '{path}'"
    )
    try:
        assert result.returncode != 0
        assert "Reparse" in result.stderr
        assert (outside / "keep.txt").read_text() == "preserve"
    finally:
        if (root / "link").exists():
            os.rmdir(root / "link")


def test_native_detached_output_does_not_wait_for_inherited_pipe():
    exe = sys.executable.replace("'", "''")
    # Fast native parent exits immediately; a child holds its output pipe for 8s.
    probe = (
        'import subprocess,sys; subprocess.Popen([sys.executable,"-c",'
        '"import time; time.sleep(8)"],stdout=sys.stdout,stderr=sys.stderr)'
    )
    result = run_module(
        "$clock=[Diagnostics.Stopwatch]::StartNew(); "
        f"$null=Invoke-TestDbNative -Executable '{exe}' -NativeArguments @('-c','{probe}') "
        "-Label 'detached process' -DiscardOutput; "
        "if($clock.Elapsed.TotalSeconds -gt 4){throw 'waited for child pipe'}; 'bounded'"
    )
    assert result.returncode == 0, result.stderr
    assert "bounded" in result.stdout


@pytest.mark.parametrize("failure", ["", "pytest", "ruff", "npm-test"])
def test_local_aggregator_always_cleans_after_gate(tmp_path, failure):
    import shutil

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("check-local.ps1", "check-platform-foundation.ps1"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    # Resource boundary double: the real aggregate and canonical gate are unchanged.
    (scripts / "testdb.psm1").write_text(
        "function Start-HiAtlasTestDb { param($PostgresRoot); Set-Content -LiteralPath $env:LOCAL_GATE_RESOURCE -Value owned }\n"
        "function Assert-HiAtlasTestDb { if(-not(Test-Path -LiteralPath $env:LOCAL_GATE_RESOURCE)){throw 'not started'} }\n"
        "function Stop-HiAtlasTestDb { Remove-Item -LiteralPath $env:LOCAL_GATE_RESOURCE -ErrorAction Stop }\n"
        "Export-ModuleMember -Function Start-HiAtlasTestDb,Assert-HiAtlasTestDb,Stop-HiAtlasTestDb\n"
    )
    shim = tmp_path / "bin"
    shim.mkdir()
    for name in ("uv", "npm", "git"):
        body = "@echo off\n"
        if name == "uv":
            body += 'if "%3"=="%LOCAL_GATE_FAILURE%" exit /b 23\n'
        if name == "npm":
            body += 'if "%1"=="test" if "%LOCAL_GATE_FAILURE%"=="npm-test" exit /b 24\n'
        body += "exit /b 0\n"
        (shim / f"{name}.cmd").write_text(body)
    resource = tmp_path / "owned-resource"
    env = os.environ.copy()
    env.update(
        PATH=str(shim) + os.pathsep + env["PATH"],
        LOCAL_GATE_RESOURCE=str(resource),
        LOCAL_GATE_FAILURE=failure,
    )
    result = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts / "check-local.ps1"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=45,
        check=False,
    )
    assert (result.returncode == 0) == (failure == ""), result.stdout + result.stderr
    assert not resource.exists(), "cleanup did not run after canonical gate exit"
    assert ("[PASS] HiAtlas local" in result.stdout) == (failure == "")


def test_missing_distribution_reports_actionable_instruction_from_aggregate(tmp_path):
    result = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/check-local.ps1"),
            "-PostgresRoot",
            str(tmp_path / "absent"),
        ],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=45,
        check=False,
    )
    assert result.returncode != 0
    assert "HIATLAS_TEST_POSTGRES_ROOT" in result.stdout
    assert "No download" in result.stdout
    assert "[PASS]" not in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("seal", [None, "hiatlas-owned-cluster:wrong"])
def test_owned_root_still_requires_matching_ownership_seal(tmp_path, seal):
    identifier = "0" * 32
    root = tmp_path / f"hiatlas-testdb-{identifier}"
    root.mkdir()
    if seal is not None:
        (root / ".hiatlas-owned-cluster").write_text(seal)
    parent = str(tmp_path).replace("'", "''")
    path = str(root).replace("'", "''")
    result = run_module(
        f"Assert-OwnedTestRoot @{{Id='{identifier}';Root='{path}';TempParent='{parent}'}}"
    )
    assert result.returncode != 0
    assert "Ownership" in result.stderr
    assert root.exists()


@pytest.mark.parametrize(
    "stage", ["STARTING", "BOOTSTRAP", "DATABASE_CREATING", "READY"]
)
def test_stop_refuses_missing_pid_after_start_attempt(tmp_path, stage):
    identifier = "0" * 32
    root = tmp_path / f"hiatlas-testdb-{identifier}"
    root.mkdir()
    (root / "data").mkdir()
    (root / ".hiatlas-owned-cluster").write_text(f"hiatlas-owned-cluster:{identifier}")
    parent = str(tmp_path).replace("'", "''")
    path = str(root).replace("'", "''")
    result = run_module(
        f"$script:ActiveCluster=@{{Id='{identifier}';Root='{path}';TempParent='{parent}';Data='{path}/data';Stage='{stage}';PreviousEnvironment=@{{}}}}; "
        "$denied=$false; try {Stop-HiAtlasTestDb} catch {$denied=$true}; "
        f"if(-not $denied -or -not(Test-Path -LiteralPath '{path}')){{throw 'unproven process cleanup proceeded'}}; 'refused'"
    )
    assert result.returncode == 0, result.stderr
    assert "refused" in result.stdout
    assert root.exists()


def test_locked_initdb_password_aborts_instead_of_silently_continuing(tmp_path):
    identifier = "0" * 32
    root = tmp_path / f"hiatlas-testdb-{identifier}"
    root.mkdir()
    (root / ".hiatlas-owned-cluster").write_text(f"hiatlas-owned-cluster:{identifier}")
    (root / "initdb-password").write_text("sentinel-secret")
    parent = str(tmp_path).replace("'", "''")
    path = str(root).replace("'", "''")
    result = run_module(
        "Get-Command Remove-InitPassword -ErrorAction Stop | Out-Null; "
        f"$s=@{{Id='{identifier}';Root='{path}';TempParent='{parent}'}}; "
        f"$locked=[IO.File]::Open('{path}/initdb-password','Open','ReadWrite','None'); "
        "$denied=$false; try {try {Remove-InitPassword $s} catch {$denied=$true}} finally {$locked.Dispose()}; "
        "if(-not $denied){throw 'plaintext removal failure was ignored'}; 'refused'"
    )
    assert result.returncode == 0, result.stderr
    assert "refused" in result.stdout
    assert "sentinel-secret" not in result.stdout + result.stderr


def test_stop_uses_exit_status_without_waiting_for_inherited_daemon_pipe(tmp_path):
    identifier = "0" * 32
    root = tmp_path / f"hiatlas-testdb-{identifier}"
    root.mkdir()
    (root / "data").mkdir()
    (root / "data/postmaster.pid").write_text("controlled fixture")
    (root / ".hiatlas-owned-cluster").write_text(f"hiatlas-owned-cluster:{identifier}")
    parent = str(tmp_path).replace("'", "''")
    path = str(root).replace("'", "''")
    executable = sys.executable.replace("'", "''")
    probe = (
        f'import pathlib,subprocess,sys; pathlib.Path(r"{root / "data/postmaster.pid"}").unlink(); '
        'subprocess.Popen([sys.executable,"-c","import time; time.sleep(8)"],stdout=sys.stdout,stderr=sys.stderr)'
    )
    # SQL/server attestation is a resource boundary double for this synthetic
    # directory. The native helper, pipe handling and cleanup are real.
    result = run_module(
        "$originalNative=(Get-Item Function:Invoke-TestDbNative).ScriptBlock; "
        "function Assert-OwnedServer { param($State) Assert-OwnedTestRoot $State }; "
        "function Assert-TestConnections { param($State) Assert-OwnedTestRoot $State }; "
        "function Invoke-TestDbNative { param($Executable,$NativeArguments,$Label,[switch]$DiscardOutput); "
        f"& $originalNative -Executable '{executable}' -NativeArguments @('-c','{probe}') -Label $Label -DiscardOutput:$DiscardOutput }}; "
        f"$script:ActiveCluster=@{{Id='{identifier}';Root='{path}';TempParent='{parent}';Data='{path}/data';Bin='{path}/bin';Stage='READY';PreviousEnvironment=@{{}}}}; "
        "$clock=[Diagnostics.Stopwatch]::StartNew(); Stop-HiAtlasTestDb; "
        f"if(Test-Path -LiteralPath '{path}'){{throw 'stopped directory retained'}}; "
        "if($clock.Elapsed.TotalSeconds -gt 4){throw 'cleanup waited for inherited pipe'}; 'cleaned'"
    )
    assert result.returncode == 0, result.stderr
    assert "cleaned" in result.stdout
    assert not root.exists()
