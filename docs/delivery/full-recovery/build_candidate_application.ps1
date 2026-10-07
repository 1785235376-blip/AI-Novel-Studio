param(
    [Parameter(Mandatory = $true)]
    [string]$ExpectedSourceFingerprint,
    [string]$BuildSuffix = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$runtimeRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot '.runtime\full-recovery'))
$baseApplication = Join-Path $runtimeRoot 'windows-base-final'
if ($BuildSuffix -notmatch '^[a-zA-Z0-9-]+$') { throw 'Build suffix must be a plain directory identifier' }
$outputRoot = [IO.Path]::GetFullPath((Join-Path $runtimeRoot "candidate-application-$BuildSuffix"))
$hostPublish = [IO.Path]::GetFullPath((Join-Path $runtimeRoot "candidate-host-publish-$BuildSuffix"))
foreach ($path in @($outputRoot, $hostPublish)) {
    if (-not $path.StartsWith($runtimeRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Build path escapes isolated runtime' }
    if (Test-Path -LiteralPath $path) { throw "Build output must be fresh: $path" }
}
# The original builder replaces these known staged subtrees. Verify each
# absolute deletion target is inside the fresh isolated output before invoking it.
foreach ($relative in @('frontend-build\dist','Application\Frontend\dist','Application\Backend','Application\Database\Migrations','Application\DesktopHost')) {
    $target = [IO.Path]::GetFullPath((Join-Path $outputRoot $relative))
    if (-not $target.StartsWith($outputRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Staged deletion target escapes output' }
}
if (@(Get-ChildItem -LiteralPath $baseApplication -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
    throw 'Base package contains a reparse point; fresh staged tree safety cannot be established'
}
$env:PYTHONPATH = Join-Path $projectRoot '.github\ci'
$env:PYTHONUTF8 = '1'
$env:DOTNET_CLI_HOME = Join-Path $runtimeRoot 'dotnet-cli-home'
$env:NUGET_PACKAGES = Join-Path $runtimeRoot 'nuget-packages'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$check = @'
import gzip,json,sys
from pathlib import Path
from suite_coverage import source_errors
root=Path(sys.argv[1]); expected=sys.argv[2]
manifest=json.loads(gzip.decompress((root/'.github/ci/coverage_manifest.json.gz').read_bytes()))
if manifest['full_recovery_inventory']['source_files_fingerprint_sha256'] != expected:
    raise SystemExit('Expected frozen candidate source fingerprint differs')
errors=source_errors(root,manifest)
if errors: raise SystemExit('\n'.join(errors))
print('FROZEN_CANDIDATE_SOURCE_VERIFIED '+expected)
'@
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -c $check $projectRoot $ExpectedSourceFingerprint
if ($LASTEXITCODE -ne 0) { throw 'Candidate source changed after freeze; regenerate strict inventory before building' }
Push-Location -LiteralPath $projectRoot
try {
    & (Join-Path $projectRoot 'scripts\build_windows_application.ps1') `
        -BaseApplication $baseApplication -OutputRoot $outputRoot -HostPublishDirectory $hostPublish `
        -DotnetPath (Join-Path $runtimeRoot 'dotnet-sdk-8.0.424\dotnet.exe') `
        -NodePath 'C:\Program Files\nodejs\node.exe' `
        -ViteCliPath (Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js') `
        -VerifiedFontDirectory (Join-Path $runtimeRoot 'fonts')
    if (-not (Test-Path -LiteralPath (Join-Path $outputRoot 'application-provenance.json'))) { throw 'Build did not produce original application provenance' }
    [ordered]@{
        evidence_boundary = 'Fresh local Windows candidate build from frozen current working source; not old PR45 package evidence'
        expected_source_fingerprint = $ExpectedSourceFingerprint
        candidate_manifest_sha256 = (Get-FileHash -LiteralPath (Join-Path $projectRoot '.github\ci\coverage_manifest.json.gz') -Algorithm SHA256).Hash.ToLowerInvariant()
        actual_git_head = (& git rev-parse HEAD)
        working_tree_modified = $true
        original_base_used_only_for_runtime_payload = $baseApplication
        fresh_application = (Join-Path $outputRoot 'Application')
        sdk_recovery_receipt = (Join-Path $PSScriptRoot 'dotnet-sdk-recovery.json')
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputRoot 'candidate-working-source-provenance.json') -Encoding utf8
    Write-Output "FRESH_CANDIDATE_APPLICATION $(Join-Path $outputRoot 'Application')"
}
finally { Pop-Location }
