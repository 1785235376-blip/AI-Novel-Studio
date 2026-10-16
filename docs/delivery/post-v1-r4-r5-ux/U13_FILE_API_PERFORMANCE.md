# U13 large-project File/API performance receipt

Status: MEASURED. This is backend runtime evidence; browser/OS acceptance is separate.

## Provenance
- Commit: `0a2a85f4ec04218bbd6cc33b2363b71a52cd2b95`
- Git tree: `0f390e5a79c27558f7bffdedcfdbd8c0a04ec09b`
- Python source SHA-256 before and after: `56ee935709c008a294b14c05d947cf24f67bf156151b6d1a40d1dca1e8a1e31e`
- Detached clone resolved to its own .git; source stayed clean and unchanged.
- Run started: 2026-10-05T15:35:05.895630+00:00
- Raw receipt: `r4-u13-performance-0a2a85f.json` (109,326 bytes); SHA-256 `d1f78ac15993bb5c67ebaa74813dc33266402fa515a956efde313a6896fbadd3`
- Environment: Linux x86_64, Python 3.12.14, 9 logical CPUs; FastAPI 0.142.2, Starlette 1.7.0, HTTPX 0.28.1, Pydantic 2.13.5.

## Predetermined method
- Six fresh processes: 100,000 / 500,000 / 1,000,000 exact Han characters, each flags off and workspace_tools_v2 on.
- Each project contains 12 chapters, three named characters and two legacy story-route planning records. These are not collaboration-branch manuscripts.
- Original deterministic repeated synthetic prose, not imported novels or model output. Representative semantic markers are present, but lexical diversity is deliberately limited.
- Mounted FastAPI TestClient and real File services/storage. In-process API timings include middleware and response serialization; they exclude browser and TCP transport.
- Warm search: three warmups, then 30 retained queries; nearest-rank p50/p95. Six-query cycle contains four expected hits and two expected misses. No outliers were discarded.
- Fresh process/import/index; OS filesystem cache was not flushed. RSS includes Python, application imports and fixture creation, and is not a browser-memory measurement.

## Measured search results
| Han characters | API p50 ms | API p95 ms | Max ms | Target 500 ms | Process RSS MiB |
|---:|---:|---:|---:|:---|---:|
| 100,000 | 43.34 | 49.50 | 54.52 | PASS | 120.55 |
| 500,000 | 158.63 | 193.13 | 210.96 | PASS | 126.32 |
| 1,000,000 | 289.62 | 314.92 | 317.95 | PASS | 140.33 |

- Each enabled run retained 20 expected hits and 10 expected misses, with zero HTTP errors, zero truncation and zero changed documents during warm queries.
- Editing one chapter updated exactly one indexed document at every size. Archiving that chapter removed its unique search result.
- These targets passed for this recorded environment and corpus only; no general hardware guarantee or browser-input target pass is implied.

## Flags-off, startup and serialization
| Han characters | Flags-off open p95 ms | Enabled import ms | Chapter-list API ms | List response bytes | Loaded-list JSON encode ms |
|---:|---:|---:|---:|---:|---:|
| 100,000 | 5.36 | 1939.74 | 46.50 | 343,259 | 0.39 |
| 500,000 | 17.96 | 1961.51 | 172.26 | 1,705,539 | 2.63 |
| 1,000,000 | 27.38 | 1917.16 | 272.39 | 3,408,376 | 4.50 |

- All flags-off search attempts returned 404 and left zero workspace index scopes. Each baseline retained 30 chapter-open samples.
- All six processes recorded zero blocked network-connection attempts, requested no model execution, and did not load torch, transformers, diffusers or tensorflow at application startup.
- JSON encode figures measure stdlib encoding of the already-loaded chapter list. They are not an isolated measurement of FastAPI serialization.
- All six owned temporary fixture directories were removed. No preexisting data/profile path was used.

## Long task history
- Created and cancelled 240 real File-backed deterministic tasks in the 100k enabled fixture; executed tasks: zero.
- Authority pagination returned 100 / 100 / 40 unique cancelled records; has_more was true / true / false.
- Workspace projection p50 13.98 ms; p95 18.52 ms across 30 samples after three warmups.
- The workspace projection returned its capped 100 records and truthfully reported truncation on all 30 samples. This is not full-history display or virtual-list verification.

## Remaining bottleneck and bounded next step
- The search cache reuses derived documents, but each query still reads and hashes authoritative source chapters.
- At 1m Han, direct chapter-list p50 was 261.23 ms, direct search p50 269.70 ms and mounted search p50 289.62 ms. These separate measurements are consistent with source loading dominating, rather than JSON encoding (4.50 ms for the loaded list).
- Source inspection shows FileChapterRepository.list calls get per chapter; get reaches backend.chapter, which lists the corpus again. With 12 chapters, this repeats full-source reads.
- Suggested bounded optimization: produce one locked File chapter snapshot and read its current per-chapter version metadata without re-enumerating all chapters for each get. Preserve project guards, archive filtering, authoritative versions and existing access checks; rerun File/PG parity, concurrency, invalidation and this same fixed benchmark before claiming improvement.

## Explicitly not verified
- Browser input-to-render p95, browser fetch timing and screenshots: NOT_RUN in this backend measurement. Authored browser suite awaits hosted CI.
- Native Windows IME, screen reader, physical input latency, native browser/OS zoom and multi-monitor behavior: NOT_RUN.
- Real model/GPU/literary quality and PostgreSQL performance: NOT_RUN in this benchmark.
- No claim that all 1m characters are simultaneously mounted in the editor. The browser suite opens one of 12 chapters.

## Receipt validation
- Recomputed all recorded warm p95 values from the 30 raw samples; checked hit/miss expectations, cache counts, update/archive outcomes, all six exact Han counts, task pagination, flags-off gates, network counters and cleanup.
- Sanitization check found no workspace/home/temp-profile paths, session token, API-key environment names, database URL or bearer-credential value in the raw receipt. Only generic platform/runtime versions and synthetic metadata are included.
