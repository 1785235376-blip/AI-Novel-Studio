param(
    [string]$ApplicationRoot,
    [string]$LocalAppDataRoot,
    [string]$UserProfileRoot
)

$ErrorActionPreference = 'Stop'

function Resolve-AbsolutePath([string]$Value, [string]$Label) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "$Label is required." }
    if ($Value -match '[%$~]') { throw "$Label contains an unresolved variable." }
    return [IO.Path]::GetFullPath($Value)
}

$launcherRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$applicationCandidates = @()
if ($ApplicationRoot) {
    $applicationCandidates = @(Resolve-AbsolutePath $ApplicationRoot 'ApplicationRoot')
} else {
    # The launcher is copied both into Application\Launcher and into the
    # acceptance package root. Resolve both layouts without using cwd.
    $applicationCandidates = @(
        (Resolve-AbsolutePath (Join-Path $launcherRoot '..') 'ApplicationRoot'),
        (Resolve-AbsolutePath (Join-Path $launcherRoot 'Application') 'ApplicationRoot')
    )
}
$application = $applicationCandidates |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ 'Runtime\Python\python.exe') -PathType Leaf } |
    Select-Object -First 1
if (-not $application) {
    throw 'AI-Novel-Studio Application root could not be resolved.'
}
$python = Join-Path $application 'Runtime\Python\python.exe'
$backend = Join-Path $application 'Backend'
$required = @(
    $python,
    (Join-Path $backend 'app\packaging\packaged_desktop_launcher.py'),
    (Join-Path $backend 'app\main.py'),
    (Join-Path $application 'Frontend\dist\index.html'),
    (Join-Path $application 'DesktopHost\AI-Novel-Studio.DesktopHost.exe'),
    (Join-Path $application 'PostgreSQL\bin\postgres.exe'),
    (Join-Path $application 'PostgreSQL\bin\initdb.exe'),
    (Join-Path $application 'release\version.json')
)
foreach ($item in $required) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) {
        throw "AI-Novel-Studio runtime is incomplete: $item"
    }
}

$local = if ($LocalAppDataRoot) { Resolve-AbsolutePath $LocalAppDataRoot 'LocalAppDataRoot' } else { Resolve-AbsolutePath $env:LOCALAPPDATA 'LOCALAPPDATA' }
$profile = if ($UserProfileRoot) { Resolve-AbsolutePath $UserProfileRoot 'UserProfileRoot' } else { Resolve-AbsolutePath $env:USERPROFILE 'USERPROFILE' }
if ([string]::IsNullOrWhiteSpace($local) -or [string]::IsNullOrWhiteSpace($profile)) {
    throw 'LOCALAPPDATA and USERPROFILE are required for the packaged runtime.'
}

# The packaged launcher is the only supported DesktopHost entry point.  It
# starts the local PostgreSQL/backend pair, establishes the one-shot session,
# and then owns the WebView2 host process.  No provider secret is read here.
$launcherArgs = @(
    '-I', '-m', 'app.packaging.packaged_desktop_launcher',
    '--application-root', $application,
    '--local-app-data', $local,
    '--user-profile', $profile
)
Push-Location -LiteralPath $backend
try {
    & $python @launcherArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
