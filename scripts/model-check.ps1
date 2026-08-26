. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; Get-Content (Join-Path $root 'config/model_manifest.json')
if (Test-Command ollama) { ollama list } else { Write-Warning 'Ollama is missing. Install models listed in model_manifest.json.' }
