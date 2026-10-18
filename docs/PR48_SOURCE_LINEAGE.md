# PR #48 source lineage reconciliation

The product branch descends from PR #47's current a072cf9 head, but PR #48's current 58bbaad head is not a direct Git ancestor. This does not mean its nine commits are missing. A read-only reconciliation against product source 49ef1caa found:

- Seven upstream commits have Git patch-equivalent commits in the product history.
- Upstream fa658666 has exactly the same complete tree as local ancestor 28bf733d: 7221f5a2af2187770d75fb5cf68c3ec6fe131d19.
- Upstream aa95c407 has exactly the same complete tree as local ancestor 953fcbe7: b80bfe91b285ce09c930b1835415233ffe6add5e.

Machine-readable IDs and proof classification are in docs/v2/pr48-source-lineage-20261018.json. Current code contains subsequent changes; this is source-history inclusion evidence, not current whole-product functional equivalence or acceptance. The original broker pending-submit scenario was later moved into ModelBrokerPanel.additive.test.tsx by the existing 14ced102 reconciliation; its route/privacy-change assertions are still present.

Main and both PR heads were actually rechecked at 11:08 UTC and remain unchanged. Existing archive bundles publish continuation source and evidence separately. This check did not merge branches, move any source ref, rewrite commits or force-push. A future PR integration must respect the divergent Git history instead of pretending it is a simple fast-forward.
