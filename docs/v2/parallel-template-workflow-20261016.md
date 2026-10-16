# B01 personal template-copy editing, 2026-10-16

Base: `ece0ac7`. Slice state: IMPLEMENTED (bounded local source, focused UI and File evidence). B01 overall remains PARTIAL.

## Audited gap and delivery

TemplateLibraryPanel already mounted a complete catalog/import/copy/CAS edit/update/history/revert owner, and PersonalSkillBriefComposer already created declarative personal briefs. This slice does not recreate them.

A saved section-based brief previously required JSON editing; history displayed raw content only. The existing panel now offers labelled section text fields synchronized with the original JSON editor, author/license/provenance display, and historical-versus-saved changed blocks. History comparison is presentation-only, explicitly not a minimal semantic diff; each side is capped at 100 lines with truncation disclosure and original history still available.

The structured editor preserves section keys/titles and other JSON properties, supports 1–20 uniquely keyed sections and 8,000 Unicode code points per text. Unsupported content remains editable through the existing JSON path. Every save still calls the original template-library PUT with expected_version. No new storage, execution, publishing, provider/model request, permission or capability is introduced.

Unsaved edits disable copy switching, new catalog copy creation, update and restore until saved or explicitly discarded. Server conflicts retain the draft. A fresh client remount clears scoped state. Installation preview digests, source identity, CAS and original owners are unchanged. Structured controls are disabled during outstanding actions.

## Verification

- Frontend, `vitest run --no-cache src/experimental/templateCopyEditing.test.ts src/experimental/TemplateCopyEditing.test.tsx src/experimental/DeclarativeTemplatePanels.test.tsx src/experimental/PersonalSkillBriefComposer.test.tsx src/experimental/personalSkillBrief.test.ts`: 46 passed, exit 0. Final focused 3-test rerun includes catalog-copy dirty guard.
- `tsc --noEmit`: exit 0.
- `vite build`: exit 0, existing large-chunk warnings. Outputs stay in this worktree.
- `node scripts/check_ui_design_tokens.mjs`: PASS, exit 0.
- Real File owner test: `python -B -m pytest -q tests/test_template_copy_editing_workflow.py -m file_backend_only --basetemp=.runtime/template-copy-editing/pytest -o cache_dir=.runtime/template-copy-editing/cache`: 1 passed, 1 PostgreSQL case deliberately deselected, exit 0. New store/service reopening reads disk state and verifies content, metadata, CAS conflict, history and non-destructive revert. This is service/File evidence, not browser-to-HTTP integration evidence.
- File command used the existing approved `.venv/bin/python` interpreter and `scripts.run_v2_checks.isolated_environment` with all app/HOME/cache/data paths under this worktree `.runtime/template-copy-editing/profile`; provider/database secrets removed, mock provider and cloud disabled. No new installs. Initial default Python probe lacked pytest; subsequently used existing interpreter.
- Early Vitest runs used the existing dependency symlink with its default cache; after reviewer notice, all later test commands use `--no-cache`. No package or dependency changes committed.

## Limits

Real browser/visual screenshot, Windows/GPU/model execution, PostgreSQL, remote CI and push: NOT_RUN. No P0 security, lifecycle or gate changes. The full B01 advanced-template scope is not declared complete. No App/Workbench integration seam is needed because the existing mounted panel owns the new controls. No shared ledger or checkpoint edited.
