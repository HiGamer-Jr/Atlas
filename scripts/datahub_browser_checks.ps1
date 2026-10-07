param([Parameter(Mandatory)][string]$EnvironmentFile)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if([IO.Path]::GetFullPath($projectRoot) -ne 'D:\Atlas'){throw 'Official development checkout required'}
$taskConfig=Get-Content -Raw -LiteralPath $EnvironmentFile | ConvertFrom-Json
foreach($property in $taskConfig.PSObject.Properties){[Environment]::SetEnvironmentVariable($property.Name,[string]$property.Value,'Process')}
$env:PYTHONPATH="$projectRoot/scripts;$projectRoot/backend"
foreach($port in @(8018,5188)){if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw 'Owned E2E port occupied'}}
$python="$projectRoot/backend/.venv/Scripts/python.exe"
$node='C:/Users/romil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$api=$null;$vite=$null
try{
 $api=Start-Process $python -ArgumentList @('-m','uvicorn','datahub_browser_fixture:create_browser_app','--factory','--host','127.0.0.1','--port','8018','--no-access-log','--no-proxy-headers') -WorkingDirectory "$projectRoot/backend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$env:HIATLAS_E2E_STATE/api.out" -RedirectStandardError "$env:HIATLAS_E2E_STATE/api.err"
 $vite=Start-Process $node -ArgumentList @("$projectRoot/frontend/node_modules/vite/bin/vite.js",'--host','127.0.0.1','--port','5188','--strictPort') -WorkingDirectory "$projectRoot/frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$env:HIATLAS_E2E_STATE/vite.out" -RedirectStandardError "$env:HIATLAS_E2E_STATE/vite.err"
 $ready=$false
 for($i=0;$i -lt 60;$i++){
  Start-Sleep -Milliseconds 500
  try{if((Invoke-RestMethod 'https://localhost:5188/api/health/ready' -SkipCertificateCheck).status -eq 'ok'){$ready=$true;break}}catch{}
  if($api.HasExited -or $vite.HasExited){throw 'Owned E2E service exited; private logs preserved'}
 }
 if(-not $ready){throw 'Owned E2E readiness timeout'}
 Push-Location "$projectRoot/frontend"
 try{& $node "$projectRoot/frontend/e2e/datahub.mjs";if($LASTEXITCODE){throw 'Controlled DataHub E2E failed'}}finally{Pop-Location}
}finally{
 foreach($process in @($api,$vite)){if($null -ne $process -and -not $process.HasExited){Stop-Process -Id $process.Id;$process.WaitForExit(10000)|Out-Null}}
 try {
  & $python "$projectRoot/scripts/datahub_browser_fixture.py" clean | Out-Null
  if($LASTEXITCODE){throw 'Owned synthetic database cleanup failed'}
 } finally {
  foreach($property in $taskConfig.PSObject.Properties){Remove-Item -LiteralPath ('Env:'+ $property.Name) -ErrorAction SilentlyContinue}
 }
}
