. $PSScriptRoot/common.ps1
$ErrorActionPreference='Stop'
$root=Get-ProjectRoot
$runtime=Join-Path $root '.runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

function Test-Port([int]$Port) { $client=[Net.Sockets.TcpClient]::new(); try { $task=$client.ConnectAsync('127.0.0.1',$Port); if (-not $task.Wait(500)) { return $false }; return $client.Connected } catch { return $false } finally { $client.Dispose() } }
function Wait-Url([string]$Url,[int]$Seconds=60) { $end=(Get-Date).AddSeconds($Seconds); do { try { $response=Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3; if ($response.StatusCode -eq 200) { return } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $end); throw "Service readiness timeout: $Url" }
function Find-Node { if ($env:ACCEPTANCE_NODE -and (Test-Path -LiteralPath $env:ACCEPTANCE_NODE)) { return $env:ACCEPTANCE_NODE }; $command=Get-Command node -ErrorAction SilentlyContinue; if ($command) { return $command.Source }; $bundled=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'; if (Test-Path -LiteralPath $bundled) { return $bundled }; throw 'Node.js 20+ was not found. Install Node.js or set ACCEPTANCE_NODE.' }

$python=Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing: .venv\Scripts\python.exe' }
$node=Find-Node
$envValues=Read-DotEnv $root
if (-not $envValues.ContainsKey('DATABASE_URL') -or -not $envValues['DATABASE_URL']) { throw 'DATABASE_URL is missing from .env.' }
$baseDatabaseUrl=$envValues['DATABASE_URL']
$env:DATABASE_URL=$baseDatabaseUrl
$acceptanceDatabaseUrl=& $python (Join-Path $root 'scripts\prepare_acceptance.py') url

$postgresStarted=$false
if (-not (Test-Port 54329)) {
  $pgctl=Join-Path $root '.runtime\postgresql-16.4\pgsql\bin\pg_ctl.exe'; $data=Join-Path $root '.runtime\pgdata-main'; $log=Join-Path $runtime 'acceptance-postgres.log'
  if (-not (Test-Path -LiteralPath $pgctl) -or -not (Test-Path -LiteralPath $data)) { throw 'PostgreSQL is unavailable. Start the configured PostgreSQL 16 runtime first.' }
  & $pgctl start -D $data -l $log -o '-p 54329' | Out-Host; $postgresStarted=$true
  for($i=0;$i -lt 40 -and -not (Test-Port 54329);$i++){Start-Sleep -Milliseconds 500}
  if (-not (Test-Port 54329)) { throw 'PostgreSQL failed to become ready on 127.0.0.1:54329.' }
}

$env:DATABASE_URL=$baseDatabaseUrl
& $python (Join-Path $root 'scripts\prepare_acceptance.py') | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Acceptance database preparation failed.' }

$sessions=@(
  @{role='ADMIN';token=('accept-admin-'+[guid]::NewGuid().ToString('N'));actor_id='acceptance-admin';workspace_id='acceptance-alpha';session_id=('accept-'+[guid]::NewGuid().ToString('N'));client_id='acceptance-browser'},
  @{role='DOMAIN_LEAD';token=('accept-lead-'+[guid]::NewGuid().ToString('N'));actor_id='acceptance-lead';workspace_id='acceptance-alpha';session_id=('accept-'+[guid]::NewGuid().ToString('N'));client_id='acceptance-browser'},
  @{role='MEMBER';token=('accept-member-'+[guid]::NewGuid().ToString('N'));actor_id='acceptance-member';workspace_id='acceptance-alpha';session_id=('accept-'+[guid]::NewGuid().ToString('N'));client_id='acceptance-browser'}
)
$sessionPath=Join-Path $runtime 'acceptance-sessions.json'; $sessions | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $sessionPath -Encoding UTF8
$state=[ordered]@{postgres_started=$postgresStarted;backend=@{name='backend';started=$false};frontend=@{name='frontend';started=$false}}

if (Test-Port 8000) { throw 'PORT CONFLICT: port 8000 is already occupied. Stop that service before starting the isolated acceptance backend.' }
$env:STORAGE_BACKEND='postgres'; $env:DATABASE_URL=$acceptanceDatabaseUrl; $env:ENABLE_COLLABORATION_RUNTIME='true'; $env:MOCK_PROVIDER='true'; $env:MOCK_STREAM_DELAY_MS='0'; $env:FRONTEND_ORIGIN='http://127.0.0.1:4173'; $env:COLLABORATION_DEV_SESSIONS_JSON=($sessions | ForEach-Object { @{token=$_.token;actor_id=$_.actor_id;workspace_id=$_.workspace_id;session_id=$_.session_id;client_id=$_.client_id} } | ConvertTo-Json -Compress)
$backend=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'acceptance-backend.stdout.log') -RedirectStandardError (Join-Path $runtime 'acceptance-backend.stderr.log') -PassThru
$state.backend=@{name='backend';started=$true;pid=$backend.Id;process_name=$backend.ProcessName}
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtime 'acceptance-processes.json') -Encoding UTF8
Wait-Url 'http://127.0.0.1:8000/health'
$listener=Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8000 -State Listen -ErrorAction Stop | Select-Object -First 1
$backendProcess=Get-Process -Id $listener.OwningProcess -ErrorAction Stop
$state.backend=@{name='backend';started=$true;pid=$backendProcess.Id;process_name=$backendProcess.ProcessName}
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtime 'acceptance-processes.json') -Encoding UTF8

if (Test-Port 4173) { & $PSScriptRoot/stop_acceptance.ps1; throw 'PORT CONFLICT: port 4173 is already occupied.' }
Push-Location (Join-Path $root 'frontend')
try { & $node 'node_modules/typescript/bin/tsc' '-b'; if($LASTEXITCODE -ne 0){throw 'TypeScript build failed.'}; & $node 'node_modules/vite/bin/vite.js' 'build'; if($LASTEXITCODE -ne 0){throw 'Vite build failed.'} } finally { Pop-Location }
$frontend=Start-Process -FilePath $node -ArgumentList @('node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port','4173','--strictPort') -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'acceptance-frontend.stdout.log') -RedirectStandardError (Join-Path $runtime 'acceptance-frontend.stderr.log') -PassThru
$state.frontend=@{name='frontend';started=$true;pid=$frontend.Id;process_name=$frontend.ProcessName}
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtime 'acceptance-processes.json') -Encoding UTF8
Wait-Url 'http://127.0.0.1:4173/'
& $PSScriptRoot/smoke_acceptance.ps1
Write-Host ''
Write-Host 'AI Novel Studio acceptance environment is READY.'
Write-Host 'Browser: http://127.0.0.1:4173/'
Write-Host 'Identity details: powershell -ExecutionPolicy Bypass -File scripts/show_acceptance_identity.ps1'
Write-Host 'Stop: powershell -ExecutionPolicy Bypass -File scripts/stop_acceptance.ps1'
