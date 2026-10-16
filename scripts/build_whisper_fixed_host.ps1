param(
    [Parameter(Mandatory = $true)][string]$WhisperSourceDirectory,
    [Parameter(Mandatory = $true)][string]$CMakePath,
    [Parameter(Mandatory = $true)][string]$BuildRoot,
    [Parameter(Mandatory = $true)][string]$PackageDirectory
)
$ErrorActionPreference = 'Stop'
$expectedWhisperCommit = '4979e04f5dcaccb36057e059bbaed8a2f5288315'
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeSource = Join-Path $projectRoot 'native\local_whisper_host'
$upstream = (Resolve-Path -LiteralPath $WhisperSourceDirectory).Path
$cmake = (Resolve-Path -LiteralPath $CMakePath).Path
$buildAbsolute = [IO.Path]::GetFullPath($BuildRoot).TrimEnd('\')
$packageAbsolute = [IO.Path]::GetFullPath($PackageDirectory).TrimEnd('\')
foreach ($candidate in @($buildAbsolute, $packageAbsolute)) {
    if ($candidate -notmatch '^[A-Za-z]:\\') { throw 'Build/package roots must be absolute local Windows paths' }
    $ancestor = $candidate
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $existing = Get-Item -LiteralPath $ancestor
            if (-not $existing.PSIsContainer -or $existing.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Build/package roots cannot traverse files, junctions or links'
            }
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    foreach ($inputRoot in @($upstream, $projectRoot)) {
        $inputAbsolute = [IO.Path]::GetFullPath($inputRoot).TrimEnd('\')
        if ($candidate.Equals($inputAbsolute, [StringComparison]::OrdinalIgnoreCase) -or
            $candidate.StartsWith($inputAbsolute + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Build/package roots must be external to both source trees'
        }
    }
}
if ($buildAbsolute.Equals($packageAbsolute, [StringComparison]::OrdinalIgnoreCase) -or
    $buildAbsolute.StartsWith($packageAbsolute + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $packageAbsolute.StartsWith($buildAbsolute + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build/package roots must be separate and non-overlapping'
}
$BuildRoot = $buildAbsolute
$PackageDirectory = $packageAbsolute
if (-not (Test-Path -LiteralPath $cmake -PathType Leaf)) { throw 'Explicit CMake executable required' }
if (Test-Path -LiteralPath $BuildRoot) { throw 'BuildRoot must be fresh' }
if (Test-Path -LiteralPath $PackageDirectory) { throw 'PackageDirectory must be fresh' }
function Assert-PinnedWhisperSource([string]$SourceDirectory, [string]$Commit) {
    $head = [string](& git -C $SourceDirectory rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne $Commit) { throw 'Offline upstream must be the pinned whisper.cpp 1.8.2 commit' }
    $status = @(& git -C $SourceDirectory status --porcelain --untracked-files=all --ignored)
    if ($LASTEXITCODE -ne 0 -or $status.Count) { throw 'Pinned upstream tracked, untracked and ignored source must be clean' }
    $submodules = @(& git -C $SourceDirectory submodule status --recursive)
    if ($LASTEXITCODE -ne 0 -or @($submodules | Where-Object { $_ -match '^[+\-U]' }).Count) { throw 'Pinned upstream submodules are missing or changed' }
    $submoduleStatus = @(& git -C $SourceDirectory submodule foreach --quiet --recursive 'git status --porcelain --untracked-files=all --ignored')
    if ($LASTEXITCODE -ne 0 -or $submoduleStatus.Count) { throw 'Every pinned submodule tracked, untracked and ignored tree must be clean' }
}
Assert-PinnedWhisperSource $upstream $expectedWhisperCommit
foreach ($relative in @('include\whisper.h', 'examples\server\httplib.h', 'examples\json.hpp', 'LICENSE', 'ggml\include\ggml.h')) {
    if (-not (Test-Path -LiteralPath (Join-Path $upstream $relative) -PathType Leaf)) { throw "Offline upstream input missing: $relative" }
}
[void](New-Item -ItemType Directory -Path $BuildRoot)
[void](New-Item -ItemType Directory -Path $PackageDirectory)
$sourceFiles = @(Get-ChildItem -LiteralPath $nativeSource -File | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.Name; size = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() }
})
$cmakeVersion = @(& $cmake --version)
if ($LASTEXITCODE -ne 0) { throw 'CMake version read failed' }
# No FetchContent, clone, dependency download, model download or native inference.
# The current build deliberately uses a static CPU backend. It does not prove
# the original GPU gate; GPU packaging is a separately reviewed build profile.
& $cmake -S $nativeSource -B $BuildRoot -A x64 `
    "-DWHISPER_SOURCE_DIR=$upstream" -DGGML_CUDA=OFF -DGGML_NATIVE=OFF -DGGML_CCACHE=OFF `
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
if ($LASTEXITCODE -ne 0) { throw "Fixed Whisper configure failed: $LASTEXITCODE" }
& $cmake --build $BuildRoot --config Release --target studio-fixed-whisper-host
if ($LASTEXITCODE -ne 0) { throw "Fixed Whisper build failed: $LASTEXITCODE" }
Assert-PinnedWhisperSource $upstream $expectedWhisperCommit
$afterSourceFiles = @(Get-ChildItem -LiteralPath $nativeSource -File | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.Name; size = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() }
})
if (($sourceFiles | ConvertTo-Json -Depth 4 -Compress) -cne ($afterSourceFiles | ConvertTo-Json -Depth 4 -Compress)) {
    throw 'Native source inputs changed during build; package not admitted'
}
# Preserve the actual compiler/toolset/SDK and generated compile/link inputs.
# Do not infer versions from PATH or claim that these records prove inference.
$cachePath = Join-Path $BuildRoot 'CMakeCache.txt'
$cacheFile = Get-Item -LiteralPath $cachePath
if ($cacheFile.Length -gt 1MB -or $cacheFile.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'CMake toolchain cache capacity or identity invalid'
}
$toolchainFlags = @(Get-Content -LiteralPath $cachePath | Where-Object {
    $_ -cmatch '^(CMAKE_(BUILD_TYPE|GENERATOR[^:]*|C_COMPILER[^:]*|CXX_COMPILER[^:]*|C_FLAGS[^:]*|CXX_FLAGS[^:]*|EXE_LINKER_FLAGS[^:]*|MSVC_RUNTIME_LIBRARY|VS_[^:]*)|GGML_[^:]*|WHISPER_[^:]*):'
})
$compilerMetadata = @(Get-ChildItem -LiteralPath (Join-Path $BuildRoot 'CMakeFiles') -Recurse -File |
    Where-Object { $_.Name -in @('CMakeCCompiler.cmake', 'CMakeCXXCompiler.cmake') } | Sort-Object FullName)
$generatedProjects = @(Get-ChildItem -LiteralPath $BuildRoot -Recurse -File -Filter '*.vcxproj' | Sort-Object FullName)
if ($compilerMetadata.Count -ne 2 -or $generatedProjects.Count -lt 1 -or $generatedProjects.Count -gt 32) {
    throw 'Actual Visual Studio compiler metadata and generated projects are required'
}
$toolchainBytes = 0L
$toolchainRecords = @(@($compilerMetadata) + @($generatedProjects) | ForEach-Object {
    $toolchainBytes += $_.Length
    if ($_.Length -lt 1 -or $_.Length -gt 1MB -or $toolchainBytes -gt 3MB -or
        $_.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Toolchain evidence capacity or identity invalid' }
    [ordered]@{ path = $_.FullName.Substring($buildAbsolute.Length).TrimStart('\').Replace('\', '/')
        size = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        content = Get-Content -LiteralPath $_.FullName -Raw }
})
$hostBinary = Join-Path $PackageDirectory 'studio-fixed-whisper-host.exe'
$builtBinary = Join-Path $BuildRoot 'host-bin\Release\studio-fixed-whisper-host.exe'
if (-not (Test-Path -LiteralPath $builtBinary -PathType Leaf)) { throw 'Fresh fixed Whisper executable missing' }
Copy-Item -LiteralPath $builtBinary -Destination $hostBinary
if (-not (Test-Path -LiteralPath $hostBinary -PathType Leaf)) { throw 'Fixed Whisper executable missing' }
$binary = Get-Item -LiteralPath $hostBinary
if ($binary.Length -lt 1 -or $binary.Length -gt 512MB) { throw 'Fixed Whisper binary capacity invalid' }
# Preserve full notices, including the embedded licenses in both vendored headers.
$noticeRoot = Join-Path $PackageDirectory 'Licenses'
[void](New-Item -ItemType Directory -Path $noticeRoot)
foreach ($entry in @(
    @{ input = 'LICENSE'; output = 'whisper-LICENSE.txt' },
    @{ input = 'ggml\include\ggml.h'; output = 'ggml-source-with-license.h' },
    @{ input = 'examples\server\httplib.h'; output = 'httplib-source-with-license.h' },
    @{ input = 'examples\json.hpp'; output = 'json-source-with-license.hpp' }
)) { Copy-Item -LiteralPath (Join-Path $upstream $entry.input) -Destination (Join-Path $noticeRoot $entry.output) }
$inventory = @(Get-ChildItem -LiteralPath $PackageDirectory -File -Recurse | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring((Resolve-Path -LiteralPath $PackageDirectory).Path.Length).TrimStart('\').Replace('\', '/')
        size = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant() }
})
$packageHead = [string](& git -C $projectRoot rev-parse HEAD)
$sourceStatus = @(& git -C $projectRoot status --porcelain --untracked-files=no)
[ordered]@{
    schema = 'studio-fixed-whisper-package/1'
    protocol = 'studio-fixed-whisper-host/1'
    executable = 'studio-fixed-whisper-host.exe'
    executable_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $hostBinary).Hash.ToLowerInvariant()
    upstream_version = '1.8.2'; upstream_commit = $expectedWhisperCommit
    studio_source_commit = $packageHead.Trim(); studio_tracked_source_clean = ($sourceStatus.Count -eq 0)
    native_source_files = $sourceFiles; cmake = $cmake; cmake_version = $cmakeVersion
    toolchain = [ordered]@{ verification = 'BUILD_METADATA_ONLY'; cache_flags = $toolchainFlags
        compiler_and_generated_projects = $toolchainRecords }
    backend = 'CPU_STATIC'; gpu_verification = 'NOT_RUN'; inference_verification = 'NOT_RUN'
    product_acceptance = 'LOCAL_REQUIRED'; files = $inventory
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PackageDirectory 'whisper-fixed-host-package.json') -Encoding utf8
if ((Get-Item -LiteralPath (Join-Path $PackageDirectory 'whisper-fixed-host-package.json')).Length -gt 8MB) {
    throw 'Fixed Whisper manifest evidence capacity exceeded; package not admitted'
}
Write-Output "WHISPER_FIXED_HOST_PACKAGE $PackageDirectory"
Write-Output "WHISPER_FIXED_HOST_SHA256 $((Get-FileHash -Algorithm SHA256 -LiteralPath $hostBinary).Hash.ToLowerInvariant())"
