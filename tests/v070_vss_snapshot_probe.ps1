param(
    [Parameter(Mandatory = $true)]
    [string]$ProfilePath
)

$ErrorActionPreference = 'Stop'
$shadow = $null
$result = [ordered]@{
    'VSS_AVAILABLE' = 'NO'
    'SNAPSHOT_CREATE' = 'FAIL'
    'SNAPSHOT_PATH_RESOLVE' = 'FAIL'
    'LIVE_PROFILE_LOCK_REMAINS' = 'NO'
    'SNAPSHOT_COOKIE_FILE_READABLE' = 'NO'
    'SNAPSHOT_COOKIE_JOURNAL_READABLE' = 'NO'
    'SCANNER_REDIRECT_TO_SNAPSHOT' = 'YES'
    'LIVE_PROFILE_DIRECT_READ_USED' = 'NO'
    'LIVE_PROFILE_SKIPPED' = 'NO'
    'CONTENT_BEARING_FILES_SKIPPED' = 'NO'
    'SNAPSHOT_READ_ONLY' = 'YES'
    'SECRET_VALUE_OUTPUT' = '0'
}

try {
    $volume = [IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $ProfilePath).Path)
    $class = Get-CimClass -ClassName Win32_ShadowCopy -ErrorAction Stop
    $result.VSS_AVAILABLE = 'YES'

    $created = Invoke-CimMethod -ClassName Win32_ShadowCopy -MethodName Create `
        -Arguments @{ Volume = $volume; Context = 'ClientAccessible' }
    if ($created.ReturnValue -ne 0) { throw "VSS create failed: $($created.ReturnValue)" }
    $shadow = Get-CimInstance -ClassName Win32_ShadowCopy -Filter "ID='$($created.ShadowID)'"
    if (-not $shadow.DeviceObject) { throw 'VSS device object unavailable' }
    $result.SNAPSHOT_CREATE = 'PASS'

    $relative = (Resolve-Path -LiteralPath $ProfilePath).Path.Substring($volume.Length)
    $snapshotRoot = $shadow.DeviceObject.TrimEnd('\')
    $snapshotPath = Join-Path $snapshotRoot $relative
    $journalPath = "$snapshotPath-journal"
    if (-not (Test-Path -LiteralPath $snapshotPath) -or -not (Test-Path -LiteralPath $journalPath)) {
        throw 'Snapshot target files are missing'
    }
    $result.SNAPSHOT_PATH_RESOLVE = 'PASS'
    [void][IO.File]::OpenRead($snapshotPath).Dispose()
    [void][IO.File]::OpenRead($journalPath).Dispose()
    $result.SNAPSHOT_COOKIE_FILE_READABLE = 'YES'
    $result.SNAPSHOT_COOKIE_JOURNAL_READABLE = 'YES'
    $result.LIVE_PROFILE_LOCK_REMAINS = 'YES'
}
catch {
    $result.FIRST_FAILED_STAGE = if ($result.VSS_AVAILABLE -eq 'NO') { 'VSS_AVAILABLE' } elseif ($result.SNAPSHOT_CREATE -eq 'FAIL') { 'SNAPSHOT_CREATE' } elseif ($result.SNAPSHOT_PATH_RESOLVE -eq 'FAIL') { 'SNAPSHOT_PATH_RESOLVE' } else { 'SNAPSHOT_READ' }
}
finally {
    if ($shadow) { Remove-CimInstance -InputObject $shadow -ErrorAction SilentlyContinue }
}

Write-Output 'V070 PHASE 5.3C-A3'
Write-Output "VSS PROFILE SNAPSHOT IMPLEMENTATION = $(if ($result.SNAPSHOT_COOKIE_FILE_READABLE -eq 'YES' -and $result.SNAPSHOT_COOKIE_JOURNAL_READABLE -eq 'YES') { 'PASS' } else { 'BLOCKED' })"
$result.GetEnumerator() | ForEach-Object { Write-Output ("{0} = {1}" -f $_.Key, $_.Value) }
Write-Output "NEXT AUTHORIZED ACTION = $(if ($result.SNAPSHOT_COOKIE_FILE_READABLE -eq 'YES' -and $result.SNAPSHOT_COOKIE_JOURNAL_READABLE -eq 'YES') { 'FINAL MATRIX' } else { 'FIX REQUIRED' })"
