# R3-I route-mount diagnosis (P0-A)

**HEAD `ed45e1a`** · interpreter `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9) ·
cwd `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` · `EXPERIMENTAL_FEATURES=narrative_production_v2,asset_lineage_v2`

The prompt-adoption API was reported NOT WIRED. This records what was actually measured, so the
next agent does not re-run the same dead ends.

## 1. The static assembly chain is COMPLETE and CORRECT

Measured in a fresh process, with the module files confirmed to be the working-tree copies:

| Step | Evidence | Result |
| --- | --- | --- |
| Sub-router | `create_prompt_adoption_router(object(), invoke)` | produces **both** routes: `POST /projects/{nid}/studio/documents/{document_id}/shots/{shot_id}/prompt-adoption` and `GET /projects/{nid}/studio/documents/{document_id}/prompt-adoption` |
| Factory | `app/creative/workspace_api.py` | `router.include_router(create_prompt_adoption_router(prompt_adoption_service, invoke))` at **line 281**, and `return router` at **line 292** — the include is **before** the return, so there is no early-return shadowing it |
| Assembly | `app/experimental/api.py` | `PromptAdoptionService` constructed at **700-701**, passed as `prompt_adoption_service=` at **709** |
| Admission | `is_independent_studio_route` | admits exactly the two intended paths; refuses `POST .../documents/{d}/prompt-adoption`, `PUT` on the adoption path, and any other action under that prefix |

So there is **no static defect** in the wiring, and no include_router should be added again.

## 2. But the routes do not reach a running app — and the reason is NOT what the first scan suggested

Two independent measurements:

* In a process that imports `app.experimental.api`, its module-level `router` reports **45 routes
  and ZERO paths containing `/studio/`**. The studio router contributes nothing there — so the
  gap affects the **entire studio router**, not only prompt-adoption.
* `app.main.app` reports **23 routes**: `/openapi.json`, `/docs`, `/docs/oauth2-redirect`,
  `/redoc`, and ~11 empty-path `Mount` objects. **It carries no `/api` routes at all.**

## 3. The methodological error to avoid repeating

**`app.main.app` is not the API application.** Inspecting `app.main.app.routes` to decide whether
an API route is mounted is therefore invalid: it will report "not mounted" for *every* studio
route, including ones known to work, and it produced the earlier false conclusion that the
adoption route alone was missing. A `sys.modules` sweep for `FastAPI` instances likewise found no
studio-carrying app, which is consistent with the real API app being built by a **factory at
runtime** rather than existing as an importable module attribute.

## 4. What remains UNRESOLVED

The exact assembly-time reason the studio router's ~40 routes do not appear on
`app.experimental.api.router` (conditional assembly, a swallowed exception during module
assembly, or a lazily built app) is **not established**. Until it is:

* **the adoption API stays unwired and POST stays closed** — the directive's wiring gate is unmet;
* the correct guard test is a **mounted-app** assertion against the app object the server actually
  serves, not against `app.main.app`;
* the next step is to find the runtime entry point that builds the served app (the object the
  server binds), then assert the adoption route on **that** object.
