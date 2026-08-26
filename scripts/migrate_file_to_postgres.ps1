param(
  [string]$Source = "novel_data",
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [string]$Report = "migration_report.json"
)
$ErrorActionPreference = "Stop"
if (-not $DatabaseUrl) { throw "DATABASE_URL or -DatabaseUrl is required" }
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
& $python -m app.migrate_file_to_postgres --source $Source --database-url $DatabaseUrl --report $Report
if ($LASTEXITCODE -ne 0) { throw "File-to-PostgreSQL migration failed with exit code $LASTEXITCODE" }
