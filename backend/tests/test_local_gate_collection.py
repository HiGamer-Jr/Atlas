"""Backend collection must not import a Windows-only script harness."""

import subprocess
import sys
from pathlib import Path


def test_backend_collection_does_not_require_windows_systemroot():
    # Initialize Windows asyncio first: removing SystemRoot at process startup
    # breaks Winsock itself and would obscure the collection regression.
    command = (
        "import asyncio,os,pytest; "
        "[os.environ.pop(n) for n in tuple(os.environ) if n.casefold()=='systemroot']; "
        "raise SystemExit(pytest.main(['--collect-only','-q','tests']))"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
