#requires -Version 5.1
[CmdletBinding()]
param([string]$PostgresRoot=$env:HIATLAS_TEST_POSTGRES_ROOT)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'testdb.psm1') -ErrorAction Stop
$failed=$false
$started=$false
try {
    Start-HiAtlasTestDb -PostgresRoot $PostgresRoot
    $started=$true
    Assert-HiAtlasTestDb
    & (Join-Path $PSScriptRoot 'check-platform-foundation.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Canonical quality gate failed.' }
} catch {
    Write-Host '[FAIL] Local quality gate failed; see the failed step above.'
    $failed=$true
} finally {
    # Do not stop a cluster owned by an earlier manual workflow if start refused.
    if ($started) {
        try { Stop-HiAtlasTestDb } catch {
            Write-Host '[FAIL] Cleanup refused. Keep this process open for investigation.'
            $failed=$true
        }
    }
}
if ($failed) { exit 1 }
Write-Host '[PASS] HiAtlas local quality gate and disposable database cleanup'
exit 0
