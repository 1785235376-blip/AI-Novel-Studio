# Pinned native OCR adapter

2026-10-18. **Native adapter and one English smoke case work; Research OCR is
not enabled and its original JobManager integration remains unfinished.**

The original VisionOCRModelNode now accepts an explicit native admission shape
in addition to its unchanged loopback HTTP shape. The native shape pins executable
and traineddata SHA-256, one explicit language, provider/model identities and an
admission digest. No network endpoint, credential, installation, discovery,
registration, default model or background job is created by construction.

LocalTesseractOCRProvider uses a host-supplied installed executable and traineddata
file with exact pins. It does not choose or download tools. Paths are included in
the admission digest, not exposed in route metadata. Each dispatch and polling
guard revalidates files and original caller authority. One provider invocation may
run at a time; contention is reported, not put into a second queue.

The adapter validates actual PNG/JPEG pixels, rejects animated/mismatched inputs,
limits dimensions to 8192 per side and 16 million pixels, and strips metadata by
normalizing into a temporary RGB PNG. Transparency is composited on white. Original
input bytes and SHA remain unchanged. The original native-process containment
helper is reused with fixed argv, shell disabled, cleaned environment, one OpenMP
thread and a 30-second limit. Cancellation/authority loss is polled; the helper
kills its process group/Windows Job on close and bounds output/workspace growth.
This is a trusted host-tool contract, not an OS sandbox against a hostile binary
or privileged concurrent filesystem attacker. POSIX memory use is not hard-capped.

Output must be nonempty UTF-8 without NUL and at most 256 KiB. The original typed
node validates source/input/route/language/output receipts, adds durable identities
and requires human review. No automatic Canon or manuscript mutation occurs.

## Actual evidence

- Final r2: 61 targeted checks passed, 10 PostgreSQL cases deselected, zero skips.
  Includes current Research source preparation and the unchanged original OCR node
  checks. Earlier r1 had 49 passing checks before transparent-image/error refinements.
- The actual installed Tesseract 5.5.0 process read a generated English image through
  the native provider and original VisionOCRModelNode, returning exactly
  `STUDIO OCR 123`. This specific case did not stub the native runner.
- Executable SHA-256: 74b76a5b994adcc18be362bf64ed5118082b2401d5d9a35242e92fc4c62e2b4b.
- English traineddata SHA-256: 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2.
- Other tests cover no-process construction, pre-dispatch cancellation, changed pins,
  unsupported language, malformed/mismatched/oversized images, transparent input,
  output limits, invalid UTF-8, timeout/error mapping and authority loss after output.
  Deliberately fake runners in error-path tests are not additional OCR quality proof.
- Three original PUBLIC checks passed, including a real offline wheel build and
  artifact/metadata validation. Manifest adds only the STANDARD native adapter.
  No new dependency, public route or private-backend exception was added.
- No frontend changed; previous TypeScript/build evidence is unchanged. The source
  preparation's real PostgreSQL checks are in the preceding slice, not rerun here.

## Still open

Research's real-adapter guard stays closed; broker availability is not changed.
Original JobManager preparation/admission, cancellation, durable terminal publication,
restart semantics and human review must be connected before this becomes a Research
user feature. Installed Chinese language data, Chinese OCR, PDFs, layout/table/chart
understanding, Windows packaging and product-browser acceptance are not established.
One clean English image is not general OCR quality acceptance, so model_quality
remains NOT_RUN. No paid API, user computer or GPU was used. The 0.7.0 test wheel is
not a V2 Beta or Release.
