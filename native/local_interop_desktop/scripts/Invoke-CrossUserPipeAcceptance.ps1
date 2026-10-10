# Requires two already provisioned Windows accounts and two manually opened sessions.
# Never creates accounts, changes ACLs, handles credentials, or claims a same-user pass.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Server','Client','Verify')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$ServerReceipt,
    [string]$ClientReceipt,
    [string]$OutputReceipt = 'cross-user-pipe-result.json'
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) { throw 'Windows is required. Result: NOT_RUN.' }
$project = Join-Path $PSScriptRoot '../PoemSeed.LocalInterop.Pipes.Acceptance'
function Read-JsonLines([string]$path) {
    $records = @()
    foreach ($line in Get-Content -LiteralPath $path) {
        if ($line.StartsWith('{')) { $records += ($line | ConvertFrom-Json) }
    }
    return $records
}
if ($Mode -eq 'Server') {
    # A second user needs read access to the ordinary metadata receipt. The operator
    # selects an already suitable location; this harness never widens permissions.
    dotnet run --project $project -c Release --no-build -- --cross-user-server 2>&1 | Tee-Object -FilePath $ServerReceipt
    if ($LASTEXITCODE -notin @(0,2)) { throw "Server harness failed ($LASTEXITCODE)." }
    return
}
if (-not $ClientReceipt) { throw 'ClientReceipt is required for Client and Verify.' }
$server = @(Read-JsonLines $ServerReceipt)
$ready = @($server | Where-Object { $_.state -eq 'LISTENING' })
if ($ready.Count -ne 1) { throw 'Expected exactly one server readiness record. Result: NOT_RUN.' }
if ($Mode -eq 'Client') {
    dotnet run --project $project -c Release --no-build -- --cross-user-client $ready[0].pipe_name $ready[0].server_sid 2>&1 | Tee-Object -FilePath $ClientReceipt
    if ($LASTEXITCODE -ne 0) { throw "Cross-user attempt did not establish denial ($LASTEXITCODE)." }
    return
}
$attempt = @(Read-JsonLines $ClientReceipt | Where-Object { $_.status -eq 'ACCESS_DENIED' })
$end = @($server | Where-Object { $_.reason -eq 'PAIR_WITH_DISTINCT_USER_ACCESS_DENIED_RECEIPT' })
$failed = @($server | Where-Object { $_.status -eq 'FAILED' })
$valid = $attempt.Count -eq 1 -and $end.Count -eq 1 -and $failed.Count -eq 0
if ($valid) {
    $valid = $attempt[0].pipe_name -eq $ready[0].pipe_name -and $end[0].pipe_name -eq $ready[0].pipe_name -and
        $attempt[0].server_sid -eq $ready[0].server_sid -and $end[0].server_sid -eq $ready[0].server_sid -and
        $attempt[0].client_sid -ne $ready[0].server_sid -and $attempt[0].client_pid -ne $ready[0].server_pid -and
        [DateTimeOffset]$attempt[0].attempted_at -ge [DateTimeOffset]$ready[0].started_at -and
        [DateTimeOffset]$attempt[0].attempted_at -le [DateTimeOffset]$end[0].ended_at -and
        [DateTimeOffset]$attempt[0].attempted_at -le ([DateTimeOffset]$ready[0].started_at).AddSeconds($ready[0].window_seconds)
}
$result = [ordered]@{
    scenario = 'A21'; scope = 'HOSTILE_CROSS_USER_WINDOWS_ACL'; status = $(if ($valid) { 'PASS' } else { 'NOT_RUN' });
    same_user_substitute = $false; real_desktop_integration = 'LOCAL_REQUIRED';
    server_sid = $ready[0].server_sid; pipe_name = $ready[0].pipe_name;
    reason = $(if ($valid) { 'Distinct OS SID received access denied while matching server stayed live.' } else { 'Missing, mismatched or inconclusive distinct-user receipts.' })
}
$result | ConvertTo-Json | Set-Content -LiteralPath $OutputReceipt -Encoding utf8
$result | ConvertTo-Json
if (-not $valid) { throw 'Hostile cross-user test remains NOT_RUN.' }
