# Shared R1/R2/R3 repair evidence

Baseline: `c6f2126115b52e17839d48efea091dc21ec08c61`, tree `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`.

The three scripts in `reproductions/` are extracted without text edits from the user-supplied external review. The source report was reconstructed from its complete authorized Library read; this is not a claim of byte-exact original attachment preservation. The scripts deliberately observe defects and their exit status of zero is not a PASS. Their synthetic data and in-memory test sessions never represent private user projects, real credentials, or provider-quality evidence.

An immutable baseline archive was preserved before runtime edits. All three defects reproduced separately with Python 3.12.14 and all 31 constraint versions matched. That is supplemental local evidence, not the locked Python 3.12.9 result. `Shared R123 evidence` checks out the exact untouched baseline and uses Python 3.12.9 plus its original dependency constraints, runs each unchanged script in its own process, preserves stdout/stderr, and explicitly asserts each known RED observation. A green evidence-job conclusion means the defects were reproduced, not that the baseline is safe.

This is ordinary implementation/regression work on supplied findings. The historical independent follow-up review remains platform BLOCKED, without restart, rephrasing or rerouting. The product matrix remains 39 PARTIAL plus F00 INTEGRATED. Real model/GPU/TTS/translation quality, native Windows interaction and target applications remain NOT_RUN. PR37/38 are frozen; no merge, release, deployment or backport is authorized here.
