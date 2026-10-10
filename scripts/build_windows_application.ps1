param(
    [Parameter(Mandatory = $true)]
    [string]$BaseApplication,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [Parameter(Mandatory = $true)]
    [string]$HostPublishDirectory,

    [Parameter(Mandatory = $true)]
    [string]$DotnetPath
    ,
    [Parameter(Mandatory = $true)]
    [string]$NodePath,

    [Parameter(Mandatory = $true)]
    [string]$ViteCliPath,
    [Parameter(Mandatory = $true)]
    [string]$VerifiedFontDirectory
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$hostSource = Join-Path $projectRoot 'desktop-host\AI.NovelStudio.DesktopHost'
$hostProject = Join-Path $hostSource 'AI.NovelStudio.DesktopHost.csproj'
$outputApplication = Join-Path $OutputRoot 'Application'
$sourceManifest = Join-Path $OutputRoot 'desktophost-source-manifest.json'
$publishManifest = Join-Path $OutputRoot 'desktophost-publish-manifest.json'
$provenanceManifest = Join-Path $OutputRoot 'desktophost-provenance.json'
$applicationManifest = Join-Path $OutputRoot 'application-provenance.json'
$frontendBuild = Join-Path $OutputRoot 'frontend-build\dist'

function Resolve-ExistingPath([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label does not exist: $Path"
    }
    (Resolve-Path -LiteralPath $Path).Path
}

function New-FileInventory([string]$Root) {
    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    @(
        Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File |
            Sort-Object FullName |
            ForEach-Object {
                [ordered]@{
                    path = $_.FullName.Substring($resolvedRoot.Length).TrimStart('\')
                    size = $_.Length
                    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
                }
            }
    )
}

function Assert-InventoriesMatch($SourceInventory, $StagedInventory, [string]$Label) {
    $sourceJson = $SourceInventory | ConvertTo-Json -Depth 4 -Compress
    $stagedJson = $StagedInventory | ConvertTo-Json -Depth 4 -Compress
    if ($sourceJson -ne $stagedJson) {
        throw "$Label source/stage inventory mismatch"
    }
}

function Copy-ProductTree([string]$Source, [string]$Destination, [string[]]$Extensions) {
    $sourcePath = Resolve-ExistingPath $Source 'Product source'
    [void](New-Item -ItemType Directory -Path $Destination -Force)
    Get-ChildItem -LiteralPath $sourcePath -Recurse -File |
        Where-Object {
            $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and
            $_.Extension -notin @('.pyc', '.pyo') -and
            ($Extensions.Count -eq 0 -or $_.Extension -in $Extensions)
        } | ForEach-Object {
            $relative = $_.FullName.Substring($sourcePath.Length).TrimStart('\')
            $target = Join-Path $Destination $relative
            [void](New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force)
            Copy-Item -LiteralPath $_.FullName -Destination $target
        }
}

function New-ProductInventory([string]$Source, [string]$Prefix, [string[]]$Extensions) {
    $sourcePath = Resolve-ExistingPath $Source 'Product source'
    @(
        Get-ChildItem -LiteralPath $sourcePath -Recurse -File |
            Where-Object {
                $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and
                $_.Extension -notin @('.pyc', '.pyo') -and
                ($Extensions.Count -eq 0 -or $_.Extension -in $Extensions)
            } | Sort-Object FullName | ForEach-Object {
                [ordered]@{
                    path = "$Prefix\$($_.FullName.Substring($sourcePath.Length).TrimStart('\'))"
                    size = $_.Length
                    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
                }
            }
    )
}

# The font is fetched from a pinned official source with a checked digest and
# full OFL license. It is build material, never a copied proprietary OS font.
# Preparation is explicit below after the owned output tree has been staged.
$baseApplicationPath = Resolve-ExistingPath $BaseApplication 'Base Application'
$dotnetExecutable = Resolve-ExistingPath $DotnetPath '.NET host'
$nodeExecutable = Resolve-ExistingPath $NodePath 'Node.js host'
$viteCli = Resolve-ExistingPath $ViteCliPath 'Vite CLI'
$hostSourcePath = Resolve-ExistingPath $hostSource 'DesktopHost source'
$hostProjectPath = Resolve-ExistingPath $hostProject 'DesktopHost project'
$frontendSource = Resolve-ExistingPath (Join-Path $projectRoot 'frontend') 'Frontend source'
$backendAppSource = Resolve-ExistingPath (Join-Path $projectRoot 'app') 'Backend app source'

$installedSdks = @(& $dotnetExecutable --list-sdks 2>$null)
if ($LASTEXITCODE -ne 0 -or $installedSdks.Count -eq 0) {
    throw '.NET SDK is required for same-run DesktopHost provenance'
}
$selectedSdk = $installedSdks | Where-Object { $_ -match '^8\.0\.424\s+\[(.+)\]$' } | Select-Object -First 1
if (-not $selectedSdk) {
    throw 'Approved .NET SDK 8.0.424 is required for DesktopHost provenance'
}
$sdkRoot = [regex]::Match($selectedSdk, '\[(.+)\]').Groups[1].Value
$sdkVersion = '8.0.424'
$sdkBasePath = Join-Path $sdkRoot $sdkVersion
# `dotnet --list-sdks` localises the installation path on some Chinese
# Windows images (for example, output can contain replacement glyphs).  The
# executable supplied to this script is authoritative, so recover the SDK
# root from its parent when the parsed display path is not usable.
if (-not (Test-Path -LiteralPath $sdkBasePath -PathType Container)) {
    $knownSdkRoot = Split-Path -Parent $dotnetExecutable
    $knownSdkBasePath = Join-Path $knownSdkRoot (Join-Path 'sdk' $sdkVersion)
    if (Test-Path -LiteralPath $knownSdkBasePath -PathType Container) {
        $sdkRoot = $knownSdkRoot
        $sdkBasePath = $knownSdkBasePath
    }
}
if (-not (Test-Path -LiteralPath $sdkBasePath -PathType Container)) {
    throw "Selected .NET SDK base path does not exist: $sdkBasePath"
}
$hostProjectXml = [xml](Get-Content -LiteralPath $hostProjectPath -Raw)
$hostTargetFramework = [string]$hostProjectXml.Project.PropertyGroup.TargetFramework
if (-not $hostTargetFramework) {
    throw 'DesktopHost target framework is missing'
}

if (Test-Path -LiteralPath $OutputRoot) {
    throw "Output root must be fresh: $OutputRoot"
}
if (Test-Path -LiteralPath $HostPublishDirectory) {
    throw "Host publish directory must be fresh: $HostPublishDirectory"
}

[void](New-Item -ItemType Directory -Path $OutputRoot)
[void](New-Item -ItemType Directory -Path $HostPublishDirectory)

Push-Location -LiteralPath $frontendSource
try {
    & $nodeExecutable $viteCli build --configLoader runner --outDir $frontendBuild --emptyOutDir
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend production build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendBuild 'index.html') -PathType Leaf)) {
    throw 'Fresh frontend build is missing index.html'
}

$compiledSourceFiles = @(
    Get-ChildItem -LiteralPath $hostSourcePath -File -Filter '*.cs'
    Get-Item -LiteralPath $hostProjectPath
) | Sort-Object FullName -Unique
$sourceInventory = @(
    $compiledSourceFiles | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($projectRoot.Length).TrimStart('\')
            size = $_.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
        }
    }
)
$sourceInventory | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $sourceManifest -Encoding utf8

& $dotnetExecutable restore $hostProjectPath -r win-x64 -p:SelfContained=true
if ($LASTEXITCODE -ne 0) { throw "DesktopHost dependency restore failed with exit code $LASTEXITCODE" }
& $dotnetExecutable publish $hostProjectPath `
    -c Release `
    -r win-x64 `
    --self-contained true `
    --no-restore `
    -o $HostPublishDirectory
if ($LASTEXITCODE -ne 0) {
    throw "DesktopHost publish failed with exit code $LASTEXITCODE"
}

$freshHostDll = Join-Path $HostPublishDirectory 'AI-Novel-Studio.DesktopHost.dll'
if (-not (Test-Path -LiteralPath $freshHostDll -PathType Leaf)) {
    throw 'Fresh DesktopHost managed assembly is missing'
}

Copy-Item -LiteralPath $baseApplicationPath -Destination $outputApplication -Recurse

$stagedFrontend = Join-Path $outputApplication 'Frontend\dist'
if (Test-Path -LiteralPath $stagedFrontend) {
    Remove-Item -LiteralPath $stagedFrontend -Recurse -Force
}
[void](New-Item -ItemType Directory -Path (Split-Path -Parent $stagedFrontend) -Force)
Copy-Item -LiteralPath $frontendBuild -Destination $stagedFrontend -Recurse
$frontendBuildInventory = New-FileInventory $frontendBuild
$frontendStageInventory = New-FileInventory $stagedFrontend
Assert-InventoriesMatch $frontendBuildInventory $frontendStageInventory 'Frontend'

$stagedBackend = Join-Path $outputApplication 'Backend'
if (Test-Path -LiteralPath $stagedBackend) {
    Remove-Item -LiteralPath $stagedBackend -Recurse -Force
}
[void](New-Item -ItemType Directory -Path $stagedBackend)
Copy-ProductTree $backendAppSource (Join-Path $stagedBackend 'app') @('.py')
Copy-ProductTree (Join-Path $projectRoot 'local_interop_protocol') (Join-Path $stagedBackend 'local_interop_protocol') @('.py')
Copy-ProductTree (Join-Path $projectRoot 'local_interop_desktop') (Join-Path $stagedBackend 'local_interop_desktop') @('.py')
foreach ($name in @('config', 'prompts', 'workflows')) {
    Copy-ProductTree (Join-Path $projectRoot $name) (Join-Path $stagedBackend $name) @()
}
$backendSourceInventory = @()
$backendStageInventory = @()
foreach ($name in @('app', 'local_interop_protocol', 'local_interop_desktop', 'config', 'prompts', 'workflows')) {
    $extensions = if ($name -in @('app', 'local_interop_protocol', 'local_interop_desktop')) { @('.py') } else { @() }
    $backendSourceInventory += New-ProductInventory (Join-Path $projectRoot $name) $name $extensions
    $stageRoot = Join-Path $stagedBackend $name
    $stageItems = New-FileInventory $stageRoot | ForEach-Object {
        [ordered]@{ path = "$name\$($_.path)"; size = $_.size; sha256 = $_.sha256 }
    }
    $backendStageInventory += $stageItems
}
if ($backendStageInventory.Count -eq 0 -or -not (Test-Path -LiteralPath (Join-Path $stagedBackend 'app\main.py'))) {
    throw 'Backend staging inventory is missing required product files'
}
Assert-InventoriesMatch $backendSourceInventory $backendStageInventory 'Backend'

$fontSource = Resolve-ExistingPath $VerifiedFontDirectory 'Pinned CJK font directory'
$fontName = 'NotoSansSC-Regular.ttf'
$fontHash = 'eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461'
$licenseHash = '1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9'
if ((Get-FileHash (Join-Path $fontSource $fontName) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $fontHash) { throw 'CJK font is not the verified regular build; run scripts/prepare_pdf_font.py with pinned dependencies.' }
if ((Get-FileHash (Join-Path $fontSource 'OFL.txt') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $licenseHash) { throw 'Complete pinned OFL license is required.' }
$stagedFonts = Join-Path $stagedBackend 'assets\fonts'
[void](New-Item -ItemType Directory -Path $stagedFonts -Force)
foreach ($name in @($fontName, 'OFL.txt', 'font-manifest.json')) {
    Copy-Item -LiteralPath (Join-Path $fontSource $name) -Destination $stagedFonts -Force
}
$fontInventory = New-FileInventory $stagedFonts

$stagedMigrations = Join-Path $outputApplication 'Database\Migrations'
if (Test-Path -LiteralPath $stagedMigrations) {
    Remove-Item -LiteralPath $stagedMigrations -Recurse -Force
}
Copy-ProductTree (Join-Path $projectRoot 'database\migrations') $stagedMigrations @('.sql')

$stagedRelease = Join-Path $outputApplication 'release\version.json'
[void](New-Item -ItemType Directory -Path (Split-Path -Parent $stagedRelease) -Force)
Copy-Item -LiteralPath (Join-Path $projectRoot 'release\version.json') -Destination $stagedRelease -Force

$stagedHost = Join-Path $outputApplication 'DesktopHost'
if (Test-Path -LiteralPath $stagedHost) {
    Remove-Item -LiteralPath $stagedHost -Recurse -Force
}
Copy-Item -LiteralPath $HostPublishDirectory -Destination $stagedHost -Recurse

# Preserve full notices from precisely the packages restored for this build.
# NuGet package folders and exact dependency versions come from project.assets;
# do not copy unrelated versions from a shared global package cache.
$assetsPath = Join-Path $hostSourcePath 'obj\project.assets.json'
$restoredAssets = Get-Content -LiteralPath $assetsPath -Raw | ConvertFrom-Json
$packageRoots = @($restoredAssets.packageFolders.PSObject.Properties | ForEach-Object { $_.Name })
$licensePackages = @([ordered]@{ id = 'Microsoft.Web.WebView2'; version = '1.0.3537.50'; require_notices = $false })
foreach ($framework in $restoredAssets.project.frameworks.PSObject.Properties) {
    foreach ($dependency in $framework.Value.downloadDependencies) {
        if ($dependency.name -in @('Microsoft.NETCore.App.Runtime.win-x64', 'Microsoft.WindowsDesktop.App.Runtime.win-x64')) {
            $match = [regex]::Match([string]$dependency.version, '^\[(8\.0\.\d+),\s*\1\]$')
            if (-not $match.Success) { throw "Runtime license source is not an exact .NET 8 pin: $($dependency.name)" }
            $licensePackages += [ordered]@{ id = [string]$dependency.name; version = $match.Groups[1].Value; require_notices = ($dependency.name -eq 'Microsoft.NETCore.App.Runtime.win-x64') }
        }
    }
}
$licensePackages = @($licensePackages | Sort-Object { $_.id } -Unique)
if ($licensePackages.Count -ne 3) { throw 'Exact restored .NET Runtime/WindowsDesktop/WebView2 license sources are required.' }
$runtimeLicenseRoot = Join-Path $outputApplication 'Licenses\DesktopHost'
$runtimeLicenseProvenance = @()
foreach ($package in $licensePackages) {
    $relative = $package.id.ToLowerInvariant() + '\' + $package.version
    $packageDirectory = $packageRoots | ForEach-Object { Join-Path $_ $relative } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -First 1
    if (-not $packageDirectory) { throw "Restored package license source missing: $relative" }
    $licenseFiles = @(Get-ChildItem -LiteralPath $packageDirectory -File | Where-Object {
        $_.Name -match '^(?i:LICENSE)(?:[._-].*)?$' -or $_.Name -match '^(?i:THIRD-PARTY-NOTICES)(?:[._-].*)?$'
    })
    if (-not @($licenseFiles | Where-Object { $_.Name -match '^(?i:LICENSE)' }).Count) {
        throw "Full license missing in restored package: $relative"
    }
    if ($package.require_notices -and -not @($licenseFiles | Where-Object { $_.Name -match '^(?i:THIRD-PARTY-NOTICES)' }).Count) {
        throw "Full third-party notices missing in restored package: $relative"
    }
    $destination = Join-Path $runtimeLicenseRoot ($package.id + '-' + $package.version)
    [void](New-Item -ItemType Directory -Path $destination -Force)
    foreach ($file in $licenseFiles) {
        Copy-Item -LiteralPath $file.FullName -Destination $destination
        $runtimeLicenseProvenance += [ordered]@{
            package = $package.id; version = $package.version; source = $file.FullName
            staged = (Join-Path $destination $file.Name)
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        }
    }
}
$runtimeLicenseProvenance | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtimeLicenseRoot 'provenance.json') -Encoding utf8

$stagedHostDll = Join-Path $stagedHost 'AI-Novel-Studio.DesktopHost.dll'
$freshHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $freshHostDll).Hash
$stagedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $stagedHostDll).Hash
if ($freshHash -ne $stagedHash) {
    throw 'Staged DesktopHost DLL does not match the same-run fresh publish DLL'
}

$publishInventory = New-FileInventory $HostPublishDirectory
$publishInventory | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $publishManifest -Encoding utf8

[ordered]@{
    source_root = $hostSourcePath
    source_manifest = $sourceManifest
    host_publish_directory = (Resolve-Path -LiteralPath $HostPublishDirectory).Path
    fresh_host_dll_sha256 = $freshHash
    staged_host_directory = (Resolve-Path -LiteralPath $stagedHost).Path
    staged_host_dll_sha256 = $stagedHash
    hashes_match = $true
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $provenanceManifest -Encoding utf8

$release = Get-Content -LiteralPath (Join-Path $projectRoot 'release\version.json') -Raw | ConvertFrom-Json
[ordered]@{
    product_version = $release.version
    channel = 'beta'
    packaged_at_utc = [DateTime]::UtcNow.ToString('o')
    application = (Resolve-Path -LiteralPath $outputApplication).Path
    frozen_payload_source = $baseApplicationPath
    frozen_payload = @('Runtime', 'PostgreSQL', 'Launcher', 'Licenses', 'Tools', 'ConfigDefaults')
    frontend = [ordered]@{
        source = $frontendSource
        build = (Resolve-Path -LiteralPath $frontendBuild).Path
        stage = (Resolve-Path -LiteralPath $stagedFrontend).Path
        inventory = $frontendStageInventory
    }
    backend = [ordered]@{
        source = $projectRoot
        stage = (Resolve-Path -LiteralPath $stagedBackend).Path
        inventory = $backendStageInventory
    }
    desktophost = [ordered]@{
        source = $hostSourcePath
        publish = (Resolve-Path -LiteralPath $HostPublishDirectory).Path
        stage = (Resolve-Path -LiteralPath $stagedHost).Path
        managed_dll_sha256 = $stagedHash
        target_framework = $hostTargetFramework
        dotnet_executable = $dotnetExecutable
        dotnet_sdk_version = $sdkVersion
        dotnet_sdk_base_path = $sdkBasePath
    }
    source_commit = (& git -C $projectRoot rev-parse HEAD)
    font_inventory = $fontInventory
    runtime_license_provenance = $runtimeLicenseProvenance
    python_runtime = (& (Join-Path $baseApplicationPath 'Runtime\Python\python.exe') --version)
    postgresql_runtime = (& (Join-Path $baseApplicationPath 'PostgreSQL\bin\pg_ctl.exe') --version)
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $applicationManifest -Encoding utf8

Write-Output "APPLICATION_STAGED $outputApplication"
Write-Output "DESKTOPHOST_DLL_SHA256 $freshHash"
Write-Output "PROVENANCE_MANIFEST $provenanceManifest"
Write-Output "APPLICATION_PROVENANCE_MANIFEST $applicationManifest"
