#requires -Version 5.1
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'testdb.psm1') -ErrorAction Stop
Stop-HiAtlasTestDb
