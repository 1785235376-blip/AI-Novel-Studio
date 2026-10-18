# Off-screen media canvas search and location

2026-10-18. Searching card or visible asset IDs now provides a bounded list of the first 20 matches, including cards outside the camera and inside collapsed groups. Explicit Locate moves the current view to the card and expands only its ancestor groups. These are presentation changes owned by the original media-view edit/history/save path; asset pins and card positions are unchanged. No binary read or execution occurs.

At extreme world coordinates, focusing can reduce zoom enough to keep the camera within its original ±100000 bounds. The viewport culler retains its 128-card DOM cap and now ensures a visible selected card is included when many cards overlap, rather than losing selection behind the first 128 records. Search output includes the full match count so a broad query can be refined; it does not render all 1000 search results.

Evidence: media-canvas-search, 44 focused checks passed, TypeScript and Vite production build passed, existing shared-token guard passed. Cases include extreme coordinates, nested group reveal preserving unrelated groups, unchanged source/card data, overlap prioritization, actual panel locate→undo→redo→original save and existing graph handoff/gesture regressions. No backend or database contract changed. Browser pixels/FPS and full-product acceptance are still unverified.
