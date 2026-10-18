# Explicit native OCR Research routes

The original Research router now exposes explicit native-preview and native-dispatch actions before its generic action route. They require a trusted NativeResearchOCRCoordinator already attached to the same service; otherwise they return RESEARCH_OCR_NOT_CONFIGURED. This slice does not install that coordinator in production composition or register native tools.

Native routes check existing runtime feature flags before request-body parsing and again through the live authorization guard. Original session, project incarnation, author, branch and domain.write checks are preserved. Native result review additionally requires domain.review, including through the existing generic review action. All responses retain no-store handling. Request models forbid extra parameters and require an explicit reviewed preview digest for execution.

Mounted original-router evidence uses actual installed English OCR, original File/PostgreSQL jobs and broker settlement: research-native-ocr-routes-file-r1 and research-native-ocr-routes-pg-r1 each passed 2 tests (opposite backend deselected), with no skipped native cases. Review without permission returns 403; explicit permission permits review; invalid sessions are rejected. An unconfigured coordinator returns 409, and a disabled route rejects malformed bodies before parsing without creating jobs or ledger entries.

Existing Research File regressions: research-native-ocr-routes-compat-r1, 25 passed, 25 PostgreSQL cases deselected. PostgreSQL native run reused OID 31303 and stopped its server. No production startup, frontend, fresh migration, general OCR quality or release claim. Production composition, host setup and UI remain pending.
