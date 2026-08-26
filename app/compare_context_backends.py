from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import Settings
from .repository import read_json
from .repositories.factory import create_repository_bundle
from .services import ContextService


SOURCE_KEYS = ("characters", "locations", "timeline", "secrets", "foreshadowing", "canon", "summaries", "story_state", "style_profile")


def canonical_json_normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonical_json_normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonical_json_normalize(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def differences(file_value: Any, postgres_value: Any, path: str = "") -> list[dict]:
    left, right = canonical_json_normalize(file_value), canonical_json_normalize(postgres_value)
    if isinstance(left, dict) and isinstance(right, dict):
        output = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else key
            if key not in left: output.append({"path": child, "file": "<missing>", "postgres": right[key]})
            elif key not in right: output.append({"path": child, "file": left[key], "postgres": "<missing>"})
            else: output.extend(differences(left[key], right[key], child))
        return output
    if isinstance(left, list) and isinstance(right, list):
        output = []
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left): output.append({"path": child, "file": "<missing>", "postgres": right[index]})
            elif index >= len(right): output.append({"path": child, "file": left[index], "postgres": "<missing>"})
            else: output.extend(differences(left[index], right[index], child))
        return output
    return [] if left == right else [{"path": path or "$", "file": left, "postgres": right}]


def _file_raw(root: Path, novel_id: str) -> dict:
    novel = root / "novels" / novel_id
    return {
        "characters": read_json(novel / "characters/characters.json", []),
        "locations": read_json(novel / "locations/locations.json", []),
        "timeline": read_json(novel / "timeline/events.json", []),
        "secrets": read_json(novel / "secrets.json", []),
        "foreshadowing": read_json(novel / "foreshadowing.json", []),
        "canon": read_json(novel / "canon.json", []),
        "summaries": read_json(novel / "summaries/index.json", []),
        "story_state": read_json(novel / "story_state.json", {}),
        "style_profile": read_json(novel / "style/profile.json", {}),
    }


def _semantic_sources(bundle, novel_id: str) -> dict:
    context = bundle.novels.get_context_sources(novel_id)
    return {
        "characters": bundle.novels.get_data_set(novel_id, "characters"),
        "locations": bundle.novels.get_data_set(novel_id, "locations"),
        "timeline": bundle.novels.get_data_set(novel_id, "timeline"),
        "secrets": context["secrets"],
        "foreshadowing": bundle.novels.get_data_set(novel_id, "foreshadowing"),
        "canon": bundle.novels.get_data_set(novel_id, "canon"),
        "summaries": context["summaries"],
        "story_state": context["story_state"],
        "style_profile": context["style_profile"],
    }


def compare(data_root: Path, database_url: str, novel_id: str, chapter_number: int,
            instruction: str, cloud: bool, report_path: Path) -> dict:
    file_bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=data_root), data_root)
    postgres_bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=database_url))
    file_raw = _file_raw(data_root, novel_id)
    postgres_raw = _semantic_sources(postgres_bundle, novel_id)
    file_serialized = _semantic_sources(file_bundle, novel_id)
    postgres_serialized = _semantic_sources(postgres_bundle, novel_id)
    chapter_id = f"{novel_id}:{chapter_number}"
    file_chapter = file_bundle.chapters.get(chapter_id)
    postgres_chapter = postgres_bundle.chapters.get(chapter_id)
    chapter_fields = ("id", "novel_id", "number", "title", "content", "version", "document")
    file_current = {key: file_chapter.get(key) for key in chapter_fields}
    postgres_current = {key: postgres_chapter.get(key) for key in chapter_fields}
    file_context = ContextService(file_bundle.novels, file_bundle.chapters).build(novel_id, chapter_number, instruction, cloud)
    postgres_context = ContextService(postgres_bundle.novels, postgres_bundle.chapters).build(novel_id, chapter_number, instruction, cloud)
    file_pack = {**file_context, "current_chapter": file_current,
                 "token_estimate": len(json.dumps(file_context, ensure_ascii=False)) // 3}
    postgres_pack = {**postgres_context, "current_chapter": postgres_current,
                     "token_estimate": len(json.dumps(postgres_context, ensure_ascii=False)) // 3}
    raw_differences = differences(file_raw, postgres_raw, "raw")
    serialized_differences = differences(file_serialized, postgres_serialized, "serialized")
    pack_differences = differences(file_pack, postgres_pack, "context_pack")
    dataset_results = {key: not differences(file_serialized[key], postgres_serialized[key], key) for key in SOURCE_KEYS}
    all_differences = raw_differences + serialized_differences + pack_differences
    report = {
        "status": "MATCH" if not all_differences else "DIFFERENT",
        "inputs": {"novel_id": novel_id, "chapter_id": chapter_id, "instruction": instruction,
                   "provider_mode": "CLOUD" if cloud else "LOCAL_ONLY", "cloud": cloud},
        "raw_sources_equal": not raw_differences,
        "serialized_sources_equal": not serialized_differences,
        "context_pack_equal": not pack_differences,
        "datasets": dataset_results,
        "differences": all_differences,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="novel_data")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--novel-id", default="sample_novel")
    parser.add_argument("--chapter", type=int, default=2)
    parser.add_argument("--instruction", default="Continue validation scene")
    parser.add_argument("--cloud", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--report", default="context_backend_compare.json")
    args = parser.parse_args()
    report = compare(Path(args.data_root), args.database_url, args.novel_id, args.chapter,
                     args.instruction, args.cloud, Path(args.report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "MATCH" else 1)


if __name__ == "__main__":
    main()
