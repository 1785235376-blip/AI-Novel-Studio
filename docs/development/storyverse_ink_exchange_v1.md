# DIF-10 bounded Ink exchange, development evidence

Base: `79fbb1e5d80574e513cd51c09b54118b12c80d90`. This is an additive adapter on original `InteractiveStoryService` approval/source/export ownership, not DIF-10 full acceptance.

## Target and provenance

- Target: `INKJS_2_3_2_TYPED_TEXT_SUBSET`, adapter revision 1.
- Official maintainer: https://github.com/y-lohse/inkjs/releases/tag/v2.3.2
- Compiler/runtime interface: https://github.com/y-lohse/inkjs (Compiler.Compile, Story.ChooseChoiceIndex, state.ToJson/LoadJson).
- Language source: https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md
- Registry metadata: https://registry.npmjs.org/inkjs/2.3.2
- Archive: https://registry.npmjs.org/inkjs/-/inkjs-2.3.2.tgz
- SHA512: `iZjrY0lLeRiC+HtDzCfV9IEAP9ExCmBZUrxKkyLy1qIbbGbR1uTXNZ8LDIg8oVkMXZ9TeKKyEFQpQ/m5nQds8w==`
- Archive SHA256: `8dbf9d64218ed86d1c905a4e972bba5c1f6ff451df2d63b2a30a18c0d29cf232`
- Compiled full bundle SHA256: `4a76187c713c889b5e71d9380b37b5b42eaba9d24af099bb9f968d02311cfeef`

Inkjs is the community JavaScript implementation acknowledged by inkle, not the native C# target. No .NET installation, runtime service, browser, model/API call or PostgreSQL execution was performed. Downloaded test dependency is task-local, excluded from the deliverable, integrity checked before execution, and extracted with regular-file/directory, traversal and size checks. No lifecycle scripts ran. Product never loads the test dependency.

## Contract

Existing typed bool/int AST, constant assignments, numeric generated identifiers, sticky choices, convergence, loops and the original step cap are emitted as trusted templates. No user condition is interpolated as code. Punctuation is escaped inside Ink string expressions; physical narrative newlines are emitted separately. Choice CR/tab/newline and narrative CR/tab are unsupported. Canonical story review and RenPy/neutral export remain unchanged: unsupported Ink is explicitly omitted, identified per node/choice in preflight and in `ink/validation.json`, before the original loss acknowledgement. No silently stripped conditions or text.

Supported exports include `ink/story.ink`, a pinned target/source map and compact original-owner replay witnesses in `ink/validation.json`, plus the exact source/review/export receipt and original bundle checksums. Witness coverage is one path per discovered ending, not all paths. Media, speaker styling, whitespace presentation and native-C# compatibility are explicitly limited. Every generated artifact says runtime NOT_RUN; fixture runtime verification never certifies an arbitrary current user artifact.

## Verification

`tests/test_storyverse_ink_exchange.py` uses an opt-in real compiler/runtime test. It compares original `play()` node/state/available choices/step/status to the pinned runtime across initial state, repeat loops, both branch routes, convergence and step cap. Actual target state is serialized and loaded into a fresh compiled Story after every step. Injection text includes INCLUDE, EXTERNAL, redirects, comments, tags, braces, brackets, quotes and newlines. Compiler uses a deny-all file handler (zero calls) and no bound external functions. Test-only harness checks the compiled bundle hash before loading it.

Pure tests, original File-backed owner export, source drift, actor denial, and preservation of old newline/tab/CR RenPy/neutral exports are covered. Existing mounted tests exercise original authorization. Opt-in PostgreSQL cases are skipped without a DSN.

Local regression excluding an unrelated pre-existing audio admission expectation: 100 passed, 78 skipped, 2 deselected. Full selected regression before that exclusion had 96 passed, 75 skipped, one failure: `test_real_model_adapter_requires_original_runtime_admission[file]` expects an old audio runtime admission string. The unchanged source now returns `ORIGINAL_AUDIO_MODEL_NODE_EXPLICIT_REGISTERED_LOCAL_ROUTE_REQUIRED`. This change does not repair or claim that gate.

Reproduction: obtain the exact archive separately; run `scripts/prepare_inkjs_test_dependency.py ARCHIVE NEW_DIRECTORY`; set `POEMSEED_INKJS_ROOT` to its `package` directory and `POEMSEED_NODE` to the existing Node binary. Use a writable task-local `XDG_DATA_HOME`, File test storage, cloud disabled and the existing mock configuration for fixture-only initialization. Run the new test file and existing interactive story suites. The preparation utility performs no download or executable loading.

## Still open

Native C# Ink and native RenPy runtime execution, arbitrary user artifact validation, full visual approved-world-rule impact navigation and the wider DIF-10 acceptance remain open. No new fact owner, branch permissions, workflow engine, game interpreter, approval lifecycle or persistence store is introduced.

### Final verification after review fixes

- Final adapter suite: **21 passed, 7 PostgreSQL cases skipped**. Includes execution of the Ink script extracted from the original-owner ZIP, Unicode names/dialogue, and exact result/snapshot-count checks before comparing runtime traces.
- Selected original regression: **115 passed, 81 skipped, 2 deselected** (the unrelated audio assertion and its PG parameter).
- Existing InteractiveStory UI suites plus target status tests: **88 passed**.
- TypeScript project typecheck: **PASS**. UI design-token guard: **PASS**. No styling/shell geometry changed. Browser/visual/geometry runtime checks were **NOT_RUN** under the no-browser constraint.
- Global witness generation is capped at **1,024 prefix states and 1 MiB compact witness JSON**, with explicit truncation and no repeated story text.
- Speaker newline/tab/CR is tested as target-specific unsupported text, with exact node and character IDs; original RenPy output is unchanged.
- Isolated clean baseline `79fbb1e5d80574e513cd51c09b54118b12c80d90` reproduces the audio assertion: **1 failed, 1 skipped, 65 deselected**. Baseline worktree tracked files are clean; the old assertion is unchanged. Raw initial and baseline failure logs are retained under `storyverse-ink-evidence/` alongside final results. This is separately owned compatibility work, not an Ink adapter failure.
