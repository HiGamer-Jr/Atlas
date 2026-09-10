$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$dist = Join-Path $frontend "dist"
$web = Join-Path $root "web"

function Assert-PathInside {
    param(
        [string]$PathToCheck,
        [string]$ExpectedRoot
    )

    $resolvedRoot = [System.IO.Path]::GetFullPath($ExpectedRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($PathToCheck)

    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path outside workspace: $resolvedPath"
    }
}

Assert-PathInside -PathToCheck $web -ExpectedRoot $root

Push-Location $frontend
try {
    npm run build
}
finally {
    Pop-Location
}

if (-not (Test-Path $dist)) {
    throw "Build output not found: $dist"
}

if (Test-Path $web) {
    $webFullPath = [System.IO.Path]::GetFullPath($web)
    Assert-PathInside -PathToCheck $webFullPath -ExpectedRoot $root
    Remove-Item -LiteralPath $webFullPath -Recurse -Force
}

New-Item -ItemType Directory -Force $web | Out-Null
Copy-Item -Path (Join-Path $dist "*") -Destination $web -Recurse -Force

$indexPath = Join-Path $web "index.html"
$index = Get-Content -Raw $indexPath
$index = $index.Replace('<script type="module" crossorigin src=', '<script defer src=')
$index = $index.Replace('<link rel="stylesheet" crossorigin href=', '<link rel="stylesheet" href=')
Set-Content -Path $indexPath -Value $index -Encoding UTF8

Write-Host "Atlas web preview published to: $web"
