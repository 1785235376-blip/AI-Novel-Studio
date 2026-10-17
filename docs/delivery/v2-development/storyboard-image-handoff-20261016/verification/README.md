# Sequential build and token verification

Initial forced TypeScript attempt failed (exit 1): the new recipient's generic `perform` inferred only the directory-list result from a list/get ternary. The complete original output is retained in `typecheck.log`. The correction supplies an explicit `CreativeDocument | { items: CreativeDocument[] }` type parameter; all runtime id/version/mode checks remain.

A fresh source boundary then passed, sequentially:

1. `./node_modules/.bin/tsc -b --force --pretty false` — exit 0; `typecheck-final.log` is correctly empty.
2. `./node_modules/.bin/vite build` — exit 0; 2287 transformed modules. The existing large-chunk warning is retained in `build-final.log`.
3. `node scripts/check_ui_design_tokens.mjs` — exit 0, 52 files.
4. Scoped scan of all four touched runtime files for raw hex/rgb/hsl colors — exit 0.
5. SHA-256 comparison against `source.final.before.sha256` — all six then-current runtime/additive-test files unchanged (`source-stability.log`). Paths in snapshots are relative to frontend.

The first source snapshot is retained independently. Additional wrapper tests and independent verification are recorded separately; these build results do not claim their later bytes were checked. No browser, Python, paid compute, install, real HTTP/backend/model execution, release or hosted CI was run.

## Final pre-independent build checkpoint

After the expanded owner-ABA suite passed 176/176 and forced TypeScript passed (test evidence run 5), `build-acceptance.log`, `tokens-*-acceptance.log` and `source-acceptance-stability.log` record another sequential PASS on seven unchanged runtime/additive-test files. The source boundary is `source.acceptance.before.sha256`.

Independent static review then found one wrapper retirement-loading cleanup dependency omission: an observed owner-output ABA during a pending read could leave the Close button disabled. The correction keys the existing cleanup effect on permanent `retiredNow`, with a delayed-response Close regression. Therefore this checkpoint is retained historical evidence, not a claim that the later cleanup bytes were built here. The independent final verification records that last boundary separately.
