# Independent Astra review resolutions

Reviewed implementation checkpoint: local `18decd93c89e26078d92b0cd80a56180b41749d5`, identical source tree `e72842b5c49fed125d067990c2f4dcab3d84a1bf` published as `9488d83694eaf5ea1c0635ff1efbe730f23995db`.

Seven reproduced backend issues were corrected and independently revalidated:

1. Retiring approved world Canon now requires review authority; a write-only actor cannot archive it.
2. Media and audiobook projections expose their actual domain review actions in the Inbox.
3. Interrupted cross-store asset promotion persists APPROVING intent and the asset checkpoint; rejection cannot contradict an already promoted asset, and approval resumes idempotently.
4. Audiobook attribution uses the same immutable chapter snapshot for text and provenance; changes during attribution fail closed, with exact segment evidence checked again on review.
5. Storyboard and scene embedding lineage validate the original scene source version; stale scene text cannot be relabelled with a newer chapter version.
6. A legacy domain's stronger access requirement remains enforced while other independently authorized Inbox domains stay available; denied rows are not projected.
7. Missing legacy privacy metadata is UNKNOWN rather than assumed LOCAL_ONLY; execution target is retained separately.

Additional hardening includes explicit local-only import adapter contracts and per-chunk authority checks, planning ancestor-version fences, immutable archived hierarchy handling, one-snapshot character-state queries, and fail-closed corrupted collection scope metadata.

The planning editor also retains local drafts on a same-node version change and requires an explicit comparison/rebase decision before saving again. It does not silently submit or discard fields.

Independent verification at this checkpoint: 142 File tests passed with 123 real-PostgreSQL parameters deselected; 13 focused frontend unit tests passed. Six optional real-HTTP tests were skipped in that review invocation. The separate implementation-side real-HTTP run passed all six. These counts do not substitute for the full inherited suite or real browser/PostgreSQL CI.

No reproduced HIGH/MEDIUM issue remained open in the inspected scope at that checkpoint. This is a bounded code review, not certification that all defects are absent. Actual PostgreSQL, Chromium and Windows hosted results are recorded separately. Real providers, interactive Windows, maximum-scale long-book throughput and production acceptance remain outside verified scope.

## Final corrective delta

The later `7f4b7e6` source tree (`c8aa2e581887f2481ac0f155ecdc2f841bc3891b`, remote `86c4b104b31eeb30af24b51dfa76b05a26e4eee4`) was separately reviewed. Twenty-two focused frontend tests passed, including all seven media promotion-recovery tests, planning draft/hydration recovery, exact native-control label association and request-boundary cases. All 60 production Field uses preserve a single native input/textarea/select with explicit label association.

A real hosted PostgreSQL run executed all 123 new PG parameters with zero skips and zero assertion failures, but two fixture teardown errors kept its lane red. The correction removes only tracked synthetic lore junction/proposal/evidence IDs belonging to the fixture project, in foreign-key order, before deleting that fixture novel. No migration, domain assertion or PG skip behavior was changed. The corrected hosted PostgreSQL rerun passed 2,322 tests with 135 profile-specific skips; the final exact-source receipt separately records all 123 new PG cases and their zero-skip result.

The first actual R3 Chromium run passed default-off/acceptance override and reached planning hierarchy/edit/save, then found an exact-label lookup issue. Remaining journeys were blocked by a retained fixture project and their empty-backend assumption. The correction preserves all seven business cases/assertions and deletes only project IDs returned by those individual synthetic create requests. It does not enumerate and delete unrelated projects. Actual corrected browser execution is recorded separately.

Interrupted media approval now retains the asset ID/digest in the direct panel and Inbox, offers explicit resume only for verified-current sources, and has no reject/batch path after promotion intent. Failed refresh retains the checkpoint but blocks resume until freshness is verified again. Planning initializes before exposing editable controls; same-node refresh continues to preserve drafts.

## Browser execution corrections

The corrected second real Chromium run passed five of seven business journeys. The remaining World result was present but lacked a semantic named region; it now uses a named native section, with component and real-HTTP regression coverage. Media dispatch correctly failed closed with MEDIA_VALIDATOR_NOT_CONFIGURED because the frontend runner lacked ffmpeg/ffprobe. CI now installs and verifies those real validators; no decoder or image check was bypassed. Planning comparison screenshots now expand and visibly assert both Mock ending values before capture.

These final changes preserve all seven business cases and the inherited browser assertions. Their successful hosted execution must be read from the final evidence receipt rather than inferred from code review.

## Browser fixture lifecycle, not production deletion remediation

A subsequent hosted journey completed the World business assertions but encountered `Directory not empty` during exact-owned-ID fixture deletion while the page still had live reads. Local commit `70c01ff` (published as `20cd2679ee104702529962202ce4b9d894bffc89`) observes API requests during the test without intercepting them; only after the business body finishes does teardown stop new requests, drain tracked requests, close the page and delete exact owned IDs. Failure screenshots are captured before closing. Timeout or close failure prevents deletion; HTTP 500 is still a failure.

Independent review passed three lifecycle regressions and confirmed all seven business bodies/assertions byte-identical. A client requestfailed event is not proof the corresponding server handler has stopped. The inherited File delete/lazy-read resurrection defect remains OPEN and is documented separately; no zero-known-defects claim is made.
