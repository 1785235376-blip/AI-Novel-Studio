# Retained eight-check Windows transport reference

This executable still runs the original eight synthetic transport checks:

```
dotnet run --project interop-reference/PoemSeed.LocalInterop.Pipes -c Release
```

It now references the callable production-boundary library at
[`native/local_interop_desktop`](../../native/local_interop_desktop/README.md).
The implementation no longer lives solely in a demo. The library also has a
separate acceptance executable and a real distinct-user hostile harness.

This runner is MOCK_ONLY / CONTRACT_VERIFIED. It does not establish real Desktop
wiring, hostile different-Windows-user denial, signed-binary trust, or installation
registration. Those remain LOCAL_REQUIRED / NOT_RUN until independently executed.
