# Peak normalization omission baseline

Captured before runtime edits at e1e66cedeb7a140b6894850bc21a1e5ac7e06c16. Actual original MediaCommand serializers, ProductionExecutionService.preview, recipe digest, owner _body/_binding and _receipt were called. Scope, source, egress and binding collaborators use fixed synthetic inputs. The receipt is a fixed constructed QUEUED row, not an executed job. No clock patch was needed: these methods do not use wall time for this projection. Source snapshot digest is synthetic; source_sha256 is the existing empty prompt hash, not media bytes. This capture proves serialization only, not native execution or lifecycle.

Frozen fixture SHA256: d818680bf5895014cd400671d5ed95d3ca61a8886cec4e58c2f8dfcc0c4dcc16. Seven variants include omitted controls, gain/rate/channels, FLAC, versioned MP3, graph trim, explicit zero fade and positive fades. Existing fade and MP3 fixtures remain untouched.

The sole clean Python launched fresh natural startup and actual original run_v2_checks.py child PathFinder probes before/after capture. Runner receipts retain full source before/after hashes and HEAD. Native tools and heavy tests have not run for this line.
