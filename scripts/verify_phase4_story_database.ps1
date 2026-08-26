param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$baseTemp = Join-Path $projectRoot '.pytest-tmp-phase4-acceptance'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python runtime not found: $python"
}

Write-Host 'Phase 4 backend acceptance'
& $python -m pytest @(
    'tests/test_phase4_world_summary.py',
    'tests/test_phase4_characters.py',
    'tests/test_phase4_locations.py',
    'tests/test_phase4_timeline.py',
    'tests/test_phase4_foreshadowing.py',
    'tests/test_phase4_relationships.py'
) -q --basetemp $baseTemp
if ($LASTEXITCODE -ne 0) { throw 'Phase 4 backend acceptance failed' }

Write-Host 'Phase 4 frontend acceptance'
Push-Location $frontend
try {
    & npm test -- --run @(
        'src/novel/WorldSummaryEditor.test.tsx',
        'src/novel/CharacterEditor.test.tsx',
        'src/novel/LocationEditor.test.tsx',
        'src/novel/TimelineEditor.test.tsx',
        'src/novel/ForeshadowingEditor.test.tsx',
        'src/novel/RelationshipEditor.test.tsx'
    )
    if ($LASTEXITCODE -ne 0) { throw 'Phase 4 frontend acceptance failed' }
    & npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'UI design token acceptance failed' }
    if (-not $SkipBuild) {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed' }
    }
} finally {
    Pop-Location
}

Write-Host 'PHASE 4 STORY DATABASE ACCEPTANCE: PASS'
