# Known inherited File lifecycle defect

Status: **OPEN at the R3 checkpoint**. This is not covered by the statement that reproduced R3 domain-review findings were corrected.

## Observed behavior

- R3 hosted Chromium run [37319444460](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37319444460), frontend job 111794445584: World review/continuity assertions completed, then owned synthetic-project deletion raised `OSError: [Errno 39] Directory not empty` from the unchanged `app/repository.py` File delete path. The still-open page could perform lazy document reads.
- A separate deterministic synthetic-project reproduction on unchanged R3 paused a read immediately before lazy document migration, deleted that same project, then resumed the read. The directory was recreated and the project appeared in listing again. This establishes a real application lifecycle race, not merely a flaky selector. The variant deletes completely before the read resumes; it is distinct from the DirectoryNotEmpty observation. The R3 integrator reran this synthetic reproduction against local `70c01ff` (remote source `20cd2679ee104702529962202ce4b9d894bffc89`) and observed `{"absent_after_delete": true, "ghost_list_entry": true, "recreated_by_read": true}`.

Owning unchanged paths: `app/repositories/chapter_repository.py:ChapterRepository.get` lazily creates a document package; `app/repository.py:FileRepository.delete_novel` uses unsynchronized recursive deletion; `app/storage.py:atomic_write` recreates parent directories; `FileRepository.list_novels` includes the recreated directory even without novel metadata.

## Boundary and next action

R3 fixture teardown blocks new page API requests, drains tracked client requests and closes the page before deleting only IDs created by that test. It neither changes the production repository nor proves all server work ended. Cleanup failures remain failures.

The subsequent user-authorized engineering branch will own a separate shared-fix/backport-candidate commit and deterministic concurrency regressions. Any proposed V1 backport must preserve the frozen acceptance record and be separately authorized; no such backport or PR #37 change was made here.
