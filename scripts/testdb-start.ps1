#requires -Version 5.1
[CmdletBinding()]
param([string]$PostgresRoot=$env:HIATLAS_TEST_POSTGRES_ROOT)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'testdb.psm1') -ErrorAction Stop
Start-HiAtlasTestDb -PostgresRoot $PostgresRoot
