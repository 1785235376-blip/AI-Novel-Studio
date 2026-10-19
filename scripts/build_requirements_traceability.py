"""Generate the unique V2 requirement traceability matrix (ENG-2026.10.19-r1).

The matrix is the single machine-readable index for:
  * original Master Roadmap release-required items (V2-*),
  * the 40 A/B/U/F advanced capability packages parsed from the in-tree server registry,
  * DIF-01..DIF-12 differentiated capabilities,
  * IMAGE-COMIC-01..IMAGE-COMIC-20 comic sub-features.

Requirement status and test result are independent axes. A row is never promoted to
INTEGRATION_VERIFIED or ACCEPTED by documentation alone: test evidence must be bound to a SHA
and human acceptance is required for ACCEPTED.

Usage:
    python scripts/build_requirements_traceability.py [--check]

--check verifies the committed JSON is exactly what the generator would emit (CI-friendly).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "v2" / "engineering" / "requirements-traceability.json"
EVIDENCE = ROOT / "docs" / "v2" / "engineering" / "test-evidence-20261019-r1.json"

SPEC_ID = "SPEC-2026.10.19-r1"
SPEC_PATH = ROOT / "docs" / "v2" / "engineering" / "spec" / "SPEC-2026.10.19-r1.txt"
SPEC_REL = "docs/v2/engineering/spec/SPEC-2026.10.19-r1.txt"
SPEC_TITLE = "PoemSeed Studio V2 发布版全量增强需求书"

TESTED_BASELINE_SHA = "a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3"
BASELINE_BRANCH = "work/v2-eng-baseline-20261019"
BASE_BRANCH = "feature/v2-narrative-platform"
REPOSITORY = "1785235376-blip/AI-Novel-Studio"

STATUS_VALUES = ["PLANNED", "IMPLEMENTED", "INTEGRATION_VERIFIED", "ACCEPTED", "BLOCKED"]
TEST_RESULT_VALUES = ["PASS", "FAIL", "PARTIAL", "BLOCKED", "NOT_RUN"]
GAP_TYPES = ["NONE", "PARTIAL", "MISSING", "NOT_INTEGRATED", "BLOCKED", "SOURCE_MISSING"]
RELEASE_BLOCKING = ["HIGH", "MEDIUM", "LOW", "NONE"]

FOCUSED_CMD = "python -m pytest -q -p no:cacheprovider -ra --tb=short"


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return TESTED_BASELINE_SHA


def _spec_field(body: str, label: str) -> str:
    match = re.search(r"\*\*" + re.escape(label) + r"：\*\*(.*?)(?=\n\*\*[^\n：]+：\*\*|\Z)", body, re.S)
    return " ".join(match.group(1).split()) if match else ""


def load_spec() -> dict:
    if not SPEC_PATH.exists():
        raise ValueError(f"SPEC_SOURCE_MISSING: {SPEC_REL}")
    data = SPEC_PATH.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8")
    if not text.startswith("# " + SPEC_TITLE):
        raise ValueError("SPEC_TITLE_MISMATCH")
    if SPEC_ID not in text:
        raise ValueError("SPEC_VERSION_MISSING")
    dif: dict[str, dict] = {}
    headings = list(re.finditer(r"^### (DIF-\d{2})｜(.+)$", text, re.M))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else text.find("\n## 3.", match.end())
        if end < 0:
            end = len(text)
        body = text[match.end():end]
        dif[match.group(1)] = {
            "line": text.count("\n", 0, match.start()) + 1,
            "section": "2",
            "title": match.group(2).strip(),
            "goal": _spec_field(body, "目标"),
            "must": _spec_field(body, "MUST"),
            "forbidden": _spec_field(body, "不可偷换"),
            "acceptance": _spec_field(body, "验收"),
        }
    comic: dict[str, dict] = {}
    for match in re.finditer(r"^\*\*(IMAGE-COMIC-(\d{2}))｜(.+?)\*\*(.*)$", text, re.M):
        comic[match.group(1)] = {
            "line": text.count("\n", 0, match.start()) + 1,
            "section": "3.2",
            "title": match.group(3).strip().rstrip("。"),
            "requirement": " ".join(match.group(4).split()),
        }
    if len(dif) != 12 or len(comic) != 20:
        raise ValueError(f"SPEC_COVERAGE_INCOMPLETE dif={len(dif)} comic={len(comic)}")
    return {
        "id": SPEC_ID,
        "path": SPEC_REL,
        "sha256": digest,
        "bytes": len(data),
        "lines": text.count("\n") + 1,
        "title": SPEC_TITLE,
        "dif": dif,
        "comic": comic,
    }


def bind_spec(rows: list[dict], spec: dict) -> None:
    meta = {"document": spec["id"], "path": spec["path"], "sha256": spec["sha256"]}
    for entry in rows:
        if entry["group"] == "DIF":
            item = spec["dif"].get(entry["id"])
            if item is None:
                raise ValueError(f"SPEC_BINDING_MISSING {entry['id']}")
            entry["spec"] = {**meta, "section": item["section"], "line": item["line"], "title": item["title"],
                             "goal": item["goal"], "must": item["must"],
                             "forbidden": item["forbidden"], "acceptance": item["acceptance"]}
            entry["user_behavior_must"] = item["must"] or entry["user_behavior_must"]
            entry["expected_result"] = item["acceptance"] or entry["expected_result"]
        elif entry["group"] == "IMAGE_COMIC":
            item = spec["comic"].get(entry["id"])
            if item is None:
                raise ValueError(f"SPEC_BINDING_MISSING {entry['id']}")
            entry["spec"] = {**meta, "section": item["section"], "line": item["line"],
                             "title": item["title"], "requirement": item["requirement"]}
            entry["user_behavior_must"] = item["requirement"] or entry["user_behavior_must"]
        else:
            continue


def parse_capabilities() -> tuple[list[dict], frozenset[str]]:
    text = (ROOT / "app" / "experimental" / "capabilities.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{'id': '([^']+)', 'title': '([^']+)', 'mode': '([^']+)', 'flag': ([^,]+), "
        r"'dependencies': \[([^\]]*)\], 'wave': (\d+), 'model_requirement': '([^']+)', "
        r"'network_requirement': '([^']+)'"
    )
    rows = []
    for match in pattern.finditer(text):
        deps_raw = match.group(5).strip()
        deps = [item.strip().strip("'") for item in deps_raw.split(",") if item.strip()]
        rows.append(
            {
                "id": match.group(1),
                "title": match.group(2),
                "mode": match.group(3),
                "flag": None if match.group(4).strip() == "None" else match.group(4).strip().strip("'"),
                "dependencies": deps,
                "wave": int(match.group(6)),
                "model_requirement": match.group(7),
                "network_requirement": match.group(8),
            }
        )
    integrated = frozenset(re.findall(r"'([A-Z][0-9]{2})'", re.search(r"INTEGRATED_PACKAGES = frozenset\(\{([^}]*)\}\)", text).group(1)))
    return rows, integrated


def load_evidence() -> dict:
    if not EVIDENCE.exists():
        return {}
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def row(**kwargs) -> dict:
    base = {
        "id": "",
        "group": "",
        "title": "",
        "user_behavior_must": "",
        "authority_owner": "",
        "existing_source_interfaces": [],
        "gap_type": "PLANNED",
        "data_api_contract": "",
        "identity_permission_source_rules": "",
        "dependencies": [],
        "test_layers": [],
        "test_command": "",
        "input_sample": "",
        "expected_result": "",
        "actual_result": "NOT_RUN in this baseline round.",
        "evidence_path": None,
        "code_sha": TESTED_BASELINE_SHA,
        "status": "PLANNED",
        "test_result": "NOT_RUN",
        "release_blocking": "HIGH",
        "notes": "",
    }
    base.update(kwargs)
    missing = [field for field in ("id", "group", "title", "user_behavior_must", "authority_owner") if not base[field]]
    if missing:
        raise ValueError(f"row missing mandatory fields {missing}: {base}")
    return base


# ---------------------------------------------------------------------------
# Original Master Roadmap release-required items (V2-*)
# ---------------------------------------------------------------------------
AUTH = "domain.read / domain.write / domain.review checked against project incarnation, scope, actor/session, branch authority"
ORIGINAL = [
    row(id="V2-M0", group="ORIGINAL_V2", title="M0 current-state audit, frozen compatibility and baseline pin",
        user_behavior_must="Before any feature work, fetch the real remote HEAD/PRs, compare roadmap to source, classify EXISTS/PARTIAL/MISSING/BLOCKED, keep V1 manifest/RC1/user data unchanged and record real CI capacity status.",
        authority_owner="Engineering baseline documents + git/remote state (no product owner)",
        existing_source_interfaces=["docs/v2/engineering/BASELINE_20261019_r1.md", "V2_ADVANCED_CAPABILITY_GAP_REPORT.md", "docs/v2/README.md"],
        gap_type="NONE", release_blocking="NONE",
        data_api_contract="Read-only audit; no product API change.",
        identity_permission_source_rules="Read-only; no credentials copied.",
        dependencies=[], test_layers=["MANUAL"],
        test_command="gh pr view 47/48; git fetch; git rev-list; read-only source audit",
        input_sample="Live repository at a072cf90 + origin/main fed2404c + PR #47/#48",
        expected_result="Baseline facts recorded as actual repository state, not historical claims.",
        status="IMPLEMENTED", test_result="PASS",
        actual_result="This round: remote fetched; origin/main=fed2404c; PR #47 (feature/v2-narrative-platform) Draft MERGEABLE, PR #48 CONFLICTING; archive branch verified artifact-only.",
        evidence_path="docs/v2/engineering/BASELINE_20261019_r1.md",
        notes="Archive branch origin/archive/verified-studio-v2-... adds artifacts/ only: verified by diff-name filtering; no source delta."),
    row(id="V2-M1", group="ORIGINAL_V2", title="M1 Project intent, storage and asset core",
        user_behavior_must="Independent project intent/workspace presets (non-binding), standalone asset IDs/versions/license/source index, no-model editable project, external file import/save/find/export and cross-project isolation.",
        authority_owner="Existing V1.X project/chapter owners + AssetLibraryService + settings/storage managers",
        existing_source_interfaces=["app/services/asset_library_service.py", "app/asset_lifecycle_api.py", "app/config.py", "tests/test_asset_library.py", "tests/test_independent_media_job*"],
        gap_type="PARTIAL",
        data_api_contract="Asset revisions are content-addressed and versioned; project data under NOVEL_DATA_PATH; storage categories separated from model/cache/export paths.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M0"], test_layers=["UNIT", "API", "INTEGRATION", "POSTGRES"],
        test_command="python -m pytest -q tests/test_asset_library.py tests/test_asset_lifecycle_r2.py tests/test_media_library*.py",
        input_sample="Synthetic isolated File project with imported real PNG/WAV fixtures.",
        expected_result="Import/save/reopen/find/export asset works; cross-project read denied; no model needed.",
        release_blocking="HIGH"),
    row(id="V2-M2", group="ORIGINAL_V2", title="M2 Creative Graph engine and usable canvas",
        user_behavior_must="Typed node registry/ports, graph save/restore, partial execution, review nodes, caching, Job Manager integration, model capability constraints, canvas keyboard/large-graph usability; graph complete without Director node.",
        authority_owner=("app/creative/graph.py + graph_models.py + graph_api.py + graph_execution.py + WorkflowRun/JobManager"),
        existing_source_interfaces=["app/creative/graph.py", "app/creative/graph_api.py", "app/creative/graph_execution.py", "frontend/src/creative", "tests/test_v2_creative_workflows.py"],
        gap_type="PARTIAL",
        data_api_contract="Graph schema 1 unchanged; model node promotes schema 2 with explicit review gate; invalid edges/cycles rejected; node deletion preserves reviewed assets.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M1"], test_layers=["UNIT", "API", "INTEGRATION", "BROWSER"],
        test_command="python -m pytest -q tests/test_v2_creative_workflows.py tests/test_creative_graph*.py",
        input_sample="Blank synthetic project with a local typed graph.",
        expected_result="Save/reload graph, execute local nodes, reject malformed edges, never call model without explicit gate.",
        release_blocking="HIGH"),
    row(id="V2-M3", group="ORIGINAL_V2", title="M3 Model Center local-first onboarding and optional API",
        user_behavior_must="Bounded trusted scan, reuse installed models, duplicate detection, zero manual port entry for trusted local services, model-missing editing remains available, API provider contract behind explicit consent and budget.",
        authority_owner="app/model_center/* + provider registry/broker; release_readiness",
        existing_source_interfaces=["app/model_center/", "app/experimental/model_broker.py", "app/release_readiness.py", "tests/test_local_ai_environment_v2.py", "tests/test_model_center*.py"],
        gap_type="PARTIAL",
        data_api_contract="Discovery is read-only bounded metadata; no execution authority from discovery; provider dispatch needs explicit route/budget/consent.",
        identity_permission_source_rules="Host-session protected API; credentials in vault; no keys in responses/logs. " + AUTH,
        dependencies=["V2-M1"], test_layers=["UNIT", "API", "INTEGRATION", "MANUAL"],
        test_command="python -m pytest -q tests/test_local_ai_environment_v2.py tests/test_r4_local_ai_inspection.py",
        input_sample="Isolated profile with no model installed; synthetic GGUF headers.",
        expected_result="Reports what was discovered vs verified; never starts runtime; editing works without model.",
        release_blocking="HIGH"),
    row(id="V2-M4", group="ORIGINAL_V2", title="M4 Text, screenplay, adaptation and creative agents",
        user_behavior_must="Keep all V1 long-form writing; novel→screenplay adaptation agent/skill, independent screenplay documents, review, format export; generic text assets usable without Graph.",
        authority_owner="V1.X novel/chapter owner + CreativeService screenplay documents + adaptation receipts",
        existing_source_interfaces=["app/creative/adaptation*.py", "app/creative/screenplay_export.py", "app/creative/prompt_authoring.py", "frontend/src/creative", "tests/test_r4_*.py"],
        gap_type="PARTIAL",
        data_api_contract="Screenplay/adaptation documents are versioned via CreativeService CAS; source versions pinned; export formats (TXT/Fountain/EPUB) deterministic.",
        identity_permission_source_rules=AUTH + "; source privacy/egress review bound to exact chapter version+digest",
        dependencies=["V2-M1", "V2-M3"], test_layers=["UNIT", "API", "INTEGRATION", "BROWSER"],
        test_command="python -m pytest -q tests/test_v2_screenplay_export.py tests/test_screenplay_*.py tests/test_r4_revision_*.py",
        input_sample="Synthetic short novel with two chapters; adaptation run without paid model.",
        expected_result="Adaptation/screenplay saves with exact source evidence; original novel unchanged; exports readable.",
        release_blocking="HIGH"),
    row(id="V2-M5", group="ORIGINAL_V2", title="M5 Image Studio visual generation and real adapter",
        user_behavior_must="Image canvas, generate/edit/reference/character/scene/style/layer-mask interfaces, history/output, installed ComfyUI/local model or optional API, asset version propagation and license provenance.",
        authority_owner="Image services (studio_image_*), AssetLibraryService, provider registry",
        existing_source_interfaces=["app/services/studio_image_execution.py", "app/services/studio_image_mask_authoring.py", "app/services/studio_image_cutout.py", "frontend/src/image*", "tests/test_v2_creative_workflows.py"],
        gap_type="PARTIAL",
        data_api_contract="Image provider dispatch only through configured original adapters; output asset records exact source versions and provider/runtime evidence.",
        identity_permission_source_rules=AUTH + "; no cloud dispatch without explicit consent",
        dependencies=["V2-M1", "V2-M3"], test_layers=["UNIT", "API", "INTEGRATION", "MEDIA", "MANUAL"],
        test_command="python -m pytest -q tests/test_r4_registered_local_media.py tests/test_r2_media_api.py",
        input_sample="Imported PNG + synthetic provider stub for contract; real model NOT run.",
        expected_result="Image asset lifecycle and deterministic CPU edits verified; model generation explicitly NOT_RUN.",
        release_blocking="HIGH"),
    row(id="V2-M6", group="ORIGINAL_V2", title="M6 Director and Storyboard specialization",
        user_behavior_must="Director console multi-objective planning with human review; shot language/action/order; Shot List/Shot Board/storyboard canvas with image/video/3D reference; shots sourced without requiring a screenplay.",
        authority_owner="DirectorService + storyboard document owners + CreativeService",
        existing_source_interfaces=["app/experimental/director.py", "app/creative/director_workspace.py", "app/creative/storyboard.py", "frontend/src/director", "tests/test_v2_director_workspace.py"],
        gap_type="PARTIAL",
        data_api_contract="Director notes/storyboard are typed documents with CAS; shot references pin source versions; camera language is evidence-backed text, not rendered video.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M2", "V2-M4"], test_layers=["UNIT", "API", "INTEGRATION", "BROWSER"],
        test_command="python -m pytest -q tests/test_v2_director_workspace.py tests/test_r4_director*.py",
        input_sample="Existing image or shot card as storyboard start.",
        expected_result="Director/storyboard documents save, reopen and keep provenance; director node removable without breaking independent images.",
        release_blocking="HIGH"),
    row(id="V2-M7", group="ORIGINAL_V2", title="M7 Video Studio, previs and reference control",
        user_behavior_must="T2V/I2V/V2V only as capability allows, typed reference image/video/previs/camera/depth/pose, local/authorized async adapters, queue/resource limits, preview and media storage; grey-model video vs true 3D camera clearly distinguished.",
        authority_owner="Video execution/assembly services + model registry + media validator",
        existing_source_interfaces=["app/services/studio_video_execution.py", "app/services/video_assembly_service.py", "frontend/src/video*", "tests/test_v2_video_runtime_foundation.py"],
        gap_type="PARTIAL",
        data_api_contract="Unsupported reference controls fail closed; produced video assets record provider/runtime evidence; no ref-control success claim without real output.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M3", "V2-M6"], test_layers=["UNIT", "API", "INTEGRATION", "MEDIA", "MANUAL"],
        test_command="python -m pytest -q tests/test_v2_video_runtime_foundation.py tests/test_v2_graph_video_foundation.py",
        input_sample="Synthetic image + explicit unavailable provider state.",
        expected_result="Video planning/foundation contract passes; real generation reported NOT_RUN/LOCAL_REQUIRED.",
        release_blocking="HIGH"),
    row(id="V2-M8", group="ORIGINAL_V2", title="M8 Audio Studio (TTS/voice/ASR/SFX/music)",
        user_behavior_must="Standalone audio: one sentence text→speech without a text project, voice profiles, ASR, basic editing/SFX/BGM assets, waveforms, independent export and timecode links without corrupting sources.",
        authority_owner="AudiobookService + audio execution/mix owners + asset library",
        existing_source_interfaces=["app/audio_production_store.py", "app/services/audiobook_service.py", "app/services/studio_audio_execution.py", "app/experimental/subtitle_timeline.py", "tests/test_v2_audio_editing_pipeline.py"],
        gap_type="PARTIAL",
        data_api_contract="Audio tasks/captions versioned; real PCM/FFmpeg mixdown verified by independent parser; ASR/TTS model adapters NOT_CONFIGURED unless injected.",
        identity_permission_source_rules=AUTH + "; voice authorization evidence required for cloned voices",
        dependencies=["V2-M1", "V2-M3"], test_layers=["UNIT", "API", "INTEGRATION", "MEDIA"],
        test_command="python -m pytest -q tests/test_v2_audio_editing_pipeline.py tests/test_r5_voice_subtitles.py tests/test_r5_pause_aware_audio.py",
        input_sample="Synthetic WAV tone + caption fixture.",
        expected_result="Real CPU editing/trim/mix and subtitle processing produce verifiable artifacts; model synthesis NOT_RUN.",
        release_blocking="HIGH"),
    row(id="V2-M9", group="ORIGINAL_V2", title="M9 Editing Studio real multi-track NLE",
        user_behavior_must="Independent video/audio/subtitle tracks, drag, in/out points, split/transition, volume, subtitles, preview cache, real FFmpeg composition into a reopenable project exporting a complete video; audio/video sync and offline-media behavior reproducible.",
        authority_owner="studio_timeline_* owners + export snapshot authority",
        existing_source_interfaces=["app/services/studio_timeline_edit.py", "app/services/studio_timeline_render.py", "app/services/studio_timeline_exchange.py", "frontend/src/nle", "tests/test_phase4_timeline.py"],
        gap_type="PARTIAL",
        data_api_contract="Timeline documents versioned; render jobs are normal jobs; output MP4/WebM verified by ffprobe; OTIO/SRT/VTT loss reported.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M8"], test_layers=["UNIT", "API", "INTEGRATION", "MEDIA", "BROWSER"],
        test_command="python -m pytest -q tests/test_phase4_timeline.py tests/test_r4_timeline_exchange.py",
        input_sample="Two external synthetic video clips + one audio clip.",
        expected_result="Timeline reopens; real render produces playable artifact with expected streams; offline media explicit.",
        release_blocking="HIGH"),
    row(id="V2-M10", group="ORIGINAL_V2", title="M10 3D reference, research, publishing and QingJian integration",
        user_behavior_must="Lightweight 3D assets and camera/grey-model reference handoff, project research sources/licensing/citations, delivery manifest; QingJian Tutor slot/context/advice adapter over Local Interop v1; interop cannot read unauthorized project content; missing QingJian does not block work.",
        authority_owner="Local interop owners + research library + export/delivery; 3D reference owner still missing",
        existing_source_interfaces=["app/local_interop/", "contracts/local-interop/v1/", "app/experimental/research_library.py", "app/experimental/offline_sync.py", "tests/test_local_interop*.py"],
        gap_type="PARTIAL",
        data_api_contract="Interop keeps stable v1 IDs; research sources carry license/citation; delivery manifest lists versions/digests; 3D exchange is NOT implemented.",
        identity_permission_source_rules="Consult the interop contracts: explicit session/permission grants; no shared global token. " + AUTH,
        dependencies=["V2-M1", "V2-M9"], test_layers=["UNIT", "API", "INTEGRATION", "MANUAL"],
        test_command="python -m pytest -q tests/test_post_interop_wave3_research.py tests/test_r5_offline_sync.py",
        input_sample="Synthetic project + interop peer fixture.",
        expected_result="Research/interop contracts pass; 3D reference and full QingJian product acceptance remain PLANNED/blocked.",
        release_blocking="MEDIUM"),
    row(id="V2-M11", group="ORIGINAL_V2", title="M11 Cross-module journeys, performance and full regression",
        user_behavior_must="Five independent journeys and combined paths (no hard-coded novel→video prerequisite); drag/asset replacement/cache reclaim/NLE latency/async queue/model offline/conflict/revocation/crash recovery; complete matrix and API/UI/test comparison at a frozen SHA.",
        authority_owner="Integration-level verification across existing owners (no new module)",
        existing_source_interfaces=["tests/", ".github/ci/coverage_manifest_v2.json.gz", "scripts/run_v2_checks.py", "tests/test_v2_studio_ci.py", "docs/delivery/functional-surface-freeze/"],
        gap_type="PARTIAL",
        data_api_contract="No new contract; this gate proves the existing ones compose.",
        identity_permission_source_rules="Each journey keeps its owner's authorization rules.",
        dependencies=["V2-M4", "V2-M5", "V2-M6", "V2-M7", "V2-M8", "V2-M9"], test_layers=["INTEGRATION", "BROWSER", "MEDIA", "MANUAL"],
        test_command="python -m pytest -q (full File suite) + frontend + browser journeys",
        input_sample="Multiple isolated sample projects, no user data.",
        expected_result="Complete suite PASS or exact environment evidence; unverified model quality never PASS.",
        release_blocking="HIGH"),
    row(id="V2-M12", group="ORIGINAL_V2", title="M12 Windows final acceptance (user-authorized)",
        user_behavior_must="On Windows 11 + RTX 5080 16GB + 64GB: real install/upgrade/uninstall, first-run scan, reuse existing models/ComfyUI, full studio chain, security exit; 8/12/16GB VRAM constraints addressed; no user data in public repo; IME/high-DPI/interop results recorded separately.",
        authority_owner="User + released package; not a cloud/automated run",
        existing_source_interfaces=["AI_NOVEL_STUDIO_V2_WINDOWS_ACCEPTANCE_PLAN.md", "docs/desktop_host_acceptance_checklist.md", "AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md"],
        gap_type="BLOCKED",
        data_api_contract="Acceptance binds explicit package SHA256 and file hashes.",
        identity_permission_source_rules="User-authorized local only.",
        dependencies=["V2-M11"], test_layers=["WINDOWS", "MANUAL", "MEDIA"],
        test_command="user-executed Windows acceptance; NOT a CI command",
        input_sample="Released candidate package on the user's machine.",
        expected_result="User-signed acceptance report bound to package hashes; this baseline does not run it.",
        status="BLOCKED", test_result="NOT_RUN", release_blocking="HIGH",
        actual_result="NOT_RUN: requires user authorization and a release candidate; developer-machine build is not acceptance.",
        notes="LOCAL_REQUIRED."),
    # ---- cross-cutting original V2 requirements ----
    row(id="V2-X01", group="ORIGINAL_V2", title="Single authoritative data source (no parallel owners)",
        user_behavior_must="Every domain has exactly one authority; V2 work extends the existing owner instead of creating a second Project/Asset/Job/Provider/Model Center/Timeline/QingJian registry.",
        authority_owner="Owner map in EXECUTION_AND_DATA_CONTRACTS.md section 1",
        existing_source_interfaces=["docs/v2/engineering/EXECUTION_AND_DATA_CONTRACTS.md", "app/jobs.py", "app/services/asset_library_service.py", "app/creative/service.py"],
        gap_type="NONE",
        data_api_contract="CAS/versioned writes through the owning service; no generic write API.",
        identity_permission_source_rules=AUTH,
        dependencies=[], test_layers=["MANUAL", "UNIT"],
        test_command="owner map review + targeted owner tests",
        input_sample="Source tree at tested SHA.",
        expected_result="No duplicated authority introduced by this round.",
        status="IMPLEMENTED", test_result="PASS",
        actual_result="This round added documentation/test tooling only; no new authority module was introduced.",
        evidence_path="docs/v2/engineering/EXECUTION_AND_DATA_CONTRACTS.md", release_blocking="HIGH"),
    row(id="V2-X02", group="ORIGINAL_V2", title="Project permission, scope and branch isolation",
        user_behavior_must="Every read/write is scope/actor/branch checked; cross-project and revoked access fail closed; collaboration conflict/revocation behavior preserved.",
        authority_owner="Authorization + collaboration scope owners",
        existing_source_interfaces=["app/authorization.py", "app/services/collaboration_scope_service.py", "tests/test_authorization*.py", "tests/test_collaboration_scope*.py"],
        gap_type="NONE",
        data_api_contract="Trusted session token + project/branch headers; no client-supplied scope expansion.",
        identity_permission_source_rules=AUTH,
        dependencies=[], test_layers=["UNIT", "API", "INTEGRATION", "POSTGRES"],
        test_command="python -m pytest -q tests/test_authorization*.py tests/test_collaboration_scope*.py",
        input_sample="Two synthetic actors/projects.",
        expected_result="Cross-project/revoked access denied; audit fields intact.",
        release_blocking="HIGH"),
    row(id="V2-X03", group="ORIGINAL_V2", title="Migration, backup, restore and upgrade compatibility",
        user_behavior_must="Schema changes are ordered migrations; existing projects upgrade with readback verification; backup/restore and rollback are repeatable; no ad-hoc table creation.",
        authority_owner="database/migrations + scripts/backup.ps1 + scripts/restore.ps1 + scripts/migrate.ps1",
        existing_source_interfaces=["database/migrations/", "scripts/backup.ps1", "scripts/restore.ps1", "docs/backup_restore.md", "tests/test_migration*.py"],
        gap_type="PARTIAL",
        data_api_contract="Migrations 001-020 append-only; PostgreSQL/File parity tests exist.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M1"], test_layers=["INTEGRATION", "POSTGRES"],
        test_command="python -m pytest -q tests/test_migration*.py tests/test_backup_restore*.py",
        input_sample="Fresh isolated database + synthetic project backup.",
        expected_result="Upgrade/newer-project readback works; restore reproduces project; no data loss.",
        release_blocking="HIGH"),
    row(id="V2-X04", group="ORIGINAL_V2", title="Asset CAS, source provenance and review",
        user_behavior_must="Immutable asset bytes, content digests, exact source version pinning, lineage relations, human review state, stale detection and soft delete.",
        authority_owner="AssetLibraryService + review owners",
        existing_source_interfaces=["app/services/asset_library_service.py", "app/asset_lifecycle_api.py", "app/review.py", "tests/test_asset_lifecycle_r2.py"],
        gap_type="NONE", data_api_contract="Content-addressed immutable bytes + CAS metadata revisions; review bound to digest.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M1"], test_layers=["UNIT", "API", "INTEGRATION", "POSTGRES"],
        test_command="python -m pytest -q tests/test_asset_lifecycle_r2.py tests/test_asset_library.py",
        input_sample="Synthetic PNG/WAV/MP4 imports.",
        expected_result="Version bump requires CAS; stale derived assets flagged; delete is soft.",
        release_blocking="HIGH"),
    row(id="V2-X05", group="ORIGINAL_V2", title="Job state machine, cancellation, UNKNOWN and idempotency",
        user_behavior_must="One queue; explicit states including CANCEL_REQUESTED/CANCELLED/BLOCKED/UNKNOWN_UPSTREAM; cooperative cancel without duplicate paid calls; idempotent retry; no automatic replay; restart recovery explicit.",
        authority_owner="app/jobs.py JobManager + generation settlement hooks",
        existing_source_interfaces=["app/jobs.py", "app/model_execution.py", "tests/test_generation*.py", "tests/test_v2_independent_media_job.py"],
        gap_type="PARTIAL",
        data_api_contract="Job records persist actor/inputs/route/receipt; terminal hook + ledger settlement before output acceptance.",
        identity_permission_source_rules=AUTH,
        dependencies=["V2-M2"], test_layers=["UNIT", "API", "INTEGRATION", "POSTGRES"],
        test_command="python -m pytest -q tests/test_generation_idempotency*.py tests/test_job*.py",
        input_sample="Synthetic jobs with duplicate submissions and interrupted worker.",
        expected_result="Duplicate key reuses job; unknown state never replays; cancel/late output discarded.",
        release_blocking="HIGH"),
    row(id="V2-X06", group="ORIGINAL_V2", title="Model discovery, capability admission and resource budgets",
        user_behavior_must="Capability-based admission, no execution from discovery, price/license/budget checks, bounded resource use and release, honest NOT_RUN when unverified.",
        authority_owner="Model Center + model broker + host hardware inventory",
        existing_source_interfaces=["app/model_center/", "app/experimental/model_broker.py", "app/provider_runtime_v2_*", "tests/test_r4_model_broker.py"],
        gap_type="PARTIAL", data_api_contract="Route/preview/admission receipts; no client-supplied endpoint/credential.",
        identity_permission_source_rules="Host authority + vault; explicit consent for paid/cloud.",
        dependencies=["V2-M3"], test_layers=["UNIT", "API", "INTEGRATION"],
        test_command="python -m pytest -q tests/test_r4_model_broker.py tests/test_post_interop_wave3_broker.py",
        input_sample="Synthetic provider/model records; no paid call.",
        expected_result="Broker/environment contracts pass; real GPU inference NOT_RUN.",
        release_blocking="HIGH"),
    row(id="V2-X07", group="ORIGINAL_V2", title="No-model mode and graceful degradation",
        user_behavior_must="With no model/network the app still starts, opens projects, edits/saves/reopens and exports existing content; model-dependent actions show actionable unavailable states.",
        authority_owner="Existing settings/feature flags + UI error states",
        existing_source_interfaces=["app/config.py", "frontend/src/", "tests/test_*error*.py", "tests/test_local_ai_environment_v2.py"],
        gap_type="NONE", data_api_contract="Capability state reported by server; disabled features fail closed with codes.",
        identity_permission_source_rules=AUTH,
        dependencies=[], test_layers=["UNIT", "API", "INTEGRATION"],
        test_command="python -m pytest -q tests/test_local_ai_environment_v2.py tests/test_v2_media_prerequisites.py",
        input_sample="Isolated profile with MOCK_PROVIDER/ENABLE_CLOUD off, no runtime.",
        expected_result="Editing and existing-content operations succeed; unavailable features are explicit.",
        release_blocking="HIGH"),
    row(id="V2-X08", group="ORIGINAL_V2", title="Privacy, consent and secure egress",
        user_behavior_must="Privacy levels fail closed (LOCAL_ONLY/REDACT_BEFORE_CLOUD/CLOUD_ALLOWED); chapter egress consent is version/digest/branch bound; outbound host allowlist; secrets in vault; no sensitive data in logs.",
        authority_owner="app/privacy.py + app/source_privacy.py + app/net_safety.py + credential vault",
        existing_source_interfaces=["app/privacy.py", "app/source_privacy.py", "app/net_safety.py", "tests/test_source_privacy*.py", "tests/test_privacy*.py"],
        gap_type="PARTIAL", data_api_contract="Cloud context builders merge strictest privacy; unknown policy = LOCAL_ONLY.",
        identity_permission_source_rules="Consent is separate from credential configuration. " + AUTH,
        dependencies=["V2-M3"], test_layers=["UNIT", "API", "INTEGRATION"],
        test_command="python -m pytest -q tests/test_privacy*.py tests/test_source_privacy*.py tests/test_net_safety*.py",
        input_sample="Protected chapter fixture + hostile URLs.",
        expected_result="Egress denied/redacted; URL allowlist enforced; no secret leakage.",
        release_blocking="HIGH"),
    row(id="V2-X09", group="ORIGINAL_V2", title="Public/internal research edition isolation",
        user_behavior_must="Public and internal research versions are separated at the backend, data, runtime-policy and authorization levels, not hidden only in the frontend; internal data never reaches public builds.",
        authority_owner="Not implemented; requires edition manifest + separate backend profile + edition-scoped authz/data root",
        existing_source_interfaces=["app/experimental/flags.py (partial)", "app/packaging/runtime_identity.py (partial)", "app/release_readiness.py (partial)"],
        gap_type="MISSING",
        data_api_contract="Required: edition identity in requests/build, separate data root, edition-scoped authorization, redaction audit. None exists.",
        identity_permission_source_rules="Edition must not be selectable by client input.",
        dependencies=["V2-X07", "V2-X08"], test_layers=["UNIT", "INTEGRATION", "ACCEPTANCE"],
        test_command="NOT_RUN - no implementation",
        input_sample="n/a", expected_result="Public build cannot access internal routes/data; internal build isolated.",
        status="PLANNED", test_result="NOT_RUN", release_blocking="HIGH",
        actual_result="MISSING at a072cf90: flags are runtime opt-ins, not an edition boundary; documented in SECURITY_AND_ISOLATION.md section 6."),
    row(id="V2-X10", group="ORIGINAL_V2", title="UI design-system compliance and shared shell",
        user_behavior_must="All UI work reuses tokens/primitives/AppShell/ModuleWorkspace; no parallel shell; design-token/geometry checks stay green; Chinese input/accessibility preserved.",
        authority_owner="docs/ui/design_system.md + scripts/check_ui_design_tokens.mjs",
        existing_source_interfaces=["docs/ui/design_system.md", "scripts/check_ui_design_tokens.mjs", "frontend/src/ui/tokens.css"],
        gap_type="NONE", data_api_contract="Token source of truth; visual baseline documents.",
        identity_permission_source_rules="n/a",
        dependencies=[], test_layers=["UNIT", "BROWSER"],
        test_command="cd frontend && corepack pnpm lint && corepack pnpm build",
        input_sample="Frontend tree.", expected_result="Design-token lint and build pass; no UI redesign in this round.",
        release_blocking="MEDIUM"),
    row(id="V2-X11", group="ORIGINAL_V2", title="CI truth, hosted evidence and capacity accounting",
        user_behavior_must="Report actual hosted CI conclusions; distinguish no-runner/canceled from assertion failure; never splice runs or delete tests to pass; local baseline must be reproducible.",
        authority_owner=".github/workflows/cloud-ci.yml + .github/ci/*",
        existing_source_interfaces=[".github/workflows/cloud-ci.yml", ".github/ci/", "docs/cloud_ci.md"],
        gap_type="BLOCKED",
        data_api_contract="JUnit receipts bound to SHA; job conclusion authority.",
        identity_permission_source_rules="Read-only CI token; no secrets to jobs.",
        dependencies=[], test_layers=["MANUAL"],
        test_command="gh run list / gh pr checks (hosted CI)",
        input_sample="GitHub Actions hosted runs.",
        expected_result="Hosted result reported truthfully.",
        status="BLOCKED", test_result="BLOCKED", release_blocking="HIGH",
        actual_result="BLOCKED_EXTERNAL: hosted CI runner/account unavailable in this environment; local isolated runs used and labeled local, not CI PASS."),
    row(id="V2-X12", group="ORIGINAL_V2", title="Test isolation, disk budget and cleanup",
        user_behavior_must="Tests run from isolated PROJECT_ROOT/NOVEL_DATA_PATH/profile/temp/database/browser profile; bounded disk; cleanup only self-created data while retaining logs/hashes/evidence; never touch user data/models/RC1.",
        authority_owner="scripts/run_v2_checks.py + runbook isolation contract",
        existing_source_interfaces=["scripts/run_v2_checks.py", "docs/v2/engineering/RUNBOOK.md", "scripts/pytest_temp_isolation.py"],
        gap_type="NONE", data_api_contract="Isolated environment before app import; receipts under docs/delivery/v2-development.",
        identity_permission_source_rules="No production credentials or user data.",
        dependencies=[], test_layers=["MANUAL"],
        test_command="see RUNBOOK section 2 + this round's Engineering-Runs run directory",
        input_sample="Fresh isolated run directory on D:.",
        expected_result="Isolation verified by paths in settings; cleanup recorded.",
        status="IMPLEMENTED", test_result="PASS",
        actual_result="This round used D:/PoemSeed/Engineering-Runs/20261019-r1 for data/tmp/pgdata/logs/evidence; repo working tree kept clean of generated data (see BASELINE).",
        evidence_path="docs/v2/engineering/BASELINE_20261019_r1.md", release_blocking="MEDIUM"),
]

# ---------------------------------------------------------------------------
# DIF-01..DIF-12 (differentiated capabilities)
# ---------------------------------------------------------------------------
DIF = [
    row(id="DIF-01", group="DIF", title="Story Kernel",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1 (not present on disk). Known intent from the instruction: a single authoritative narrative kernel linking story facts, canon, causality and generation boundaries.",
        authority_owner="Candidate reuse: temporal story graph (A04) + character mind (A05) + canon/finding review owners; no dedicated Story Kernel owner exists",
        existing_source_interfaces=["app/experimental/story_graph.py", "app/experimental/change_impact.py", "app/experimental/character_author_context.py", "tests/test_post_interop_scene_mind.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-01. Reusable owner: versioned story-graph/scene-mind documents in ExperimentalStore with scope/CAS.",
        identity_permission_source_rules=AUTH,
        dependencies=["A04", "A05"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_post_interop_scene_mind.py (related owner coverage only)",
        input_sample="Synthetic project with story graph facts.",
        expected_result="A Story Kernel acceptance scenario must be authored once the SPEC is supplied; related owner tests alone cannot accept it.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement text source missing; related A04/A05 owners are IMPLEMENTED/PARTIAL and tested separately."),
    row(id="DIF-02", group="DIF", title="Impact Engine",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: compute and preview the impact of a change across story, assets, tasks and downstream artifacts before applying it.",
        authority_owner="Candidate reuse: U06 change impact and selective refresh; asset lineage (A09); production manifest (A13)",
        existing_source_interfaces=["app/experimental/change_impact.py", "app/experimental/change_impact_api.py", "tests/test_r4_change_impact.py", "tests/test_r4_change_impact_mounted.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-02. Reusable owner: change-impact preview over pinned versions/lineage, no direct mutation.",
        identity_permission_source_rules=AUTH,
        dependencies=["A04", "A09", "U06"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r4_change_impact.py tests/test_r4_change_impact_mounted.py (related owner coverage only)",
        input_sample="Synthetic change set over versioned documents.",
        expected_result="DIF-02 acceptance scenario required; existing impact preview tests are not a DIF-02 acceptance.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; related U06 owner is implemented and contract-tested."),
    row(id="DIF-03", group="DIF", title="Identity Studio",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: authoritative character identity/appearance consistency across text and visual stages.",
        authority_owner="Candidate reuse: character knowledge and mind state (A05), visual identity/embeddings, asset appearance references, Character/Scene Bible",
        existing_source_interfaces=["app/experimental/visual_identity.py", "app/experimental/embeddings.py", "app/experimental/bible_api.py", "app/repositories/file/identity.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-03. Reusable owners: bible/character documents and approved appearance asset references.",
        identity_permission_source_rules=AUTH,
        dependencies=["A05", "A09"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_round2_bible.py tests/test_post_interop_embedding_feature_isolation.py (related owner coverage only)",
        input_sample="Synthetic character bible + reference image.",
        expected_result="DIF-03 acceptance requires a defined identity contract and cross-stage consistency scenario.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; character/bible/embedding owners exist but no Identity Studio acceptance."),
    row(id="DIF-04", group="DIF", title="Semantic Rebuild",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: rebuild a derived artifact from its exact semantic sources after an upstream change, preserving provenance and review.",
        authority_owner="Candidate reuse: revision intelligence (A11), selection assistant (U05), change impact (U06), asset lineage",
        existing_source_interfaces=["app/experimental/revision_intelligence.py", "app/experimental/revision_intelligence_api.py", "app/experimental/selection_assistant*.py", "tests/test_post_interop_revision_model.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-04. Reusable owners: CAS revision proposals and partial accept flows.",
        identity_permission_source_rules=AUTH,
        dependencies=["A11", "U05", "U06"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_post_interop_revision_model.py tests/test_post_interop_revision_compare.py (related owner coverage only)",
        input_sample="Synthetic revision proposal set.",
        expected_result="DIF-04 needs a rebuild scenario (source change -> semantic diff -> rebuild -> review) before acceptance.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; related revision-intelligence owner implemented contract-level."),
    row(id="DIF-05", group="DIF", title="Scene Twin",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: a scene-level simulation/twin of alternative staging or outcomes for directing/storyboarding decisions.",
        authority_owner="Candidate reuse: bounded story simulation (A01), Director workspace, storyboard; no dedicated Scene Twin owner",
        existing_source_interfaces=["app/experimental/story_simulator.py", "app/creative/director_workspace.py", "tests/test_r4_*"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-05. No owner guarantees a scene-twin comparison artifact.",
        identity_permission_source_rules=AUTH,
        dependencies=["A01", "A08"], test_layers=["UNIT", "API"],
        test_command="NOT_RUN - no DIF-05 scenario exists",
        input_sample="n/a",
        expected_result="Requires a authored Scene Twin scenario and owner; simulation owner is not a twin acceptance.",
        release_blocking="HIGH",
        actual_result="PLANNED: no DIF-05 implementation or acceptance; A01 simulator is a different bounded capability."),
    row(id="DIF-06", group="DIF", title="Performance Director",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: guide performance/emotion/pacing across scenes with evidence-linked direction notes.",
        authority_owner="Candidate reuse: camera grammar and scene direction (A08/ai_director_v2), Director notes, voice direction (B03)",
        existing_source_interfaces=["app/creative/camera_language.py", "app/creative/director_intent.py", "app/experimental/director.py", "frontend/src/director"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-06. Existing director notes are typed CAS documents.",
        identity_permission_source_rules=AUTH,
        dependencies=["A08", "B03"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_v2_director_workspace.py tests/test_r4_director.py (related owner coverage only)",
        input_sample="Synthetic scene + director notes.",
        expected_result="DIF-06 acceptance requires a defined performance-direction scenario; camera grammar is not sufficient.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; A08 owner exists contract-level."),
    row(id="DIF-07", group="DIF", title="Studio QA",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: cross-stage quality assurance with evidence, findings, review and regression against the project's own canon/style.",
        authority_owner="Candidate reuse: evidence-based narrative judge (A03), reader preflight (U11), safe batch preflight (U16), finding review",
        existing_source_interfaces=["app/experimental/narrative_judge.py", "app/experimental/reader_preflight.py", "app/experimental/safe_batches.py", "app/services/finding_review_service.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-07. Existing finding/review owners keep exact source+digest.",
        identity_permission_source_rules=AUTH + "; review requires domain.review",
        dependencies=["A03", "U11", "U16"], test_layers=["UNIT", "API", "INTEGRATION"],
        test_command="python -m pytest -q tests/test_post_interop_style_judge.py tests/test_r4_portable_batches.py (related owner coverage only)",
        input_sample="Synthetic manuscript with known issues.",
        expected_result="DIF-07 needs an end-to-end QA scenario; related judges/preflight are inputs, not acceptance.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; related owners exist contract-level."),
    row(id="DIF-08", group="DIF", title="Model Lab",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: benchmark/compare local models and routes with real evidence, resource measurement and honest quality statements.",
        authority_owner="Candidate reuse: explainable model broker (A06) + model benchmark (A07) + Model Center discovery",
        existing_source_interfaces=["app/experimental/model_benchmark.py", "app/experimental/model_benchmark_api.py", "app/experimental/model_broker.py", "tests/test_post_interop_wave3_broker.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-08. Reusable broker/benchmark receipts store route/model/resource evidence.",
        identity_permission_source_rules="Explicit local/authorized routes only; no paid API without consent. " + AUTH,
        dependencies=["A06", "A07"], test_layers=["UNIT", "API", "MANUAL"],
        test_command="python -m pytest -q tests/test_r4_model_broker.py tests/test_post_interop_wave3_broker.py (related owner coverage only)",
        input_sample="Synthetic routes; real inference NOT_RUN.",
        expected_result="DIF-08 acceptance requires real benchmark runs on defined models; contract tests do not qualify as quality evidence.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; no real model benchmark executed (no authorized model)."),
    row(id="DIF-09", group="DIF", title="Style DNA",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: extract, store and enforce a project/style fingerprint used for consistency and drift detection.",
        authority_owner="Candidate reuse: A02 style metrics and drift (style_dna_v2), embeddings, style analysis",
        existing_source_interfaces=["app/experimental/style_analysis.py", "app/experimental/style_analysis_api.py", "tests/test_post_interop_style_model.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-09. Reusable owner: versioned style metrics/drift records.",
        identity_permission_source_rules=AUTH,
        dependencies=["A02"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_post_interop_style_model.py tests/test_post_interop_style_judge.py (related owner coverage only)",
        input_sample="Synthetic two-style text corpus.",
        expected_result="DIF-09 acceptance needs defined metric thresholds and drift scenarios; owner tests stop short.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; A02 style owner implemented contract-level."),
    row(id="DIF-10", group="DIF", title="Storyverse",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: shared-universe/multi-story world model with cross-story canon links and fork/merge safety.",
        authority_owner="Candidate reuse: shared-universe snapshots/pins, project forks (B09), temporal story graph (A04), offline sync (B10)",
        existing_source_interfaces=["app/experimental/story_graph.py", "app/experimental/project_forks.py", "app/experimental/structured_forks.py", "tests/test_post_interop_shared_universe.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-10. Existing forks/universe snapshots are versioned CAS documents.",
        identity_permission_source_rules=AUTH,
        dependencies=["A04", "B09", "B10"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_post_interop_shared_universe.py tests/test_r5_project_forks.py (related owner coverage only)",
        input_sample="Two synthetic stories sharing a universe.",
        expected_result="DIF-10 acceptance scenario required; shared-universe snapshot owner is smaller in scope.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; related universe/fork owners exist."),
    row(id="DIF-11", group="DIF", title="Audience Lab",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: simulate/measure audience reaction or reader experience to guide revision priorities.",
        authority_owner="Candidate reuse: reader preflight (U11), writer room (B08), reader sessions",
        existing_source_interfaces=["app/experimental/reader_preflight.py", "app/experimental/reader_sources.py", "app/experimental/teams.py", "tests/test_r4_reader_sessions.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-11. No audience model owner; reader preflight is deterministic/local checks.",
        identity_permission_source_rules=AUTH,
        dependencies=["U11", "B08"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r4_reader_sessions.py tests/test_r5_writer_room_mounted.py (related owner coverage only)",
        input_sample="n/a",
        expected_result="DIF-11 needs an audience definition; reader preflight is not an audience lab.",
        release_blocking="HIGH",
        actual_result="PLANNED: no audience-lab implementation."),
    row(id="DIF-12", group="DIF", title="Production Passport",
        user_behavior_must="SOURCE_MISSING: acceptance MUST text is defined by SPEC-2026.10.19-r1. Known intent: a portable, verifiable production passport for an artifact/project: sources, routes, reviews, rights and hashes across stages.",
        authority_owner="Candidate reuse: production manifest and controlled replay (A13), asset lineage (A09), portable project (U14), export snapshot authority",
        existing_source_interfaces=["app/experimental/production_lineage.py", "app/creative/production_contracts.py", "app/services/export_snapshot_authority.py", "app/experimental/portable_projects.py"],
        gap_type="SOURCE_MISSING",
        data_api_contract="Not defined for DIF-12. Existing lineage/manifest receipts are internal provenance, not a passport format.",
        identity_permission_source_rules=AUTH,
        dependencies=["A09", "A13", "U14"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r4_production_lineage.py tests/test_r4_portable_batches.py (related owner coverage only)",
        input_sample="Synthetic project with derived artifacts.",
        expected_result="DIF-12 requires a defined passport schema/verification; lineage is a prerequisite, not the passport.",
        release_blocking="HIGH",
        actual_result="PLANNED: requirement source missing; internal provenance owners exist."),
]

# ---------------------------------------------------------------------------
# IMAGE-COMIC-01..20
# ---------------------------------------------------------------------------
COMIC = [
    row(id="IMAGE-COMIC-01", group="IMAGE_COMIC", title="Comic sub-entry (Image Studio child)",
        user_behavior_must="Comic creation is a child feature of Image Studio (not a new top-level module), with a real entry from the existing workbench and the same project/asset system.",
        authority_owner="frontend ExperimentalWorkbench + app/experimental/comic_layouts*",
        existing_source_interfaces=["frontend/src/experimental/ExperimentalWorkbench.tsx", "app/experimental/comic_layouts_api.py", "tests/test_r5_comic_mounted.py"],
        gap_type="NONE", data_api_contract="Existing mounted API prefix /novels/{nid}/experimental/comic-layouts under both /api and /api/v1.",
        identity_permission_source_rules=AUTH + "; flag comic_layouts_v2 + deps asset_lineage_v2, ai_director_v2",
        dependencies=["B06", "A08", "A09"], test_layers=["UNIT", "API", "BROWSER"],
        test_command="python -m pytest -q tests/test_r5_comic_mounted.py tests/test_r5_comic_layouts.py",
        input_sample="Mounted app with trusted session and enabled flags + approved synthetic image.",
        expected_result="Entry/API reachable only with flags; OFF/V1/dependency fences hold.", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-02", group="IMAGE_COMIC", title="Comic project tree (volume/chapter/page)",
        user_behavior_must="A comic production tree organizing volumes/chapters/pages/panels inside the project and asset system.",
        authority_owner="MISSING; current layout records are flat per screenplay",
        existing_source_interfaces=["app/experimental/comic_layouts.py (layout records only)"],
        gap_type="MISSING", data_api_contract="No comic volume/chapter/page tree contract exists.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01"], test_layers=["UNIT", "API"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires owner + tree data model + API + tests.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-03", group="IMAGE_COMIC", title="Smart episode/panel splitting",
        user_behavior_must="Intelligently split a story/script into episodes and panels respecting pacing and reading order.",
        authority_owner="MISSING; only preset generation from existing screenplay shots",
        existing_source_interfaces=["app/experimental/comic_layouts.py: PRESETS PAGE/WEBTOON, initial ≤4/6 shots + manual add"],
        gap_type="MISSING", data_api_contract="No splitting algorithm/contract.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01"], test_layers=["UNIT", "API", "MANUAL"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires defined splitting policy + evidence; presets are not intelligent splitting.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-04", group="IMAGE_COMIC", title="Professional panel canvas",
        user_behavior_must="A professional page/panel canvas with spatial editing, layers/guides and direct manipulation.",
        authority_owner="MISSING full canvas; numeric geometry controls + server raster preview only",
        existing_source_interfaces=["app/experimental/comic_layouts.py: Rect/ComicPanel geometry", "frontend ComicLayoutsPanel (numeric controls)"],
        gap_type="MISSING", data_api_contract="Integer page-pixel geometry; no layer/guide model.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01"], test_layers=["UNIT", "BROWSER"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="A real canvas and its geometry regression are required; numeric controls are not a professional canvas.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-05", group="IMAGE_COMIC", title="Per-panel image generation",
        user_behavior_must="Generate a panel image from its brief via configured/authorized image capability, with review and provenance.",
        authority_owner="MISSING in comic; image generation exists only in Image Studio owners",
        existing_source_interfaces=["app/services/studio_image_execution.py (image owner, not comic-connected)"],
        gap_type="MISSING", data_api_contract="Comic panel binding only accepts already-approved image assets.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01", "V2-M5"], test_layers=["INTEGRATION", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires dispatch route+cost/consent+review integration; not present.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-06", group="IMAGE_COMIC", title="Character/costume consistency",
        user_behavior_must="Keep characters and costumes consistent across panels using authoritative identity/appearance references.",
        authority_owner="Partial contract: character_ids + AppearanceReference on panels; no consistency engine",
        existing_source_interfaces=["app/experimental/comic_layouts.py: AppearanceReference(character_id, asset_id, expected_asset_version)"],
        gap_type="PARTIAL", data_api_contract="References pin approved asset versions; no generative consistency enforcement.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01", "DIF-03"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r5_comic_layouts.py (reference contract subset)",
        input_sample="Panel with character + approved reference asset.", expected_result="References validated and stale-bound; generation consistency NOT_RUN.",
        status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-07", group="IMAGE_COMIC", title="Pose / spatial control",
        user_behavior_must="Control pose, camera and spatial composition of panel art.",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No pose/depth/camera contract in comic layouts.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-05"], test_layers=["INTEGRATION", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires control contract + provider support; absent.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-08", group="IMAGE_COMIC", title="Local panel repaint/inpainting",
        user_behavior_must="Repaint a region of a panel with mask-based local editing and review.",
        authority_owner="Image Studio mask/inpaint exists for image assets; not connected to comic panels",
        existing_source_interfaces=["app/services/studio_image_mask_authoring.py", "app/services/studio_image_cutout.py"],
        gap_type="PARTIAL", data_api_contract="No comic-panel repaint route; image owner contract only.",
        identity_permission_source_rules=AUTH, dependencies=["IMAGE-COMIC-05", "V2-M5"], test_layers=["INTEGRATION", "MEDIA"],
        test_command="NOT_RUN for comic; image mask owner tests separate", input_sample="n/a",
        expected_result="Panel-level repaint with provenance and review required.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-09", group="IMAGE_COMIC", title="Independent bubble text",
        user_behavior_must="Bubbles/narration are independently editable objects with speaker, text, position and measured typography.",
        authority_owner="app/experimental/comic_layouts.py Bubble",
        existing_source_interfaces=["app/experimental/comic_layouts.py: Bubble(plain text, kind, speaker, font_size); measured layout/preflight"],
        gap_type="PARTIAL", data_api_contract="Plain text ≤1000 chars, 80 bubbles/page, measured overflow/segment-cut warnings; no rich text.",
        identity_permission_source_rules=AUTH + "; review requires domain.review",
        dependencies=["IMAGE-COMIC-01"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r5_comic_layouts.py tests/test_r5_comic_mounted.py",
        input_sample="Page with CJK dialogue bubbles.", expected_result="Bubbles render as real pixels with deterministic layout; rich text unsupported.",
        release_blocking="MEDIUM"),
    row(id="IMAGE-COMIC-10", group="IMAGE_COMIC", title="SFX / onomatopoeia effects",
        user_behavior_must="Sound-effect text/graphic effects with placement and typographic styling.",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No SFX object type.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-09"], test_layers=["UNIT", "BROWSER"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires SFX model + rendering + review.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-11", group="IMAGE_COMIC", title="Line-art colorization",
        user_behavior_must="Colorize line art with character/style consistency and review.",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No colorization contract.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-05"], test_layers=["INTEGRATION", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires model adapter + quality evidence.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-12", group="IMAGE_COMIC", title="Cross-panel continuity",
        user_behavior_must="Maintain visual/story continuity across panels (costume, props, space, lighting).",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No continuity analysis between comic panels.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-06"], test_layers=["INTEGRATION"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires a continuity model/checks and acceptance scenarios.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-13", group="IMAGE_COMIC", title="Page comic / webtoon",
        user_behavior_must="Support both page-based comics and vertical scrolling webtoon layouts with page/segment geometry.",
        authority_owner="app/experimental/comic_layouts.py PRESETS PAGE/WEBTOON",
        existing_source_interfaces=["app/experimental/comic_layouts.py: PAGE 800x1120, WEBTOON 800x2400, segment_height; segments preview/export"],
        gap_type="NONE", data_api_contract="Integer geometry, safe area, segment boundaries; segment-cut bubbles warned.",
        identity_permission_source_rules=AUTH,
        dependencies=["IMAGE-COMIC-01"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r5_comic_layouts.py tests/test_r5_comic_mounted.py",
        input_sample="Webtoon preset with multiple shots.", expected_result="Segmented PNG output deterministic and preview-identical.",
        release_blocking="MEDIUM"),
    row(id="IMAGE-COMIC-14", group="IMAGE_COMIC", title="Pacing and page-turn rhythm",
        user_behavior_must="Guide pacing, page turns and reading rhythm for the layout.",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No pacing model or rhythm contract.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-13"], test_layers=["UNIT"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires defined pacing rules and evidence; absent.", status="PLANNED", release_blocking="MEDIUM"),
    row(id="IMAGE-COMIC-15", group="IMAGE_COMIC", title="Layers / ORA",
        user_behavior_must="Layer-based editing with ORA/PSD-compatible import/export.",
        authority_owner="MISSING", existing_source_interfaces=[],
        gap_type="MISSING", data_api_contract="No layer model; no ORA/PSD reader/writer in source (verified: no CBZ/ORA matches).",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-04"], test_layers=["UNIT", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires layer data model + ORA round-trip; absent.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-16", group="IMAGE_COMIC", title="Multilingual typesetting",
        user_behavior_must="Typeset text in multiple languages with correct line breaking, fonts and reading direction.",
        authority_owner="PARTIAL: single pinned font Noto Sans SC only",
        existing_source_interfaces=["app/experimental/comic_layouts.py: font_family Literal['NOTO_SANS_SC_OFL'], CJK punctuation rules"],
        gap_type="MISSING", data_api_contract="No language/font selection or RTL support.",
        identity_permission_source_rules="n/a", dependencies=["IMAGE-COMIC-09"], test_layers=["UNIT", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Multilingual typesetting unverified; only Simplified Chinese font path supported.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-17", group="IMAGE_COMIC", title="Local re-layout / remake",
        user_behavior_must="Re-layout or remake selected pages/panels without destroying approved history.",
        authority_owner="PARTIAL: versioned restore creates a new DRAFT; no partial re-layout engine",
        existing_source_interfaces=["app/experimental/comic_layouts.py: saved-version restore/recheck"],
        gap_type="PARTIAL", data_api_contract="CAS version restore only; no selective re-layout request contract.",
        identity_permission_source_rules=AUTH, dependencies=["IMAGE-COMIC-04"], test_layers=["UNIT", "API"],
        test_command="python -m pytest -q tests/test_r5_comic_layouts.py (restore subset)",
        input_sample="Approved layout version.", expected_result="Restore is safe; partial re-layout NOT implemented.",
        status="PLANNED", release_blocking="MEDIUM"),
    row(id="IMAGE-COMIC-18", group="IMAGE_COMIC", title="Comic format export",
        user_behavior_must="Export comic deliverables in standard formats (e.g. ORA/CBZ/PDF/EPUB) with deterministic bytes.",
        authority_owner="PARTIAL: PNG segments + ZIP manifest + OFL only",
        existing_source_interfaces=["app/experimental/comic_layouts.py: ZIP segment-NNN.png + manifest.json + OFL.txt"],
        gap_type="PARTIAL", data_api_contract="Deterministic ZIP export exists; CBZ/PDF/EPUB exporters absent (verified no CBZ/ORA in source).",
        identity_permission_source_rules="Review required; no external publish.",
        dependencies=["IMAGE-COMIC-13", "IMAGE-COMIC-15"], test_layers=["UNIT", "MEDIA"],
        test_command="python -m pytest -q tests/test_r5_comic_layouts.py (ZIP/PNG subset)",
        input_sample="Approved PAGE layout.", expected_result="ZIP+PNG verified byte-identical to preview; other formats NOT_RUN.",
        status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-19", group="IMAGE_COMIC", title="Dynamic-comic handoff",
        user_behavior_must="Hand off comic pages to dynamic-comic (motion/voice/subtitle) production with preserved sources.",
        authority_owner="MISSING", existing_source_interfaces=["timeline/video owners exist but no comic→dynamic handoff contract"],
        gap_type="MISSING", data_api_contract="No comic-to-timeline/video handoff route.",
        identity_permission_source_rules=AUTH, dependencies=["IMAGE-COMIC-13", "V2-M9"], test_layers=["INTEGRATION", "MEDIA"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires handoff schema + review + rendered evidence.", status="PLANNED", release_blocking="HIGH"),
    row(id="IMAGE-COMIC-20", group="IMAGE_COMIC", title="Comic Agent review",
        user_behavior_must="Automated/assisted comic review (layout, readability, continuity, text) with evidence and human approval.",
        authority_owner="MISSING comic-specific review; human digest review and narrative judge owners exist",
        existing_source_interfaces=["app/experimental/comic_layouts.py preflight + review", "app/experimental/narrative_judge.py (text owner)"],
        gap_type="MISSING", data_api_contract="No comic-agent evaluator contract.",
        identity_permission_source_rules="Reviewer must hold domain.review; agent proposals cannot self-approve.",
        dependencies=["IMAGE-COMIC-12", "DIF-07"], test_layers=["INTEGRATION"],
        test_command="NOT_RUN - not implemented", input_sample="n/a",
        expected_result="Requires evaluator + evidence + human acceptance.", status="PLANNED", release_blocking="HIGH"),
]


def build_abu_rows(evidence: dict) -> list[dict]:
    packages, integrated = parse_capabilities()
    rows = []
    for item in packages:
        pkg = item["id"]
        deps = item["dependencies"]
        status = "IMPLEMENTED" if pkg in integrated else "PLANNED"
        test_files = evidence.get(pkg, {}).get("test_files", [])
        override = evidence.get(pkg, {})
        entry = row(
            id=pkg,
            group="ABU_PACKAGE",
            title=item["title"],
            user_behavior_must=(
                f"Server-owned capability {pkg} ({item['title']}) is available only when its flag "
                f"{item['flag'] or '(foundation, no flag)'} and declared dependencies {deps} are explicitly enabled; "
                f"availability is computed server-side from implementation state and current flags; clients cannot invent it."
            ),
            authority_owner="app/experimental/capabilities.py + flags.py (server-owned registry)",
            existing_source_interfaces=["app/experimental/capabilities.py", "app/experimental/flags.py"] + test_files,
            gap_type="PARTIAL" if pkg in integrated else "MISSING",
            data_api_contract=(
                f"Capability discovery reports implementation/available/verification/disabled_reason; "
                f"wave={item['wave']}, mode={item['mode']}, model_requirement={item['model_requirement']}, "
                f"network_requirement={item['network_requirement']}. Registry is the single capability source."
            ),
            identity_permission_source_rules="Registry is read-only; enabling requires explicit EXPERIMENTAL_FEATURES opt-in and dependencies; V1_ACCEPTANCE_MODE disables all. " + AUTH,
            dependencies=deps,
            test_layers=["UNIT", "API"] if test_files else ["UNIT"],
            test_command=override.get("test_command") or ((FOCUSED_CMD + " " + " ".join(test_files)) if test_files else "NOT_RUN - no focused suite mapped"),
            input_sample="Trusted session, synthetic isolated project, explicit flags.",
            expected_result="Focused owning tests pass; disabled/dependency/V1 paths stay fenced; capability reports CONTRACT_VERIFIED not ACCEPTED.",
            actual_result=override.get("actual_result", "NOT_RUN in this baseline round."),
            evidence_path=override.get("evidence_path"),
            status="INTEGRATION_VERIFIED" if override.get("test_result") == "PASS" else status,
            test_result=override.get("test_result", "NOT_RUN"),
            release_blocking="MEDIUM",
            notes=f"Registry marks this package {'PARTIAL_INTEGRATED' if pkg in integrated else 'PENDING'}; product acceptance is not implied by contract tests."
        )
        rows.append(entry)
    return rows


def attach_original_coverage(rows: list[dict]) -> None:
    """Attach the detail index that proves each original requirement has a real owner.

    The 25 original rows already name owners/tests/evidence as free text. This pass
    resolves those names to repository paths and records existence, so the matrix is a
    coverage proof and not a list of claims. Missing owner code is a hard failure (the
    row is still allowed only when that is explicitly recorded); the validator enforces
    that original rows carry resolved coverage.
    """
    path_pattern = re.compile(r"((?:app|scripts|tests|frontend|contracts|packaging|docs)/[A-Za-z0-9_./-]+\.(?:py|ts|tsx|json|md|ps1|txt|js|mjs|gz))")
    for entry in rows:
        if entry["group"] != "ORIGINAL_V2":
            continue
        owner_sources = []
        for raw in entry.get("existing_source_interfaces", []):
            for match in path_pattern.finditer(str(raw)):
                relative = match.group(1).replace("\\", "/")
                item = {"path": relative, "exists": (ROOT / relative).exists()}
                if item not in owner_sources:
                    owner_sources.append(item)
        test_files = []
        for match in path_pattern.finditer(str(entry.get("test_command", ""))):
            relative = match.group(1).replace("\\", "/")
            if not relative.startswith("tests/"):
                continue
            item = {"path": relative, "exists": (ROOT / relative).exists()}
            if item not in test_files:
                test_files.append(item)
        evidence = []
        if entry.get("evidence_path"):
            relative = str(entry["evidence_path"]).replace("\\", "/")
            evidence.append({"path": relative, "exists": (ROOT / relative).exists()})
        status = "CODE_AND_TEST_PRESENT" if owner_sources and test_files else "CODE_PRESENT" if owner_sources else "MISSING"
        entry["coverage"] = {"owner_sources": owner_sources, "test_files": test_files,
                             "evidence": evidence, "status": status}


def main() -> int:
    head = git_head()
    evidence = load_evidence()
    override_all = evidence.get("rows", {})
    spec = load_spec()
    rows = ORIGINAL + DIF + COMIC + build_abu_rows(evidence.get("packages", {}))
    bind_spec(rows, spec)
    attach_original_coverage(rows)

    # apply evidence overlays for the hand-authored groups
    for entry in rows:
        patch = override_all.get(entry["id"])
        if not patch:
            continue
        for key in ("test_command", "actual_result", "evidence_path", "test_result", "status", "notes"):
            if key in patch:
                entry[key] = patch[key]
        if (patch.get("test_result") == "PASS" and entry["group"] != "DIF"
                and entry["status"] in {"IMPLEMENTED", "PLANNED"}):
            entry["status"] = "INTEGRATION_VERIFIED"

    # Original roadmap rows describe implemented owners unless explicitly marked otherwise.
    for entry in rows:
        if entry["group"] == "ORIGINAL_V2" and entry["status"] == "PLANNED" and entry["id"] not in {"V2-X09"}:
            entry["status"] = "IMPLEMENTED"

    # normalize defaults that must be explicit
    for entry in rows:
        entry["code_sha"] = TESTED_BASELINE_SHA
        if entry["status"] not in STATUS_VALUES:
            raise ValueError(f"bad status {entry['status']} in {entry['id']}")
        if entry["test_result"] not in TEST_RESULT_VALUES:
            raise ValueError(f"bad test_result {entry['test_result']} in {entry['id']}")
        if entry["gap_type"] not in GAP_TYPES:
            raise ValueError(f"bad gap_type {entry['gap_type']} in {entry['id']}")
        if entry["release_blocking"] not in RELEASE_BLOCKING:
            raise ValueError(f"bad release_blocking {entry['release_blocking']} in {entry['id']}")

    ids = [entry["id"] for entry in rows]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"duplicate requirement ids: {duplicates}")

    dif_ids = [f"DIF-{index:02d}" for index in range(1, 13)]
    comic_ids = [f"IMAGE-COMIC-{index:02d}" for index in range(1, 21)]
    for required in dif_ids + comic_ids:
        if required not in ids:
            raise ValueError(f"missing required requirement id {required}")
    packages, _ = parse_capabilities()
    package_ids = [f"{item['id']}" for item in packages]
    for required in package_ids:
        if required not in ids:
            raise ValueError(f"missing A/B/U package {required}")

    def count_by(field: str) -> dict:
        result: dict[str, int] = {}
        for entry in rows:
            result[entry[field]] = result.get(entry[field], 0) + 1
        return dict(sorted(result.items()))

    document = {
        "schema_version": 1,
        "document_version": "ENG-2026.10.19-r1",
        "repository": REPOSITORY,
        "base_branch": BASE_BRANCH,
        "engineering_branch": BASELINE_BRANCH,
        "tested_baseline_sha": TESTED_BASELINE_SHA,
        "generated_from_sha": head,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "release_policy": (
            "Official V2 requires the original Master Roadmap release items + DIF-01..12 + "
            "IMAGE-COMIC-01..20 + final same-build acceptance. This matrix is a tracking index, "
            "not a release certificate."
        ),
        "sources": {
            "release_scope_spec": {
                "id": spec["id"],
                "title": spec["title"],
                "path": spec["path"],
                "sha256": spec["sha256"],
                "bytes": spec["bytes"],
                "lines": spec["lines"],
                "utf8_valid": True,
                "status": "INGESTED_AND_HASH_VERIFIED",
                "consumed_by": "DIF-01..DIF-12 and IMAGE-COMIC-01..IMAGE-COMIC-20 bindings in this matrix",
            },
            "master_roadmap": {
                "path": "D:/PoemSeed/Documents/AI-Novel-Studio_V2/AI_NOVEL_STUDIO_V2_MASTER_ROADMAP.md",
                "status": "REFERENCED_EXTERNAL_NOT_INGESTED",
            },
            "abu_registry_in_tree": {
                "path": "app/experimental/capabilities.py",
                "status": "PARSED_FROM_TREE",
            },
        },
        "spec_coverage": {
            "document": spec["id"],
            "sha256": spec["sha256"],
            "dif_bound": len(spec["dif"]),
            "comic_bound": len(spec["comic"]),
            "binding": "each DIF/COMIC row carries spec.section, spec.line, spec.title and its MUST/acceptance text",
        },
        "source_status": {
            "release_scope_spec": "INGESTED: SPEC-2026.10.19-r1 present at " + SPEC_REL + " with sha256 " + spec["sha256"],
            "master_roadmap": "D:/PoemSeed/Documents/AI-Novel-Studio_V2/AI_NOVEL_STUDIO_V2_MASTER_ROADMAP.md (external to repo)",
            "abu_registry_in_tree": "app/experimental/capabilities.py (40 packages)",
        },
        "vocabulary": {
            "status": STATUS_VALUES,
            "test_result": TEST_RESULT_VALUES,
            "gap_type": GAP_TYPES,
            "release_blocking": RELEASE_BLOCKING,
        },
        "counts": {
            "total": len(rows),
            "by_group": count_by("group"),
            "by_status": count_by("status"),
            "by_test_result": count_by("test_result"),
            "by_release_blocking": count_by("release_blocking"),
        },
        "coverage_summary": {
            "original_rows": len(ORIGINAL),
            "original_with_resolved_owner": sum(1 for entry in rows if entry["group"] == "ORIGINAL_V2" and entry["coverage"]["owner_sources"]),
            "original_with_test_file": sum(1 for entry in rows if entry["group"] == "ORIGINAL_V2" and entry["coverage"]["test_files"]),
            "original_with_evidence": sum(1 for entry in rows if entry["group"] == "ORIGINAL_V2" and entry["coverage"]["evidence"]),
        },
        "groups": {
            "ORIGINAL_V2": "Original Master Roadmap release-required items and cross-cutting contracts",
            "ABU_PACKAGE": "A/B/U/F advanced capability packages parsed from the server-owned registry",
            "DIF": "Differentiated capabilities DIF-01..DIF-12",
            "IMAGE_COMIC": "Image Studio comic sub-features IMAGE-COMIC-01..20",
        },
        "requirements": sorted(rows, key=lambda entry: (["ORIGINAL_V2", "ABU_PACKAGE", "DIF", "IMAGE_COMIC"].index(entry["group"]), entry["id"])),
    }
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if "--check" in sys.argv:
        if not OUT.exists():
            print("MISSING", OUT)
            return 1
        try:
            committed = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("INVALID_JSON", OUT)
            return 1
        volatile = {"generated_at_utc", "generated_from_sha"}
        current = {key: value for key, value in document.items() if key not in volatile}
        existing = {key: value for key, value in committed.items() if key not in volatile}
        if existing != current:
            print("OUT_OF_DATE", OUT)
            differing = [key for key in set(current) | set(existing) if current.get(key) != existing.get(key)]
            print("DIFFERING_KEYS", differing)
            return 1
        print("TRACEABILITY_MATRIX_CURRENT", len(rows), "rows")
        return 0

    OUT.write_text(rendered, encoding="utf-8")
    print("WROTE", OUT)
    print("ROWS", len(rows))
    print("COUNTS", json.dumps(document["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
