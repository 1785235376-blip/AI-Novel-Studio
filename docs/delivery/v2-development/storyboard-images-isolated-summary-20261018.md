# Saved Shot Board thumbnails and text/image comparison

Implementation e7bf9c22 extends the existing CreativeCanvas cards, not another Storyboard or generation owner. Explicit opt-in opens six-shot pages with formal exact image_asset pins, actual image elements and a selected saved-text comparison. Both image/video bindings still select the image explicitly. Viewing does not save, approve, generate or navigate.

Authenticated streaming is capped before complete-body allocation. Source limit: 8 MiB, 4096 per side, 4,194,304 pixels. Static PNG/JPEG/WebP only; animation, unsupported compressed metadata/profiles, progressive JPEG and interlaced PNG are rejected without altering originals. One pipeline serializes native decode. Six thumbnail renditions (320px/512KiB each) and one comparison rendition (1024px/5MiB) retain at most 8MiB of derived blobs, not a guarantee about browser-process memory.

Exact saved document/shot/Asset identity and SHA256 are checked around reads and rendering. Metadata/download waits have linked 30-second owned aborts. Known 404/409, changed Asset, integrity failure, timeout, source/permission/Host ABA, dirty state, page/selection changes, blur/hide and unmount invalidate/release previews. Bitmap/canvas/URL cleanup retains original privacy and editing boundaries. The existing receipt endpoint still validates formal bindings across the whole board; lazy client downloads are not a claim of lazy backend validation.

A narrow compatibility fix admits the original server's optional continuity.time/lighting fields with null/absence and 4000-code-point bounds, preserving unknown-key rejection and legacy absent shapes.

Final isolated checks exclude the unfinished video benchmark lane: 409 tests across 16 files passed, TypeScript, Vite production build and 52-file token guard passed. PUBLIC/catalog 6 passed; no backend/API change was needed. The first isolated run passed tests but failed TypeScript on unsupported query options and insufficient pin narrowing. Those failures remain retained. Explicit control flow/narrowed locals and anchored role-name matching fixed the two files without removing source checks or assertions.

Catalog remains 2417 operations, fingerprint c89b2d50cd9edb15954084a7da62fb6c33bdca274082bf9d2bb83ae3ceab1759. Browser decoder/geometry, Windows and full-product acceptance remain NOT_RUN. This closes the stated bounded thumbnail/text-comparison implementation gap; it does not certify every requirement in roadmap 12.2 or general image-format compatibility.
