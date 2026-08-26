. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'scripts\v061_acceptance_supervisor.py') stop
exit $LASTEXITCODE
