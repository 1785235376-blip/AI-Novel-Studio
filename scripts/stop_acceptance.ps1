. $PSScriptRoot/common.ps1
$ErrorActionPreference='Stop'
$root=Get-ProjectRoot
$statePath=Join-Path $root '.runtime\acceptance-processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'No launcher-managed acceptance processes are recorded.'; exit 0 }
$state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($entry in @($state.frontend,$state.backend)) {
  if ($entry -and $entry.started -and $entry.pid) {
    $process=Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq $entry.process_name) { Stop-Process -Id $entry.pid; Write-Host "Stopped $($entry.name) (PID $($entry.pid))." }
  }
}
if ($state.postgres_started) {
  $pgctl=Join-Path $root '.runtime\postgresql-16.4\pgsql\bin\pg_ctl.exe'
  $data=Join-Path $root '.runtime\pgdata-main'
  & $pgctl stop -D $data -m fast | Out-Host
}
Remove-Item -LiteralPath $statePath -Force
Write-Host 'Acceptance shutdown complete. Persistent acceptance data was preserved.'
