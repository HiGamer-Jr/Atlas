# State and credentials remain private to this module in the current process.
Set-StrictMode -Version Latest
$script:ActiveCluster = $null
$script:EnvironmentNames = @('TEST_DATABASE_OWNER_URL','TEST_DATABASE_RUNTIME_URL','HIATLAS_TEST_DATABASE_RESET','HIATLAS_TEST_RECOVERY_DATABASE_URL','RECOVERY_DATABASE_ROLE')

function Assert-TestDatabaseName {
    param([string]$Name)
    if ($Name -cnotmatch '^[A-Za-z_][A-Za-z0-9_]*_test$') { throw 'Only a simple database name ending in _test is allowed.' }
}
function Assert-NoReparsePath {
    param([string]$Path)
    if (-not [IO.Path]::IsPathRooted($Path) -or $Path.StartsWith('\\')) { throw 'Unsafe path: local absolute paths required.' }
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse points forbidden in owned paths.' }
        }
        $current = [IO.Path]::GetDirectoryName($current)
    }
}
function Assert-NoReparseTree {
    param([string]$Path)
    Assert-NoReparsePath $Path
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point; cleanup refused.' }
        if ($item.PSIsContainer) { Assert-NoReparseTree $item.FullName }
    }
}
function Assert-OwnedTestRoot {
    param($State)
    $root = [IO.Path]::GetFullPath($State.Root).TrimEnd('\')
    $parent = [IO.Path]::GetFullPath($State.TempParent).TrimEnd('\')
    if ($State.Id -cnotmatch '^[a-f0-9]{32}$' -or $State.Root -match '(^|[\\/])\.\.([\\/]|$)' -or
        [IO.Path]::GetDirectoryName($root) -ine $parent -or [IO.Path]::GetFileName($root) -cne ('hiatlas-testdb-' + $State.Id)) {
        throw 'Unsafe cleanup directory; only the exact owned temporary child is allowed.'
    }
    Assert-NoReparsePath $root
    $seal = Join-Path $root '.hiatlas-owned-cluster'
    if (-not (Test-Path -LiteralPath $seal -PathType Leaf)) { throw 'Ownership proof missing; cleanup refused.' }
    Assert-NoReparsePath $seal
    if ([IO.File]::ReadAllText($seal) -cne ('hiatlas-owned-cluster:' + $State.Id)) { throw 'Ownership proof mismatch; cleanup refused.' }
}
function Assert-PortableDistribution {
    param([string]$PostgresRoot)
    if (-not $PostgresRoot -or -not [IO.Path]::IsPathRooted($PostgresRoot) -or -not (Test-Path -LiteralPath $PostgresRoot -PathType Container)) {
        throw 'PostgreSQL portable unavailable. Extract PostgreSQL 18.6 and pass -PostgresRoot or set HIATLAS_TEST_POSTGRES_ROOT. No download is performed.'
    }
    foreach ($relative in @('bin/postgres.exe','bin/initdb.exe','bin/pg_ctl.exe','bin/pg_isready.exe','bin/psql.exe','share/postgres.bki')) {
        if (-not (Test-Path -LiteralPath (Join-Path $PostgresRoot $relative) -PathType Leaf)) { throw "PostgreSQL portable distribution is incomplete: missing $relative. Extract the complete distribution; no download is performed." }
    }
    return [IO.Path]::GetFullPath($PostgresRoot)
}
function ConvertTo-NativeArgument {
    param([string]$Value)
    if ($Value -match '[\r\n\x00]') { throw 'Invalid native argument.' }
    # CommandLineToArgvW quoting for paths with spaces and trailing backslashes.
    $quoted = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '$1$1')
    return '"' + $quoted + '"'
}
function Invoke-TestDbNative {
    param([string]$Executable,[string[]]$NativeArguments,[string]$Label,[string]$InputText='',[hashtable]$ChildEnvironment=@{},[int]$TimeoutSeconds=60,[switch]$DiscardOutput)
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.Arguments = ($NativeArguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    # Clear libpq overrides in the child only; they must not redirect connections.
    foreach ($name in @($info.EnvironmentVariables.Keys)) { if ($name -like 'PG*') { $info.EnvironmentVariables.Remove($name) } }
    foreach ($name in $ChildEnvironment.Keys) { $info.EnvironmentVariables[$name] = $ChildEnvironment[$name] }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    $exitCode = $null
    try {
        $null = $process.Start()
        # Never start asynchronous pipe readers for a detached daemon launcher.
        # Disposing a pending reader can itself wait for the daemon on Windows.
        if (-not $DiscardOutput) {
            $stdout = $process.StandardOutput.ReadToEndAsync()
            $stderr = $process.StandardError.ReadToEndAsync()
        }
        if ($InputText) { $process.StandardInput.Write($InputText) }
        $process.StandardInput.Close()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) { $process.Kill(); throw 'Native timeout.' }
        $exitCode = $process.ExitCode
        # pg_ctl start can leave pipe handles inherited by postgres on Windows.
        # Its exit code is authoritative; callers needing SQL output still bound drainage.
        if ($DiscardOutput) { if ($exitCode -ne 0) { throw 'Native command failed.' }; return '' }
        if (-not $stdout.Wait(2000) -or -not $stderr.Wait(2000)) { throw 'Native output drainage timed out.' }
        $output = $stdout.GetAwaiter().GetResult()
        $null = $stderr.GetAwaiter().GetResult()
        if ($exitCode -ne 0) { throw 'Native command failed.' }
        return $output
    } catch { throw "$Label failed (exit $exitCode); native diagnostics withheld." }
    finally { $process.Dispose() }
}
function New-TestSecret {
    $bytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
}
function Remove-InitPassword {
    param($State)
    Assert-OwnedTestRoot $State
    $passwordFile = Join-Path $State.Root 'initdb-password'
    Assert-NoReparsePath $passwordFile
    if (Test-Path -LiteralPath $passwordFile) {
        Remove-Item -LiteralPath $passwordFile -ErrorAction Stop
    }
    if (Test-Path -LiteralPath $passwordFile) { throw 'Temporary password removal failed; startup refused.' }
}
function Get-FreeLoopbackPort {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,0)
    try { $listener.Start(); return $listener.LocalEndpoint.Port } finally { $listener.Stop() }
}
function Set-PrivateDirectoryAcl {
    param([string]$Path)
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Assert-OwnedServer {
    param($State)
    Assert-OwnedTestRoot $State
    $pidFile = Join-Path $State.Data 'postmaster.pid'
    Assert-NoReparsePath $pidFile
    $lines = [IO.File]::ReadAllLines($pidFile)
    if ($lines.Length -lt 6 -or [IO.Path]::GetFullPath($lines[1]).TrimEnd('\') -ine $State.Data -or $lines[3] -ne [string]$State.Port -or $lines[5] -ne '127.0.0.1') {
        throw 'Owned PostgreSQL identity mismatch; access/cleanup refused.'
    }
    $serverProcess = Get-Process -Id ([int]$lines[0]) -ErrorAction Stop
    $epoch = [DateTimeOffset]::FromUnixTimeSeconds([long]$lines[2]).UtcDateTime
    if ($serverProcess.Path -ine (Join-Path $State.Bin 'postgres.exe') -or [Math]::Abs(($serverProcess.StartTime.ToUniversalTime() - $epoch).TotalSeconds) -gt 3) {
        throw 'Owned PostgreSQL process mismatch; cleanup refused.'
    }
}
function Invoke-OwnedSql {
    param($State,[string]$Role,[string]$Password,[string]$Database,[string]$Sql)
    Assert-OwnedServer $State
    return Invoke-TestDbNative -Executable (Join-Path $State.Bin 'psql.exe') -Label 'Disposable PostgreSQL SQL' `
        -NativeArguments @('-X','-w','-h','127.0.0.1','-p',[string]$State.Port,'-U',$Role,'-d',$Database,'-v','ON_ERROR_STOP=1','-A','-t') `
        -ChildEnvironment @{PGPASSWORD=$Password;PGCONNECT_TIMEOUT='5';PGCLIENTENCODING='UTF8'} -InputText $Sql
}
function Assert-TestConnections {
    param($State)
    Assert-TestDatabaseName $State.Database
    Assert-OwnedServer $State
    $null = Invoke-TestDbNative -Executable (Join-Path $State.Bin 'pg_isready.exe') -Label 'PostgreSQL readiness' `
        -NativeArguments @('-h','127.0.0.1','-p',[string]$State.Port,'-d',$State.Database,'-t','5')
    $sql = @"
SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),
       shobj_description(d.oid,'pg_database'),r.rolsuper,r.rolcreatedb,r.rolcreaterole,
       r.rolbypassrls,r.rolinherit,EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid),d.datdba=r.oid
FROM pg_database d,pg_roles r WHERE d.datname=current_database() AND r.rolname=current_user;
"@
    foreach ($role in @('hiatlas_test_owner','hiatlas_test_runtime','hiatlas_test_recovery')) {
        $actual = Invoke-OwnedSql $State $role $State.Passwords[$role] $State.Database $sql
        $owns = if ($role -eq 'hiatlas_test_owner') { 't' } else { 'f' }
        $expected = "$($State.Database)|$role|127.0.0.1|$($State.Port)|hiatlas-disposable-test-db|f|f|f|f|f|f|$owns"
        if ($actual.Trim() -cne $expected) { throw 'Disposable marker, connection or role attestation failed; tests/cleanup refused.' }
    }
}
function Restore-TestEnvironment {
    param($State)
    foreach ($name in $script:EnvironmentNames) {
        if ($null -eq $State.PreviousEnvironment[$name]) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name,$State.PreviousEnvironment[$name],'Process') }
    }
}
function Start-HiAtlasTestDb {
    [CmdletBinding()]
    param([string]$PostgresRoot=$env:HIATLAS_TEST_POSTGRES_ROOT)
    if ($script:ActiveCluster) { throw 'This process already owns a test cluster. Stop it first.' }
    if ($env:OS -ne 'Windows_NT') { throw 'This local gate requires Windows.' }
    try {
        $distribution = Assert-PortableDistribution $PostgresRoot
        $version = Invoke-TestDbNative -Executable (Join-Path $distribution 'bin/postgres.exe') -NativeArguments @('--version') -Label 'PostgreSQL version'
        if ($version -notmatch '^postgres \(PostgreSQL\) 18\.6\s*$') { throw 'This gate supports PostgreSQL portable 18.6; provide that version.' }
    } catch { Write-Host "[FAIL] $($_.Exception.Message)"; throw }
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    Assert-NoReparsePath $parent
    if ($parent -eq [IO.Path]::GetPathRoot($parent).TrimEnd('\')) { throw 'Unsafe temporary parent.' }
    $id = [Guid]::NewGuid().ToString('N')
    $root = Join-Path $parent ('hiatlas-testdb-' + $id)
    if (Test-Path -LiteralPath $root) { throw 'Temporary directory collision; refusing reuse.' }
    $saved = @{}
    foreach ($name in $script:EnvironmentNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
    $state = @{
        Id=$id;Root=$root;TempParent=$parent;Data=(Join-Path $root 'data');Bin=(Join-Path $distribution 'bin')
        Port=(Get-FreeLoopbackPort);Database='hiatlas_foundation_test';Stage='INIT';Passwords=@{};PreviousEnvironment=$saved
    }
    foreach ($role in @('hiatlas_test_bootstrap','hiatlas_test_owner','hiatlas_test_runtime','hiatlas_test_recovery')) { $state.Passwords[$role] = New-TestSecret }
    try {
        $null = New-Item -ItemType Directory -Path $root
        Set-PrivateDirectoryAcl $root
        [IO.File]::WriteAllText((Join-Path $root '.hiatlas-owned-cluster'),('hiatlas-owned-cluster:' + $id))
        $script:ActiveCluster = $state
        Write-Host "[START] Owned temporary cluster: $root"
        $passwordFile = Join-Path $root 'initdb-password'
        [IO.File]::WriteAllText($passwordFile,$state.Passwords.hiatlas_test_bootstrap,(New-Object Text.UTF8Encoding($false)))
        $state.Stage = 'INITIALIZING'
        try {
            $null = Invoke-TestDbNative -Executable (Join-Path $state.Bin 'initdb.exe') -Label 'PostgreSQL initdb' `
                -NativeArguments @('-D',$state.Data,'-U','hiatlas_test_bootstrap','--pwfile',$passwordFile,'--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8','--locale=C')
        } finally { Remove-InitPassword $state }
        $state.Stage = 'INITIALIZED'
        $config = @"
listen_addresses = '127.0.0.1'
port = $($state.Port)
password_encryption = 'scram-sha-256'
log_statement = 'none'
log_min_error_statement = 'panic'
log_min_messages = 'fatal'
"@
        [IO.File]::AppendAllText((Join-Path $state.Data 'postgresql.conf'),"`n$config`n",(New-Object Text.UTF8Encoding($false)))
        [IO.File]::WriteAllText((Join-Path $state.Data 'pg_hba.conf'),"host all all 127.0.0.1/32 scram-sha-256`n",(New-Object Text.UTF8Encoding($false)))
        $state.Stage = 'STARTING'
        $null = Invoke-TestDbNative -Executable (Join-Path $state.Bin 'pg_ctl.exe') -Label 'PostgreSQL start' -DiscardOutput `
            -NativeArguments @('-D',$state.Data,'-l',(Join-Path $root 'postgres.log'),'-w','-t','30','start')
        $state.Stage = 'BOOTSTRAP'
        # Authenticate and prove the fresh data directory before any DDL.
        $identity = Invoke-OwnedSql $state 'hiatlas_test_bootstrap' $state.Passwords.hiatlas_test_bootstrap 'postgres' `
            "SELECT current_setting('data_directory'),host(inet_server_addr()),inet_server_port();"
        $parts = $identity.Trim().Split('|')
        if ($parts.Length -ne 3 -or [IO.Path]::GetFullPath($parts[0]).TrimEnd('\') -ine $state.Data -or $parts[1] -ne '127.0.0.1' -or $parts[2] -ne [string]$state.Port) {
            throw 'Fresh cluster attestation failed; no DDL allowed.'
        }
        foreach ($role in @('hiatlas_test_owner','hiatlas_test_runtime','hiatlas_test_recovery')) {
            $secret = $state.Passwords[$role]
            $null = Invoke-OwnedSql $state 'hiatlas_test_bootstrap' $state.Passwords.hiatlas_test_bootstrap 'postgres' `
                "CREATE ROLE $role LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '$secret';"
        }
        Assert-TestDatabaseName $state.Database
        $state.Stage = 'DATABASE_CREATING'
        $null = Invoke-OwnedSql $state 'hiatlas_test_bootstrap' $state.Passwords.hiatlas_test_bootstrap 'postgres' "CREATE DATABASE $($state.Database) OWNER hiatlas_test_owner;"
        $null = Invoke-OwnedSql $state 'hiatlas_test_bootstrap' $state.Passwords.hiatlas_test_bootstrap 'postgres' @"
COMMENT ON DATABASE $($state.Database) IS 'hiatlas-disposable-test-db';
REVOKE ALL ON DATABASE $($state.Database) FROM PUBLIC;
GRANT CONNECT ON DATABASE $($state.Database) TO hiatlas_test_owner,hiatlas_test_runtime,hiatlas_test_recovery;
"@
        $null = Invoke-OwnedSql $state 'hiatlas_test_bootstrap' $state.Passwords.hiatlas_test_bootstrap $state.Database @"
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO hiatlas_test_runtime,hiatlas_test_recovery;
"@
        Assert-TestConnections $state
        $state.Stage = 'READY'
        $prefix = 'postgresql+psycopg://'
        $endpoint = "@127.0.0.1:$($state.Port)/$($state.Database)"
        $env:TEST_DATABASE_OWNER_URL = $prefix + 'hiatlas_test_owner:' + $state.Passwords.hiatlas_test_owner + $endpoint
        $env:TEST_DATABASE_RUNTIME_URL = $prefix + 'hiatlas_test_runtime:' + $state.Passwords.hiatlas_test_runtime + $endpoint
        $env:HIATLAS_TEST_RECOVERY_DATABASE_URL = $prefix + 'hiatlas_test_recovery:' + $state.Passwords.hiatlas_test_recovery + $endpoint
        $env:RECOVERY_DATABASE_ROLE = 'hiatlas_test_recovery'
        $env:HIATLAS_TEST_DATABASE_RESET = '1'
        Write-Host "[READY] Disposable PostgreSQL 18.6 on 127.0.0.1:$($state.Port); owner/runtime/recovery verified."
    } catch {
        Write-Host '[FAIL] Disposable PostgreSQL setup failed; no external database used.'
        if ($script:ActiveCluster) { try { Stop-HiAtlasTestDb } catch { Write-Host '[FAIL] Cleanup refused; owned state retained in this process for investigation.' } }
        throw
    }
}
function Assert-HiAtlasTestDb {
    if (-not $script:ActiveCluster -or $script:ActiveCluster.Stage -ne 'READY') { throw 'No ready cluster owned by this process.' }
    Assert-TestConnections $script:ActiveCluster
    foreach ($name in @('TEST_DATABASE_OWNER_URL','TEST_DATABASE_RUNTIME_URL','HIATLAS_TEST_RECOVERY_DATABASE_URL')) {
        $role = switch ($name) { 'TEST_DATABASE_OWNER_URL' {'hiatlas_test_owner'} 'TEST_DATABASE_RUNTIME_URL' {'hiatlas_test_runtime'} default {'hiatlas_test_recovery'} }
        $expected = "postgresql+psycopg://${role}:$($script:ActiveCluster.Passwords[$role])@127.0.0.1:$($script:ActiveCluster.Port)/$($script:ActiveCluster.Database)"
        if ([Environment]::GetEnvironmentVariable($name,'Process') -cne $expected) { throw 'Test environment changed; gate refused.' }
    }
    if ($env:HIATLAS_TEST_DATABASE_RESET -ne '1' -or $env:RECOVERY_DATABASE_ROLE -ne 'hiatlas_test_recovery') { throw 'Test environment changed; gate refused.' }
}
function Stop-HiAtlasTestDb {
    if (-not $script:ActiveCluster) { Write-Host '[INFO] This process owns no cluster; no database/directory touched.'; return }
    $state = $script:ActiveCluster
    $cleanupStep = 'ownership/tree'
    try {
        Assert-OwnedTestRoot $state
        Assert-NoReparseTree $state.Root
        $pidFile = Join-Path $state.Data 'postmaster.pid'
        if (Test-Path -LiteralPath $pidFile) {
            Assert-OwnedServer $state
            $cleanupStep = 'connection/marker attestation'
            if ($state.Stage -in @('DATABASE_CREATING','READY')) { Assert-TestConnections $state }
            $cleanupStep = 'native stop'
            $null = Invoke-TestDbNative -Executable (Join-Path $state.Bin 'pg_ctl.exe') -Label 'PostgreSQL stop' -DiscardOutput -NativeArguments @('-D',$state.Data,'-m','fast','-w','-t','30','stop')
            if (Test-Path -LiteralPath $pidFile) { throw 'PostgreSQL did not stop; cleanup refused.' }
        } elseif ($state.Stage -notin @('INIT','INITIALIZED')) { throw 'Server cannot be attested after a start attempt; cleanup refused. No restart or discovery.' }
        Assert-OwnedTestRoot $state
        Assert-NoReparseTree $state.Root
        $cleanupStep = 'owned directory removal'
        Remove-Item -LiteralPath $state.Root -Recurse -Force -ErrorAction Stop
        $script:ActiveCluster = $null
        Write-Host '[CLEAN] Owned disposable cluster stopped and removed.'
    } catch {
        Write-Host "[FAIL] Cleanup stage: $cleanupStep; category: $($_.CategoryInfo.Category). Diagnostics withheld."
        throw
    } finally { Restore-TestEnvironment $state }
}
Export-ModuleMember -Function Start-HiAtlasTestDb,Assert-HiAtlasTestDb,Stop-HiAtlasTestDb
