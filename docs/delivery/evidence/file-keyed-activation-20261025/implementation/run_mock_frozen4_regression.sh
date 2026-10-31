#!/bin/bash
set -o pipefail
cd /workspace/scratch/20a0022d2b33/file-keyed-activation
# Freeze all Python implementation/tests rather than only touched files.
find app tests -name '*.py' -type f -print0 | sort -z | xargs -0 sha256sum > .runtime/file-keyed-activation/mock-final-frozen4-before.sha256
sha256sum .runtime/file-keyed-activation/test_live_staging_supplement.py .runtime/file-keyed-activation/test_automatic_route_supplement.py .runtime/file-keyed-activation/run_mock_tests.py .runtime/file-keyed-activation/run_mock_frozen4_regression.sh >> .runtime/file-keyed-activation/mock-final-frozen4-before.sha256
../studio-backend-20261025/.venv/bin/python .runtime/file-keyed-activation/run_mock_tests.py \
 tests/test_file_keyed_activation.py tests/test_file_writer_context_ports.py tests/test_file_writer_binding_v2.py \
 tests/test_memory_final_port_fences.py tests/test_file_local_bound_review.py \
 tests/test_bound_memory_project_owner.py tests/test_bound_review_port_blockers.py \
 tests/test_memory_agent_contract.py tests/test_memory_contract.py \
 tests/test_ordinary_project_binding.py tests/test_ordinary_project_binding_postgres.py \
 tests/test_passive_generation_manager_binding.py tests/test_passive_generation_manager_postgres.py \
 tests/test_generation_restart_recovery.py tests/test_generation_worker_authority.py \
 tests/test_generation_idempotency_contracts.py tests/test_chapter_concurrency.py \
 tests/test_chapter_archive_lifecycle_v070.py tests/test_chapter_markdown_contract.py \
 tests/test_v061_acceptance_lifecycle.py tests/test_generation_admission_receipts.py \
 tests/test_generation_variants_phase3.py tests/test_generation_snapshot_runtime_v056.py \
 tests/test_model_runtime_v070.py tests/test_phase7_adaptation.py \
 tests/test_phase7_adaptation_authorization.py tests/test_studio_production_query.py \
 .runtime/file-keyed-activation/test_automatic_route_supplement.py \
 .runtime/file-keyed-activation/test_live_staging_supplement.py \
 -q --junitxml=.runtime/file-keyed-activation/mock-final-frozen4-regression.xml \
 > .runtime/file-keyed-activation/mock-final-frozen4-regression.log 2>&1
status=$?
find app tests -name '*.py' -type f -print0 | sort -z | xargs -0 sha256sum > .runtime/file-keyed-activation/mock-final-frozen4-after.sha256
sha256sum .runtime/file-keyed-activation/test_live_staging_supplement.py .runtime/file-keyed-activation/test_automatic_route_supplement.py .runtime/file-keyed-activation/run_mock_tests.py .runtime/file-keyed-activation/run_mock_frozen4_regression.sh >> .runtime/file-keyed-activation/mock-final-frozen4-after.sha256
diff -u .runtime/file-keyed-activation/mock-final-frozen4-before.sha256 .runtime/file-keyed-activation/mock-final-frozen4-after.sha256 > .runtime/file-keyed-activation/mock-final-frozen4-diff.txt
printf 'pytest exit=%s; source hash diff exit=%s\n' "$status" "$?" > .runtime/file-keyed-activation/mock-final-frozen4-status.txt
tail -20 .runtime/file-keyed-activation/mock-final-frozen4-regression.log
cat .runtime/file-keyed-activation/mock-final-frozen4-status.txt
exit "$status"
