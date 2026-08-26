param(
    [string]$PayloadRoot = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Application'),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\AI-Novel-Studio'),
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'

function Resolve-SafePath([string]$Value, [string]$Label) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "$Label is required." }
    if ($Value -match '[%$~]') { throw "$Label contains an unresolved variable." }
    $path = [IO.Path]::GetFullPath($Value)
    return $path
}

function Assert-UnderRoot([string]$Candidate, [string]$Root, [string]$Label) {
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $candidatePath = [IO.Path]::GetFullPath($Candidate).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($candidatePath.Equals($rootPath, [StringComparison]::OrdinalIgnoreCase) -or
        -not $candidatePath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must remain under $rootPath."
    }
}

function Assert-NoReparsePoint([string]$Path, [string]$StopAt) {
    $current = [IO.DirectoryInfo]([IO.Path]::GetFullPath($Path))
    $stop = [IO.Path]::GetFullPath($StopAt).TrimEnd([IO.Path]::DirectorySeparatorChar)
    while ($null -ne $current) {
        if ($current.Exists -and (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Refusing to traverse a reparse point: $($current.FullName)"
        }
        if ($current.FullName.TrimEnd([IO.Path]::DirectorySeparatorChar).Equals($stop, [StringComparison]::OrdinalIgnoreCase)) { break }
        $current = $current.Parent
    }
}

$payload = Resolve-SafePath $PayloadRoot 'PayloadRoot'
$destination = Resolve-SafePath $InstallRoot 'InstallRoot'
$approvedRoot = Resolve-SafePath (Join-Path $env:LOCALAPPDATA 'Programs') 'InstallRoot parent'
Assert-UnderRoot $destination $approvedRoot 'InstallRoot'
Assert-NoReparsePoint $approvedRoot ([IO.Path]::GetPathRoot($approvedRoot))
if (Test-Path -LiteralPath $destination) { Assert-NoReparsePoint $destination $approvedRoot }
$required = @(
    (Join-Path $payload 'DesktopHost\AI-Novel-Studio.DesktopHost.exe'),
    (Join-Path $payload 'Backend\app\main.py'),
    (Join-Path $payload 'Runtime\Python\python.exe'),
    (Join-Path $payload 'Frontend\dist\index.html')
)
foreach ($item in $required) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "Package is incomplete: $item" }
}

# Never place user data in the application tree.  Existing data, config,
# logs, cache and backups are deliberately preserved by this installer.
$parent = Split-Path -Parent $destination
[void](New-Item -ItemType Directory -Path $parent -Force)
$staging = Join-Path $parent ('.AI-Novel-Studio-install-' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $staging -Force)
$backup = "$destination.previous"
$movedExisting = $false
try {
    Copy-Item -LiteralPath $payload -Destination $staging -Recurse -Force
    $staged = Join-Path $staging (Split-Path -Leaf $payload)
    foreach ($item in $required) {
        $relative = $item.Substring($payload.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath (Join-Path $staged $relative) -PathType Leaf)) {
            throw "Staged package is incomplete: $relative"
        }
    }
    if (Test-Path -LiteralPath $destination) {
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
        Move-Item -LiteralPath $destination -Destination $backup
        $movedExisting = $true
    }
    Move-Item -LiteralPath $staged -Destination $destination
} catch {
    if ($movedExisting -and -not (Test-Path -LiteralPath $destination) -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $destination -ErrorAction SilentlyContinue
    }
    throw
} finally {
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue }
}

$launcher = Join-Path $destination 'Launcher\Launch-AI-Novel-Studio.cmd'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Installed launcher is missing.' }

if (-not $NoShortcut) {
    $shortcutRoot = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AI-Novel-Studio'
    [void](New-Item -ItemType Directory -Path $shortcutRoot -Force)
    $shortcut = Join-Path $shortcutRoot 'AI-Novel-Studio.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    $link.TargetPath = $launcher
    $link.WorkingDirectory = (Split-Path -Parent $launcher)
    $link.Description = 'AI-Novel-Studio DesktopHost'
    $link.Save()
}

Write-Output ("INSTALLED " + $destination)
