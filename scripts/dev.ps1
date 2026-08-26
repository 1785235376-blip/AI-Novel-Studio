. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot
$python=Get-Command python -ErrorAction SilentlyContinue; $npm=Get-Command npm -ErrorAction SilentlyContinue
$docker=Get-Command docker -ErrorAction SilentlyContinue
if(-not $python){throw 'Python 3.11+ is required. Missing: Python. Nothing was installed automatically.'}
if(-not $npm){throw 'Node.js 20+ and npm are required. Missing: Node/npm. Nothing was installed automatically.'}
if(-not $docker){Write-Warning 'Docker is missing. Backend will use file runtime; PostgreSQL is unavailable.'}
Start-Process -FilePath $python.Source -ArgumentList '-m','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','8000' -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath $npm.Source -ArgumentList 'run','dev' -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden
Write-Output 'Backend: http://localhost:8000/docs  Frontend: http://localhost:5173'
