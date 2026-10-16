param(
    [Parameter(Mandatory)][string]$BackupPath,
    [Parameter(Mandatory)][string]$Destination,
    [string]$DatabaseUrlEnv,
    [switch]$Force
)
. $PSScriptRoot/common.ps1
if($Force){throw '-Force is no longer supported. Restore to a new directory and a new database; existing data is never overwritten.'}
$root=Get-ProjectRoot
$python=Join-Path $root '.venv/Scripts/python.exe'; if(-not(Test-Path $python)){$python='python'}
$arguments=@('-m','app.backup_restore','restore','--backup',$BackupPath,'--destination',$Destination)
if($DatabaseUrlEnv){$arguments+=@('--database-url-env',$DatabaseUrlEnv)}
Push-Location $root
try { & $python @arguments; if($LASTEXITCODE -ne 0){throw 'Verified restore failed; do not start the application from an incomplete target.'} }
finally { Pop-Location }
