# Cloud image-node queue slice

The professional image dual canvas previously kept node labels and connections in browser storage, with no path from a selected node to a persistent task. An `image_generate` node now has a separate prompt draft and an explicit action that opens the existing image-job queue. A server-returned job ID is shown after the author chooses a service/model and saves the request. Opening the panel never creates or executes a task.

## Source and scope

Only code fetched from `1785235376-blip/AI-Novel-Studio` was used. No migration-package source or Windows data was read or imported for this slice.

Remote heads observed on 2026-10-23:

| Branch | HEAD |
| --- | --- |
| `main` | `7b35e4cb4bd9efabe7cff54e67d7b24e8e469385` |
| `work/studio-v2-dual-canvas-public-20261021` | `252e88fed697ac57dff76b5a4657c6de723906fa` |
| `work/hermia-frontend-refactor-20261022` | `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed` |
| `work/studio-comic-media-7bad-tests-20261023` | `36e4a685abc22815d0dba1b08d04a552ecb53d1d` |
| `work/full-recovery-product-candidate` | `edb3e8577c32c2bb8e0ca3825f223aa75149f9a8` |
| `archive/verified-studio-v2-20261017-5a6f697` | `41b2e96e2a79a86009a4497e31f1e22f35b7c0b6` |

The working branch is `cloud/canvas-task-20261023`, based on Hermia `6ba25ad7` (tree `4193b3c22c49647dfc6e52241b5ff459f0064654`). Main is an ancestor of the public dual-canvas branch, which is an ancestor of Hermia. Comic and Hermia are divergent histories; their complete trees were not merged. All inspected heads have top-level source trees, but archive evidence volume does not establish product completeness.

Requirements and contracts were checked against `AGENTS.md`, the repository UI skill, `docs/ui/design_system.md`, `docs/ui/protected_ui_surfaces.md`, the public Hermia delivery/capability documents, and the actual canvas/queue source. This is a module-content change using existing primitives; it does not change AppShell, tokens or protected layout.

## Behavior

1. Select an image-generation node and edit **本次提示词**. The title, edges and other local nodes are not silently converted into task inputs.
2. Choose **为此节点准备图片任务** in the professional image dual canvas. This captures the prompt and opens **画布图片任务**.
3. Select a configured/registered image service and confirm the model. Unknown or remote service locality requires the existing per-request cloud consent. Changing the model or identity retires that consent.
4. **保存到生成队列** uses the original `POST /api/novels/{id}/image-jobs`. The existing queue reads and displays the actual server job ID and parameters. Execution, cancellation and acceptance remain separate explicit actions.

Canvas sessions are keyed by project and kind. The task panel additionally retires its provider and queue owners on identity transitions, including a same-batch A/B/A switch. Late old-scope responses cannot populate the new owner. The confirmed regression is covered by a behavioral test.

## Verification

| Check | Observed result |
| --- | --- |
| Five targeted frontend files | **23 passed**, one worker |
| Actual `ImageRebuild → DualCanvas → node → Drawer → ImageQueuePanel` wiring | **2 passed**, one worker |
| New File-backend HTTP queue tests | **2 passed**; provider resolution and media execution both zero |
| Vite production bundle | **PASS**, 8.93 seconds; existing large-chunk warnings |
| Full TypeScript check | **FAIL**, 280 diagnostics in the current environment; none in the changed slice. Missing declared `@types/node`/`fountain-js` and unchanged App/GraphCanvas/handoff-test errors remain. This is not a full type-check pass. |
| Three-viewport browser/geometry check | **BLOCKED before test body**: Chromium SUID sandbox helper has non-root ownership. No geometry, screenshot or browser acceptance pass is claimed. |
| `git diff --check` | **PASS** |
| Previously restricted media-backend security review | **NOT_RUN**, no alternate route attempted |

The frontend tests use explicitly labeled software HTTP fixtures and exercise actual production components. They do not establish live-provider or real-File browser acceptance. Separately, `tests/test_cloud_canvas_image_queue.py` uses a real File repository, real queue persistence and HTTP routes. It verifies stored prompt/model/parameters, UUID identity, reopening through a new owner/client, and rejection of conflicting parameters under the same idempotency key; it never invokes execution.

Reproduce targeted frontend checks from `frontend`:

```sh
node node_modules/vitest/vitest.mjs run \
  src/rebuild/canvas/RebuildCanvas.test.tsx \
  src/rebuild/canvas/RebuildCanvas.taskIntent.test.tsx \
  src/rebuild/image/CanvasImageQueue.test.tsx \
  src/rebuild/image/ImageDualGate.test.tsx \
  src/novel/ImageQueuePanel.test.tsx \
  src/rebuild/image/ImageRebuild.canvasQueue.test.tsx \
  --maxWorkers=1 --minWorkers=1
```

The File tests were run with cloud/model dispatch disabled and temporary data/identity roots, using the existing venv plus the existing system Python package directory to supply `jsonschema`. Nothing was installed. The frontend checks used existing Node tools directly; the declared pnpm version is 10.6.5, and the environment's old pnpm 9.15.0 was not used to change the lockfile.

Browser checks are defined in `frontend/playwright.cloud-canvas.config.ts` and `frontend/tests/e2e/cloud-canvas-queue.spec.ts`. They keep Chromium sandboxing enabled. In this cloud environment `/usr/lib/chromium/chrome-sandbox` is mode 4755 but owned by `nobody:nogroup`, so all three launches stopped before rendering. No permissions or security configuration was changed; the managed Vite port was stopped afterward.

Cloud evidence is under `/workspace/cloud-development-20261023/`: `checkpoint.json`, `frontend-targeted.log`, `frontend-root-wiring.log`, `build.log`, `typecheck-current.log`, and `visual/results.json`.

## Limits

- This is a prompt-to-persistent-task slice. It does not save the browser graph to the server or create a durable canvas/card/job binding.
- Video draft nodes still have no task dispatch wiring. That limit is visible in the UI.
- Inference, GPU, paid providers, PostgreSQL and media processing were not exercised. A configured service is not described as verified inference.
- Backend same-key idempotency tests do not prove frontend exactly-once recovery after an uncertain response; the existing API client generates a new key for each separate POST.
- This does not restore the original local commits, trees, history, media or private project data. It is new cloud work based on public GitHub source.
- No push, public upload, source cleanup, credential creation or main-branch change was performed.
