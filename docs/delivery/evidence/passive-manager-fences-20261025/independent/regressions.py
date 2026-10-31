import run
if __name__=='__main__':
    import pytest
    raise SystemExit(pytest.main(['-q',
      'tests/test_generation_restart_recovery.py',
      'tests/test_passive_generation_manager_binding.py::test_collaborative_retry_keeps_original_preview_guard_before_passive_guard',
      'tests/test_passive_generation_manager_binding.py::test_registered_branch_passive_reads_require_the_original_registered_owner',
      'tests/test_generation_worker_authority.py::test_valid_live_callback_and_no_callback_legacy_complete',
      'tests/test_generation_worker_authority.py::test_transient_callback_is_not_reconstructed_by_existing_restart_recovery',
      'tests/test_generation_idempotency_contracts.py::test_generation_replay_returns_cached_result_without_creating',
      'tests/test_generation_idempotency_contracts.py::test_generation_without_idempotency_key_creates_independently',
      '--junitxml='+str(run.EVIDENCE/'regressions.xml')]))
