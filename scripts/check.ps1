$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"

function Invoke-AtlasStep {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host ">> $Name"

    & $Action

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[FAIL] $Name"
        exit $LASTEXITCODE
    }

    Write-Host "[PASS] $Name"
}

Write-Host ""
Write-Host "========================================"
Write-Host " ATLAS - QUALITY GATE"
Write-Host "========================================"

Push-Location $root
try {
    Invoke-AtlasStep "Legacy Cargo.Ops syntax" {
        node --check .\legacy\cargo-ops-prototype\app.js
    }

    Invoke-AtlasStep "Static web preview" {
        if (-not (Test-Path .\web\index.html)) {
            throw "web/index.html not found. Run .\scripts\publish-web-preview.ps1."
        }

        $index = Get-Content -Raw .\web\index.html
        if ($index -notmatch "Atlas Supply") {
            throw "web/index.html does not identify Atlas Supply."
        }

        if ($index -match 'src="/assets|href="/assets') {
            throw "web/index.html uses absolute asset paths."
        }

        if ($index -match 'type="module"') {
            throw "web/index.html uses module scripts, which Chrome blocks from file:// previews."
        }

        if ($index -match "crossorigin") {
            throw "web/index.html contains crossorigin attributes that are not needed for local previews."
        }

        if ($index -notmatch '<script defer src="\./assets/[^"]+\.js"></script>') {
            throw "web/index.html must defer the app script so #root exists before React starts."
        }
    }
}
finally {
    Pop-Location
}

Push-Location $frontend
try {
    Invoke-AtlasStep "Frontend tests" {
        npm test
    }

    Invoke-AtlasStep "Frontend lint" {
        npm run lint
    }

    Invoke-AtlasStep "Frontend build" {
        npm run build
    }
}
finally {
    Pop-Location
}

Push-Location $backend
try {
    Invoke-AtlasStep "Backend tests" {
        uv run pytest
    }

    Invoke-AtlasStep "Backend lint" {
        uv run ruff check app tests
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "========================================"
Write-Host " ATLAS QUALITY GATE: PASS"
Write-Host "========================================"
