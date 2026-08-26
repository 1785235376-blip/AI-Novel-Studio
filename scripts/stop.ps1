. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
if (-not (Test-Command docker)) { throw 'Docker is not installed or not on PATH.' }
docker compose --project-directory $root down
