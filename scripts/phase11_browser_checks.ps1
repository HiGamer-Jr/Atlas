param([Parameter(Mandatory)][string]$EnvironmentFile,[switch]$Build,[ValidateSet('05','06','07','08','09','10')][string]$Phase='05',[ValidateSet('normal','controlled')][string]$Mode='normal')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$EnvironmentFile=(Resolve-Path -LiteralPath $EnvironmentFile).Path
$taskTemp=Split-Path -Parent $EnvironmentFile
. $EnvironmentFile
if($Build -and ($Phase -ne '10' -or $Mode -ne 'normal')){throw 'Build requires phase10 normal'}
$env:HIATLAS_PHASE11_BUILD=if($Build){'1'}else{'0'}
$env:HIATLAS_PHASE11_E2E='1'
$env:PYTHONPATH="$projectRoot/scripts;$projectRoot/backend"
$env:HIATLAS_PHASE10_CONTROLLED=if($Mode -eq 'controlled'){'1'}else{'0'}
$env:HIATLAS_PHASE10_E2E=$Mode
$env:HIATLAS_E2E_OUTPUT="$projectRoot/docs/superpowers/validation/hiatlas-platform/phase-11-visual/phase-$Phase-$Mode"
$suffix=if($Build){'build'}else{$Mode}
$env:HIATLAS_E2E_OUTPUT="$projectRoot/docs/superpowers/validation/hiatlas-platform/phase-11-visual/phase-$Phase-$suffix"
$copies=Join-Path $taskTemp 'browser-harnesses'
New-Item -ItemType Directory $copies,$env:HIATLAS_E2E_OUTPUT -Force | Out-Null
$source=Join-Path $projectRoot "frontend/e2e/phase$Phase.mjs"
$harness=Join-Path $copies "phase$Phase-$suffix.mjs"
$text=[IO.File]::ReadAllText($source)
$text=[regex]::Replace($text,'const output=path.resolve\([^\r\n]*\);','const output=path.resolve(process.env.HIATLAS_E2E_OUTPUT);',1)
[IO.File]::WriteAllText($harness,$text)
foreach($port in @(8011,5181)){if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw "E2E port occupied: $port"}}
$python="$projectRoot/backend/.venv/Scripts/python.exe"
# Requires coordinator exclusive configured disposable E2E database slot before execution.
$guardJson=& $python (Join-Path $projectRoot "scripts/phase11_browser_fixture.py") --validate-env
if($LASTEXITCODE){throw "Dedicated E2E configuration rejected before cleanup"}
$guard=$guardJson | ConvertFrom-Json
& $python "$projectRoot/scripts/phase06_browser_fixture.py" clean
if($LASTEXITCODE){throw 'Attested controlled fixture cleanup failed'}
$api=$null; $vite=$null; $ready=$false
try{
 $apiArgs=@('-m','uvicorn','phase11_browser_fixture:create_browser_app','--factory','--host','127.0.0.1','--no-proxy-headers','--no-access-log')
 if($Build){$apiArgs+=@('--port','5181','--ssl-certfile',$env:HIATLAS_TLS_CERT,'--ssl-keyfile',$env:HIATLAS_TLS_KEY)}else{$apiArgs+=@('--port','8011')}
 $api=Start-Process $python -ArgumentList $apiArgs -WorkingDirectory "$projectRoot/backend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$taskTemp/api-$Phase-$Mode.out" -RedirectStandardError "$taskTemp/api-$Phase-$Mode.err"
 if(-not $Build){$vite=Start-Process 'C:/Program Files/nodejs/node.exe' -ArgumentList @("$projectRoot/frontend/node_modules/vite/bin/vite.js",'--host','127.0.0.1','--port','5181','--strictPort') -WorkingDirectory "$projectRoot/frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$taskTemp/vite-$Phase-$Mode.out" -RedirectStandardError "$taskTemp/vite-$Phase-$Mode.err"}
 $postgresPid=[int](Get-Content "$taskTemp/data/postmaster.pid" -TotalCount 1)
 @{postgres=$postgresPid;api=$api.Id;vite=if($vite){$vite.Id}else{$null};phase=$Phase;mode=$suffix;api_port=if($Build){5181}else{8011};vite_port=5181;postgres_port=55491;e2e_database=$guard.database;e2e_roles=@($guard.owner,$guard.runtime)} | ConvertTo-Json | Set-Content "$taskTemp/pid-manifest.json"
 for($n=0;$n -lt 40;$n++){
  Start-Sleep -Milliseconds 500
  try{ $health=Invoke-RestMethod ($env:HIATLAS_E2E_ORIGIN+'/api/health/ready') -SkipCertificateCheck; $web=Invoke-WebRequest 'https://localhost:5181/' -SkipCertificateCheck; if($health.status -eq 'ok' -and $web.StatusCode -eq 200){$ready=$true;break} }catch{}
  if($api.HasExited -or ($vite -and $vite.HasExited)){throw 'E2E service exited; private logs preserved'}
 }
 if(-not $ready){throw "Owned E2E service readiness timeout"}
 Push-Location "$projectRoot/frontend"
 try{if($Build){& 'C:/Program Files/nodejs/node.exe' (Join-Path $projectRoot 'frontend/e2e/phase11-build.mjs');if($LASTEXITCODE){throw 'Production build proof failed'}};& 'C:/Program Files/nodejs/node.exe' $harness; if($LASTEXITCODE){throw "Phase$Phase $Mode E2E failed"}}finally{Pop-Location}
}finally{
 foreach($process in @($api,$vite)){
  if($null -ne $process -and -not $process.HasExited){Stop-Process -Id $process.Id; $process.WaitForExit(10000) | Out-Null}
 }
 if($null -ne $api){@{postgres=$postgresPid;api_stopped=$api.Id;vite_stopped=if($vite){$vite.Id}else{$null};phase=$Phase;mode=$suffix;e2e_database=$guard.database;e2e_roles=@($guard.owner,$guard.runtime)} | ConvertTo-Json | Set-Content "$taskTemp/pid-manifest.json"}
}
