. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
$path=Join-Path $root '.runtime\acceptance-sessions.json'
if (-not (Test-Path -LiteralPath $path)) { throw 'Acceptance environment is not running. Run scripts/start_acceptance.ps1 first.' }
$sessions=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
Write-Host 'Use one identity below in the Connection screen. Tokens are local runtime credentials; do not share them.'
foreach ($item in $sessions) {
  Write-Host ""
  Write-Host "[$($item.role)]"
  Write-Host "Session token: $($item.token)"
  Write-Host "workspaceId: acceptance-alpha"
  Write-Host "projectId: acceptance-alpha-novel"
  Write-Host "storylineId: acceptance-alpha-storyline"
  Write-Host "branchId: acceptance-alpha-main"
}
