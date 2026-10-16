# Activation acknowledgement client boundary

## Reproduction

The unchanged `EntryExperience.studio.test.tsx` reproduces one failure and five
passes on exact published baseline `4534bed9129bcf2a549b44a91f062c79a77e173b`.
The client had applied full-overview preference validation to an activation
acknowledgement that the original consumer uses only for project identity.

Historical client `57986cb` accepted activation through `checkedProject`.
Both historical and current backend implementations return the full project
projection, including preferences. This repair does not claim that an older
server omitted those fields; it restores the minimal client acknowledgement
boundary demonstrated by the original client and unchanged entry contract.

## Repair

The activation client returns only matching, own-property project ID, string
title and `NEUTRAL_STUDIO` identity. Capabilities and unknown metadata are not
forwarded. If preferences are included they must still validate. No default
preference version, inferred authorization, permission or workspace state is
manufactured. Full overview and preference reads remain strict and unchanged.

The original server domain.write/scope/incarnation guards, captured request
headers, eligible-navigation lookup and post-response current-authority check
remain intact. The actual workspace separately fetches its full overview.

## Verification

- Exact original baseline: 1 failed / 5 passed, retained privately.
- Additive tests before repair: 2 failed / 15 passed, retained privately.
- Combined original entry/client/mask and additive tests: **72 passed**.
- TypeScript: **PASS**; design-token guard: **PASS**, 52 files.
- Independent read-only source review: no blocking findings.
- Original test bytes, assertions, skips and timeouts: unchanged.
- Browser, Windows and user-machine acceptance: not established by these tests.

The other 23 frontend failures have a separate shared-controller/client repair.
This report is not a full frontend green claim or a hosted CI receipt.
