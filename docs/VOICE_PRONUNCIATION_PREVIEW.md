# Local pronunciation-rule preview

The existing Voice Direction segment editor now previews the text produced by its literal pronunciation rules before explicit Save or synthesis. Preview and Save use one line-rule parser. Terms retain authored whitespace, longest original terms take precedence, and replacement text is not scanned again. Regex punctuation and replacement-dollar strings remain literal. Duplicate terms, empty replacements, disallowed markup/control characters and original rule-count/Unicode character bounds are rejected visibly.

The preview retains at most 4000 Unicode code points for display while counting the complete transformed text. Original input is limited to 20000 code points as in the existing segment contract. A 4.8-million-character theoretical expansion is counted without retaining that expanded string. No model/TTS call, save, voice authorization, speaker-review change or cloud request is introduced by previewing. Actual pronunciation still requires listening to a real authorized voice; this is only the original textual transformation.

Evidence:
- The same six JSON examples are consumed by the existing Python PronunciationRule/spoken_text owners and frontend tests: Chinese overlapping terms, non-cascading replacement, literal regex punctuation, supplementary Unicode, authored whitespace and unchanged text. Python contract check passed.
- 27 focused React tests passed, including 15 new parser/preview checks and existing voice/subtitle behavior.
- The original mounted segment Save test was strengthened to assert the preview matches the submitted rules and that no PUT/POST occurs before explicit Save; all 7 cases passed again.
- TypeScript passed both runs. Actual Vite build and token guard passed. No backend source changed, so no new PostgreSQL runtime test was needed for this pure local projection.

Full browser visual acceptance remains blocked by the previously recorded sandbox socket restriction. No browser baseline or guard was weakened. This is a bounded B03 usability addition, not real TTS quality or whole-V2 acceptance.
