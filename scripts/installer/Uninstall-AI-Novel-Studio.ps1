param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\AI-Novel-Studio'),
    [switch]$RemoveUserData
)

$ErrorActionPreference = 'Stop'

function Resolve-SafePath([string]$Value, [string]$Label) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "$Label is required." }
    if ($Value -match '[%$~]') { throw "$Label contains an unresolved variable." }
    [IO.Path]::GetFullPath($Value)
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

$destination = Resolve-SafePath $InstallRoot 'InstallRoot'
$approvedRoot = Resolve-SafePath (Join-Path $env:LOCALAPPDATA 'Programs') 'InstallRoot parent'
if ($destination.Equals($approvedRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not $destination.StartsWith($approvedRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'InstallRoot must remain under %LOCALAPPDATA%\Programs.'
}
Assert-NoReparsePoint $approvedRoot ([IO.Path]::GetPathRoot($approvedRoot))
if (Test-Path -LiteralPath $destination) { Assert-NoReparsePoint $destination $approvedRoot }
if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
$shortcutRoot = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AI-Novel-Studio'
if (Test-Path -LiteralPath $shortcutRoot) {
    Assert-NoReparsePoint $shortcutRoot (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
    Remove-Item -LiteralPath $shortcutRoot -Recurse -Force
}
if ($RemoveUserData) {
    $userRoot = Resolve-SafePath (Join-Path $env:LOCALAPPDATA 'AI-Novel-Studio') 'UserDataRoot'
    Assert-NoReparsePoint $userRoot ([IO.Path]::GetPathRoot($userRoot))
    if (Test-Path -LiteralPath $userRoot) { Remove-Item -LiteralPath $userRoot -Recurse -Force }
}
Write-Output ('UNINSTALLED ' + $destination)
