# Overnight Studio authoring checkpoint

This archive preserves five original commits after c6eb39abe593782824a072246236751f9a8bb324 through 28bab429031aaa6bc2c9c507a273de1108c5cce7. Code, focused regression checks, reports and original successful/failed logs are contained in continuation.bundle. The archive storage commit is distinct from the source head.

Included authoring features:
- Literal Prompt variable filling with bounded preview and original draft editing.
- Interactive story backtracking through the original source-validated play service.
- Comic reading-number repair matching the original coordinate rule and undo owner.
- Saved audio gain/fade display estimate alongside the unchanged measured source waveform.
- Conditional local Timeline range rejection after reading an exact-source waveform duration.

The audio projection is not rendered PCM, mixed waveform or loudness. Generic backend Timeline Save still does not decode every source duration: its unchanged six-second WAV/nine-second range limitation test remains passing. Only newly changed local ranges with a retained valid measurement are rejected. Four original File-owner tests used genuine generated WAV; UI tests use mocked transport. These are distinct evidence scopes, not a combined browser/native end-to-end claim.

No automatic model calls, provider selection, cloud fallback, saves or renders were added. Each feature report states its focused tests and limitations. No new installer or full acceptance package was built. Broad regression, production build, browser/model acceptance and current-source inventory reconciliation remain deferred. This is not a Release or a V2 percentage-complete claim.

## Restore without overwriting work

Restore the previous archive prerequisites, including artifacts/overnight-authoring-20261017-c6eb39a. Preserve existing local changes and use a new recovery branch. Do not reset, force update or merge main.

```sh
(cd artifacts/overnight-editing-20261017-28bab42 && sha256sum -c SHA256SUMS)
git bundle verify artifacts/overnight-editing-20261017-28bab42/continuation.bundle
git fetch artifacts/overnight-editing-20261017-28bab42/continuation.bundle refs/heads/work/dot-director-transport-20261017:refs/heads/recovered/studio-editing-20261017-28bab42
```

Read docs/V2_CONTINUATION_20261017.md for the precise evidence and remaining boundaries. This append changes only the existing archive branch. Skipped archive CI is not passing product CI. The static scan found no matches among 41 new blobs; it is not an absolute guarantee of secret absence.
