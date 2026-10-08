#requires -Version 5.1
# Optional real lifecycle regression. Always creates its own disposable cluster.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PostgresRoot)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$names=@('TEST_DATABASE_OWNER_URL','TEST_DATABASE_RUNTIME_URL','HIATLAS_TEST_DATABASE_RESET','HIATLAS_TEST_RECOVERY_DATABASE_URL','RECOVERY_DATABASE_ROLE')
$before=@{}
foreach($name in $names){$before[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$started=$false
$ownedRoot=$null
try {
    & (Join-Path $root 'scripts/testdb-start.ps1') -PostgresRoot $PostgresRoot
    $started=$true
    $modulePath=Join-Path $root 'scripts/testdb.psm1'
    $module=Get-Module | Where-Object { $_.Path -eq $modulePath }
    if(-not $module){throw 'Owned module missing'}
    & $module { Assert-HiAtlasTestDb }
    $ownedRoot=& $module { $script:ActiveCluster.Root }
    if(Test-Path -LiteralPath (Join-Path $ownedRoot 'initdb-password')){throw 'Temporary initdb password was retained'}
    $oldUrl=$env:TEST_DATABASE_OWNER_URL
    $env:TEST_DATABASE_OWNER_URL='postgresql+psycopg://wrong:sentinel@127.0.0.1:1/unrelated_test'
    $denied=$false
    try { & $module { Assert-HiAtlasTestDb } } catch { $denied=$true }
    $env:TEST_DATABASE_OWNER_URL=$oldUrl
    if(-not $denied){throw 'Changed environment was accepted'}
    # A duplicate start must not replace/stop the first workflow.
    $denied=$false
    try { & $module { param($distribution) Start-HiAtlasTestDb -PostgresRoot $distribution } $PostgresRoot }
    catch { $denied=$_.Exception.Message -like 'This process already owns*' }
    if(-not $denied){throw 'Duplicate start was accepted'}
    & $module { Assert-HiAtlasTestDb }
    & $module {
        $s=$script:ActiveCluster
        $null=Invoke-OwnedSql $s 'hiatlas_test_owner' $s.Passwords.hiatlas_test_owner $s.Database "COMMENT ON DATABASE hiatlas_foundation_test IS NULL;"
    }
    $denied=$false
    try { & $module { Assert-HiAtlasTestDb } } catch { $denied=$true }
    if(-not $denied){throw 'Missing disposable marker was accepted'}
    $denied=$false
    try { & $module { Stop-HiAtlasTestDb } } catch { $denied=$true }
    if(-not $denied -or -not (Test-Path -LiteralPath $ownedRoot)){throw 'Cleanup proceeded without marker'}
    # Restore only our deliberately modified marker to finish this controlled test.
    & $module {
        $s=$script:ActiveCluster
        Assert-OwnedServer $s
        $null=Invoke-OwnedSql $s 'hiatlas_test_owner' $s.Passwords.hiatlas_test_owner $s.Database "COMMENT ON DATABASE hiatlas_foundation_test IS 'hiatlas-disposable-test-db';"
    }
} finally {
    if($started){ & (Join-Path $root 'scripts/testdb-stop.ps1') }
}
if($ownedRoot -and (Test-Path -LiteralPath $ownedRoot)){throw 'Owned cluster directory remained after cleanup'}
foreach($name in $names){
    if([Environment]::GetEnvironmentVariable($name,'Process') -cne $before[$name]){throw 'Previous process environment not restored'}
}
Write-Host '[PASS] Real disposable lifecycle: roles, readiness, environment refusal, duplicate start, marker refusal, safe cleanup and environment restore'
