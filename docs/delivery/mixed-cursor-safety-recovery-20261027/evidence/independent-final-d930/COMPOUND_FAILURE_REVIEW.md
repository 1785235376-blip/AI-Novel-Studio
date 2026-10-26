# Independent compound-HTTP failure assessment

Reviewed 2026-10-26 final2/compound-http.log and source receipt for d93034821efa4f064ac680b8bfdedef86faa3b0d (app 775a084c75dd5cfd7ccf0189060b056bf8f1c309).

Frozen business compound result: 3 passed, 1 failed. Local /api/v1 case received 409 STUDIO_ASSET_USAGE_UNAVAILABLE at the first warmed strict asset page after compatible first page, continuation and replay succeeded. This case did not reach its subsequent mixed cursor, mutation and reopen checks. The /api success cannot substitute for this missing /api/v1 acceptance.

Independent 99-pass group establishes its tested mixed-cursor, ASGI context-isolation, observer and POSIX process contracts only. It neither erases this business failure nor establishes absence of regressions. No causal determination from this failure alone; do not label environment-only, baseline-only, or fixed F37. Additional instrumented diagnosis must be separate from frozen acceptance evidence.

Acceptable deliverable classification: PARTIAL, independent review branch with known failed acceptance, not full unified acceptance, production readiness or main-merge recommendation. Preserve raw failure/receipt and hand off this blocker for Work's later unified acceptance. Do not relax budgets or modify asset business merely to make this suite green.

This assessment is technical scope/release-label review, not publication authorization.
