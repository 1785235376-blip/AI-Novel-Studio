. $PSScriptRoot/common.ps1

$root = Get-ProjectRoot
$envValues = Read-DotEnv $root
$databaseUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { $envValues['DATABASE_URL'] }
$postgresPort = if ($env:POSTGRES_PORT) { [int]$env:POSTGRES_PORT } elseif ($envValues['POSTGRES_PORT']) { [int]$envValues['POSTGRES_PORT'] } else { 54329 }
$dockerAvailable = Test-Command docker
$composeAvailable = $false
$daemonAvailable = $false

if ($dockerAvailable) {
  try { docker compose version *> $null; $composeAvailable = ($LASTEXITCODE -eq 0) } catch { $composeAvailable = $false }
  try { docker info *> $null; $daemonAvailable = ($LASTEXITCODE -eq 0) } catch { $daemonAvailable = $false }
}

$portOpen = $false
$client = [System.Net.Sockets.TcpClient]::new()
try {
  $connect = $client.ConnectAsync('127.0.0.1', $postgresPort)
  $portOpen = $connect.Wait(1500) -and $client.Connected
} catch { $portOpen = $false } finally { $client.Dispose() }

$checks = @(
  [pscustomobject]@{ Check = 'Docker CLI'; Ready = $dockerAvailable; Detail = $(if ($dockerAvailable) { 'available' } else { 'not found' }) }
  [pscustomobject]@{ Check = 'Docker Compose'; Ready = $composeAvailable; Detail = $(if ($composeAvailable) { 'available' } else { 'not available' }) }
  [pscustomobject]@{ Check = 'Docker daemon'; Ready = $daemonAvailable; Detail = $(if ($daemonAvailable) { 'available' } else { 'not available' }) }
  [pscustomobject]@{ Check = 'DATABASE_URL'; Ready = [bool]$databaseUrl; Detail = $(if ($databaseUrl) { 'configured' } else { 'not configured' }) }
  [pscustomobject]@{ Check = "PostgreSQL port $postgresPort"; Ready = $portOpen; Detail = $(if ($portOpen) { 'open' } else { 'closed' }) }
)

$checks | Format-Table -AutoSize
if (@($checks | Where-Object { -not $_.Ready }).Count -eq 0) {
  Write-Output 'READY'
  exit 0
}
Write-Output 'NOT READY'
exit 1
