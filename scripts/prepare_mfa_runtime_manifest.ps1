param(
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$PythonRelativePath,
    [Parameter(Mandatory = $true)][string]$CliRelativePath,
    [Parameter(Mandatory = $true)][string]$ManifestPath
)
$ErrorActionPreference = 'Stop'
# File preparation only: no install, model download, Python or MFA execution.
$prefixRoot = (Resolve-Path -LiteralPath $RuntimeRoot).Path.TrimEnd('\')
if (-not (Test-Path -LiteralPath $prefixRoot -PathType Container)) { throw 'A self-contained runtime prefix is required' }
if ((Get-Item -LiteralPath $prefixRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime links are rejected' }
if (-not [IO.Path]::IsPathRooted($ManifestPath)) { throw 'ManifestPath must be absolute' }
$manifestTarget = [IO.Path]::GetFullPath($ManifestPath)
if ($manifestTarget.Equals($prefixRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $manifestTarget.StartsWith($prefixRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest must be outside the runtime prefix' }
if ([IO.Path]::GetExtension($manifestTarget) -cne '.json' -or (Test-Path -LiteralPath $manifestTarget)) { throw 'A fresh external .json manifest is required' }
if (-not (Test-Path -LiteralPath (Split-Path -Parent $manifestTarget) -PathType Container)) { throw 'Manifest parent directory must already exist' }
function Assert-RelativePath([string]$Name) {
    if ($Name.Length -lt 1 -or $Name.Length -gt 1024 -or $Name -match '[\\:\x00-\x1f]' -or $Name.StartsWith('/')) { throw 'Invalid relative runtime path' }
    $segments = $Name.Split('/')
    if ($segments.Count -gt 32 -or @($segments | Where-Object { $_ -in @('', '.', '..') }).Count) { throw 'Invalid relative runtime path' }
}
Assert-RelativePath $PythonRelativePath
Assert-RelativePath $CliRelativePath
if ([IO.Path]::GetFileName($PythonRelativePath) -ine 'python.exe' -or [IO.Path]::GetFileName($CliRelativePath) -ine 'mfa.exe') {
    throw 'The Windows prefix must contain explicit python.exe and mfa.exe'
}
$pendingDirectories = [Collections.Generic.Stack[string]]::new()
$pendingDirectories.Push($prefixRoot)
$fileRows = [Collections.Generic.List[object]]::new()
$names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$identities = @{}
$directoryIdentities = @{}
$totalBytes = [long]0
while ($pendingDirectories.Count) {
    $directory = $pendingDirectories.Pop()
    $directoryInfo = Get-Item -LiteralPath $directory
    if ($directoryInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime links are rejected' }
    $directoryIdentities[$directory] = $directoryInfo.LastWriteTimeUtc.Ticks
    if ($directoryIdentities.Count -gt 40000) { throw 'Runtime directory limit exceeded' }
    foreach ($entry in Get-ChildItem -LiteralPath $directory -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime links are rejected' }
        $relative = $entry.FullName.Substring($prefixRoot.Length + 1).Replace('\', '/')
        Assert-RelativePath $relative
        if ($entry.PSIsContainer) { $pendingDirectories.Push($entry.FullName); continue }
        if ($entry -isnot [IO.FileInfo] -or -not $names.Add($relative)) { throw 'Duplicate or non-regular runtime file' }
        if ($entry.Name -ieq 'pyvenv.cfg') { throw 'A delegated venv is not a self-contained runtime' }
        $totalBytes += $entry.Length
        if ($fileRows.Count -ge 20000 -or $totalBytes -gt 8GB) { throw 'Runtime file or byte limit exceeded' }
        $identity = @($entry.Length, $entry.LastWriteTimeUtc.Ticks, $entry.CreationTimeUtc.Ticks) -join ':'
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $entry.FullName).Hash.ToLowerInvariant()
        $after = Get-Item -LiteralPath $entry.FullName
        if ((@($after.Length, $after.LastWriteTimeUtc.Ticks, $after.CreationTimeUtc.Ticks) -join ':') -cne $identity) { throw 'Runtime changed while preparing manifest' }
        $identities[$entry.FullName] = $identity
        $fileRows.Add([ordered]@{ path = $relative; sha256 = $hash })
    }
}
$actualNames = @($fileRows | ForEach-Object { $_.path })
if (-not ($actualNames -ccontains $PythonRelativePath) -or -not ($actualNames -ccontains $CliRelativePath) -or -not ($actualNames -ccontains 'Lib/os.py')) {
    throw 'Pinned Python, CLI and standard library are required'
}
if (-not @($actualNames | Where-Object { $_ -match '\.(dll|pyd)$' }).Count) { throw 'Complete native runtime dependencies are required' }
$metadata = @($fileRows | Where-Object { $_.path -cmatch '(^|/)montreal_forced_aligner-[^/]+\.dist-info/METADATA$' })
if ($metadata.Count -ne 1) { throw 'Exactly one MFA package METADATA is required' }
$metadataFile = Join-Path $prefixRoot $metadata[0].path
if ((Get-Item -LiteralPath $metadataFile).Length -gt 1MB) { throw 'MFA package metadata too large' }
$package = Get-Content -LiteralPath $metadataFile -Raw -Encoding UTF8
if ($package -notmatch '(?im)^Name: montreal[-_]forced[-_]aligner\r?$' -or $package -notmatch '(?m)^Version: 3\.3\.7\r?$') { throw 'Pinned MFA 3.3.7 is required' }
foreach ($path in $identities.Keys) {
    $file = Get-Item -LiteralPath $path
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        (@($file.Length, $file.LastWriteTimeUtc.Ticks, $file.CreationTimeUtc.Ticks) -join ':') -cne $identities[$path]) { throw 'Runtime changed before manifest publication' }
}
foreach ($path in $directoryIdentities.Keys) {
    $directory = Get-Item -LiteralPath $path
    if (($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $directory.LastWriteTimeUtc.Ticks -ne $directoryIdentities[$path]) { throw 'Runtime directory changed before manifest publication' }
}
$manifest = [ordered]@{ schema = 'studio-mfa-runtime/1'; engine_version = '3.3.7'; cli = $CliRelativePath;
    python = $PythonRelativePath; files = @($fileRows | Sort-Object { $_.path }) }
$bytes = [Text.UTF8Encoding]::new($false).GetBytes(($manifest | ConvertTo-Json -Depth 5))
if ($bytes.Length -gt 4MB) { throw 'Runtime manifest capacity exceeded' }
$output = [IO.File]::Open($manifestTarget, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $output.Write($bytes, 0, $bytes.Length); $output.Flush($true) } finally { $output.Dispose() }
Write-Output "MFA_RUNTIME_MANIFEST $manifestTarget"
Write-Output "MFA_RUNTIME_MANIFEST_SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $manifestTarget).Hash.ToLowerInvariant())"
Write-Output 'MFA_RUNTIME_EXECUTION NOT_RUN'
