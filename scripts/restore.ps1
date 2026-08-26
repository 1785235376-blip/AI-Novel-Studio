param([Parameter(Mandatory)][string]$BackupPath,[switch]$Force)
. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; $backup=(Resolve-Path $BackupPath).Path; $manifest=Join-Path $backup 'manifest.json'; if(-not(Test-Path $manifest)){throw 'Invalid backup: manifest.json is missing.'}
$existing=Get-ChildItem (Join-Path $root 'novel_data/novels') -Directory -ErrorAction SilentlyContinue; if($existing -and -not $Force){throw 'Target contains novels. Review first, then use -Force to explicitly allow merging/overwriting same-name files.'}
foreach($name in 'novel_data','prompts','workflows','config'){if(Test-Path (Join-Path $backup $name)){Copy-Item (Join-Path $backup $name) (Join-Path $root $name) -Recurse -Force}}
if(Test-Path (Join-Path $backup 'database.dump')){if(-not(Test-Command docker)){Write-Warning 'Database dump was not restored because Docker is unavailable.'}else{docker compose --project-directory $root cp (Join-Path $backup 'database.dump') postgres:/tmp/novel.dump; docker compose --project-directory $root exec -T postgres pg_restore -U novel_studio -d ai_novel_studio --clean --if-exists /tmp/novel.dump}}
& $PSScriptRoot/model-check.ps1
