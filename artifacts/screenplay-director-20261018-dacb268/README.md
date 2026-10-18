# Independent screenplay Director checkpoint

Preserves five original commits after 5a9fc376648edcff4f3266a94b8ffb7def48dcd1 through dacb268a9aeb417e3b82aa44900585f484182c9f. continuation.bundle contains source, tests, reports, original successful/failed logs and the actual captured File HTTP test wire. Archive storage HEAD differs from source HEAD.

An explicitly saved independent SCREENPLAY can now use the existing Director review UI and versioned model-v2 transport: exact scene-bound prompt, explicit local known-zero route preview and human consent, original Job/broker execution, durable terminal evidence, pending candidates, explicit human review, original Director DRAFT and reopen. Scene/note IDs are frozen, with exact source/version/digest/incarnation and existing authority checks. No fake chapter or fabricated shot mapping. V1 remains storyboard-only. No new workflow engine, automatic cloud call or model retry.

Relevant private lifecycle/binding checks:283 PASS,57 environment-gated SKIP. Actual mounted File HTTP plus unchanged V1 transport checks:49 PASS. Captured-wire mounted React/client/draft-preservation checks:87 PASS and TypeScript PASS. Counts overlap and must not be added as acceptance coverage. The model adapter output was a fixture; UI transport was mocked separately. No real browser end-to-end, live-model quality, PostgreSQL, full build or full V2 acceptance is claimed. Generic unstructured SCRIPT remains a separate unfinished source direction.

## Safe recovery

Restore prior prerequisites including artifacts/static-glb-20261017-5a9fc37. Preserve current changes and recover on a new branch, never reset or force update.

```sh
(cd artifacts/screenplay-director-20261018-dacb268 && sha256sum -c SHA256SUMS)
git bundle verify artifacts/screenplay-director-20261018-dacb268/continuation.bundle
git fetch artifacts/screenplay-director-20261018-dacb268/continuation.bundle refs/heads/work/dot-director-transport-20261017:refs/heads/recovered/studio-screenplay-20261018-dacb268
```

See docs/V2_CONTINUATION_20261017.md for precise boundaries. No main merge, Release or new installer/package. Static scan found no patterns in52 new blobs, not a guarantee of secret absence. Skipped archive CI is not passing product CI.
