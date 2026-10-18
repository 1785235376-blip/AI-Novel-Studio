# Optional media-view grid and drag snapping

2026-10-18. Bounded implementation, not whole-workbench acceptance.

The original CanvasViewDefinition now optionally carries view_options with a strict grid boolean and snap_step of null/8/16/24/32 world units. Absent options remain absent in serialized legacy records, preserving their definitions and digests. Explicit null, coercions, unsupported steps and extra fields are rejected. Existing canvas storage, authorization, revisions, asset pins and CAS are reused.

The existing viewport offers explicit grid and drag-snap controls. The grid follows the camera and zoom. A dragged card anchors snapping in world space; all selected cards keep their relative offsets. Original world bounds take priority over perfect snapping at the boundary. Blank-space panning and keyboard movement retain their original behavior. Options are local draft changes until saved and can use existing undo and local recovery.

Evidence:
- canvas-grid-file: 24 passed, 10 deselected, including actual saved record/history and reopened owner reads.
- canvas-grid-pg: 10 passed, 24 deselected against real retained PostgreSQL 17.11 UTF8 database; server stopped cleanly.
- canvas-grid-ui: 29 passed, TypeScript and Vite production build passed; original UI token guard passed. Large-chunk warning retained.
- canvas-grid-public: 6 passed, including actual PUBLIC wheel and refreshed API catalog. Endpoint count remains 2375; DTO components updated.

No model calls, job creation, additional graph engine or execution-limit changes. DOM/geometry tests do not establish actual browser pixels, accessibility acceptance, FPS or 1000-card rendering performance. Those remain outstanding. This slice does not claim all Graph/Director/A/B/U requirements complete.
