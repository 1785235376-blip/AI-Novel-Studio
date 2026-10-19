#!/usr/bin/env python3
"""Validate GitHub Issue Forms templates and config.

GitHub renders .github/ISSUE_TEMPLATE/*.yml as Issue Forms. Invalid YAML, an
unknown field type or a duplicated/missing field id silently breaks the form, so
this validator checks both the YAML parse and the documented form structure.

PyYAML is an *optional local validation dependency* (python -m pip install pyyaml),
not a runtime dependency of the application. When it is missing the script fails
closed with BLOCKED instead of pretending the templates are valid.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
ALLOWED_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
REQUIRED_BUG_IDS = {
    "commit_sha", "operating_system", "toolchain", "reproduction_steps",
    "actual_result", "expected_result", "data_impact",
}
REQUIRED_FEATURE_IDS = {
    "user_scenario", "current_gap", "desired_capability", "affected_modules",
    "acceptance_criteria", "compatibility", "resource_budget",
}
REQUIRED_BY_TEMPLATE = {
    "bug_report.yml": REQUIRED_BUG_IDS,
    "feature_request.yml": REQUIRED_FEATURE_IDS,
}


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_template(name: str, document: object, errors: list[str]) -> None:
    check(isinstance(document, dict), f"{name}: root must be a mapping", errors)
    if not isinstance(document, dict):
        return
    check(isinstance(document.get("name"), str) and bool(document["name"].strip()),
          f"{name}: missing/blank name", errors)
    description = document.get("description")
    check(isinstance(description, str) and 0 < len(description) <= 200,
          f"{name}: description must be a non-empty string <= 200 chars", errors)
    title = document.get("title")
    check(title is None or isinstance(title, str), f"{name}: title must be a string", errors)
    labels = document.get("labels")
    check(labels is None or (isinstance(labels, list) and all(isinstance(item, str) for item in labels)),
          f"{name}: labels must be a list of strings", errors)
    body = document.get("body")
    check(isinstance(body, list) and bool(body), f"{name}: body must be a non-empty list", errors)
    if not isinstance(body, list):
        return
    seen_ids: set[str] = set()
    for index, item in enumerate(body):
        where = f"{name}: body[{index}]"
        check(isinstance(item, dict), f"{where}: must be a mapping", errors)
        if not isinstance(item, dict):
            continue
        field_type = item.get("type")
        check(field_type in ALLOWED_TYPES, f"{where}: unsupported type {field_type!r}", errors)
        attributes = item.get("attributes")
        check(isinstance(attributes, dict), f"{where}: attributes must be a mapping", errors)
        attributes = attributes if isinstance(attributes, dict) else {}
        validations = item.get("validations", {})
        check(isinstance(validations, dict), f"{where}: validations must be a mapping", errors)
        validations = validations if isinstance(validations, dict) else {}
        if field_type == "markdown":
            check(isinstance(attributes.get("value"), str) and bool(attributes["value"].strip()),
                  f"{where}: markdown needs a non-empty attributes.value", errors)
            continue
        field_id = item.get("id")
        check(isinstance(field_id, str) and bool(ID_PATTERN.fullmatch(field_id or "")),
              f"{where}: id must match [A-Za-z0-9_-]+", errors)
        if isinstance(field_id, str):
            check(field_id not in seen_ids, f"{where}: duplicate id {field_id!r}", errors)
            seen_ids.add(field_id)
        check("required" not in validations or isinstance(validations["required"], bool),
              f"{where}: validations.required must be a boolean", errors)
        if field_type == "input":
            check(isinstance(attributes.get("label"), str), f"{where}: input needs attributes.label", errors)
        elif field_type == "textarea":
            check(isinstance(attributes.get("label"), str), f"{where}: textarea needs attributes.label", errors)
            render = attributes.get("render")
            check(render is None or render in {"markdown", "shell", "text"},
                  f"{where}: unsupported render {render!r}", errors)
        elif field_type == "dropdown":
            options = attributes.get("options")
            check(isinstance(options, list) and len(options) >= 1,
                  f"{where}: dropdown needs at least one option", errors)
            check(isinstance(attributes.get("label"), str), f"{where}: dropdown needs attributes.label", errors)
        elif field_type == "checkboxes":
            options = attributes.get("options")
            check(isinstance(options, list) and len(options) >= 1,
                  f"{where}: checkboxes needs at least one option", errors)
            if isinstance(options, list):
                for option in options:
                    check(isinstance(option, dict) and isinstance(option.get("label"), str),
                          f"{where}: every checkbox option needs a label", errors)
    required = REQUIRED_BY_TEMPLATE.get(name)
    if required:
        missing = sorted(required - seen_ids)
        check(not missing, f"{name}: missing required field ids {missing}", errors)


def validate_config(name: str, document: object, errors: list[str]) -> None:
    check(isinstance(document, dict), f"{name}: root must be a mapping", errors)
    if not isinstance(document, dict):
        return
    check(isinstance(document.get("blank_issues_enabled"), bool),
          f"{name}: blank_issues_enabled must be a boolean", errors)
    links = document.get("contact_links")
    check(isinstance(links, list) and bool(links), f"{name}: contact_links must be a non-empty list", errors)
    if isinstance(links, list):
        for index, link in enumerate(links):
            where = f"{name}: contact_links[{index}]"
            check(isinstance(link, dict), f"{where}: must be a mapping", errors)
            if isinstance(link, dict):
                for key in ("name", "url", "about"):
                    check(isinstance(link.get(key), str) and bool(link[key].strip()),
                          f"{where}: missing {key}", errors)
                check(str(link.get("url", "")).startswith("https://"), f"{where}: url must be https", errors)


def main() -> int:
    try:
        import yaml  # noqa: PLC0415 - optional validation dependency
    except ImportError:
        print(json.dumps({"status": "BLOCKED", "reason": "PyYAML is not installed",
                          "hint": "python -m pip install pyyaml"}, ensure_ascii=False, indent=2))
        return 2
    errors: list[str] = []
    results: dict[str, object] = {}
    for name in ("bug_report.yml", "feature_request.yml", "config.yml"):
        path = TEMPLATE_DIR / name
        if not path.exists():
            errors.append(f"{name}: file is missing")
            continue
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{name}: invalid YAML: {exc}")
            continue
        if name == "config.yml":
            validate_config(name, document, errors)
        else:
            validate_template(name, document, errors)
        results[name] = "PARSED"
    report = {"status": "PASS" if not errors else "FAIL",
              "files": results, "errors": errors,
              "issue_forms_schema": "github-issue-forms/manual-structural-check"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
