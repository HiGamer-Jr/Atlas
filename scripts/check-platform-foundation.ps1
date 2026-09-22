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
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        Invoke-FoundationCheck 'Backend tests (PostgreSQL required)' { uv run --frozen pytest }
        Invoke-FoundationCheck 'Backend lint' { uv run --frozen ruff check app tests alembic }
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
