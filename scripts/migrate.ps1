param([Parameter(Mandatory)][string]$Destination)
& $PSScriptRoot/backup.ps1 -Destination $Destination
Write-Output 'Migration bundle created. On the new machine, run restore.ps1 and install models from model_manifest.json.'
