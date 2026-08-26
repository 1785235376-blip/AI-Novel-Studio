param(
  [string]$Report = 'postgres_runtime_validation_report.json'
)
. $PSScriptRoot/common.ps1

$root = Get-ProjectRoot
$envValues = Read-DotEnv $root
$databaseUrl = if ($env:TEST_POSTGRES_DATABASE_URL) { $env:TEST_POSTGRES_DATABASE_URL } elseif ($env:DATABASE_URL) { $env:DATABASE_URL } else { $envValues['DATABASE_URL'] }
$reportPath = if ([IO.Path]::IsPathRooted($Report)) { $Report } else { Join-Path $root $Report }
$results = [ordered]@{
  timestamp = [DateTimeOffset]::UtcNow.ToString('o')
  status = 'NOT VERIFIED'
  database_connection = 'NOT VERIFIED'
  migrations = [ordered]@{ '001' = 'NOT VERIFIED'; '002' = 'NOT VERIFIED'; '003' = 'NOT VERIFIED' }
  repository_contracts = 'NOT VERIFIED'
  context_compare = 'NOT VERIFIED'
  author_flow = 'NOT VERIFIED'
  details = @()
}

$readinessScript = Join-Path $PSScriptRoot 'check_postgres_ready.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $readinessScript
if ($LASTEXITCODE -ne 0) {
  $results.details += 'Environment readiness check failed. No real PostgreSQL validation was performed.'
  $results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8
  Write-Output "NOT VERIFIED - report: $reportPath"
  exit 1
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$env:TEST_POSTGRES_DATABASE_URL = $databaseUrl
$postgresUser = if ($envValues['POSTGRES_USER']) { $envValues['POSTGRES_USER'] } else { 'novel_studio' }
$postgresDb = if ($envValues['POSTGRES_DB']) { $envValues['POSTGRES_DB'] } else { 'ai_novel_studio' }

try {
  & $python -c "from app.repositories.postgres.session import Database; Database(r'''$databaseUrl''').require_healthy(); print('DATABASE_HEALTHY')"
  if ($LASTEXITCODE -ne 0) { throw 'Database health check failed.' }
  $results.database_connection = 'REAL VERIFIED'

  $migrationQuery = "SELECT version FROM schema_versions WHERE version IN ('0.1.0','0.2.0','0.4.0') ORDER BY version;"
  $versions = docker compose --project-directory $root exec -T postgres psql -U $postgresUser -d $postgresDb -At -v ON_ERROR_STOP=1 -c $migrationQuery
  if ($LASTEXITCODE -ne 0) { throw 'Migration status query failed.' }
  $results.migrations['001'] = $(if ($versions -contains '0.1.0') { 'REAL VERIFIED' } else { 'NOT VERIFIED' })
  $results.migrations['002'] = $(if ($versions -contains '0.2.0') { 'REAL VERIFIED' } else { 'NOT VERIFIED' })
  $results.migrations['003'] = $(if ($versions -contains '0.4.0') { 'REAL VERIFIED' } else { 'NOT VERIFIED' })

  & $python -m pytest tests/test_postgres_repository_contracts.py -q
  if ($LASTEXITCODE -eq 0) { $results.repository_contracts = 'REAL VERIFIED' } else { $results.repository_contracts = 'PARTIAL' }
  $results.status = $(if ($results.database_connection -eq 'REAL VERIFIED' -and $results.repository_contracts -eq 'REAL VERIFIED' -and @($results.migrations.Values | Where-Object { $_ -ne 'REAL VERIFIED' }).Count -eq 0) { 'PARTIAL' } else { 'PARTIAL' })
  $results.details += 'Database, migration markers, and Repository Contract Tests were executed. Context comparison and author flow require their dedicated fixtures before REAL VERIFIED can be claimed.'
} catch {
  $results.status = 'PARTIAL'
  $results.details += $_.Exception.Message
} finally {
  $results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8
}
Write-Output "$($results.status) - report: $reportPath"
if ($results.status -ne 'REAL VERIFIED') { exit 1 }
