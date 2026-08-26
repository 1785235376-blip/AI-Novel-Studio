. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
if (-not (Test-Path -LiteralPath (Join-Path $root '.env'))) { throw 'Missing .env. Copy .env.example and set POSTGRES_PASSWORD.' }
if (-not (Test-Command docker)) { throw 'Docker is not installed or not on PATH. No automatic installation was attempted.' }
docker compose --project-directory $root up -d --build
& $PSScriptRoot/health-check.ps1
