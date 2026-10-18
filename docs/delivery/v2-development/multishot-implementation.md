# Independent screenplay multi-shot implementation

Additive opt-in `planning_mode=MULTI_SHOT_V1`, output `INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1`, V3 public preview/pending projections over existing model-v2 routes. Original omitted/null mode payload and V2 prompt/schema remain compatible. The contract is documented in `contracts/independent-screenplay-shot-plan-v1.md`.

## Final focused verification

- Independent frozen File check: 53 passed, 27 PostgreSQL parser cases deselected; source hashes unchanged during check. Receipt: `multishot-independent-frozen.json`.
- Wider original File lifecycle/transport regression: 125 passed. `multishot-independent-legacy.json` truthfully records source changes during the check; do not present it as a fully frozen final-source pass.
- Frontend: 116 tests passed across seven files. Independent frontend review ran 115 tests with the same production hashes; the one extra test proves unchanged generic human editing for V2.
- Runtime hashes: directorModelClient.ts `4a2241e9c063598080c9a64fd00890153c982b86004d027af398d8fb4bb636f5`; IndependentDirectorModelReview.tsx `2a9ab1dd2a9c133c1a9af8d4515c7ac7f6cc492c22b12b024fb3c24a8caca72e`.
- Source whitespace check and frontend UI token guard passed. Raw failed-run logs retain original pytest whitespace and their receipt hashes unchanged.

## What the tests establish

Injected synthetic wire data traverses original File/Broker/Job ownership, durable terminal, restart, explicit pending publication/reconciliation, human content edit and one Director DRAFT. Existing DIRECTOR_NOTES derivation yields four Shots with selected3+1 scene associations and exact direct-parent ancestry. Source remains unchanged. Sealed original model text/candidate digest remain separate from human-edited output digest. No replay or extra reservation occurs.

Malformed membership/coverage/order/numbering/evidence/duration and incomplete JSON fail closed. More than two source scenes fail explicitly without mutation; 2049 tokens is rejected. Missing planning mode preserves the exact legacy delegated payload; V2 preview survives restart with byte-identical public receipt. Candidate identities/order remain immutable only in the new contract; original V2 content editing stays unchanged.

## Limits and failed attempts

All model wire content is synthetic. No real provider inference, model quality, provider token-fit, browser UI, production build or PostgreSQL model lifecycle was tested here. Original backend-neutral parser fixture retains File/PG parameterization; PG parser/source/proposal validation is left to root integration, distinct from File-only Job lifecycle.

Early isolated runs failed on omitted sparse imports and missing owned pytest basetemp. Subsequent test assertions incorrectly expected preview reads after dispatch and flattened ancestry; both were corrected to match unchanged original-owner behavior. Initial independent review's ancestry failure is retained in `multishot-independent-review.{json,log}`; final frozen success supersedes it. There was no engine or ancestry implementation change to hide those test mistakes.
