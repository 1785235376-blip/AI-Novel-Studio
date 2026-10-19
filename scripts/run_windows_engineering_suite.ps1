# Single Windows engineering test entry point (SPEC/ENG-2026.10.19).
#
# Runs one or all dedicated profiles from docs/v2/engineering/windows_profiles.json.
# Each profile gets its own isolated directory, NOVEL_DATA_PATH (engineering-runs or
# v2-checks as the profile demands), environment, raw log and JUnit receipt, plus a
# machine-readable result file. The aggregate report never upgrades a failure to a
# pass and never hides a skip: counts are parsed from the JUnit receipt.
#
# Usage:
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_windows_engineering_suite.ps1 -Profile targeted
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_windows_engineering_suite.ps1 -Profile all -Label round3
param(
    [ValidateSet('full','targeted','collaboration','round3i-adoption','round3i-authorized','r3-import','all')]
    [string]$Profile = 'all',
    [string]$Label = '',
    [string]$RunRoot = ''
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
if (-not (Test-Path (Join-Path $repo 'docs/v2/engineering/windows_profiles.json'))) {
    throw "windows_profiles.json missing under $repo"
}
if (-not $Label) { $Label = 'windows-' + (Get-Date -Format 'yyyyMMdd-HHmmss') }
if (-not $RunRoot) {
    $workspaceRoot = Split-Path -Parent (Split-Path -Parent $repo)
    $pipelineRoot = Join-Path $workspaceRoot 'Engineering-Runs'
    $RunRoot = Join-Path $pipelineRoot ('windows-engineering/' + $Label)
}
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$manifest = Get-Content (Join-Path $repo 'docs/v2/engineering/windows_profiles.json') -Raw | ConvertFrom-Json
$profileNames = if ($Profile -eq 'all') { @($manifest.profiles.PSObject.Properties.Name) } else { @($Profile) }
$gitHead = (& git -C $repo rev-parse HEAD).Trim()
$gitBranch = (& git -C $repo rev-parse --abbrev-ref HEAD).Trim()
$pythonVersion = (& python --version 2>&1) -join ' '
$results = @()
$failedProfiles = 0

function Set-CommonEnvironment {
    param([string]$WorkDir, [hashtable]$Extra)
    foreach ($name in @('PROJECT_ROOT','PYTHONPATH','NOVEL_DATA_PATH','TMP','TEMP','TMPDIR','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','STORAGE_BACKEND','MOCK_PROVIDER','ENABLE_CLOUD','ENABLE_PROVIDER_FALLBACK','CREDENTIAL_VAULT_BACKEND','CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK','PYTHONDONTWRITEBYTECODE','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','ENABLE_COLLABORATION_RUNTIME','EXPERIMENTAL_FEATURES')) {
        Remove-Item ("Env:" + $name) -ErrorAction SilentlyContinue
    }
    $env:PATH = 'D:\Git\bin;' + $env:PATH
    $env:PROJECT_ROOT = $repo
    $env:PYTHONPATH = $repo
    $env:TMP = Join-Path $WorkDir 'tmp'
    $env:TEMP = $env:TMP
    $env:TMPDIR = $env:TMP
    $env:HOME = Join-Path $WorkDir 'home'
    $env:USERPROFILE = $env:HOME
    $env:APPDATA = Join-Path $WorkDir 'appdata'
    $env:LOCALAPPDATA = Join-Path $WorkDir 'localappdata'
    $env:XDG_DATA_HOME = Join-Path $WorkDir 'xdg-data'
    $env:XDG_CONFIG_HOME = Join-Path $WorkDir 'xdg-config'
    $env:XDG_CACHE_HOME = Join-Path $WorkDir 'xdg-cache'
    $env:STORAGE_BACKEND = 'file'
    $env:MOCK_PROVIDER = 'true'
    $env:ENABLE_CLOUD = 'false'
    $env:ENABLE_PROVIDER_FALLBACK = 'false'
    $env:CREDENTIAL_VAULT_BACKEND = 'memory'
    $env:CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK = 'true'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:ENABLE_COLLABORATION_RUNTIME = 'false'
    if ($Extra) {
        foreach ($key in $Extra.Keys) { Set-Item ("Env:" + $key) -Value $Extra[$key] }
    }
}

function Read-JUnitCounts {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{ tests = 0; failures = 0; errors = 0; skipped = 0; unavailable = $true } }
    try {
        [xml]$xml = Get-Content $Path -Raw
        $suites = @($xml.GetElementsByTagName('testsuite'))
        $counts = @{ tests = 0; failures = 0; errors = 0; skipped = 0; unavailable = $false }
        foreach ($suite in $suites) {
            foreach ($field in @('tests','failures','errors','skipped')) {
                $value = $suite.GetAttribute($field)
                if ($value) { $counts[$field] = $counts[$field] + [int]$value }
            }
        }
        return $counts
    } catch {
        return @{ tests = 0; failures = 0; errors = 0; skipped = 0; unavailable = $true }
    }
}

foreach ($name in $profileNames) {
    $definition = $manifest.profiles.$name
    if (-not $definition) { throw "unknown profile $name" }
    $safeName = $name -replace '[^a-z0-9-]', '-'
    if ($definition.profile_kind -eq 'v2-checks') {
        $profileDir = Join-Path $repo ('.runtime/v2-checks/' + $Label + '-' + $safeName)
        $novelData = Join-Path $profileDir 'data/novels'
    } else {
        $profileDir = Join-Path $repo ('.runtime/engineering-runs/' + $Label + '-' + $safeName)
        $novelData = Join-Path $profileDir 'data/novels'
    }
    $baseTemp = Join-Path $profileDir 'pytest'
    foreach ($sub in @($novelData, (Join-Path $profileDir 'tmp'), (Join-Path $profileDir 'home'), (Join-Path $profileDir 'appdata'), (Join-Path $profileDir 'localappdata'), (Join-Path $profileDir 'xdg-data'), (Join-Path $profileDir 'xdg-config'), (Join-Path $profileDir 'xdg-cache'), $baseTemp, (Join-Path $RunRoot 'profiles'))) {
        New-Item -ItemType Directory -Force -Path $sub | Out-Null
    }
    $extra = @{}
    if ($definition.environment) {
        foreach ($property in $definition.environment.PSObject.Properties) { $extra[$property.Name] = [string]$property.Value }
    }
    Set-CommonEnvironment -WorkDir $profileDir -Extra $extra
    $env:NOVEL_DATA_PATH = $novelData
    $junit = Join-Path $RunRoot ('profiles/' + $safeName + '.xml')
    $log = Join-Path $RunRoot ('profiles/' + $safeName + '.log')
    $arguments = @('-m','pytest','-p','no:cacheprovider','--basetemp', $baseTemp, '-q','-ra','--tb=short')
    $arguments += ('--junitxml=' + $junit)
    foreach ($path in @($definition.test_paths)) { $arguments += $path }
    foreach ($deselect in @($definition.deselections)) {
        if ($deselect) { $arguments += '--deselect'; $arguments += $deselect }
    }
    $started = Get-Date
    Push-Location $repo
    try {
        & python @arguments *> $log
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $finished = Get-Date
    $counts = Read-JUnitCounts -Path $junit
    $status = if ($exitCode -eq 0 -and $counts.failures -eq 0 -and $counts.errors -eq 0 -and -not $counts.unavailable) { 'PASS' } elseif ($counts.unavailable) { 'RECEIPT_MISSING' } else { 'FAIL' }
    if ($status -ne 'PASS') { $failedProfiles = $failedProfiles + 1 }
    $record = [ordered]@{
        profile = $name
        description = $definition.description
        status = $status
        exit_code = $exitCode
        started_utc = $started.ToUniversalTime().ToString('o')
        finished_utc = $finished.ToUniversalTime().ToString('o')
        duration_seconds = [math]::Round(($finished - $started).TotalSeconds, 1)
        counts = $counts
        command = ('python ' + ($arguments -join ' '))
        log = $log
        junit = $junit
        profile_dir = $profileDir
        novel_data_path = $novelData
        environment = $extra
    }
    $recordPath = Join-Path $RunRoot ('profiles/' + $safeName + '.json')
    $record | ConvertTo-Json -Depth 6 | Set-Content -Path $recordPath -Encoding utf8
    $results += [pscustomobject]$record
    Write-Output ('PROFILE ' + $name + ' -> ' + $status + ' exit=' + $exitCode + ' tests=' + $counts.tests + ' failures=' + $counts.failures + ' errors=' + $counts.errors + ' skipped=' + $counts.skipped)
}

$aggregate = [ordered]@{
    schema_version = 1
    document = 'windows-engineering-suite-aggregate/1'
    label = $Label
    repository = $repo
    git_head = $gitHead
    git_branch = $gitBranch
    python = $pythonVersion
    os = [System.Environment]::OSVersion.VersionString
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    profile_manifest = 'docs/v2/engineering/windows_profiles.json'
    overall_status = if ($failedProfiles -eq 0) { 'PASS' } else { 'FAIL' }
    failed_profiles = $failedProfiles
    profiles = $results
}
$aggregatePath = Join-Path $RunRoot 'aggregate.json'
$aggregate | ConvertTo-Json -Depth 8 | Set-Content -Path $aggregatePath -Encoding utf8
Write-Output ('AGGREGATE ' + $aggregatePath)
Write-Output ('OVERALL ' + $aggregate.overall_status + ' failed_profiles=' + $failedProfiles)
if ($failedProfiles -gt 0) { exit 1 }
exit 0
