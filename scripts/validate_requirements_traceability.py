"""Validate the unique V2 requirement traceability matrix (fail closed).

Checks:
  * document/meta schema and vocabulary,
  * unique IDs and mandatory fields,
  * complete DIF-01..12 and IMAGE-COMIC-01..20 coverage,
  * A/B/U/F coverage exactly matching app/experimental/capabilities.py,
  * status/test-result consistency rules (no false promotion),
  * evidence paths exist for PASS/INTEGRATION_VERIFIED/ACCEPTED rows,
  * counts match the rows.

Exit code 0 only when everything holds. Safe read-only: starts no app, model or scanner.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "v2" / "engineering" / "requirements-traceability.json"
SPEC_ID = "SPEC-2026.10.19-r1"
SPEC_PATH = ROOT / "docs" / "v2" / "engineering" / "spec" / "SPEC-2026.10.19-r1.txt"
SPEC_REL = "docs/v2/engineering/spec/SPEC-2026.10.19-r1.txt"
CAPABILITIES = ROOT / "app" / "experimental" / "capabilities.py"

STATUS_VALUES = {"PLANNED", "IMPLEMENTED", "INTEGRATION_VERIFIED", "ACCEPTED", "BLOCKED"}
TEST_RESULT_VALUES = {"PASS", "FAIL", "PARTIAL", "BLOCKED", "NOT_RUN"}
GAP_TYPES = {"NONE", "PARTIAL", "MISSING", "NOT_INTEGRATED", "BLOCKED", "SOURCE_MISSING"}
RELEASE_BLOCKING = {"HIGH", "MEDIUM", "LOW", "NONE"}
GROUPS = {"ORIGINAL_V2", "ABU_PACKAGE", "DIF", "IMAGE_COMIC"}

MANDATORY_STRINGS = (
    "id",
    "group",
    "title",
    "user_behavior_must",
    "authority_owner",
    "data_api_contract",
    "identity_permission_source_rules",
    "test_command",
    "input_sample",
    "expected_result",
    "status",
    "test_result",
    "gap_type",
    "release_blocking",
)


def fail(problems: list[str], message: str) -> None:
    problems.append(message)


def parse_package_ids() -> set[str]:
    text = CAPABILITIES.read_text(encoding="utf-8")
    return set(re.findall(r"\{'id': '([A-Z][0-9]{2})', 'title':", text))


def validate(document: dict) -> list[str]:
    problems: list[str] = []
    if document.get("schema_version") != 1:
        fail(problems, "schema_version must be 1")
    if document.get("document_version") != "ENG-2026.10.19-r1":
        fail(problems, "document_version mismatch")
    if not document.get("tested_baseline_sha"):
        fail(problems, "tested_baseline_sha missing")
    vocabulary = document.get("vocabulary", {})
    if set(vocabulary.get("status", [])) != STATUS_VALUES:
        fail(problems, "status vocabulary mismatch")
    if set(vocabulary.get("test_result", [])) != TEST_RESULT_VALUES:
        fail(problems, "test_result vocabulary mismatch")

    spec_source = (document.get("sources") or {}).get("release_scope_spec") or {}
    if not SPEC_PATH.exists():
        fail(problems, "release scope SPEC file missing: " + SPEC_REL)
        spec_bytes = b""
    else:
        spec_bytes = SPEC_PATH.read_bytes()
        spec_sha = hashlib.sha256(spec_bytes).hexdigest()
        if spec_source.get("sha256") != spec_sha:
            fail(problems, "SPEC sha256 mismatch between matrix and ingested file")
        if spec_source.get("bytes") != len(spec_bytes):
            fail(problems, "SPEC byte size mismatch")
        spec_text = spec_bytes.decode("utf-8")
        if not spec_text.startswith("# PoemSeed Studio V2 发布版全量增强需求书"):
            fail(problems, "SPEC title/header mismatch")
        if SPEC_ID not in spec_text:
            fail(problems, "SPEC version marker missing")
        if spec_source.get("lines") != spec_text.count("\n") + 1:
            fail(problems, "SPEC line count mismatch")
        if spec_source.get("status") != "INGESTED_AND_HASH_VERIFIED":
            fail(problems, "SPEC source status is not INGESTED_AND_HASH_VERIFIED")
        if spec_source.get("path") != SPEC_REL:
            fail(problems, "SPEC path mismatch")
    spec_coverage = document.get("spec_coverage") or {}
    if spec_coverage.get("dif_bound") != 12 or spec_coverage.get("comic_bound") != 20:
        fail(problems, "spec_coverage must bind 12 DIF and 20 COMIC requirements")
    spec_sha = hashlib.sha256(spec_bytes).hexdigest() if spec_bytes else ""

    requirements = document.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return problems + ["requirements must be a non-empty list"]

    ids: list[str] = []
    seen: set[str] = set()
    by_group: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_result: dict[str, int] = {}
    for entry in requirements:
        for field in MANDATORY_STRINGS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                fail(problems, f"{entry.get('id')}: mandatory field {field} is empty")
        rid = entry.get("id", "<missing>")
        if rid in seen:
            fail(problems, f"duplicate id {rid}")
        seen.add(rid)
        ids.append(rid)
        group = entry.get("group")
        if group not in GROUPS:
            fail(problems, f"{rid}: invalid group {group}")
        by_group[group] = by_group.get(group, 0) + 1
        status = entry.get("status")
        result = entry.get("test_result")
        if status not in STATUS_VALUES:
            fail(problems, f"{rid}: invalid status {status}")
        if result not in TEST_RESULT_VALUES:
            fail(problems, f"{rid}: invalid test_result {result}")
        if entry.get("gap_type") not in GAP_TYPES:
            fail(problems, f"{rid}: invalid gap_type {entry.get('gap_type')}")
        if entry.get("release_blocking") not in RELEASE_BLOCKING:
            fail(problems, f"{rid}: invalid release_blocking {entry.get('release_blocking')}")
        if not isinstance(entry.get("dependencies"), list):
            fail(problems, f"{rid}: dependencies must be a list")
        if not isinstance(entry.get("existing_source_interfaces"), list):
            fail(problems, f"{rid}: existing_source_interfaces must be a list")
        if not isinstance(entry.get("test_layers"), list):
            fail(problems, f"{rid}: test_layers must be a list")
        by_status[status] = by_status.get(status, 0) + 1
        by_result[result] = by_result.get(result, 0) + 1

        # consistency rules
        if status == "INTEGRATION_VERIFIED" and result != "PASS":
            fail(problems, f"{rid}: INTEGRATION_VERIFIED requires test_result PASS (got {result})")
        if status == "ACCEPTED" and result != "PASS":
            fail(problems, f"{rid}: ACCEPTED requires test_result PASS")
        if status in {"PLANNED", "BLOCKED"} and result == "PASS":
            fail(problems, f"{rid}: {status} requirement cannot carry a PASS result")
        if result == "PASS":
            evidence = entry.get("evidence_path")
            if not evidence:
                fail(problems, f"{rid}: PASS requires evidence_path")
            else:
                target = (ROOT / evidence).resolve()
                if not str(target).startswith(str(ROOT.resolve())):
                    fail(problems, f"{rid}: evidence_path escapes repository: {evidence}")
                elif not target.exists():
                    fail(problems, f"{rid}: evidence_path missing: {evidence}")
        if group == "ORIGINAL_V2":
            coverage = entry.get("coverage")
            if not isinstance(coverage, dict):
                fail(problems, f"{rid}: original requirement missing detail coverage index")
            else:
                owners = coverage.get("owner_sources") or []
                if not owners:
                    fail(problems, f"{rid}: no owner source resolved in coverage")
                for owner in owners:
                    if not isinstance(owner, dict) or not owner.get("path"):
                        fail(problems, f"{rid}: invalid coverage owner entry")
                    elif not (ROOT / owner["path"]).exists():
                        fail(problems, f"{rid}: coverage owner path missing: {owner['path']}")
                for test_file in coverage.get("test_files") or []:
                    if not isinstance(test_file, dict) or not test_file.get("path"):
                        fail(problems, f"{rid}: invalid coverage test entry")
                    elif not (ROOT / test_file["path"]).exists():
                        fail(problems, f"{rid}: coverage test path missing: {test_file['path']}")
                for evidence in coverage.get("evidence") or []:
                    if isinstance(evidence, dict) and evidence.get("path") and not (ROOT / evidence["path"]).exists():
                        fail(problems, f"{rid}: coverage evidence path missing: {evidence['path']}")
                if coverage.get("status") not in {"CODE_AND_TEST_PRESENT", "CODE_PRESENT", "MISSING"}:
                    fail(problems, f"{rid}: invalid coverage status {coverage.get('status')}")
                if coverage.get("status") == "MISSING":
                    fail(problems, f"{rid}: original coverage status MISSING")
        if group in {"DIF", "IMAGE_COMIC"}:
            binding = entry.get("spec")
            if not isinstance(binding, dict):
                fail(problems, f"{rid}: missing SPEC binding")
            else:
                if binding.get("document") != SPEC_ID or binding.get("sha256") != spec_sha:
                    fail(problems, f"{rid}: SPEC binding document/sha mismatch")
                if binding.get("path") != SPEC_REL:
                    fail(problems, f"{rid}: SPEC binding path mismatch")
                if not isinstance(binding.get("line"), int) or binding["line"] < 1:
                    fail(problems, f"{rid}: SPEC binding line invalid")
                if not str(binding.get("title", "")).strip():
                    fail(problems, f"{rid}: SPEC binding title empty")
                if group == "DIF" and not (binding.get("must") and binding.get("acceptance")):
                    fail(problems, f"{rid}: SPEC binding must/acceptance empty")
                if group == "IMAGE_COMIC" and not binding.get("requirement"):
                    fail(problems, f"{rid}: SPEC binding requirement empty")
            for field in ("user_behavior_must", "expected_result"):
                if "SOURCE_MISSING" in str(entry.get(field, "")):
                    fail(problems, f"{rid}: {field} still claims SOURCE_MISSING after SPEC ingestion")

    for index in range(1, 13):
        rid = f"DIF-{index:02d}"
        if rid not in seen:
            fail(problems, f"missing required requirement id {rid}")
    for index in range(1, 21):
        rid = f"IMAGE-COMIC-{index:02d}"
        if rid not in seen:
            fail(problems, f"missing required requirement id {rid}")
    package_ids = parse_package_ids()
    present_packages = {rid for rid in ids if re.fullmatch(r"[A-Z][0-9]{2}", rid)}
    missing_packages = sorted(package_ids - present_packages)
    if missing_packages:
        fail(problems, f"missing A/B/U packages: {missing_packages}")
    unknown_packages = sorted(present_packages - package_ids)
    if unknown_packages:
        fail(problems, f"unknown A/B/U packages not in registry: {unknown_packages}")
    if by_group.get("ORIGINAL_V2", 0) < 20:
        fail(problems, "original V2 coverage must contain at least 20 requirements")

    coverage_summary = document.get("coverage_summary") or {}
    if coverage_summary.get("original_rows") != len([entry for entry in requirements if entry.get("group") == "ORIGINAL_V2"]):
        fail(problems, "coverage_summary.original_rows mismatch")
    if coverage_summary.get("original_with_resolved_owner", 0) < 20:
        fail(problems, "fewer than 20 original requirements have a resolved owner source")

    counts = document.get("counts", {})
    expected = {
        "total": len(requirements),
        "by_group": by_group,
        "by_status": by_status,
        "by_test_result": by_result,
    }
    actual_by_group = counts.get("by_group", {})
    if actual_by_group != dict(sorted(by_group.items())):
        fail(problems, f"counts.by_group mismatch: {actual_by_group} != {dict(sorted(by_group.items()))}")
    actual_by_status = counts.get("by_status", {})
    if actual_by_status != dict(sorted(by_status.items())):
        fail(problems, f"counts.by_status mismatch")
    actual_by_result = counts.get("by_test_result", {})
    if actual_by_result != dict(sorted(by_result.items())):
        fail(problems, f"counts.by_test_result mismatch")
    if counts.get("total") != len(requirements):
        fail(problems, "counts.total mismatch")
    return problems


def main() -> int:
    if not MATRIX.exists():
        print("TRACEABILITY_INVALID: matrix file missing:", MATRIX)
        return 1
    try:
        document = json.loads(MATRIX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("TRACEABILITY_INVALID: JSON parse error:", exc)
        return 1
    problems = validate(document)
    if problems:
        print("TRACEABILITY_INVALID")
        for problem in problems:
            print(" -", problem)
        return 1
    print(
        "TRACEABILITY_OK",
        "total=" + str(document["counts"]["total"]),
        "groups=" + json.dumps(document["counts"]["by_group"], ensure_ascii=False),
        "status=" + json.dumps(document["counts"]["by_status"], ensure_ascii=False),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
