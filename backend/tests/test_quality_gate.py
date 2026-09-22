"""Exercise gate exit codes using process-boundary shims, not text assertions."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Windows PowerShell gate process test"
)


@pytest.mark.parametrize(
    "failure,expected_last",
    [
        ("", "git diff --cached --check"),
        ("pytest", "uv run --frozen pytest"),
        ("ruff", "uv run --frozen ruff check app tests alembic"),
        ("npm-test", "npm test"),
    ],
)
def test_gate_stops_on_first_failed_command(tmp_path, failure, expected_last):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    shutil.copyfile(
        ROOT / "scripts/check-platform-foundation.ps1",
        scripts / "check-platform-foundation.ps1",
    )
    shim = tmp_path / "bin"
    shim.mkdir()
    log = tmp_path / "commands.log"
    for name in ("uv", "npm", "git"):
        body = f'@echo off\necho {name} %*>>"%GATE_TEST_LOG%"\n'
        if name == "uv":
            body += 'if "%3"=="%GATE_TEST_FAIL%" exit /b 23\n'
        if name == "npm":
            body += 'if "%1"=="test" if "%GATE_TEST_FAIL%"=="npm-test" exit /b 24\n'
        body += "exit /b 0\n"
        (shim / f"{name}.cmd").write_text(body)
    env = os.environ.copy()
    env.update(
        PATH=str(shim) + os.pathsep + env["PATH"],
        GATE_TEST_LOG=str(log),
        GATE_TEST_FAIL=failure,
    )
    powershell = str(
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts / "check-platform-foundation.ps1"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=60,
        check=False,
    )
    assert (result.returncode == 0) == (failure == ""), result.stdout + result.stderr
    commands = log.read_text().strip().splitlines()
    assert commands[-1].strip() == expected_last
