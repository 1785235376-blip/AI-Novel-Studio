File writer source/context/snapshot original-port implementation
Base: e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459
Worktree: file-keyed-activation (shared integration tree)

Runner: /workspace/scratch/20a0022d2b33/studio-backend-20261025/.venv/bin/python docs/delivery/evidence/file-local-bound-review-20261025/run_tests.py
Runner sets worktree cwd/PYTHONPATH, isolated HOME/XDG/data/tmp and blocks sockets.
All commands append -q --junitxml=.runtime/writer-ports/<stem>.xml and redirect stdout/stderr to <stem>.stdout.

context: initial direct pytest lacked isolated XDG_DATA_HOME; 34 setup errors, not product verdict.
isolated-context: collection hit concurrent jobs.py IndentationError; preserved without attributing to ports.
isolated-context-2: tests/test_file_writer_context_ports.py tests/test_lore_context_contract.py tests/test_context_intelligence.py tests/test_context_policy.py tests/test_context_pack_v2.py. 41 PASS, 3 SKIP.
pg-memory-ports: tests/test_passive_generation_manager_postgres.py tests/test_memory_final_port_fences.py tests/test_file_writer_context_ports.py. 68 PASS.
ports-final: tests/test_file_writer_context_ports.py. 15 PASS at earlier source snapshot.
integrated-ports: tests/test_file_writer_context_ports.py tests/test_file_local_bound_review.py tests/test_memory_final_port_fences.py tests/test_passive_generation_manager_postgres.py. 104 PASS, 2 direct passive _run contract FAIL reported to integrator and fixed separately.
ports-source-metadata: tests/test_file_writer_context_ports.py. 17 PASS.
ports-durable-snapshot: tests/test_file_writer_context_ports.py. 21 PASS, 1 fixture passed wrong same-root repository to original-target guard; corrected fixture only.
ports-frozen: tests/test_file_writer_context_ports.py. Final source hashes alongside this file.

Port tests use actual File repositories and lower-level context/snapshot calls; durable GENERATING rows in ports_for are explicitly synthetic identity fixtures, NOT writer execution grants or end-to-end generation evidence. Full keyed API/Mock E2E is tested by the separate integration task. PostgreSQL tests are offline protocol only. Live PostgreSQL, Windows and real model dispatch NOT_RUN. No network writes, uploads or commits made by this unit.
