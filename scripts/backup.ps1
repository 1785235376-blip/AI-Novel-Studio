param([string]$Destination)
. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; if(-not $Destination){$Destination=Join-Path $root ('backups/AI-Novel-Studio-Backup-'+(Get-Date -Format 'yyyy-MM-dd-HHmmss'))}
$resolvedRoot=[IO.Path]::GetFullPath($root); $resolvedDest=[IO.Path]::GetFullPath($Destination); if($resolvedDest -eq $resolvedRoot){throw 'Backup destination cannot be the project root.'}
New-Item -ItemType Directory -Path $resolvedDest -Force | Out-Null
foreach($name in 'novel_data','prompts','workflows','config','database/migrations'){ Copy-Item -LiteralPath (Join-Path $root $name) -Destination (Join-Path $resolvedDest $name) -Recurse -Force }
Copy-Item (Join-Path $root 'config/model_manifest.json') (Join-Path $resolvedDest 'model_manifest.json') -Force
if(Test-Command docker){ docker compose --project-directory $root exec -T postgres pg_dump -U novel_studio -Fc ai_novel_studio -f /tmp/novel.dump; docker compose --project-directory $root cp postgres:/tmp/novel.dump (Join-Path $resolvedDest 'database.dump') }
$files=Get-ChildItem -LiteralPath $resolvedDest -File -Recurse; $hashes=$files|ForEach-Object{[pscustomobject]@{path=$_.FullName.Substring($resolvedDest.Length+1);sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}}
$manifest=[ordered]@{backup_version='0.1.0';created_at=(Get-Date).ToUniversalTime().ToString('o');source_machine=$env:COMPUTERNAME;app_version=(Get-ReleaseVersion $root);schema_version='0.1.0';workflow_version='0.1.0';prompt_version='0.1.0';novel_count=@(Get-ChildItem (Join-Path $root 'novel_data/novels') -Directory).Count;file_count=$files.Count;model_configuration='model_manifest.json';creation_profiles=@('LOCAL_ONLY','HYBRID','QUALITY');checksum=$hashes}
$manifest|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $resolvedDest 'manifest.json') -Encoding utf8
'# Restore`nRun scripts/restore.ps1 -BackupPath <this-directory>. Model blobs are excluded.'|Set-Content -LiteralPath (Join-Path $resolvedDest 'README_RESTORE.md') -Encoding utf8
Write-Output $resolvedDest
