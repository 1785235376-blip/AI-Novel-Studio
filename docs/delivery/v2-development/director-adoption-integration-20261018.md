# Explicit local cost declaration and reviewed IMAGE scene notes

2026-10-18 20:15 UTC. Product b5062095926fb449429482467a014b66688744a1;
base c7bffde873f121f441905a4de66d8b44bf56b18c.

The original Broker now has a separate strict IMAGE accounting declaration
contract. A human explicitly confirms an amount and explanation for an exact
completed terminal/reservation. Zero is not inferred. Every projection labels
HUMAN_DECLARED_LOCAL_COST and measurement_verified=false. This is a declaration,
not a provider bill, measured hardware cost, visual-quality proof or evidence that
an interrupted upstream process stopped. Unknown accounting remains the default.
Generic upstream-bill and OCR trusted-zero paths remain separate.

The immutable V3 terminal and its historical UNKNOWN_UPSTREAM ledger snapshot
are unchanged. A distinct server-derived resolution proof links current ledger
history to that exact terminal. Prior pending records do not silently gain
adoption permission.

An explicitly confirmed review selects advice indices and authored note text for
an exact existing DIRECTOR DRAFT scene. Original CreativeService.revise_in_state
appends one scene note and server provenance, preserving unrelated content.
Original proposal adoption receipt and document proof commit atomically while
owner leases remain held. Exact same-request retry returns the historical result;
conflicting requests fail. Source/target/privacy/incarnation changes fail before
mutation. The original proposal is the durable replay anchor, independent of
bounded document history retention. Restart does not regenerate or adopt.

Independent code review is clear. File46 and real PostgreSQL46 pass, covering
24 new adoption/accounting cases plus22 prior IMAGE Job cases. Five-table exact
before/after durable hashes match. PG17.11 UTF-8 OID16384 reused without migrations;
runtime stopped. PUBLIC6 passes. All3096 final source paths match product.
Catalog2447 operations, no added routes; fingerprint
642e1c03ab0fa156a2a0a922f5d264fd5715dc4d32372d9ffb8096f80fc67304.
Frontend is unchanged and prior verified build is reused.

This slice remains internal/unmounted. Safe public list/status/reopen, cancellation
after source drift or feature disable, authenticated routes and authoring UI are
next work. No live-model, browser, Windows or full V2 acceptance is claimed.
