# Derived citation display correction

Follow-up source review found that the new OCR UI typed its citation digest as quote_sha256 (the original-text citation field). The actual Research derived block contract uses source_digest, result_digest and layer=RESEARCH_DERIVED. The previous UI test supplied the same incorrect quote field, so its green result did not verify the real derived digest label. It did not establish browser/backend end-to-end acceptance.

The UI and its fixture now use the actual derived contract. The visible digest is result_digest; accepted results must match the selected source id/version/digest and derived layer, and have a valid result digest. A mismatched source digest is rejected. Backend source ownership, original job/broker verification and human review checks are unchanged.

research-ocr-derived-citation-ui-r1: 5 focused React tests passed, including visible derived digest and wrong-source rejection; TypeScript and actual production Vite build passed. Real-browser limitations recorded in RESEARCH_NATIVE_OCR_UI.md still apply. Earlier tests/receipts are preserved rather than relabeled.
