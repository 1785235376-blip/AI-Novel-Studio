. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; $checks=@()
$checks += [pscustomobject]@{Check='Writable novel_data';OK=$(try{$p=Join-Path $root 'novel_data/.health';Set-Content -LiteralPath $p 'ok';Remove-Item -LiteralPath $p; $true}catch{$false})}
$checks += [pscustomobject]@{Check='Backup directory';OK=(Test-Path (Join-Path $root 'backups'))}
$checks += [pscustomobject]@{Check='Docker';OK=(Test-Command docker)}
$checks += [pscustomobject]@{Check='Ollama';OK=$(try{(Invoke-WebRequest 'http://localhost:11434/api/tags' -TimeoutSec 3).StatusCode -eq 200}catch{$false})}
$checks += [pscustomobject]@{Check='Novel Service';OK=$(try{(Invoke-WebRequest 'http://localhost:8000/health' -TimeoutSec 3).StatusCode -eq 200}catch{$false})}
$checks += [pscustomobject]@{Check='Dify';OK=$(try{(Invoke-WebRequest 'http://localhost:5001' -TimeoutSec 3).StatusCode -lt 500}catch{$false})}
$checks | Format-Table -AutoSize
if ($checks.Where({-not $_.OK}).Count) { Write-Warning 'Some optional/runtime checks failed. See the table above.'; exit 1 }
