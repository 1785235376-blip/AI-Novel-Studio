# Integrated current-source CPU media verification

Source checkpoint: `62606f534a00861cbd541f6e3926ba473f2de81c` (the capacity feature is `8a66e4b42a25935b13c93cf075af684dfa256d48`; the later checkpoint only binds the separate offline PUBLIC wheel). No application source was changed for this verification.

The existing original File owners were exercised with local synthetic authored media using installed `/usr/bin/ffmpeg` and `/usr/bin/ffprobe` version `7.1.5-0+deb13u1`. No tool download, model, network provider, GPU, browser, blocked lifecycle/security test or hosted CI was used.

## Exact selection and outcome

The original isolated `scripts/run_v2_checks.py` runner recorded **8 passed, 5 PostgreSQL cases deselected**, exit 0, with `sources_changed_during_check=false` in `../integrated-cpu-media-final.json`. The precise command, profile, captured source hashes and log hash are retained there. The selected cases were:

- `test_v2_audio_editing_pipeline.py::test_real_flac_formal_asset_atomic_edit_cpu_render_review_bytes_and_reopen`, both render and delivery-export parameters. Authored WAV → native trimmed FLAC → explicit review/formal Asset → original atomic Timeline edit → real MP4 → independently decoded picture/PCM → explicit output review → fresh-store reopen. The exact original request is also idempotent, and candidates remain private before review.
- `test_v2_audio_flac.py::test_actual_flac_original_private_review_reopen_and_pcm_proof`: actual lossless FLAC and decoded PCM proof, private output, review and restart/reopen.
- `test_v2_audio_mp3.py::test_actual_mp3_private_review_reopen_and_lossy_pcm`: actual libmp3lame output, exact gapless sample timing, independent ffprobe/PCM decode and bounded lossy RMS comparison, review and reopen. This does not claim lossless MP3.
- `test_v2_timeline_asset_handoff.py::test_exact_asset_draft_save_reopen_and_cas`: original exact image-asset reference save/reopen/CAS, without rendering.
- Three existing `test_v2_nle_review.py` cases: pure exchange projection/loss reporting, refusal to restore stale Studio effects after native edits, and exact rational-frame arithmetic. No external NLE application was run.

A pre-existing Starlette/httpx deprecation warning is retained in the log; no dependency was installed to suppress it.

## Actual media artifacts

`actual-media-probes.json` independently records ffprobe commands, successful exit codes, full stream/container probes, bytes and SHA256 for the four real retained outputs (review MP4, delivery MP4, standalone FLAC, standalone MP3). It also hashes the independently decoded PCM/WAV and RGB files produced by the tests. The MP4 assertions measured 64×64, ten decoded frames, 48000 Hz stereo PCM and audible nonzero content; the standalone audio assertions measured 22050 Hz mono and 15435 decoded samples (700 ms). Synthetic media bytes remain only in the isolated profile and are not published.

## Concrete next handoff gap

Read-only audit found that the shared `appendTimelineAsset` insertion currently chooses up to 1000 ms without knowing the source duration. The generic handoff persistence test uses an image; the native short-audio pipeline explicitly supplies its valid 800 ms out-point and therefore does not prove the automatic default is valid for 700–800 ms audio/video. Original rendering correctly rejects a trim beyond measured source duration. Reproducing that exact handoff and fixing only its bounded original-owner range selection is a separate next slice. Existing Asset public metadata does not currently expose a validated duration; untrusted or missing duration must not be guessed.
