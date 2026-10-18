# Actual original pinned CJK font acceptance

2026-10-18, source base 40e85c2 plus the new artifact-capture test bound by the original runner source hashes. The previous missing-font block is resolved for this owned cloud acceptance environment. Prior skipped/blocked runs are not rewritten or retroactively counted as passes.

The original official Google Fonts revision, variable font hash and complete OFL hash from scripts/prepare_pdf_font.py were downloaded and verified unchanged. The existing pyproject/CI-pinned fonttools 4.59.1 optional dependency was installed only into the owned clean test interpreter; Pillow was already the required 12.3.0. System fonts and the user's computer were not touched. The original prepare script produced the regular face with SHA256 eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461, exactly the original Comic owner's accepted pin. No substitute font or relaxed hash check was used.

- pinned-comic-font-prepare-r1: PASS with original source/license/derived manifest.
- pinned-cjk-comic-acceptance-r2: 4 PASS, 2 PostgreSQL counterparts deselected. Three original cases exercised Chinese comic text/overflow, authored-copy Unicode pixels, and an actual PDF with embedded FontFile2/ToUnicode. One additive case captured actual original approved Comic export and exact preview bytes through a fresh service instance.
- The first collection run failed because the new File-only artifact test initially inherited the original rig's PostgreSQL parameter as well. The new test was constrained explicitly to File; original tests, runner and PostgreSQL markers were not weakened. No cases ran in that failed receipt.

Artifacts here are synthetic acceptance assets, not final artwork or a browser screenshot. comic-cjk-verified.zip contains original segment PNGs, original manifest and OFL. comic-cjk-verified.png is the first segment, read back visually: Chinese text is legible with no missing-glyph boxes. The source image is deliberately labeled SYNTHETIC TEST ASSET. Full font binaries stay in the owned runtime cache and remain reproducible from the pinned official source; they are not duplicated in this evidence directory.

This does not establish PostgreSQL text rendering, browser layout, all comic flows, live model/image quality, Windows packaging, a new production package or complete V2 acceptance. No full suite/build was run. The PDF test proves embedding for its original case, not every PDF document. Original byte logs and source-bound receipts accompany this folder.
