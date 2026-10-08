$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-FoundationCheck {
    param([string]$Name, [scriptblock]$Action)
    Write-Host ">> $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed (exit $LASTEXITCODE)."
    }
}

try {
    # When started by the local helper, attest its exact cluster and environment first.
    $modulePath = Join-Path $PSScriptRoot 'testdb.psm1'
    $localDb = Get-Module | Where-Object { $_.Path -eq $modulePath }
    if ($localDb) { & $localDb { Assert-HiAtlasTestDb } }
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        Invoke-FoundationCheck 'Backend tests (PostgreSQL required)' { uv run --frozen pytest }
        Invoke-FoundationCheck 'Backend lint' { uv run --frozen ruff check app tests alembic }
        Invoke-FoundationCheck 'Windows local database safety tests' { uv run --frozen pytest ../scripts/tests/test_local_testdb_scripts.py }
        Invoke-FoundationCheck 'Windows local database test lint' { uv run --frozen ruff check ../scripts/tests/test_local_testdb_scripts.py }
    } finally { Pop-Location }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        Invoke-FoundationCheck 'Frontend tests' { npm.cmd test }
        Invoke-FoundationCheck 'Frontend lint' { npm.cmd run lint }
        Invoke-FoundationCheck 'Frontend build' { npm.cmd run build }
    } finally { Pop-Location }
    Push-Location $projectRoot
    try {
        Invoke-FoundationCheck 'Working diff' { git diff --check }
        Invoke-FoundationCheck 'Staged diff' { git diff --cached --check }
    } finally { Pop-Location }
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)"
    exit 1
}
Write-Host '[PASS] HiAtlas Phase Quality Gate'
exit 0
