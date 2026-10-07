# Explicit runtime flag discovery, preserving historical opt-ins

The first checkpoint `13b9f9171205b0e8a97d0b081a6b7e85c434a7b1` failed its
complete File and PostgreSQL suites on both push and pull-request events. Each
profile had two failures in the original mounted discovery assertions, one per
API prefix. Other backend assertions were not failed or reclassified; the
original strict aggregate correctly remained failed.

The historical `FLAGS` tuple is a published complete opt-in inventory. Four
original test node IDs also include its literal value. Keeping that inventory
stable but appending disabled new entries to its established API `features` map
changed the old complete-opt-in contract. No test or assertion was changed to
make the old expectation pass.

Discovery schema version 2 now returns:

- `features`: the established historical package inventory and its actual states
- `surface_features`: every new opt-in, including disabled and unavailable ones
- `runtime_features`: the complete current inventory and its actual states
- `dependencies`: explicit dependencies for the complete runtime inventory

Current frontend clients consume `runtime_features` as authoritative. An empty
complete map is not replaced with old grants. Older server responses remain
compatible, without inventing missing capabilities. All runtime validation uses
`RUNTIME_FLAGS`; the historical tuple does not hide new options from current
clients or settings. An old complete opt-in does not implicitly enable new
surfaces, wildcard/unknown names grant nothing, dependencies are not auto-enabled,
and V1 acceptance mode still forces every experimental flag off.

New tests cover both actual API prefixes, old and current clients, the complete
disabled inventory, exact dependencies, unknown/wildcard input and V1 override.
The original tests, node IDs, skip maps, finite CI caps and strict gate remain
unchanged. Focused local checks do not substitute for the new exact-head hosted
File/PostgreSQL/browser evidence.
