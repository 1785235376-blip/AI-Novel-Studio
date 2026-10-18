# Original Graph timeline operation ordering

The existing timeline_export node editor now exposes explicit adjacent Up/Down controls for its existing edit_operations list. This changes only the original graph draft parameters, using the same closed parameter validator/update controller. It neither changes the source timeline nor saves, previews, dispatches or renders automatically. Source snapshot, source bindings, export profile and each operation's contents remain unchanged. The 40-operation combined budget is unchanged.

Operation order is meaningful. A split/duplicate-created clip must exist before a later operation uses it. Reordering is not a claim that dependencies or the final timeline are valid: the original GraphTimelineExecution.prepare path retains its ordered apply_timeline_edits validation before explicit dispatch. No parallel execution or second timeline owner was added.

Both new reorder and existing remove controls reject retained index handlers after node/identity/client replacement, including A→B→A, and recheck current edit permission/busy state. Invalid/no-op indices do not update the draft. Existing source bindings are not rewritten when an operation is removed; original validation remains responsible for rejecting invalid references.

Evidence: graph-timeline-operation-order-r1, 3 focused controller/mounted component tests and TypeScript PASS. The tests check exact preservation/nonmutation, stale/unauthorized controls, explicit adjacent UI and normal removal. No transport is used. No new backend implementation, live browser, render, production build or full suite is claimed. Current cloud product-browser reachability remains blocked as recorded in v2/ci-browser-observation-20261018.json.
