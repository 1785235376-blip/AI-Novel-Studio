param(
    [Parameter(Mandatory = $true)] [string]$BaseApplication,
    [Parameter(Mandatory = $true)] [string]$OutputRoot,
    [Parameter(Mandatory = $true)] [string]$HostPublishDirectory,
    [Parameter(Mandatory = $true)] [string]$DotnetPath,
    [Parameter(Mandatory = $true)] [string]$NodePath,
    [Parameter(Mandatory = $true)] [string]$ViteCliPath,
    [switch]$SkipIExpress
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$buildScript = Join-Path $scriptRoot 'build_windows_application.ps1'
$installerRoot = Join-Path $scriptRoot 'installer'

function Resolve-Absolute([string]$Value, [string]$Label) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "$Label is required." }
    $path = [IO.Path]::GetFullPath($Value)
    if ($path -match '[%$~]') { throw "$Label contains an unresolved variable." }
    return $path
}

$output = Resolve-Absolute $OutputRoot 'OutputRoot'
$hostPublish = Resolve-Absolute $HostPublishDirectory 'HostPublishDirectory'
if (Test-Path -LiteralPath $output) { throw "OutputRoot must be fresh: $output" }
if (Test-Path -LiteralPath $hostPublish) { throw "HostPublishDirectory must be fresh: $hostPublish" }

& $buildScript `
    -BaseApplication (Resolve-Absolute $BaseApplication 'BaseApplication') `
    -OutputRoot $output `
    -HostPublishDirectory $hostPublish `
    -DotnetPath (Resolve-Absolute $DotnetPath 'DotnetPath') `
    -NodePath (Resolve-Absolute $NodePath 'NodePath') `
    -ViteCliPath (Resolve-Absolute $ViteCliPath 'ViteCliPath')
if ($LASTEXITCODE -ne 0) { throw "Application staging failed with exit code $LASTEXITCODE" }

$application = Join-Path $output 'Application'
$launcher = Join-Path $application 'Launcher'
[void](New-Item -ItemType Directory -Path $launcher -Force)
Copy-Item -LiteralPath (Join-Path $installerRoot 'Launch-AI-Novel-Studio.ps1') -Destination $launcher -Force
Copy-Item -LiteralPath (Join-Path $installerRoot 'Launch-AI-Novel-Studio.cmd') -Destination $launcher -Force
Copy-Item -LiteralPath (Join-Path $installerRoot 'Uninstall-AI-Novel-Studio.ps1') -Destination $launcher -Force

$packageRoot = Join-Path $output 'Package'
[void](New-Item -ItemType Directory -Path $packageRoot -Force)
Copy-Item -LiteralPath $application -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $installerRoot 'Install-AI-Novel-Studio.ps1') -Destination $packageRoot -Force
Copy-Item -LiteralPath (Join-Path $installerRoot 'Uninstall-AI-Novel-Studio.ps1') -Destination $packageRoot -Force
Copy-Item -LiteralPath (Join-Path $installerRoot 'Launch-AI-Novel-Studio.ps1') -Destination $packageRoot -Force
Copy-Item -LiteralPath (Join-Path $installerRoot 'Launch-AI-Novel-Studio.cmd') -Destination $packageRoot -Force

$versionPath = Join-Path $projectRoot 'release\version.json'
$version = Get-Content -LiteralPath $versionPath -Raw -Encoding UTF8 | ConvertFrom-Json
$readme = @"
AI-Novel-Studio $($version.display_version) - Windows DesktopHost acceptance package

This is an internal acceptance build. It is not a public release and does not
contain provider credentials or user data. Start the DesktopHost with:
  Application\Launcher\Launch-AI-Novel-Studio.cmd

Install to the normal per-user location with:
  powershell -ExecutionPolicy Bypass -File .\Install-AI-Novel-Studio.ps1

Provider credentials are entered at runtime inside DesktopHost only. The
packaged backend scrubs provider-key environment variables and uses a memory
credential vault. Do not put keys in files, logs, URLs or tests.
"@
Set-Content -LiteralPath (Join-Path $packageRoot 'README-ACCEPTANCE.txt') -Value $readme -Encoding UTF8

$manifestFiles = @(
    Get-ChildItem -LiteralPath $packageRoot -Recurse -File |
        Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' } |
        Sort-Object FullName
)
$rootResolved = (Resolve-Path -LiteralPath $packageRoot).Path
$inventory = @($manifestFiles | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($rootResolved.Length).TrimStart('\\')
        size = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
    }
})
$manifest = [ordered]@{
    package_kind = 'windows-desktophost-acceptance'
    public_release = $false
    product = $version.product
    version = $version.version
    channel = $version.channel
    packaged_at_utc = [DateTime]::UtcNow.ToString('o')
    application_root = $application
    credential_policy = 'runtime-only-desktophost-memory-vault-no-provider-env-inheritance'
    files = $inventory
}
$manifestPath = Join-Path $output 'acceptance-package-manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $packageRoot 'acceptance-package-manifest.json') -Force

$zipPath = Join-Path $output 'AI-Novel-Studio-Windows-DesktopHost-acceptance.zip'
$zipInputs = Get-ChildItem -LiteralPath $packageRoot -Force
Compress-Archive -Path $zipInputs.FullName -DestinationPath $zipPath -CompressionLevel Optimal

if (-not $SkipIExpress) {
    $iexpress = Join-Path $env:WINDIR 'System32\iexpress.exe'
    if (Test-Path -LiteralPath $iexpress) {
        # IExpress writes SED files as ANSI.  Keep its temporary source and
        # target under an ASCII-only Windows temp root so a Chinese workspace
        # path cannot be converted to `?` and silently break the build.
        $tempRoot = [IO.Path]::GetTempPath()
        if ($tempRoot -match '[^\x00-\x7F]') { $tempRoot = Join-Path $env:WINDIR 'Temp' }
        $iexpressWork = Join-Path $tempRoot ('AI-Novel-Studio-iexpress-' + [guid]::NewGuid().ToString('N'))
        $iexpressSource = Join-Path $iexpressWork 'source'
        [void](New-Item -ItemType Directory -Path $iexpressSource -Force)
        Copy-Item -LiteralPath $zipPath -Destination (Join-Path $iexpressSource 'payload.zip') -Force
        $outerInstall = @'
@echo off
setlocal
set "ROOT=%TEMP%\AI-Novel-Studio-acceptance-%RANDOM%-%RANDOM%"
set "PAYLOAD_ZIP=%~dp0payload.zip"
mkdir "%ROOT%" >nul 2>&1
if errorlevel 1 (
  set "EXIT_CODE=1"
  goto :cleanup
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory($env:PAYLOAD_ZIP, $env:ROOT)"
if errorlevel 1 (
  set "EXIT_CODE=1"
  goto :cleanup
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\Install-AI-Novel-Studio.ps1" -PayloadRoot "%ROOT%\Application"
set "EXIT_CODE=%ERRORLEVEL%"
:cleanup
rmdir /s /q "%ROOT%" >nul 2>&1
exit /b %EXIT_CODE%
'@
        Set-Content -LiteralPath (Join-Path $iexpressSource 'Install.cmd') -Value $outerInstall -Encoding ASCII
        $sedPath = Join-Path $iexpressWork 'AI-Novel-Studio-acceptance.sed'
        $targetExe = Join-Path $output 'AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe'
        $targetTemp = Join-Path $iexpressWork 'AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe'
        $sourceRoot = $iexpressSource.TrimEnd('\\') + '\\'
        $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=I
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$targetTemp
FriendlyName=AI-Novel-Studio Windows DesktopHost acceptance installer
AppLaunched=Install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="payload.zip"
FILE1="Install.cmd"
[SourceFiles]
SourceFiles0=$sourceRoot
[SourceFiles0]
%FILE0%=
%FILE1%=
"@
        Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII
        try {
            # /N is the unattended build switch.  `/Q` makes this Windows
            # IExpress version skip the final stub and return no artifact.
            & $iexpress /N $sedPath
            # IExpress launches makecab asynchronously for larger payloads;
            # wait for the target instead of treating the early process exit
            # as a failed build.
            $payloadBytes = (Get-Item -LiteralPath $zipPath).Length
            # A small stub is created before makecab finishes.  Require a
            # substantial fraction of the payload size and three consecutive
            # stable readings so we never copy that incomplete stub.
            $minimumInstallerBytes = [Math]::Max(65536, [Math]::Floor($payloadBytes * 0.5))
            $deadline = (Get-Date).AddMinutes(10)
            $lastSize = -1L
            $stableReadings = 0
            while ((Get-Date) -lt $deadline) {
                $currentSize = if (Test-Path -LiteralPath $targetTemp -PathType Leaf) { (Get-Item -LiteralPath $targetTemp).Length } else { 0L }
                if ($currentSize -ge $minimumInstallerBytes -and $currentSize -eq $lastSize) {
                    $stableReadings++
                } else {
                    $stableReadings = 0
                }
                $lastSize = $currentSize
                if ($stableReadings -ge 3) { break }
                Start-Sleep -Seconds 1
            }
            if (Test-Path -LiteralPath $targetTemp -PathType Leaf) {
                Copy-Item -LiteralPath $targetTemp -Destination $targetExe -Force
            }
        } finally {
            if (Test-Path -LiteralPath $iexpressWork) {
                Remove-Item -LiteralPath $iexpressWork -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        if (-not (Test-Path -LiteralPath $targetExe -PathType Leaf)) {
            Write-Warning 'IExpress did not produce an installer executable; the ZIP and PowerShell installer remain valid.'
        }
    } else {
        Write-Warning 'IExpress is unavailable; the ZIP and PowerShell installer remain valid.'
    }
}

Write-Output "ACCEPTANCE_PACKAGE_ROOT $packageRoot"
Write-Output "ACCEPTANCE_ZIP $zipPath"
if (Test-Path -LiteralPath (Join-Path $output 'AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe')) {
    Write-Output ("ACCEPTANCE_INSTALLER " + (Join-Path $output 'AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe'))
}
Write-Output "ACCEPTANCE_MANIFEST $manifestPath"
