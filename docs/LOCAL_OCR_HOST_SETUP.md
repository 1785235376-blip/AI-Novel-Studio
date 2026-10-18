# Explicit local OCR host configuration

Host administrators can now register an already installed, trusted Tesseract executable and language file using the existing Runtime. No executable or language data is downloaded, installed or discovered. Startup reads pinned files but performs no recognition. The default remains no native OCR route.

Set all five host-owned environment variables together before starting Studio:

- LOCAL_OCR_EXECUTABLE: absolute executable path
- LOCAL_OCR_EXECUTABLE_SHA256: expected SHA-256 from the trusted installation
- LOCAL_OCR_TRAINEDDATA: absolute language.traineddata path
- LOCAL_OCR_MODEL_SHA256: expected language-file SHA-256
- LOCAL_OCR_LANGUAGE: matching language identifier, such as eng

A partial configuration or mismatched digest fails closed during startup. Paths and digests are not accepted from a Research request. The original runtime registers provider local-tesseract-ocr and model matching the language. Existing Research, execution, narrative-production, model-broker and author-context flags and their dependencies must be enabled for explicit native preview/dispatch. This setup does not change those flags.

Application composition now attaches the coordinator to existing Research, broker and JobManager owners. Research analysis/status contains a separate native_ocr inventory with only selectable provider/model/display/language fields; executable paths, host identities and admission internals are not exposed. Generic vision availability is unchanged. Human review remains required, and no manuscript or Canon adoption is performed.

Only installed English OCR has been exercised here. Other languages, Windows installation/execution, PDFs, general vision quality, native orphan recovery and frontend controls remain pending. Local provider fee is zero; host compute is not free or included. No cloud fallback.
