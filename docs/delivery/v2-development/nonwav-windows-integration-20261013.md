# Non-WAV source handoff and Windows development verification

The verified handoff is integrated with local Windows lifecycle fixes. Related CPU/File/PostgreSQL checks passed on the final frozen source. This is source and development evidence; installed Windows, GPU, real-model and full product acceptance remain open.

## Provenance

Remote baseline: `877cf0ab39891d37ccb9ffdecb1c5a98c88e3bd2`.
The ten handoff files and full-index patch were individually verified and reproduced tree `70f81a7e6ae421087c3336a03f27e02e93214e51`.
The handoff identifies cloud-local commit `f65025548d05632ae2b4a520f531dcc1abcea8d5`; its Git commit object was not recovered. This is verified source integration, not restoration of that commit's history.

Historical `1134f8de50ad68b9e1aad189cb422e256af64c6f` remains unrecovered; subsequent work remains reconstruction. Original cloud reports are preserved unchanged and are separate from local results.

Final tested source input tree: `42d251b6a8a9ec007425dff22b80c19328222f01` (15 selected source/test/historical-report files, before regenerated metadata and this report). The final `app/creative/production_execution.py` SHA256 is `f61a436750b4104b8e865320a11c7ecb073d59c46fcff6c682a15d7c5dacae82`. Application/test source bytes were unchanged during the final checks and generation.

## Implemented behavior

- Non-WAV probe and complete decode use the original bounded, guarded native-process owner. Original 20-second probe / 30-second decode limits, fixed server argv, file/pipe protocols, private inputs and successful MIME/duration/preview/request identities remain. Two-argument `inspect_media(data, kind)` remains valid; the optional guard preserves revocation and cancellation exceptions.
- Original audio and timeline first-source inspection polls the existing Host/job/Graph fences outside Asset leases, without recursive source probing. Original task stores, CAS, private candidates, human review and no automatic replay remain.
- Windows reaped process HANDLEs are explicitly released. Cleanup sharing retries remain finite and only target the same ordinary empty private directory; ownership is rechecked after every wait. Permanent failure remains explicit and preserves the primary guard exception. The actual directory-replacement and later-content regression failed before the fix and passed afterwards.
- Windows receipt reads retain full before/after comparisons within path and FD families while excluding semantically different ctime only from the Windows cross-family comparison. Metadata checks only detect observable changes; they are not a globally atomic filesystem snapshot.
- The original disposable PostgreSQL wrapper now quotes its fixed native options correctly on Windows. Original fresh-database, migration and process-ownership gates remain.
- Two adjacent V2 checks before `timeline_get` are coalesced. Its first and final live-authority checks, all current project/incarnation/timeline reads, source Host-only guard and export-preview revalidation remain. No authorization cache, timeout increase or assertion removal was introduced.

## Actual local execution

| Final-source selection | Actual result |
| --- | --- |
| 23 related modules, File | 750 passed / 14 skipped / 307 deselected; 144.17 s |
| Same 23 modules, real fresh PostgreSQL | 762 passed / 14 skipped / 295 deselected; 1279.82 s |
| Original PostgreSQL timeline cancellation selection after the measured optimization | 8 passed / 54 deselected; 43.92 s; no observer plugin |

Each broad run retains two original POSIX cases not applicable on Windows and twelve original optional OTIO skips. The selections overlap and must not be summed. Synthetic media, real CPU FFmpeg and controlled native children are development evidence, not model or installed-application acceptance.

PostgreSQL began with an empty owned database, applied all twenty original migrations and stopped normally. Independent checks confirmed status=3, no postmaster PID file and no listener on the owned port. No user database, works, existing model/runtime process or QingJian work was changed.

### Preserved failures

The earlier focused PostgreSQL run on tree `43e0deb3ea40f738ab56694e73aad78aa75cf9b8` remains 285 passed / 1 failed / 2 skipped / 80 deselected (351.34 s). Its export flow took 5.062 s against the unchanged original 5 s assertion. Assertions after that failure were not reached. One separate diagnostic observation passed in 4.791 s and measured 164 fresh connections consuming 3.956 s; it is not a replacement acceptance result. The subsequent source change and final uninstrumented selections are recorded separately.

Earlier invalid fixture invocations, source-change receipts, Windows identity/cleanup failures and the retry-ownership failure remain external with exact source mapping. They were not overwritten or discarded. Original cloud 261/725/737 results and old local File 286 results do not validate the final source.

## Regenerated inventories

The original generators produced all four API artifacts together: **2219 operations**, bound to **427 application Python files**. The separate V2 inventory collected **13364 nodes**, retaining all **9151 frozen baseline nodes in relative order** and 4213 additional nodes. Collection is inventory, not execution success. Historical skip rules and external gates are unchanged.

Frozen V1 manifest SHA256 remains `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`. No generator or frozen-baseline edit was used to remove differences.

The original 47-check Windows invocation remains **45 passed / 2 failed / 0 skipped**. Both failures are fixture-level `WinError 1314` while creating real symlinks, before their target assertions. Surface, discovery and manifest checks passed; 26 compact checks passed. No rerun, skip addition, assertion change or Windows security-setting change was used. Any supplemental environment evidence is separately recorded in the accompanying verification JSON and does not change this original Windows result.

The same two original symlink assertions additionally passed on the existing Ubuntu environment: **2 passed; 1.37 s**. An initial supplemental collection failure is retained. Independent owned-temp checks demonstrated that DrvFS could not truncate the already-unlinked capture file while native Linux temp could. Only standard pytest `--capture=sys` was then used; original source, assertions and isolated profile boundaries remained. This does not convert the original Windows invocation into 47 passing Windows checks. No system permission or model service was changed.

## Remaining gates

GitHub Cloud CI is independently blocked before runner dispatch: the two recorded baseline runs each have eleven jobs with runner identifier 0 and no executed steps. The account dispatch restriction is confirmed in private annotations; no financial/raw annotation is published here. This proves neither product failure nor product success. No manual CI rerun was requested.

The historical PostgreSQL adaptation/archive timeout and graph-text archive failed-call were not reproduced by this media selection and remain open. Final Windows installation, trusted DesktopHost/vault/WebView2 acceptance, RTX5080 and real-model inference, heavy rendering and the complete Text→Router→Provider→Asset→Version→Review path remain NOT_RUN / LOCAL_REQUIRED. M4 and later milestone gates are unchanged.

The older workspace's 35 unfinished files were verified unchanged. Main, frozen V1 assets, original evidence, PoemSeed Local Interop 1.0 and Opus UI/UX controller boundaries remain. This stage adds no parallel Project, Asset, Model Center, queue, permission or export system. QingJian is paused.

AUDIO-12 FLAC delivery has a separate read-only assessment and is not implemented by this security increment. It should reuse the original standalone trim/review owner with actual decoded PCM equality proof; Graph's existing parameter boundary remains. MP3 needs independent lossy/delay/padding proof after FLAC.

The accompanying [sanitized verification](nonwav-windows-integration-verification-20261013.json) records source hashes and actual run mappings. Raw logs, databases, environment configuration, private paths and credentials remain external and are excluded from publication. The publication SHA is the Git commit containing this report and is separately verified in the local publication receipt; this document does not invent a self-referential commit ID.
