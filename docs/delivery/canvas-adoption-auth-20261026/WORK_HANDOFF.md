# Narrow backend repair handoff for frontend integration

Keep the integration base fixed at backend `457ea4a5a45ab13f351980665e053c5c77d15c82` and separately selected frontend `fe4f55412299fadfada0354725b3ca46e418c46a` (or an explicitly reconciled newer owner-approved frontend). Do not use the frontend branch's older bundled backend as a replacement. Do not silently include the separate TaskCenter mixed cursor branch.

This package addresses only first formal image-node association authorization. Do not reimplement the fix in parallel or drop original guards. Transplant the exact reviewed production diff plus both regression files:

- `app/creative/canvas_view_api.py`: `image_node_result` outer write invoke passes `local_input=True`; comments explain why initial empty canvases need source-read admission before the transition.
- `tests/test_canvas_adoption_auth.py`: actual TCP aliases, original queued/executed/reviewed Mock PNG result, exact retry, owner reconstruction, local-mode compatibility.
- `tests/test_canvas_adoption_auth_independent.py`: original collaboration authority denial and late-change hooks; approved-source pin, cross-target/project and incarnation boundaries.

Production commit `b7b456efa51a8a69121027e40eac4fc05c05c463`; final code/tests freeze `838f4992e4fb6d166092dc28f8f575f31dbbed01`. Both have app tree `cc826b709a03056d49553aad176980655f37f2f0`. These are local identifiers until a separate publication receipt is delivered. No remote availability is implied.

The frontend integration owner must still run the real browser path on the combined source: first empty canvas → explicit preview/create/execute → candidate → manual review → image-node-result → refreshed saved canvas → application/browser reopen. Keep request and result identity, source pins, project scope, incarnation, versions and digest checks. Browser completion is not claimed by this backend test package.

Do not remove `source_read_required`, set `source_read_authorized=True` without the original resolver, invent APPROVED jobs/assets, make private candidates public, or require a new Host policy for every legacy local metadata route. Missing-token behavior in noncollaboration local mode and denied collaboration sessions are distinct contracts.

No main merge, force push, Release, hosted Actions run, real model call or new credential handling is part of this handoff. The earlier File query F37 observations and Windows asset-list 503 remain separate.
