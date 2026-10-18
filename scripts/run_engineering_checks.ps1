# Run the V2 engineering checks from a clean isolated directory.
#
# Usage:
#   pwsh -File scripts/run_engineering_checks.ps1 -Checks backend-file,frontend,focused
#   pwsh -File scripts/run_engineering_checks.ps1 -Checks backend-pg -PostgresUrl 'postgresql://postgres@127.0.0.1:55432/v2_creative_tests'
#
# Isolation: PROJECT_ROOT is this worktree; all mutable state (data, temp, home, config,
# browser profiles, logs, JUnit) lives under -RunRoot. Nothing is written to the user profile
# or the production novel data. No model is called and no paid API is used.
param(
    [ValidateSet('backend-file', 'backend-pg', 'frontend', 'focused', 'desktop-host', 'all')]
    [string[]]$Checks = @('backend-file', 'frontend', 'focused'),
    [string]$RunRoot = '',
    [string]$PostgresUrl = ''
)

$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $RunRoot) {
    $RunRoot = Join-Path (Split-Path $repo -Parent) ('Engineering-Runs\local-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
if ($Checks -contains 'all') { $Checks = @('backend-file', 'backend-pg', 'frontend', 'focused', 'desktop-host') }

$logs = Join-Path $RunRoot 'logs'
$evidence = Join-Path $RunRoot 'evidence'
$tmp = Join-Path $RunRoot 'tmp'
foreach ($dir in @($logs, $evidence, $tmp,
        (Join-Path $RunRoot 'data\novels'), (Join-Path $RunRoot 'data\backups'),
        (Join-Path $RunRoot 'home'), (Join-Path $RunRoot 'appdata'),
        (Join-Path $RunRoot 'localappdata'), (Join-Path $RunRoot 'config'),
        (Join-Path $RunRoot 'cache'), (Join-Path $RunRoot 'state'))) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

# Isolation must be complete before any app import happens in a child pytest process.
# Repo fixtures require the profile (LOCALAPPDATA/NOVEL_DATA_PATH/basetemp) to live under
# PROJECT_ROOT/.runtime, so the profile is inside the repo while logs/evidence stay outside.
$profileName = Split-Path $RunRoot -Leaf
$profile = Join-Path $repo (Join-Path '.runtime\engineering-runs' $profileName)
foreach ($dir in @((Join-Path $profile 'data\novels'), (Join-Path $profile 'data\backups'),
        (Join-Path $profile 'tmp'), (Join-Path $profile 'home'), (Join-Path $profile 'appdata'),
        (Join-Path $profile 'localappdata'), (Join-Path $profile 'config'),
        (Join-Path $profile 'cache'), (Join-Path $profile 'state'))) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
$env:PROJECT_ROOT = $repo
$env:NOVEL_DATA_PATH = Join-Path $profile 'data\novels'
$env:BACKUP_PATH = Join-Path $profile 'data\backups'
$env:DATABASE_BACKUP_PATH = Join-Path $profile 'data\database-backups'
$env:KNOWLEDGE_SOURCE_PATH = Join-Path $profile 'data\novels'
$env:STORAGE_BACKEND = 'file'
$env:MOCK_PROVIDER = 'true'
$env:MOCK_STREAM_DELAY_MS = '0'
$env:ENABLE_CLOUD = 'false'
$env:ENABLE_PROVIDER_FALLBACK = 'false'
$env:CREDENTIAL_VAULT_BACKEND = 'memory'
$env:CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK = 'true'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:TMP = Join-Path $profile 'tmp'
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
$env:HOME = Join-Path $profile 'home'
$env:USERPROFILE = $env:HOME
$env:APPDATA = Join-Path $profile 'appdata'
$env:LOCALAPPDATA = Join-Path $profile 'localappdata'
$env:XDG_CONFIG_HOME = Join-Path $profile 'config'
$env:XDG_CACHE_HOME = Join-Path $profile 'cache'
$env:XDG_DATA_HOME = Join-Path $profile 'data'
$env:XDG_STATE_HOME = Join-Path $profile 'state'

$python = (Get-Command python -ErrorAction Stop).Source
$results = @()

function Invoke-Check([string]$Name, [string]$LogName, [scriptblock]$Action) {
    $started = Get-Date
    & $Action *> (Join-Path $logs $LogName)
    $code = $LASTEXITCODE
    $ended = Get-Date
    $script:results += [pscustomobject]@{
        check = $Name
        exit_code = $code
        duration_seconds = [math]::Round(($ended - $started).TotalSeconds, 1)
        log = (Join-Path $logs $LogName)
    }
    Write-Output ("CHECK " + $Name + " EXIT=" + $code)
}

Set-Location $repo

if ($Checks -contains 'backend-file') {
    Invoke-Check 'backend-file' 'backend-file.log' {
        & $python -m pytest -p no:cacheprovider --basetemp (Join-Path $profile 'pytest-file') -q -ra --tb=short --junitxml (Join-Path $evidence 'backend-file.xml')
    }
}

if ($Checks -contains 'backend-pg') {
    if (-not $PostgresUrl) {
        Write-Output 'CHECK backend-pg SKIPPED=NO_POSTGRES_URL (provide -PostgresUrl pointing at a disposable V2 database; see docs/v2/engineering/RUNBOOK.md)'
        $script:results += [pscustomobject]@{ check = 'backend-pg'; exit_code = 2; duration_seconds = 0; log = '' }
    } else {
        $env:STORAGE_BACKEND = 'postgres'
        $env:DATABASE_URL = $PostgresUrl
        $env:TEST_POSTGRES_DATABASE_URL = $PostgresUrl
        $env:PYTHONPATH = (Join-Path $repo '.github\ci') + ';' + $repo
        Invoke-Check 'backend-pg' 'backend-pg.log' {
            & $python -m pytest -p postgres_gate -p no:cacheprovider --basetemp (Join-Path $profile 'pytest-pg') -q -ra --tb=short --junitxml (Join-Path $evidence 'backend-pg.xml')
        }
        $env:STORAGE_BACKEND = 'file'
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:TEST_POSTGRES_DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}

if ($Checks -contains 'frontend') {
    Push-Location (Join-Path $repo 'frontend')
    try {
        Invoke-Check 'frontend-install' 'frontend-install.log' { corepack pnpm install --frozen-lockfile }
        Invoke-Check 'frontend-test' 'frontend-test.log' { corepack pnpm test }
        Invoke-Check 'frontend-build' 'frontend-build.log' { corepack pnpm build }
        Invoke-Check 'frontend-lint' 'frontend-lint.log' { corepack pnpm lint }
    } finally { Pop-Location }
}

if ($Checks -contains 'focused') {
    $focused = @(
        'tests/test_engineering_traceability.py',
        'tests/test_r5_comic_layouts.py',
        'tests/test_r5_comic_mounted.py',
        'tests/test_r5_interactive_story.py',
        'tests/test_r5_multilingual_editions.py',
        'tests/test_r5_pause_aware_audio.py',
        'tests/test_r5_voice_subtitles.py',
        'tests/test_r5_project_forks.py',
        'tests/test_r5_structured_forks.py',
        'tests/test_r5_writer_room_mounted.py',
        'tests/test_r5_offline_sync.py',
        'tests/test_r5_declarative_templates.py',
        'tests/test_post_interop_style_model.py',
        'tests/test_post_interop_scene_mind.py',
        'tests/test_post_interop_revision_model.py',
        'tests/test_post_interop_wave3_broker.py',
        'tests/test_post_interop_wave3_research.py',
        'tests/test_post_interop_shared_universe.py',
        'tests/test_post_interop_wave5_templates_sdk_comics.py',
        'tests/test_r4_change_impact.py',
        'tests/test_r4_change_impact_mounted.py',
        'tests/test_r4_author_task_projection.py',
        'tests/test_r4_portable_batches.py',
        'tests/test_r4_reader_sessions.py',
        'tests/test_r4_timeline_exchange.py',
        'tests/test_r4_director_exchange_mounted.py',
        'tests/test_r4_model_broker.py',
        'tests/test_r4_local_ai_inspection.py',
        'tests/test_r4_capabilities.py',
        'tests/test_v2_director_workspace.py',
        'tests/test_v2_creative_workflows.py',
        'tests/test_local_ai_environment_v2.py',
        'tests/test_asset_library.py',
        'tests/test_asset_lifecycle_r2.py',
        'tests/test_phase4_timeline.py',
        'tests/test_v2_audio_editing_pipeline.py',
        'tests/test_v2_video_runtime_foundation.py',
        'tests/test_v2_screenplay_export.py',
        'tests/test_r4_character_author_api.py',
        'tests/test_round2_bible.py'
    )
    Invoke-Check 'focused-capabilities' 'focused-capabilities.log' {
        & $python -m pytest -q -p no:cacheprovider -ra --tb=short --basetemp (Join-Path $profile 'pytest-focused') --junitxml (Join-Path $evidence 'focused-capabilities.xml') @focused
    }
}

if ($Checks -contains 'desktop-host') {
    $project = Join-Path $repo 'desktop-host\AI.NovelStudio.DesktopHost\AI.NovelStudio.DesktopHost.csproj'
    if (Get-Command dotnet -ErrorAction SilentlyContinue) {
        Invoke-Check 'desktop-host-build' 'desktop-host-build.log' { dotnet build $project -c Release --nologo }
    } else {
        Write-Output 'CHECK desktop-host-build SKIPPED=DOTNET_SDK_MISSING'
        $script:results += [pscustomobject]@{ check = 'desktop-host-build'; exit_code = 2; duration_seconds = 0; log = '' }
    }
}

$head = ''
try { $head = (git rev-parse HEAD).Trim() } catch { }
$receipt = [pscustomobject]@{
    schema_version = 1
    repository = '1785235376-blip/AI-Novel-Studio'
    git_sha = $head
    run_root = $RunRoot
    checks = $results
    tool_versions = [pscustomobject]@{
        python = (& $python --version 2>&1 | Out-String).Trim()
        node = (& node --version 2>&1 | Out-String).Trim()
        pnpm = (& corepack pnpm --version 2>&1 | Out-String).Trim()
        ffmpeg = (& ffmpeg -version 2>&1 | Select-Object -First 1 | Out-String).Trim()
        dotnet = if (Get-Command dotnet -ErrorAction SilentlyContinue) { (& dotnet --version 2>&1 | Out-String).Trim() } else { 'MISSING' }
        postgres = if (Get-Command psql -ErrorAction SilentlyContinue) { (& psql --version 2>&1 | Out-String).Trim() } else { 'external-url-provided-or-missing' }
    }
    isolation = [pscustomobject]@{
        project_root = $env:PROJECT_ROOT
        novel_data_path = $env:NOVEL_DATA_PATH
        storage_backend = 'file (backend-pg overrides in its subprocess only)'
        mock_provider = $env:MOCK_PROVIDER
        enable_cloud = $env:ENABLE_CLOUD
        credential_vault = $env:CREDENTIAL_VAULT_BACKEND
    }
}
$receipt | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $evidence 'checks-receipt.json')
Write-Output ('RECEIPT ' + (Join-Path $evidence 'checks-receipt.json'))
$failed = @($results | Where-Object { $_.exit_code -ne 0 })
Write-Output ('FAILED_CHECKS ' + $failed.Count)
if ($failed.Count -gt 0) { exit 1 }
exit 0
