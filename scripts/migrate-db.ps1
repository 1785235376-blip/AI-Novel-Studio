. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; if(-not(Test-Command docker)){throw 'Docker is unavailable.'}; Get-ChildItem (Join-Path $root 'database/migrations/*.sql')|Sort-Object Name|ForEach-Object{Get-Content $_.FullName -Raw|docker compose --project-directory $root exec -T postgres psql -U novel_studio -d ai_novel_studio -v ON_ERROR_STOP=1}
