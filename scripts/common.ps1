$ErrorActionPreference = 'Stop'
function Get-ProjectRoot { (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
function Read-DotEnv([string]$Root) {
  $path = Join-Path $Root '.env'; $values = @{}
  if (Test-Path -LiteralPath $path) { foreach ($line in Get-Content -LiteralPath $path) { if ($line -match '^\s*([^#=]+)=(.*)$') { $values[$matches[1].Trim()]=$matches[2].Trim() } } }
  $values
}
function Test-Command([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Get-ReleaseVersion([string]$Root) {
  $path = Join-Path $Root 'release/version.json'
  if (-not (Test-Path -LiteralPath $path)) { throw 'Missing authoritative release/version.json.' }
  $value = Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
  if (-not $value.version) { throw 'release/version.json does not declare version.' }
  [string]$value.version
}
