param(
    [switch]$SkipBuild,
    [switch]$RequireDocker
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$baseTemp = Join-Path $projectRoot '.pytest-tmp-phase5-acceptance'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python runtime not found: $python"
}

Write-Host 'Phase 5 backend acceptance'
& $python -m pytest @(
    'tests/test_phase5_outline.py',
    'tests/test_phase5_volumes.py',
    'tests/test_phase5_scenes.py',
    'tests/test_phase5_story_routes.py'
) -q --basetemp $baseTemp
if ($LASTEXITCODE -ne 0) { throw 'Phase 5 backend acceptance failed' }

Write-Host 'Phase 5 frontend acceptance'
Push-Location $frontend
try {
    & npm test -- --run @(
        'src/novel/OutlineEditor.test.tsx',
        'src/novel/VolumeEditor.test.tsx',
        'src/novel/SceneEditor.test.tsx',
        'src/novel/StoryRouteEditor.test.tsx'
    )
    if ($LASTEXITCODE -ne 0) { throw 'Phase 5 frontend acceptance failed' }
    & npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'UI design token acceptance failed' }
    if (-not $SkipBuild) {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed' }
    }
} finally {
    Pop-Location
}

Write-Host 'Phase 5 container availability'
$dockerProcess = Start-Process -FilePath 'docker' -ArgumentList 'info' -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $env:TEMP 'ai-novel-studio-docker-info.out') -RedirectStandardError (Join-Path $env:TEMP 'ai-novel-studio-docker-info.err')
if ($dockerProcess.ExitCode -eq 0) {
    Write-Host 'Docker engine available'
} elseif ($RequireDocker) {
    throw 'Docker engine is required but unavailable'
} else {
    Write-Warning 'Docker engine unavailable; container deployment verification remains pending'
}

Write-Host 'PHASE 5 STORY PLANNING ACCEPTANCE: PASS'
