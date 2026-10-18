# Session-only timeline review playback options

2026-10-18. The existing verified private-cache player now offers explicit review
speeds (0.5, 0.75, 1, 1.25, 1.5, 2 times) and full-cache looping. These controls
operate only on the currently mounted video element whose src matches the original
controller's verified visible cache. No autoplay, render, model, task, source-edit,
approval or export action is dispatched. Native rate changes are reflected in the
selector, including a bounded-by-browser observed rate outside the preset list.

A changed cache identity resets to 1x with looping off. Stale/unmounted callbacks
and mismatched media URLs are ignored. The original controller still owns candidate
attestation, byte hashes, permissions, source/version invalidation, UNKNOWN, cancellation
and Blob cache cleanup. Removing visible media removes the options and invokes the
original playback pause cleanup. The user must still begin playback explicitly.

This is browser review playback, not timeline clip retiming, an A/B loop range,
frame-exact scrubbing, audio-quality certification or export-rate editing.

Evidence: timeline-review-playback-ui-20261018-r1 receipt/raw log. 44 checks passed
(5 additive including actual panel wiring, 39 existing), TypeScript and Vite build
passed. Existing large-chunk warning remains. jsdom media property/event checks are
not real MP4 decoding or browser/native playback acceptance. No baseline test,
backend, shared shell or design token changed.
