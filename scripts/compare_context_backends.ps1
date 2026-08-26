param(
  [string]$NovelId = 'sample_novel',
  [int]$Chapter = 2,
  [string]$Instruction = 'Continue validation scene',
  [string]$Report = 'context_backend_compare.json'
)
. $PSScriptRoot/common.ps1
$root = Get-ProjectRoot
$values = Read-DotEnv $root
$databaseUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { $values['DATABASE_URL'] }
if (-not $databaseUrl) { throw 'DATABASE_URL is required.' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python -m app.compare_context_backends --data-root (Join-Path $root 'novel_data') --database-url $databaseUrl --novel-id $NovelId --chapter $Chapter --instruction $Instruction --cloud --report (Join-Path $root $Report)
exit $LASTEXITCODE
