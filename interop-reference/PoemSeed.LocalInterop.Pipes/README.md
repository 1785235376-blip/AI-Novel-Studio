# Windows current-user Named Pipe transport reference

This is a standalone explicit-run transport reference, not wiring in either desktop
application. It creates a random per-instance local pipe, denies network logons,
sets a current-user SID-only DACL and `PIPE_REJECT_REMOTE_CLIENTS`, verifies the peer
SID, uses a local-only current-user client and rejects oversized/truncated frames.
Connection or OS-user equality alone never grants protocol capabilities: the
adapter must validate canonical DTOs, negotiate, bind a session and recheck live
scope at every delivery. No server is started by importing or installing this code.

`dotnet run --project interop-reference/PoemSeed.LocalInterop.Pipes -c Release`
runs a labelled synthetic two-process Windows smoke. It checks local transport,
frame bounds, malformed object, truncation, remote-name rejection and cancel.
No real tutor desktop integration is claimed. Native cross-user hostile attempts
remain NOT_RUN, and actual desktop runtime integration remains LOCAL_REQUIRED.

Reference API sources:
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipew
- https://learn.microsoft.com/en-us/dotnet/api/system.io.pipes.pipeoptions
- https://learn.microsoft.com/en-us/dotnet/api/system.io.pipes.namedpipeserverstream.runasclient

Frame format matches the protocol draft: unsigned 32-bit little-endian byte count,
then a UTF-8 JSON object, maximum 1 MiB and depth 24. The canonical protocol handler
owns operation, schema, authority, capability, nonce, freshness and consent checks.
