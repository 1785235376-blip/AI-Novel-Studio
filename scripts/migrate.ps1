param([Parameter(Mandatory)][string]$Destination,[switch]$OfflineConfirmed,[string]$DataDirectory,[string]$DatabaseUrlEnv)
& $PSScriptRoot/backup.ps1 -Destination $Destination -OfflineConfirmed:$OfflineConfirmed -DataDirectory $DataDirectory -DatabaseUrlEnv $DatabaseUrlEnv
Write-Output 'Verified migration bundle created. Restore into a new directory and new database; install models separately.'
