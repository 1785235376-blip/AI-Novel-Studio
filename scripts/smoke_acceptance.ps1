. $PSScriptRoot/common.ps1
$ErrorActionPreference='Stop'
$root=Get-ProjectRoot
$sessions=Get-Content -LiteralPath (Join-Path $root '.runtime\acceptance-sessions.json') -Raw | ConvertFrom-Json
$admin=$sessions | Where-Object role -eq 'ADMIN' | Select-Object -First 1
$health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 10
if ($health.status -ne 'ok') { throw 'Backend core health check failed.' }
$workspaces=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/collaboration/admin/workspaces' -Headers @{'X-Session-Token'=$admin.token} -TimeoutSec 10
$ids=@($workspaces.items | ForEach-Object id)
foreach ($required in @('acceptance-alpha','acceptance-beta','acceptance-empty')) { if ($required -notin $ids) { throw "Missing acceptance workspace: $required" } }
$frontend=Invoke-WebRequest -Uri 'http://127.0.0.1:4173/' -UseBasicParsing -TimeoutSec 10
if ($frontend.StatusCode -ne 200 -or $frontend.Content -notmatch '<div id="root"></div>') { throw 'Production frontend is not reachable.' }
Write-Host 'PASS backend core health and PostgreSQL-backed Workspace API'
Write-Host 'PASS trusted ADMIN session and Workspace API'
Write-Host 'PASS production frontend / reachable'
