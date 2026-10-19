# Round-3 suite summary (raw evidence)

- Complete File suite, D-20 file excluded, then the file run standalone:
  24 failed / 10023 passed / 5087 skipped / 12 errors / 3 deselected / 5 subtests passed
  in 3456.74 s (57 m 36 s). All 36 failed/error nodes are the dedicated-profile suites
  (revocation 24, R3-I authorized 8, R3-I adoption 4) and each has a passing profile receipt.
- Excluded order-sensitive file standalone: test_post_interop_shared_universe.py
  11 passed / 11 skipped (D-20).
- Unified Windows entry profiles: targeted PASS 1427/0/429; collaboration PASS 24 skipped;
  round3i-adoption 4/4; round3i-authorized 8/8; r3-import 44 tests / 22 skipped / 0 failed.
- D-09/D-18/D-19 verification: d09-d18-d19-verification.log.gz (39 passed / 28 skipped).

Raw logs and JUnit receipts are the gzip files in this directory; SHA256SUMS.json binds them.
