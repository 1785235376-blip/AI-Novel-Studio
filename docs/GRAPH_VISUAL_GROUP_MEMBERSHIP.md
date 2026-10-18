# Editable visual group membership

2026-10-18. Bounded professional-canvas usability slice.

Previously the existing group controls required deleting a group before regrouping
its nodes. The same controls now explicitly move the selected nodes into the
chosen group, or remove selected direct members from it. This is presentation
membership only: node identities, typed edges, document pins, parameters, viewport,
assets, review state and execution remain unchanged.

Moving transfers direct membership exclusively from previous groups. Removing only
ungroups direct members of the chosen group; selecting a parent does not silently
remove child-group membership. Empty groups disappear using the existing orphan
promotion helper, preserving child groups as top-level groups. Group IDs/names and
the existing two-level/24-member constraints remain. No new group or workflow
schema was introduced.

The component emits one original graph edit with record=true, so it participates
in the original editor history and explicit graph save. It does not call an API or
execute a graph. Read-only/busy, invalid selection, unknown nodes, duplicate IDs,
no-op and overflow cases refuse. Mutation callbacks are fenced by source, selection,
owner, local choices and mount lifetime; duplicate synchronous writes are refused.

Evidence: graph-group-membership-ui-20261018-r1 original runner receipt and raw log.
101 passed: 5 additive membership checks plus 96 unchanged canvas/presentation
regressions. TypeScript and Vite production build passed; existing large-chunk
warning retained. Tests use jsdom, not a product browser or live server save.
Current full browser geometry, real save/reopen and release acceptance are not
claimed by this slice. No protected shell, tokens, baseline test, backend, model
provider or gate was modified.
