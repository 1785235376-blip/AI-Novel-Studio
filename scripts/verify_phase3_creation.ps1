param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$baseTemp = Join-Path $projectRoot '.pytest-tmp-phase3-acceptance'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python runtime not found: $python"
}

Write-Host 'Phase 3 backend acceptance'
& $python -m pytest @(
    'tests/test_generation_variants_phase3.py',
    'tests/test_generation_restart_recovery.py',
    'tests/test_jobs_v03.py',
    'tests/test_branch_revision.py'
) -q --basetemp $baseTemp
if ($LASTEXITCODE -ne 0) { throw 'Phase 3 backend acceptance failed' }

Write-Host 'Phase 3 frontend acceptance'
Push-Location $frontend
try {
    & npm test -- --run @(
        'src/generationRecovery.test.ts',
        'src/generationVariants.test.ts',
        'src/novel/AiWritingVariants.test.tsx',
        'src/novel/AiWritingPanel.test.tsx',
        'src/ConflictDialog.test.tsx',
        'src/RevisionPanel.test.tsx'
    )
    if ($LASTEXITCODE -ne 0) { throw 'Phase 3 frontend acceptance failed' }
    & npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'UI design token acceptance failed' }
    if (-not $SkipBuild) {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed' }
    }
} finally {
    Pop-Location
}

Write-Host 'PHASE 3 CREATION ACCEPTANCE: PASS'
