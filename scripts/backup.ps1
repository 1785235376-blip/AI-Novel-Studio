param(
    [string]$Destination,
    [string]$Source,
    [string]$DataDirectory,
    [string]$DatabaseUrlEnv,
    [switch]$OfflineConfirmed
)
. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
if(-not $OfflineConfirmed){throw 'Stop the application and all writers, then use -OfflineConfirmed.'}
if(-not $Source){$Source=$root}
if(-not $Destination){$Destination=Join-Path (Split-Path ([IO.Path]::GetFullPath($Source)) -Parent) ('AI-Novel-Studio-Backup-'+(Get-Date -Format 'yyyy-MM-dd-HHmmss'))}
$python=Join-Path $root '.venv/Scripts/python.exe'; if(-not(Test-Path $python)){$python='python'}
$arguments=@('-m','app.backup_restore','backup','--source',$Source,'--destination',$Destination,'--app-version',(Get-ReleaseVersion $root),'--offline-confirmed')
if($DataDirectory){$arguments+=@('--data-directory',$DataDirectory)}
if($DatabaseUrlEnv){$arguments+=@('--database-url-env',$DatabaseUrlEnv)}
Push-Location $root
try { & $python @arguments; if($LASTEXITCODE -ne 0){throw 'Verified backup failed; inspect the incomplete destination.'} }
finally { Pop-Location }
