# Shared R1/R2/R3 repair evidence

Baseline: `c6f2126115b52e17839d48efea091dc21ec08c61`, tree `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`.

The three scripts in `reproductions/` are extracted without text edits from the user-supplied external review. The source report was reconstructed from its complete authorized Library read; this is not a claim of byte-exact original attachment preservation. The scripts deliberately observe defects and their exit status of zero is not a PASS. Their synthetic data and in-memory test sessions never represent private user projects, real credentials, or provider-quality evidence.

An immutable baseline archive was preserved before runtime edits. All three defects reproduced separately with Python 3.12.14 and all 31 constraint versions matched. That is supplemental local evidence, not the locked Python 3.12.9 result. `Shared R123 evidence` checks out the exact untouched baseline and uses Python 3.12.9 plus its original dependency constraints, runs each unchanged script in its own process, preserves stdout/stderr, and explicitly asserts each known RED observation. A green evidence-job conclusion means the defects were reproduced, not that the baseline is safe.

This is ordinary implementation/regression work on supplied findings. The historical independent follow-up review remains platform BLOCKED, without restart, rephrasing or rerouting. The product matrix remains 39 PARTIAL plus F00 INTEGRATED. Real model/GPU/TTS/translation quality, native Windows interaction and target applications remain NOT_RUN. PR37/38 are frozen; no merge, release, deployment or backport is authorized here.

## Locked baseline result

Both dedicated baseline jobs completed successfully: [push37402995698](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37402995698) and [PR37403004721](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37403004721). The source, tree, actual3.12.9 version and all three asserted RED observations are retained in `BASELINE_RED_PYTHON3129.json`. This green harness conclusion means the unsafe baseline was reproduced.

## Unchanged script compatibility after repair

The adjacent `repro_*.stdout.txt` files are supplemental Python3.12.14 observations from the repair working tree. The scripts intentionally retain their original hard-coded `source` field; that field describes their original report target and does not identify the patched code. R1 now returns403 on all target reads/writes, with no body or persisted goal; R2 reportsSTOPPED/no post-revocation output. The original R3 script expects a successful rejection response with top-level `status`, so it terminates with its original KeyError when the repaired route returns409. Its stderr is preserved unchanged as a compatibility observation, not a passing assertion. The added terminal-protocol regression explicitly checks409, full eventual output and HTTP/SSE/memory/durable agreement.

Final exact source identity and actual full five-lane CI are read from DraftPR40; no test count alone establishes security or product acceptance.

## SSE delivery and compatibility boundaries

Live actual loopback HTTP/SSE tests (not TestClient substitutes) verify per-observer session, membership, role, branch-parent, feature and project lifetime. Two independently authorized sessions of the same actor receive shared output; revoking one ends only that subscription, leaves cancellation unset and lets the second receive the later body. Empty/idle streams, disconnect cleanup and deterministic wake/payload/threadpool-to-ASGI-send races are covered. The first new idle-disconnect test exposed ASGI2.4's send-only disconnect detection; its original failing observation is retained, and the unchanged assertion passes after an explicit receive-side watcher was added.70 File cases passed on supplemental Python3.12.14; their70 real-PG counterparts require hosted execution.

The final authority check is immediately before ASGI send with no intervening await. Bytes already committed to the transport cannot be recalled, and distributed revocation cannot promise retroactive removal from kernel/network buffers. This is a current-authorization send boundary, not atomic cross-host revocation or remote-client deletion.

Established chapter CAS/history remains an authorized shared-project manuscript contract. Branch ownership/project/workspace and current permission still validate; this does not manufacture branch-exclusive manuscript storage. Explicitly unsupported branch source requests fail instead of substituting base text. The original working chapter assertions remain intact.
