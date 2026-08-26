. $PSScriptRoot/common.ps1
$root = Get-ProjectRoot
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'scripts\run_real_postgres_full.py')
exit $LASTEXITCODE

