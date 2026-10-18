# Director camera-language draft lifetime correction

Two pre-fix regressions were actually reproduced against source 8b91b52:
- Selecting CLOSE_UP in the local camera-language control immediately displayed stored WIDE instead, even though the local-draft summary had changed.
- Switching from doc-1 to a pending doc-2 read still displayed the old shot cards. Local draft state was not scoped to the selected source.

The original failed tests/logs remain under director-camera-draft-baseline-r1. These are UI state defects, not evidence of unauthorized backend writes or a reproduced backend privilege escalation.

The original DirectorWorkspace now retires the entire local session when client authority identity, document ID or activation lifetime changes. A read clears the prior projection while pending. Local camera choices are attached to the exact received projection, visibly control their select value, and retain a distinct original-value label. Values must come from the original published vocabulary, an empty value or the unchanged stored legacy value. Choosing the stored value removes the local difference. Explicit clear restores original values. Explicit refresh clears drafts even if a test/injected client reuses the same response object. A source change or unmount prevents retained old projection handlers from authoring into the new session.

The user-facing text states that refresh/document switching clears session-only camera drafts. Nothing saves, adopts, generates or writes a camera change to the backend; original Creative/Graph review and save owners remain unchanged. The Graph console's existing collapse/source authority behavior and 12 original DirectorWorkspace tests remain intact.

Evidence: baseline 2 FAIL, fix 25 PASS, final 27 focused component/Graph-console tests plus TypeScript PASS. Counts overlap. New final cases additionally cover explicit clear, same-object refresh, client replacement, inactive transitions and late unmounted replies. No full build/suite, actual browser visual, model, Windows/GPU or release acceptance was performed.
