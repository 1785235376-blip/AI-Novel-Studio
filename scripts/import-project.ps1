param([Parameter(Mandatory)][string]$ProjectPath)
. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; $meta=Get-Content (Join-Path $ProjectPath 'project.json')|ConvertFrom-Json; $dest=Join-Path $root "novel_data/novels/$($meta.novel_id)"; if(Test-Path $dest){throw 'novel_id conflict. Import stopped without changing the existing project.'}; Copy-Item (Join-Path $ProjectPath 'novel') $dest -Recurse
