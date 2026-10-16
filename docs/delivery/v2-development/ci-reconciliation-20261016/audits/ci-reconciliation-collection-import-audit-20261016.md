# Static collection/import release audit

CONDITIONAL_RELEASE_RECOMMENDED: only existing collect-only inventory after the final backend receipt review and stable source checkpoint are accepted. Parent release is still required. No candidate or lifecycle/security test execution is authorized by this report.

Static review establishes no identified call path under the prescribed environment; it is not a universal proof of arbitrary imported Python behavior. Any actual import/collection error is retained and blocks manifest promotion.

## Exact conditional review command

env -u PYTHONHOME -u PYTHONPATH -u PYTHONSTARTUP -u PYTHONUSERBASE -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u DATABASE_URL -u TEST_POSTGRES_DATABASE_URL -u E2E_DATABASE_URL -u COLLABORATION_DEV_SESSIONS_JSON -u PACKAGED_RUNTIME_INSTANCE_ID -u PACKAGED_BOOTSTRAP_SECRET -u PACKAGED_CONTROL_PIPE PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHON_DOTENV_DISABLED=1 PACKAGED_WINDOWS_MODE=false /workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python scripts/extend_v2_coverage_manifest.py --report .runtime/ci-reconciliation-inventory/review-collection.json --output .runtime/ci-reconciliation-inventory/candidate-manifest-v2.json.gz

## Findings

### collection mechanism
Default tests directory only; collector invokes --collect-only and its own Inventory plugin. No test call or fixture setup phase. The sole tests hook adds backend skips and rejects contradictory markers; it does not perform lifecycle operations.
Evidence: pyproject.toml:15-23; scripts/extend_v2_coverage_manifest.py:123-145; tests/conftest.py:91-101

### pytest plugins and skips
Third-party plugin autoload is disabled; no anyio fixture/mark/config dependency was found. The sole top-level importorskip is fastapi, copied into the verified environment. Optional opentimelineio importorskip calls occur inside test functions. Autouse fixture setup does not run during collect-only. Environment skip decorators retain nodes and backend marker classifications; collect-report skips/errors must be retained and rejected.
Evidence: tests/test_round3i_adoption_mounted_api.py:18; tests/conftest.py:49-88

### app import local initialization
App import constructs the FastAPI object, File repository directories, owned stable/execution-node identity state, registries and service objects. This is not zero-side-effect inventory. These writes are confined to the generator fresh owned profile by PROJECT_ROOT/NOVEL_DATA_PATH/HOME variables. Lifespan recovery/start/shutdown is not entered by an import. Runtime bootstrap probes mock only; Ollama uses probe=False and remote adapters are constructed without egress.
Evidence: app/main.py:57-78; app/dependencies.py:52-55; app/runtime.py:20-48; app/repository.py:17; app/model_center/service.py:331-353

### packaged reader
start_packaged_control_reader is called at import, but explicitly false PACKAGED_WINDOWS_MODE returns before creating/starting a thread. Removing PACKAGED_RUNTIME_INSTANCE_ID/PACKAGED_BOOTSTRAP_SECRET/PACKAGED_CONTROL_PIPE adds defense in depth. ENABLE_PACKAGED_RUNTIME=false alone would not be sufficient.
Evidence: app/main.py:78; app/packaging/control_pipe.py:101-126

### dotenv reload
One suite calls load_dotenv at import. PYTHON_DOTENV_DISABLED=1 makes the pinned installed implementation return before searching or reading dotenv files. No .env existed at the stat-checked root/tests/ancestor locations; no dotenv contents were read. Command-local disabling is required even if no file currently exists.
Evidence: tests/test_v059_postgres_admin_concurrency.py:17; dependency dotenv/main.py:22-29,418-425

### database health decorators
Three import-time skip expressions can perform Database.health_check only if TEST_POSTGRES_DATABASE_URL is nonempty. Explicitly remove DATABASE_URL/TEST_POSTGRES_DATABASE_URL/E2E_DATABASE_URL and disable dotenv; then each expression short-circuits before Database construction/health_check. Do not alter any decorator, skip, node ID, or classification.
Evidence: tests/test_chapter_concurrency.py:93-97; tests/test_lore_postgres_contract.py:20-21; tests/test_postgres_repository_contracts.py:10-11

### latest Codex lifecycle and security suites
Top level imports types/helpers and builds parameter declarations. Actual bootstrap/create/delete/retire/revoke/database/subprocess calls remain in test functions or fixtures. Helpers are lazy. All 19 reviewed current test modules and 13 security-fixed runtime blobs exactly match a072cf9, which contains the two independently authored Codex fix commits. No candidate source origin or literal old-worktree path exists in app/tests/scripts.
Evidence: tests/test_v2_project_retirement.py:21-84; tests/test_v2_project_retirement_file_io.py:4-73; tests/test_v2_retirement_lock_order.py:16-88; tests/test_v2_scope_lifecycle.py:13-47; tests/test_round3i_pg_incarnation.py:19-64; tests/r3i_authorized_shared.py:16-52

### explicit importlib helper loading
These top-level loaders execute only helper module imports/constants/function definitions in .github/ci/screenshots.py, tests/e2e/database_fixture.py, scripts/public_build.py, scripts/prepare_pdf_font.py, scripts/prepare_windows_base.py and scripts/verify_windows_base.py. Launch/download/cleanup entry points are guarded by __main__ or deferred function bodies.
Evidence: tests/test_ci_screenshot_evidence.py; tests/test_e2e_database_fixture_contract.py; tests/test_public_build_profile.py; tests/test_public_wheel_artifact.py; tests/test_r2_pdf_font.py; tests/test_r2_windows_base_inputs.py; tests/test_r2_windows_native_verifier.py

### other constructors
sample_novel_data_root returns a Path without copying; required_child_environment returns a dict without creating directories. These top-level parameter helpers do not invoke services. No additional candidate/live operation was identified in the static top-level call review.
Evidence: tests/test_core.py:11; tests/sample_novel_fixture.py; tests/test_v2_real_text_check.py:159; scripts/run_v2_real_text_check.py

## Preconditions
- Audio final clean receipts accepted and no writer remains active.
- Source-only checkpoint committed; record HEAD/tree and complete path/hash snapshot, including frontend/scripts and frontend/e2e companion.
- Reverify all 43 restored and all 1123 old protected hashes, seven manifest/guard boundaries, and reviewed environment receipt/file hashes.
- Verify fixed .runtime/v2-checks/v2-manifest-collection profile absent or explicitly preserve/review its owned state; reject symlink ancestors. Current stat observation: absent.
- Run narrow unchanged CI helper tests only after checkpoint and release; no broad test execution implied.
- Parent explicitly releases the review-only command.

## Required preservation checks
- Preserve exit code, full stdout/stderr and raw fixed-path collection.json even on failure; archive immutable digest-named bytes before any subsequent generator invocation.
- Require zero collection errors or skipped reports and successful exit; do not change skips, IDs, collection filters or manifests to get a pass.
- Require exact ordered equality of all 15142 old rows including each backend classification against preserved old raw receipt.
- If separately released, write only a quarantine candidate using existing generator --write --output .runtime path; preserve candidate digest and raw rows; candidate full rows must equal accepted review rows.
- Canonical promotion is separate approval of exact reviewed candidate bytes, never speculative regeneration; subsequent confirmation must have identical full rows and stable sources.

## Exact module provenance

- tests/test_asset_lifecycle_r2.py | SHA256 151847ea6432dd6d12dd2c68229844267eed4aee01d4917db8cbb651413e3b5e | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_chapter_archive_lifecycle_v070.py | SHA256 6cd4e629c205430881cbf19a221314ce0404209846d18cae9fb5d11899f172a1 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_continuity_lifecycle.py | SHA256 1810691e9f550e2b7e30656763e0b1b3bb5fcbacf72ad0af0d6ef4106dd8902f | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_credential_provider_lifecycle.py | SHA256 156aa9e21df1888ca0b73c6b3a8fc16612c492b95723167ac708772e1ce13f7b | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_file_project_lifecycle.py | SHA256 843aa0b3ff32a2c74ee3da5aee77aa311626ddff558d1c0dffe402dd1aeb73d9 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_p0_security_regressions.py | SHA256 1fc168d1723f885eb64d62c221d76e243e907fa43366c1a7c61ac1c209457e8d | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_packaged_native_rc_lifecycle.py | SHA256 c188bfd2de2d5804c780a3954d4981d9ea32964c21b125a44f6045293b0ed4d8 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_plugin_discovery_security.py | SHA256 4f1aab28bea8f344c3c0cb6b948dba133f4a8f694fa43f12157b16e750effb7b | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_r2_media_lifecycle.py | SHA256 91563ef4aa4e8df362a7332687a895778803cdd05edda93f0a0b00433befabd1 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_round3i_pg_incarnation.py | SHA256 adf4c024d2d079618fa74dca1e8f0097695705bea762f30269eb9ed3ba2c4317 | a072 identical: true | old candidate: different_from_candidate
- tests/test_surface_adaptation_lifecycle.py | SHA256 6a12cf5b377237d510531fe09d3cf819ed6d8f1309c1dfd5e704728b0f1cb7a0 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_v061_acceptance_lifecycle.py | SHA256 aedd3a3bc9ff606cf9d958e1c3c8ce127999e351352e7c36b1c9f35956ab6dc8 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_v2_creative_project_lifecycle.py | SHA256 10faca7496e7f43553b9a83bcc99b19b043079309d5ad51bf7b3ea80e0458929 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_v2_media_probe_lifecycle.py | SHA256 7047e5aee8c50a301348fedeca0ea288ca5db1282c81b2c6717dc46d157a4526 | a072 identical: true | old candidate: inherited_shared_baseline_bytes
- tests/test_v2_private_prompt_lifecycle.py | SHA256 3bfe0227fb25db5b5c12acc8a39c27bddc3eecae90e54e8dbb020aa6cc8baf62 | a072 identical: true | old candidate: absent_in_candidate
- tests/test_v2_project_retirement.py | SHA256 132e7332963a9972825c223ecd403fbaebffa69feb4d925a1d17f7a442b4ce85 | a072 identical: true | old candidate: absent_in_candidate
- tests/test_v2_project_retirement_file_io.py | SHA256 8ed7589ab6d135bbdd533dc51e4c5788c209bd13872128eaf6579b7af8df58c0 | a072 identical: true | old candidate: absent_in_candidate
- tests/test_v2_retirement_lock_order.py | SHA256 b963b2355ed37968b7b7e7b61780738de495ad342ecb39fec655618c76748fbf | a072 identical: true | old candidate: absent_in_candidate
- tests/test_v2_scope_lifecycle.py | SHA256 bb79fa723be169b98294ab156d5b0dfbec2b7f20e66eadc3073d47c35ddb2699 | a072 identical: true | old candidate: absent_in_candidate

- app/api.py | SHA256 acdca1488e4906b47a71d06cad2655374fef7cbdffdbeebea49200adc77f6a47 | a072 identical: true
- app/application/persistence.py | SHA256 f34f58c6866cade1f85f1c81b9432a4cf39f3d30c07bab175c7bc3f19c4eca9d | a072 identical: true
- app/collaboration_admin.py | SHA256 47cd13de0023a40769ceedc5f3ffd32f6781e5f6013431a263da30f5e01be33c | a072 identical: true
- app/project_retirement.py | SHA256 4abf46a92326bc43988610edcc1fc20377803e3aced3e0643f408f68a37849d1 | a072 identical: true
- app/repositories/authorization_interfaces.py | SHA256 7eb4d441f125fa26925b19ff5a7414867e83721ba090197b3e786a0b59f245d3 | a072 identical: true
- app/repositories/file/novel.py | SHA256 2a1699a11363f639f838419164f8b6f795a6b81089bccba236af5ee92c2dec4d | a072 identical: true
- app/repositories/file/scope.py | SHA256 b3f664468ab78a0398ca90ee008f4395c055aedd8fc1539139088f15abecbffc | a072 identical: true
- app/repositories/postgres/novel.py | SHA256 d74cdb9b924f617e2554af5308ad63c71373566e55e863591aef821288674382 | a072 identical: true
- app/repositories/postgres/scope.py | SHA256 9097dde635bc6c3d8305a4ef6fb22acd441b2ee3dc66458783364a9a8891cfb9 | a072 identical: true
- app/repository.py | SHA256 b72108f416345ae02fb32847fb5b278e936c97318bd61f60b9396b265ff5bd80 | a072 identical: true
- app/runtime_events.py | SHA256 cc5ab2298a6731e82c9a12a48983dc956c259be67d468d0ae442da100122213e | a072 identical: true
- app/services/authorization_service.py | SHA256 ad1862ae3aa21eb9547e4d9ddadf30c08a4aeff8e9a2c4a9d345548d689bd374 | a072 identical: true
- app/services/collaboration_scope_service.py | SHA256 605fe6b9de231240f4b76fe54595db3f24ca02dbc3e060c8db637e6bcd6c1dfd | a072 identical: true

## Boundaries
- Current HEAD: 72e636f87c7299a62cb3357bcb6a6e44a9388883; this report precedes source checkpoint binding.
- Static default filenames: 587; no test/collection pass count.
- Old protected entries: 1123; mismatches: 0.
- Complete hashes and restored 43-file list are in the companion JSON.
- Raw collection uses the fixed path .runtime/v2-checks/v2-manifest-collection/collection.json, regardless of --report.
- Existing generator only internally enforces the 9151 V1 rows; independent exact preservation of all 15142 old V2 rows is mandatory.
- The original verification plan remains unchanged; this report is its clean-environment and import-safety addendum.
