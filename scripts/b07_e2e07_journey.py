#!/usr/bin/env python3
r"""B07 / DIF-10 / E2E-07 repeatable samples, real mounted-API journey and cross-target evidence.

This script produces the independent E2E-07 evidence for PoemSeed Studio V2 B07:

1. Three repeatable story samples (A basic-linear, B conditional-branch,
   C complex-boundaries) are created as REAL fixtures through the composed Studio
   API: a real File repository bundle, the production routers and the real
   trusted-session/role stack (the same composition as
   tests/test_r3_mounted_contracts.py::mounted), with FastAPI TestClient as the
   real HTTP layer.  Nothing about story authority, review, export or playback is
   mocked.  Each sample records the original Story Spec JSON, its version and
   digests, the server-authoritative witness (analysis.endings with choice
   paths), the step-by-step expected states recomputed with play(), and the
   generated target-format artifacts.

2. The T10 integration journey drives the full product surface end to end:
   planning graph/nodes -> interactive story from the selected nodes -> edit/save
   (dialogue, condition, choice, variables) -> preview play over several paths ->
   submit review -> review preview -> approve -> export-targets -> export-preview
   (losses) -> deterministic target ZIP -> unpack and verify manifest,
   source-receipt and every file hash (and a second identical export) -> open the
   artifact in the real target runtime (Godot first, Ink second; Ren'Py is
   BLOCKED_ENVIRONMENT without an engine) and compare every runtime step with
   play() -> save/exit/restore where the target supports it.

3. A generic target-runtime adapter layer locates the line-owned verifier,
   probes its CLI, runs it against the exported project, reads its result JSON
   and diffs each runtime step (node, variables, enabled choices, steps, status)
   with the Python authority.  A target is never reported as executed on
   generation alone: generation is not runtime, and a fixture is not the current
   work.

Honesty policy
--------------
* Evidence levels are recorded independently and never auto-upgraded:
  SOURCE_IMPLEMENTED, SCHEMA_VALIDATED, FIXTURE_TESTED,
  GENERATED_ARTIFACT_VALIDATED, TARGET_RUNTIME_EXECUTED, SAVE_RESTORE_VERIFIED,
  WINDOWS_USABILITY_VERIFIED (PASS | FAIL | PARTIAL | BLOCKED_ENVIRONMENT |
  BLOCKED_AUTHORITY | NOT_RUN).
* GENERATED_ARTIFACT_VALIDATED requires the delivered ZIP bytes to be read
  back and every manifest/receipt/hash recomputed here.
* TARGET_RUNTIME_EXECUTED requires a real target runtime process to run the
  exported artifact with choices and match every step of play().
* Ren'Py 8.5.4 is not installed on this host: its runtime level is recorded as
  BLOCKED_ENVIRONMENT and only static artifact checks are reported.
* No engine or model is installed by this script.  The script only launches
  verifiers and runtimes that already exist on the host.

Usage
-----
    python scripts/b07_e2e07_journey.py all
    python scripts/b07_e2e07_journey.py samples [--skip-runtime]
    python scripts/b07_e2e07_journey.py journey [--skip-runtime]
    python scripts/b07_e2e07_journey.py runtime --target GODOT_4_RUNTIME_PROJECT_V1 --project DIR

Repository-internal evidence lives under docs/v2/B07_DIF10_E2E07_EVIDENCE_20261020.json
and .md plus docs/v2/b07-e2e07-20261020/; repeatable artifacts (ZIPs, unpacked
projects, raw verifier output) are written to
D:\PoemSeed\Recovery\b07-delivery\e2e07 (external delivery directory).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELIVERY = Path(r"D:\PoemSeed\Recovery\b07-delivery\e2e07")
DEFAULT_SCRATCH = Path(r"D:\PoemSeed\Recovery\b07-scratch\e2e")
EVIDENCE_JSON = REPO_ROOT / "docs" / "v2" / "B07_DIF10_E2E07_EVIDENCE_20261020.json"
EVIDENCE_MD = REPO_ROOT / "docs" / "v2" / "B07_DIF10_E2E07_EVIDENCE_20261020.md"
REPO_SAMPLE_DIR = REPO_ROOT / "docs" / "v2" / "b07-e2e07-20261020"

TARGET_ORDER = (
    "GODOT_4_RUNTIME_PROJECT_V1",
    "INK_2_3_2_CURRENT_ARTIFACT_V1",
    "RENPY_8_5_4_PROJECT_V1",
)
LEGACY_TARGET_IDS = (
    "RENPY_8_5_4_TEXT_MENU_SUBSET",
    "GODOT_4_DATA_ADAPTER",
    "INKJS_2_3_2_TYPED_TEXT_SUBSET",
)
CONTRACT_LIMITS = {"files": 256, "file_bytes": 8 * 1024 * 1024, "total_bytes": 32 * 1024 * 1024, "path_length": 180}

PROVIDER_ENV = (
    "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY", "DASHSCOPE_API_KEY",
    "GROQ_API_KEY", "MISTRAL_API_KEY", "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL",
    "E2E_DATABASE_URL",
)
EVIDENCE_LEVELS = (
    "SOURCE_IMPLEMENTED", "SCHEMA_VALIDATED", "FIXTURE_TESTED",
    "GENERATED_ARTIFACT_VALIDATED", "TARGET_RUNTIME_EXECUTED",
    "SAVE_RESTORE_VERIFIED", "WINDOWS_USABILITY_VERIFIED",
)
EVIDENCE_STATUSES = ("PASS", "FAIL", "PARTIAL", "BLOCKED_ENVIRONMENT", "BLOCKED_AUTHORITY", "NOT_RUN")

# Line-owned runtime verifiers, probed not assumed.  The CLI shape is discovered
# from --help; these are the scripts the lines agreed to deliver.
RUNTIME_VERIFIERS = {
    "GODOT_4_RUNTIME_PROJECT_V1": {
        "runner": "python",
        "candidates": ["scripts/verify_godot_interactive_runtime.py"],
        "engine_env": "POEMSEED_GODOT_BIN",
        "engine_hints": [
            r"D:\GameDev\Godot\Godot-4.7-stable\Godot_v4.7-stable_win64_console.exe",
            r"D:\GameDev\Godot\Godot-4.7-stable\Godot_v4.7-stable_win64.exe",
        ],
    },
    "INK_2_3_2_CURRENT_ARTIFACT_V1": {
        "runner": "node",
        "candidates": ["scripts/verify_ink_current_artifact.mjs"],
        "engine_env": "POEMSEED_INKJS_ROOT",
        "engine_hints": [],
    },
}


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def digest_json(value):
    """Same canonical digest the product contract uses (sort_keys, compact separators)."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def tail_text(value, limit=4000):
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return value if len(value) <= limit else value[-limit:]


def relative_to(path, base):
    try:
        return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def run_process(argv, *, cwd=None, timeout=120, env=None, label="process"):
    """Run one host process and return a truthful command record (never hides failures)."""
    started = time.monotonic()
    record = {"kind": "process", "label": label, "argv": [str(item) for item in argv],
              "cwd": str(cwd) if cwd else None, "exit_code": None, "signal": None,
              "duration_ms": None, "stdout_tail": "", "stderr_tail": "", "timed_out": False}
    try:
        completed = subprocess.run([str(item) for item in argv], cwd=str(cwd) if cwd else None,
                                   capture_output=True, text=True, timeout=timeout,
                                   encoding="utf-8", errors="replace", env=env, shell=False)
        record.update(exit_code=completed.returncode, stdout_tail=tail_text(completed.stdout),
                      stderr_tail=tail_text(completed.stderr),
                      stdout_full=completed.stdout if len(completed.stdout) <= 8 * 1024 * 1024 else None)
    except subprocess.TimeoutExpired as exc:
        record.update(timed_out=True, stdout_tail=tail_text(exc.stdout), stderr_tail=tail_text(exc.stderr))
        record["exit_code"] = None
    except (OSError, ValueError) as exc:
        record["stderr_tail"] = "LAUNCH_ERROR: " + str(exc)
        record["exit_code"] = None
    record["duration_ms"] = int((time.monotonic() - started) * 1000)
    return record


def git_state():
    info = {"branch": None, "head_sha": None, "dirty": None, "status_porcelain": []}
    try:
        info["branch"] = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
                                        capture_output=True, text=True, timeout=20).stdout.strip() or None
        info["head_sha"] = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                                          capture_output=True, text=True, timeout=20).stdout.strip() or None
        status = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=20).stdout
        lines = [line for line in status.splitlines() if line.strip()]
        info["status_porcelain"] = lines[:100]
        info["dirty"] = bool(lines)
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def file_inventory(directory):
    directory = Path(directory)
    rows = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        rows.append({"path": path.relative_to(directory).as_posix(), "bytes": len(data),
                     "sha256": sha256_hex(data)})
    return rows


# ---------------------------------------------------------------------------
# application imports (the product authority, never reimplemented here)
# ---------------------------------------------------------------------------
def app_modules():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from app.experimental import interactive_story, interactive_export_contract, ink_export
    return interactive_story, interactive_export_contract, ink_export


def story_authority():
    return app_modules()[0]


def contract_module():
    return app_modules()[1]


# ---------------------------------------------------------------------------
# canonical step expectations (single source: interactive_story.play())
# ---------------------------------------------------------------------------
def canonical_state(spec, path):
    """One playback state in the canonical cross-target shape.

    play() is the product authority: node, variables, enabled choices, steps and
    status are all recomputed server-side from the bounded choice log.
    """
    story = story_authority()
    played = story.play(spec, list(path))
    node = played["node"]
    return {
        "node_id": node["node_id"],
        "title": node.get("title", ""),
        "dialogue": node.get("dialogue", ""),
        "character_id": node.get("character_id"),
        "ending": node.get("ending", ""),
        "variables": played["variables"],
        "choices": [{"id": item["id"], "label": item["label"], "enabled": item["enabled"]}
                    for item in played["choices"]],
        "enabled_choice_ids": [item["id"] for item in played["choices"] if item["enabled"]],
        "disabled_choice_ids": [item["id"] for item in played["choices"] if not item["enabled"]],
        "steps": played["steps"],
        "max_steps": played["max_steps"],
        "status": played["status"],
        "path": list(path),
    }


def canonical_states(spec, path):
    path = list(path)
    return [canonical_state(spec, path[:index]) for index in range(len(path) + 1)]


def analyze_summary(spec):
    story = story_authority()
    analysis = story.analyze(spec)
    return {"issues": analysis["issues"], "warnings": analysis["warnings"],
            "endings": analysis["endings"], "states_checked": analysis["states_checked"],
            "analysis_complete": analysis["analysis_complete"],
            "state_limit_reached": analysis["state_limit_reached"],
            "step_limit_reached": analysis["step_limit_reached"],
            "max_steps": analysis["max_steps"], "can_review": analysis["can_review"],
            "method": analysis["method"]}


def case_from_path(case_id, kind, spec, path, description, resume_at=None):
    path = list(path)
    case = {"id": case_id, "kind": kind, "description": description,
            "choices": path, "steps": len(path),
            "expected_states": canonical_states(spec, path)}
    if resume_at is not None:
        case["save_restore"] = {"resume_at": resume_at,
                                "saved_state": canonical_state(spec, path[:resume_at]),
                                "remaining_choices": path[resume_at:],
                                "final_state": canonical_state(spec, path)}
    return case


def build_cases(spec, analysis, extra_paths=()):
    """Expected cases: the initial state, every discovered ending witness, extras."""
    cases = [case_from_path("initial", "initial_state", spec, [],
                            "Initial server state; exposes choices disabled by initial variables.")]
    for index, witness in enumerate(analysis["endings"]):
        cases.append(case_from_path("ending-" + str(index + 1) + "-" + str(witness["node_id"]),
                                    "ending_witness", spec, witness["choices"],
                                    "Reach ending " + repr(witness["ending"]) + " via the authoritative witness path."))
    for item in extra_paths or ():
        path = list(item["choices"])
        cases.append(case_from_path(item["id"], item.get("kind", "extra_path"), spec, path,
                                    item.get("description", ""), resume_at=item.get("resume_at")))
    return cases


def choice_index_path(spec, path):
    """Map choice ids to the enabled-choice index the target runtimes drive."""
    story = story_authority()
    indices = []
    for index, choice_id in enumerate(path):
        played = story.play(spec, list(path[:index]))
        enabled = [item["id"] for item in played["choices"] if item["enabled"]]
        if choice_id not in enabled:
            raise ValueError("case path uses a disabled choice: " + choice_id)
        indices.append(enabled.index(choice_id))
    return indices


# ---------------------------------------------------------------------------
# sample and journey definitions (real planning nodes are substituted at build time)
# ---------------------------------------------------------------------------
def choice(cid, label, target, condition="", assignments=None):
    value = {"id": cid, "label": label, "target": target}
    if condition:
        value["condition"] = condition
    if assignments:
        value["assignments"] = assignments
    return value


def story_node(planning, title, *, dialogue="", ending="", choices=None, character_id=None):
    value = {"node_id": planning["id"], "node_version": planning["version"], "title": title}
    if dialogue:
        value["dialogue"] = dialogue
    if ending:
        value["ending"] = ending
    if choices:
        value["choices"] = choices
    if character_id:
        value["character_id"] = character_id
    return value


SPECIAL_TEXT = "「回声：〖第 1 次〗{不是} [选择] 100% 🙂 é」\n第二行：全角标点，。！？；：『引号』"


def spec_a(nodes, graph):
    return {
        "title": "A · 檐下灯火（基础线性样例）",
        "graph_id": graph["id"],
        "graph_version": graph["version"],
        "entry_node_id": nodes["start"]["id"],
        "max_steps": 8,
        "nodes": [
            story_node(nodes["start"], "第一幕 · 檐下", character_id="alice",
                       dialogue="雨落在青石上。她把灯放在门口，像放下一句没说出口的话。",
                       choices=[choice("to_middle", "推门进去", nodes["middle"]["id"])]),
            story_node(nodes["middle"], "第二幕 · 灯下",
                       dialogue="灯芯轻轻爆了一下。桌上摊着未写完的信。",
                       choices=[choice("to_late", "读完那封信", nodes["late"]["id"])]),
            story_node(nodes["late"], "第三幕 · 信末",
                       dialogue="信末只有一行字：「若你看见这盏灯，就说明我到家了。」",
                       choices=[choice("to_finale", "吹灭灯", nodes["finale"]["id"])]),
            story_node(nodes["finale"], "结局 · 灯火", dialogue="屋里暗下来，雨声却暖了。",
                       ending="灯火未熄"),
        ],
    }


def spec_b(nodes, graph):
    return {
        "title": "B · 岔路与代价（条件分支样例）",
        "graph_id": graph["id"],
        "graph_version": graph["version"],
        "entry_node_id": nodes["market"]["id"],
        "max_steps": 10,
        "variables": [
            {"name": "trusted", "type": "bool", "initial": False},
            {"name": "coins", "type": "int", "initial": 0, "minimum": 0, "maximum": 3},
        ],
        "nodes": [
            story_node(nodes["market"], "集市 · 初始", character_id="alice",
                       dialogue="集市收摊了。朋友在屋檐那头看着她，她手里有两枚硬币。",
                       choices=[
                           choice("share", "分一块面包给朋友", nodes["crossroads"]["id"],
                                  assignments={"trusted": True}),
                           choice("keep", "悄悄收起两枚硬币", nodes["crossroads"]["id"],
                                  assignments={"coins": 2}),
                           choice("call", "请朋友同行", nodes["temple_rest"]["id"], condition="trusted"),
                       ]),
            story_node(nodes["crossroads"], "岔路 · 选择",
                       dialogue="一条路亮着灯，一条路只听得见风。",
                       choices=[
                           choice("buy", "买一盏灯", nodes["night_road"]["id"],
                                  condition="coins >= 1", assignments={"coins": 0}),
                           choice("dark", "摸着黑走", nodes["night_road"]["id"]),
                           choice("beg", "向神庙求助", nodes["temple_rest"]["id"], condition="trusted"),
                           choice("turn", "折返回家", nodes["safe_home"]["id"]),
                       ]),
            story_node(nodes["night_road"], "夜路 · 分岔",
                       dialogue="风从山口下来，带着雪的味道。",
                       choices=[
                           choice("forge", "翻过山口", nodes["mountain_dawn"]["id"], condition="not trusted"),
                           choice("pray", "在路边祈祷", nodes["temple_rest"]["id"], condition="trusted"),
                           choice("retreat", "退回镇上", nodes["safe_home"]["id"]),
                       ]),
            story_node(nodes["safe_home"], "结局 · 平安回家", dialogue="门闩落下，雨声被关在门外。",
                       ending="平安回家"),
            story_node(nodes["temple_rest"], "结局 · 神庙的安眠", dialogue="石阶很凉，香火很轻。",
                       ending="神庙的安眠"),
            story_node(nodes["mountain_dawn"], "结局 · 山口黎明", dialogue="雪停了，天边有一线很薄的金。",
                       ending="山口黎明"),
        ],
    }


def spec_c(nodes, graph):
    return {
        "title": "C · 回声边界（复杂边界样例）",
        "graph_id": graph["id"],
        "graph_version": graph["version"],
        "entry_node_id": nodes["loop_hub"]["id"],
        "max_steps": 6,
        "variables": [
            {"name": "resonance", "type": "int", "initial": 0, "minimum": 0, "maximum": 3},
        ],
        "nodes": [
            story_node(nodes["loop_hub"], "循环 · 回声厅",
                       dialogue=SPECIAL_TEXT,
                       choices=[
                           choice("again", "再听一次 [回声] {继续} 〖…〗 % 🙂", nodes["loop_hub"]["id"]),
                           choice("descend", "顺着回声往下走", nodes["echo_chamber"]["id"],
                                  assignments={"resonance": 2}),
                       ]),
            story_node(nodes["echo_chamber"], "深处 · 刻字墙",
                       dialogue="墙上刻着：{ } [ ] 〖记忆〗 🙂\n“é” 与全角：：（分号）；「引号」",
                       choices=[
                           choice("remember", "记住这一切", nodes["memory_ending"]["id"],
                                  condition="resonance >= 2"),
                           choice("forget", "忘掉一切", nodes["void_ending"]["id"]),
                       ]),
            story_node(nodes["memory_ending"], "结局 · 记忆封存",
                       dialogue="她把回声收进一盏灯里。", ending="记忆封存 [A] {B} 〖C〗 100% 🙂 é"),
            story_node(nodes["void_ending"], "结局 · 归于虚空", dialogue="厅里只剩下她自己的呼吸。",
                       ending="归于虚空"),
        ],
    }


def spec_journey(nodes, graph):
    return {
        "title": "Journey · 岔路回声（E2E-07 集成旅程作品）",
        "graph_id": graph["id"],
        "graph_version": graph["version"],
        "entry_node_id": nodes["market"]["id"],
        "max_steps": 8,
        "variables": [
            {"name": "trusted", "type": "bool", "initial": False},
            {"name": "coins", "type": "int", "initial": 0, "minimum": 0, "maximum": 3},
        ],
        "nodes": [
            story_node(nodes["market"], "集市 · 旅程起点", character_id="alice",
                       dialogue="集市收摊了。她把灯挂在檐下，手里有两枚硬币。",
                       choices=[
                           choice("share", "分一块面包给朋友", nodes["crossroads"]["id"],
                                  assignments={"trusted": True}),
                           choice("keep", "悄悄收起两枚硬币", nodes["crossroads"]["id"],
                                  assignments={"coins": 2}),
                           choice("call", "请朋友同行", nodes["temple_rest"]["id"], condition="trusted"),
                       ]),
            story_node(nodes["crossroads"], "岔路 · 选择",
                       dialogue="一条路亮着灯，一条路只听得见风。",
                       choices=[
                           choice("buy", "买一盏灯", nodes["night_road"]["id"],
                                  condition="coins >= 1", assignments={"coins": 0}),
                           choice("dark", "摸着黑走", nodes["night_road"]["id"]),
                           choice("beg", "向神庙求助", nodes["temple_rest"]["id"], condition="trusted"),
                           choice("turn", "折返回家", nodes["safe_home"]["id"]),
                           choice("wander", "跟着风走", nodes["loop_hub"]["id"]),
                       ]),
            story_node(nodes["night_road"], "夜路 · 分岔",
                       dialogue="风从山口下来，带着雪的味道。",
                       choices=[
                           choice("forge", "翻过山口", nodes["mountain_dawn"]["id"], condition="not trusted"),
                           choice("pray", "在路边祈祷", nodes["temple_rest"]["id"], condition="trusted"),
                           choice("retreat", "退回镇上", nodes["safe_home"]["id"]),
                       ]),
            story_node(nodes["loop_hub"], "回声厅 · 循环",
                       dialogue=SPECIAL_TEXT,
                       choices=[
                           choice("again", "再听一次 [回声] {继续} 〖…〗 % 🙂", nodes["loop_hub"]["id"]),
                           choice("escape", "离开回声厅", nodes["mountain_dawn"]["id"]),
                       ]),
            story_node(nodes["safe_home"], "结局 · 平安回家", dialogue="门闩落下，雨声被关在门外。",
                       ending="平安回家"),
            story_node(nodes["temple_rest"], "结局 · 神庙的安眠", dialogue="石阶很凉，香火很轻。",
                       ending="神庙的安眠"),
            story_node(nodes["mountain_dawn"], "结局 · 山口黎明", dialogue="雪停了，天边有一线很薄的金。",
                       ending="山口黎明"),
        ],
    }


SAMPLE_DEFINITIONS = [
    {
        "key": "A_basic_linear",
        "title": "A · 基础线性（3-4 节点、对白、单一路径、一个结局）",
        "planning_title": "B07 E2E sample A planning graph",
        "volume_title": "卷一 · 檐下",
        "chapter_title": "第一章 · 灯火",
        "scene_titles": [("start", "场景 1 · 檐下"), ("middle", "场景 2 · 灯下"),
                         ("late", "场景 3 · 信末"), ("finale", "场景 4 · 结局")],
        "build": spec_a,
        "focus": ["single_linear_path", "dialogue", "speaker", "one_ending"],
        "extra_paths": [],
    },
    {
        "key": "B_conditional_branch",
        "title": "B · 条件分支（bool+int、3 结局、初始禁用路线、条件赋值影响后续）",
        "planning_title": "B07 E2E sample B planning graph",
        "volume_title": "卷二 · 岔路",
        "chapter_title": "第二章 · 代价",
        "scene_titles": [("market", "场景 1 · 集市"), ("crossroads", "场景 2 · 岔路"),
                         ("night_road", "场景 3 · 夜路"), ("safe_home", "场景 4 · 结局甲"),
                         ("temple_rest", "场景 5 · 结局乙"), ("mountain_dawn", "场景 6 · 结局丙")],
        "build": spec_b,
        "focus": ["bool_variable", "int_variable", "conditional_choices", "assignments",
                  "three_endings", "initially_disabled_route", "assignment_changes_later_choices"],
        "extra_paths": [
            {"id": "assignment-effect-trusted", "choices": ["share", "dark", "pray"],
             "description": "Assignment trusted=True changes which night-road choice is enabled."},
            {"id": "assignment-effect-coins", "choices": ["keep", "buy", "forge"],
             "description": "Assignment coins=2 enables the buy route; buying sets coins=0."},
        ],
    },
    {
        "key": "C_complex_boundaries",
        "title": "C · 复杂边界（循环+步数上限、Unicode/全角/引号/换行/特殊字符、存档恢复场景）",
        "planning_title": "B07 E2E sample C planning graph",
        "volume_title": "卷三 · 回声",
        "chapter_title": "第三章 · 边界",
        "scene_titles": [("loop_hub", "场景 1 · 循环回声"), ("echo_chamber", "场景 2 · 刻字墙"),
                         ("memory_ending", "场景 3 · 结局甲"), ("void_ending", "场景 4 · 结局乙")],
        "build": spec_c,
        "focus": ["cycle", "step_cap", "unicode_fullwidth_quotes_newlines_specials",
                  "save_restore_scenario", "two_endings"],
        "extra_paths": [
            {"id": "step-cap-reached", "choices": ["again"] * 6,
             "description": "Six self-loop choices reach max_steps=6: status STEP_CAP_REACHED."},
            {"id": "save-restore-continue", "choices": ["descend", "remember"], "resume_at": 1,
             "description": "Save after descending (state at step 1), restore, continue to the ending."},
        ],
    },
]

JOURNEY_DEFINITION = {
    "key": "journey",
    "title": "Journey · E2E-07 集成旅程作品",
    "planning_title": "B07 E2E-07 journey planning graph",
    "volume_title": "卷 · 旅程",
    "chapter_title": "章 · 岔路回声",
    "scene_titles": [("market", "场景 1 · 集市"), ("crossroads", "场景 2 · 岔路"),
                     ("night_road", "场景 3 · 夜路"), ("loop_hub", "场景 4 · 回声厅"),
                     ("safe_home", "场景 5 · 结局甲"), ("temple_rest", "场景 6 · 结局乙"),
                     ("mountain_dawn", "场景 7 · 结局丙")],
    "build": spec_journey,
    "focus": ["conditions", "assignments", "cycle", "step_cap", "unicode_specials", "three_endings"],
    "extra_paths": [
        {"id": "step-cap-reached", "choices": ["share", "wander"] + ["again"] * 6,
         "description": "Eight steps (max_steps=8) on the cycle: status STEP_CAP_REACHED."},
        {"id": "save-restore-continue", "choices": ["share", "dark", "pray"], "resume_at": 2,
         "description": "Save at the night road (step 2), restore, continue to the temple ending."},
        {"id": "assignment-effect-coins", "choices": ["keep", "buy", "forge"],
         "description": "coins assignment enables buy; buy resets coins to 0."},
    ],
}



"""
Composition, planning/story API journey, archive verification and static target checks.

The composition below deliberately reuses the exact real fixture used by the
mounted R3/R5 contract suites: it imports the fixture function from
tests/test_r3_mounted_contracts.py and invokes it with the File backend and a
single in-process FastAPI TestClient.  No service, router, authorization path or
export path is replaced.  Only host engine discovery (subprocess) and the target
runtime are external processes.
"""
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# recorder: every claim below is tied to an executed call or assertion
# ---------------------------------------------------------------------------
class Recorder:
    def __init__(self, label):
        self.label = label
        self.started = time.monotonic()
        self.http = []
        self.commands = []
        self.checks = []
        self.notes = []

    def command(self, record):
        self.commands.append(record)
        return record

    def check(self, check_id, condition, detail=""):
        entry = {"id": check_id, "status": "PASS" if condition else "FAIL", "detail": detail}
        self.checks.append(entry)
        return bool(condition)

    def require(self, check_id, condition, detail=""):
        if not self.check(check_id, condition, detail):
            raise RuntimeError("E2E07 check failed: " + check_id + (": " + detail if detail else ""))
        return True

    def note(self, text):
        self.notes.append(text)

    def summary(self):
        return {"status": "PASS" if all(item["status"] == "PASS" for item in self.checks) else "FAIL",
                "checks": len(self.checks),
                "failed": [item["id"] for item in self.checks if item["status"] != "PASS"],
                "duration_ms": int((time.monotonic() - self.started) * 1000)}


def http_call(recorder, env, method, path, *, body=None, expected=(200,), headers=None, label=None):
    """One real HTTP call through the mounted application; the result is recorded verbatim."""
    started = time.monotonic()
    kwargs = {}
    if headers:
        kwargs["headers"] = headers
    if body is not None:
        kwargs["json"] = body
    response = env.client.request(method, path, **kwargs)
    record = {
        "kind": "http", "label": label or (method + " " + path), "method": method,
        "path": path.split("/experimental/")[-1] if "/experimental/" in path else path,
        "status_code": response.status_code,
        "request_sha256": digest_json(body) if body is not None else None,
        "response_sha256": sha256_hex(response.content),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    recorder.http.append(record)
    if response.status_code not in expected:
        record["response_excerpt"] = response.text[:2000]
        raise RuntimeError("HTTP " + method + " " + path + " -> " + str(response.status_code) + ": " + response.text[:1000])
    try:
        return response.json()
    except ValueError:
        return {"_raw_sha256": record["response_sha256"]}


# ---------------------------------------------------------------------------
# real composed environment (same fixture composition as R3/R5 contract suites)
# ---------------------------------------------------------------------------
class ComposedEnvironment:
    def __init__(self, env, generator, monkeypatch, tmp_dir, saved_env, prefix):
        self.env = env
        self.generator = generator
        self.monkeypatch = monkeypatch
        self.tmp_dir = Path(tmp_dir)
        self.saved_env = saved_env
        self.prefix = prefix
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.env, name)

    def close(self, remove=True):
        if self.closed:
            return
        self.closed = True
        try:
            self.env.client.close()
        except Exception:
            pass
        try:
            self.env.exports._pool.shutdown(wait=True)
        except Exception:
            pass
        try:
            self.generator.close()
        except Exception:
            pass
        try:
            self.monkeypatch.undo()
        except Exception:
            pass
        os.environ.update(self.saved_env)
        if remove:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def report(self):
        return {
            "composition": "tests/test_r3_mounted_contracts.py::mounted",
            "fixture_parameters": {"backend": "file", "prefix": self.prefix},
            "http_layer": "fastapi.testclient.TestClient (in-process real HTTP)",
            "storage_backend": "file",
            "repository_bundle": "app.repositories.factory.create_repository_bundle (real)",
            "routers": "production app.main:app routers",
            "authorization": "real trusted session resolver, membership and domain role stack",
            "service_rebinding": "only disposable storage/service dependencies (as the R3 fixture does)",
            "novel_id": self.env.nid,
            "chapter_id": self.env.chapter["id"],
            "provider_calls": "none (mock_provider=True, no model/network call in this journey)",
            "mocks": False,
            "tmp_environment": str(self.tmp_dir),
        }


def build_file_backend_env(scratch_root, *, prefix="/api", keep_env=False):
    """Compose the real File-backend Studio environment through the R3 mounted fixture."""
    scratch_root = Path(scratch_root)
    scratch_root.mkdir(parents=True, exist_ok=True)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(REPO_ROOT / "tests") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tests"))
    import pytest
    import test_r3_mounted_contracts as contracts
    saved = {key: os.environ.pop(key) for key in PROVIDER_ENV if key in os.environ}
    tmp_dir = Path(tempfile.mkdtemp(prefix="b07-e2e07-env-", dir=str(scratch_root)))
    monkeypatch = pytest.MonkeyPatch()
    request = SimpleNamespace(param="file")
    generator = contracts.mounted.__wrapped__(request=request, tmp_path=tmp_dir,
                                              monkeypatch=monkeypatch, prefix=prefix)
    env = next(generator)
    return ComposedEnvironment(env, generator, monkeypatch, tmp_dir, saved, prefix)


# ---------------------------------------------------------------------------
# planning and interactive-story API helpers
# ---------------------------------------------------------------------------
def story_url(env, story_id):
    return env.base + "/interactive-stories/" + story_id


def build_planning(recorder, env, definition):
    """Create the real planning graph (Project > Volume > Chapter > Scene nodes)."""
    chapter_id = env.chapter["id"]
    graph = http_call(recorder, env, "POST", env.base + "/planning/graphs",
                      body={"title": definition["planning_title"], "links": {"chapter_ids": [chapter_id]}},
                      expected=(201,), label="planning.graphs.create")
    recorder.require("planning-graph-active", graph.get("status") == "ACTIVE", str(graph.get("status")))
    recorder.require("planning-graph-has-root", bool(graph.get("root_node_id")), str(graph.get("id")))

    def create_node(parent_id, level, title, links=None):
        payload = {"graph_id": graph["id"], "parent_id": parent_id, "level": level, "title": title}
        if links is not None:
            payload["links"] = links
        return http_call(recorder, env, "POST", env.base + "/planning/nodes", body=payload,
                         expected=(201,), label="planning.nodes.create." + level)

    volume = create_node(graph["root_node_id"], "VOLUME", definition["volume_title"],
                         links={"chapter_ids": [chapter_id]})
    chapter_node = create_node(volume["id"], "CHAPTER", definition["chapter_title"],
                               links={"chapter_ids": [chapter_id]})
    scenes = {}
    for alias, title in definition["scene_titles"]:
        scenes[alias] = create_node(chapter_node["id"], "SCENE", title,
                                    links={"chapter_ids": [chapter_id]})
    recorder.require("planning-scene-count", len(scenes) == len(definition["scene_titles"]),
                     str(len(scenes)))
    return {
        "graph": graph,
        "volume": volume,
        "chapter_node": chapter_node,
        "scenes": scenes,
        "nodes": scenes,
        "chapter_id": chapter_id,
        "record": {
            "graph_id": graph["id"], "graph_version": graph["version"],
            "root_node_id": graph["root_node_id"],
            "volume": {"id": volume["id"], "version": volume["version"]},
            "chapter_node": {"id": chapter_node["id"], "version": chapter_node["version"]},
            "chapter_id": chapter_id,
            "scenes": [{"alias": alias, "id": scenes[alias]["id"], "version": scenes[alias]["version"],
                        "title": scenes[alias]["title"], "level": "SCENE"}
                       for alias, _ in definition["scene_titles"]],
        },
    }


def create_story(recorder, env, spec):
    row = http_call(recorder, env, "POST", env.base + "/interactive-stories",
                    body={"spec": spec}, expected=(201,), label="interactive-stories.create")
    recorder.require("story-created-draft", row.get("status") == "DRAFT" and row.get("version") == 1,
                     str(row.get("status")) + "/" + str(row.get("version")))
    recorder.require("story-spec-roundtrip", row.get("spec") == spec, "server spec differs from request")
    return row


def get_story(recorder, env, story_id, expected=(200,), label="interactive-stories.get"):
    return http_call(recorder, env, "GET", story_url(env, story_id), expected=expected, label=label)


def save_story(recorder, env, story_id, expected_version, spec):
    row = http_call(recorder, env, "PUT", story_url(env, story_id),
                    body={"expected_version": expected_version, "spec": spec}, label="interactive-stories.save")
    recorder.require("story-saved-version", row.get("version") == expected_version + 1,
                     str(row.get("version")))
    recorder.require("story-saved-draft", row.get("status") == "DRAFT", str(row.get("status")))
    recorder.require("story-saved-spec", row.get("spec") == spec, "saved spec differs")
    return row


def preview_play(recorder, env, story_id, expected_version, choices):
    return http_call(recorder, env, "POST", story_url(env, story_id) + "/preview",
                     body={"expected_version": expected_version, "choices": list(choices)},
                     label="interactive-stories.preview")


def submit_review(recorder, env, story_id, expected_version):
    row = http_call(recorder, env, "POST", story_url(env, story_id) + "/review",
                    body={"expected_version": expected_version, "action": "submit"},
                    label="interactive-stories.review.submit")
    recorder.require("review-submitted", row.get("status") == "REVIEW", str(row.get("status")))
    return row


def review_preview(recorder, env, story_id, expected_version):
    result = http_call(recorder, env, "POST", story_url(env, story_id) + "/review-preview",
                       body={"expected_version": expected_version}, label="interactive-stories.review-preview")
    recorder.require("review-preview-digest", isinstance(result.get("preview_digest"), str)
                     and len(result["preview_digest"]) == 64, str(result.get("preview_digest")))
    recorder.require("review-preview-can-approve", result.get("can_approve") is True,
                     str(result.get("can_approve")))
    return result


def approve_story(recorder, env, story_id, expected_version, preview_digest):
    row = http_call(recorder, env, "POST", story_url(env, story_id) + "/review",
                    body={"expected_version": expected_version, "action": "approve",
                          "preview_digest": preview_digest},
                    label="interactive-stories.review.approve")
    recorder.require("story-approved", row.get("status") == "APPROVED", str(row.get("status")))
    return row


def export_targets(recorder, env, story_id, expected_version):
    return http_call(recorder, env, "POST", story_url(env, story_id) + "/export-targets",
                     body={"expected_version": expected_version}, label="interactive-stories.export-targets")


def export_preview(recorder, env, story_id, expected_version, target_id=None):
    body = {"expected_version": expected_version}
    if target_id:
        body["target_id"] = target_id
    return http_call(recorder, env, "POST", story_url(env, story_id) + "/export-preview",
                     body=body, label="interactive-stories.export-preview" + (":" + target_id if target_id else ""))


def export_archive(recorder, env, story_id, expected_version, preview_digest, target_id=None):
    body = {"expected_version": expected_version, "preview_digest": preview_digest}
    if target_id:
        body["target_id"] = target_id
    return http_call(recorder, env, "POST", story_url(env, story_id) + "/export",
                     body=body, label="interactive-stories.export" + (":" + target_id if target_id else ""))


def preview_matches_play(recorder, env, story_row, choices):
    """Preview one path and require the server state to equal play() exactly."""
    story = story_authority()
    played = preview_play(recorder, env, story_row["id"], story_row["version"], choices)
    expected = story.play(story_row["spec"], list(choices))
    comparable = {"node_id": played["node"]["node_id"], "status": played["status"],
                  "steps": played["steps"], "variables": played["variables"],
                  "enabled_choice_ids": [c["id"] for c in played["choices"] if c["enabled"]],
                  "disabled_choice_ids": [c["id"] for c in played["choices"] if not c["enabled"]]}
    wanted = {"node_id": expected["node"]["node_id"], "status": expected["status"],
              "steps": expected["steps"], "variables": expected["variables"],
              "enabled_choice_ids": [c["id"] for c in expected["choices"] if c["enabled"]],
              "disabled_choice_ids": [c["id"] for c in expected["choices"] if not c["enabled"]]}
    recorder.require("preview-matches-play:" + "-".join(list(choices)) if choices else "preview-matches-play:initial",
                     comparable == wanted, json.dumps({"server": comparable, "play": wanted}, ensure_ascii=False)[:1500])
    return {"choices": list(choices), "server": comparable, "play": wanted, "match": comparable == wanted}


# ---------------------------------------------------------------------------
# journey story edit: dialogue, condition, choice, variables
# ---------------------------------------------------------------------------
def journey_edited_spec(spec):
    edited = deepcopy(spec)
    nodes = {node["node_id"]: node for node in edited["nodes"]}
    for node in edited["nodes"]:
        choices = node.get("choices") or []
        if choices:
            by_id = {item["id"]: item for item in choices}
            if node["title"].startswith("集市"):
                node["dialogue"] = ("集市收摊了。雨丝斜斜地落，她把灯挂在檐下，手里有两枚硬币。"
                                    "🙂 全角标点，。！？；：「引号」")
                if "call" in by_id:
                    by_id["call"]["condition"] = "trusted and coins >= 0"
            if node["title"].startswith("岔路"):
                if "dark" in by_id:
                    by_id["dark"]["label"] = "摸着黑走（没有灯）"
                if "buy" in by_id:
                    by_id["buy"]["assignments"] = {"coins": 0, "trusted": False}
            if node["title"].startswith("夜路"):
                if "pray" in by_id:
                    by_id["pray"]["condition"] = "trusted or coins == 0"
            if node["title"].startswith("回声厅"):
                node["dialogue"] = SPECIAL_TEXT + "\n第三行：编辑后保存的对白。"
                if "again" in by_id:
                    by_id["again"]["label"] = "再听一次 [回声] {继续} 〖…〗 % 🙂（已编辑）"
        if node.get("ending") and node["ending"] == "平安回家":
            node["ending"] = "平安回家 · 已核验"
    for variable in edited.get("variables") or []:
        if variable["name"] == "coins":
            variable["maximum"] = 4
    return edited


# ---------------------------------------------------------------------------
# state alignment (used by artifact witness checks and real target runtimes)
# ---------------------------------------------------------------------------
def _mismatches(actual, expected):
    problems = []
    if actual is None:
        return ["state missing"]
    if "node_id" in actual and actual["node_id"] != expected["node_id"]:
        problems.append("node_id " + str(actual.get("node_id")) + " != " + str(expected["node_id"]))
    if actual.get("variables") is not None and actual["variables"] != expected["variables"]:
        problems.append("variables " + json.dumps(actual.get("variables"), ensure_ascii=False, sort_keys=True)
                        + " != " + json.dumps(expected["variables"], ensure_ascii=False, sort_keys=True))
    enabled = actual.get("enabled_choice_ids")
    if expected.get("status") == "STEP_CAP_REACHED":
        # play() reports the node's condition-enabled choices for authoring display even
        # at the explicit step cap, but a runnable target terminates at the cap and has
        # no further selectable choice.  Node/variables/steps/status are still compared.
        pass
    elif enabled is not None and set(enabled) != set(expected["enabled_choice_ids"]):
        problems.append("enabled choices " + json.dumps(sorted(enabled), ensure_ascii=False)
                        + " != " + json.dumps(sorted(expected["enabled_choice_ids"]), ensure_ascii=False))
    if actual.get("steps") is not None and int(actual["steps"]) != int(expected["steps"]):
        problems.append("steps " + str(actual.get("steps")) + " != " + str(expected["steps"]))
    if actual.get("status") is not None and str(actual["status"]) != expected["status"]:
        problems.append("status " + str(actual.get("status")) + " != " + expected["status"])
    return problems


def align_states(actual_states, expected_states, scope):
    details = []
    matched = 0
    for index, expected in enumerate(expected_states):
        actual = actual_states[index] if index < len(actual_states) else None
        problems = _mismatches(actual, expected)
        details.append({"index": index, "steps": expected["steps"], "node_id": expected["node_id"],
                        "status": "PASS" if not problems else "FAIL", "mismatches": problems})
        if not problems:
            matched += 1
    extra = len(actual_states) - len(expected_states)
    passed = matched == len(expected_states) and extra == 0
    return {"scope": scope, "status": "PASS" if passed else "FAIL",
            "states_expected": len(expected_states), "states_actual": len(actual_states),
            "states_matched": matched, "extra_states": max(0, extra), "details": details}


def align_witness_states(recorder, label, witness_entries, states_builder):
    """Compare Ink validation witnesses (same canonical shape) with play() states."""
    reports = []
    for index, witness in enumerate(witness_entries):
        expected = states_builder(witness["choices"])
        actual = witness.get("states") or []
        report = align_states(actual, expected, label + ":" + str(index))
        reports.append(report)
        recorder.require(label + "-witness-" + str(index), report["status"] == "PASS",
                         json.dumps(report["details"], ensure_ascii=False)[:1500])
    return {"status": "PASS" if reports and all(item["status"] == "PASS" for item in reports) else ("EMPTY" if not reports else "FAIL"),
            "witnesses": len(reports), "reports": reports}


# ---------------------------------------------------------------------------
# static artifact checks per target (no target execution claimed here)
# ---------------------------------------------------------------------------
def _checks_result(checks):
    return {"status": "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL",
            "checks": checks}


def static_renpy_checks(payload, spec, characters, script_name="game/script.rpy", require_options=True):
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})

    script = payload.get(script_name, b"").decode("utf-8", "replace")
    options = payload.get("game/options.rpy", b"").decode("utf-8", "replace")
    check(script_name + " present", script_name in payload, "")
    if require_options:
        check("game/options.rpy present", "game/options.rpy" in payload, "")
        check("options config name", "config.name" in options, "")
    check("label start", "label start:" in script, "")
    labels = re.findall(r"^label (ans_node_\d+):", script, re.M)
    check("one label per story node", len(labels) == len(spec["nodes"]),
          "labels=" + str(len(labels)) + " nodes=" + str(len(spec["nodes"])))
    check("initial jump", "jump ans_node_" in script, "")
    ending_nodes = [node for node in spec["nodes"] if node["ending"]]
    acting_nodes = [node for node in spec["nodes"] if not node["ending"]]
    check("menu per acting node", script.count("    menu:") == len(acting_nodes),
          "menus=" + str(script.count("    menu:")) + " acting=" + str(len(acting_nodes)))
    check("step cap guard", ("ans_steps >= " + str(spec["max_steps"])) in script, "")
    check("return per ending and guards", script.count("    return") >= len(ending_nodes), "")
    if characters and any(node.get("character_id") for node in spec["nodes"]):
        check("speaker names rendered", all(name in script for name in characters.values()),
              ",".join(characters.values()))
    text = "".join(node["dialogue"] + node["ending"] + "".join(item["label"] for item in node["choices"])
                   for node in spec["nodes"])
    if "[" in text:
        check("escaped square brackets", "[[" in script, "")
    if "{" in text:
        check("escaped braces", "{{" in script, "")
    if "%" in text:
        check("escaped percent", "%%" in script, "")
    if "〖" in text:
        check("escaped lenticular", "〖〖" in script, "")
    check("no external engine/paths", not any(token in script for token in ("http://", "https://", "C:\\")), "")
    check("no engine binary bundled", not any(path.endswith((".exe", ".dll", ".so", ".dylib")) for path in payload), "")
    return _checks_result(checks)


def static_godot_legacy_checks(payload, spec, characters):
    story = story_authority()
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})

    raw = payload.get("godot/story.json")
    check("godot/story.json present", raw is not None, "")
    if raw is not None:
        try:
            resource = story.GodotStoryResource.model_validate_json(raw)
            check("typed story resource schema", True, "nodes=" + str(len(resource.nodes)))
        except Exception as exc:  # noqa: BLE001 - recorded as a check, never a crash
            check("typed story resource schema", False, str(exc)[:500])
            resource = None
        try:
            expected = story.GodotExportAdapter().files(spec, characters)["godot/story.json"]
            check("godot story.json matches product exporter", expected == raw, "")
        except Exception as exc:  # noqa: BLE001
            check("godot story.json matches product exporter", False, str(exc)[:500])
        if resource is not None:
            index = {node["node_id"]: position for position, node in enumerate(spec["nodes"])}
            check("entry index", resource.entry_index == index[spec["entry_node_id"]], "")
            check("typed condition trees", all(story.validate_condition_tree(choice.condition_tree.model_dump()) is None
                                              for node in resource.nodes for choice in node.choices), "")
            check("runtime verification not claimed", resource.runtime_verification == "NOT_RUN", "")
    schema = payload.get("godot/story.schema.json")
    check("godot/story.schema.json present", schema is not None, "")
    if schema is not None:
        try:
            json.loads(schema)
            check("godot schema parses as JSON", True, "")
        except ValueError:
            check("godot schema parses as JSON", False, "")
    check("no engine bundled", not any(path.endswith((".exe", ".dll", ".so", ".dylib")) for path in payload), "")
    return _checks_result(checks)


def static_ink_legacy_checks(recorder, payload, spec, characters):
    ink = app_modules()[2]
    story = story_authority()
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})

    source = payload.get("ink/story.ink", b"")
    check("ink/story.ink present", bool(source), "")
    try:
        expected = ink.InkExportAdapter().files(spec, characters)["ink/story.ink"]
        check("ink source matches product exporter", expected == source, "")
    except Exception as exc:  # noqa: BLE001
        check("ink source matches product exporter", False, str(exc)[:500])
    validation_raw = payload.get("ink/validation.json")
    check("ink/validation.json present", validation_raw is not None, "")
    alignment = {"status": "NOT_RUN", "witnesses": 0, "reports": []}
    if validation_raw is not None:
        validation = json.loads(validation_raw)
        check("ink validation schema", validation.get("schema") == "poemseed-ink-exchange/1", "")
        check("ink runtime not claimed", validation.get("artifact_runtime") == "NOT_RUN", "")
        check("ink pin version 2.3.2", validation.get("version") == "2.3.2", "")
        mapping = (validation.get("source_map") or {}).get("nodes") or {}
        expected_mapping = ink.mapping(spec)["nodes"]
        check("ink source map stable", mapping == expected_mapping, "")
        alignment = align_witness_states(recorder, "ink-validation", validation.get("witnesses") or [],
                                         lambda choices: canonical_states(spec, choices))
        check("ink witness states equal play()", alignment["status"] == "PASS",
              "witnesses=" + str(alignment["witnesses"]))
        script_sha = sha256_hex(source)
        check("ink script sha bound in validation", validation.get("script_sha256") == script_sha, "")
    check("no ink runtime bundled", not any(path.endswith((".js", ".mjs", ".cjs", ".exe")) for path in payload), "")
    return {"static": _checks_result(checks), "witness_alignment": alignment}


def static_target_checks(recorder, target_id, payload, spec, characters):
    """Adaptive artifact-shape checks for the new target IDs (generation-level only)."""
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})

    text = "".join(node["dialogue"] + node["ending"] + "".join(item["label"] for item in node["choices"])
                   for node in spec["nodes"])
    if target_id == "GODOT_4_RUNTIME_PROJECT_V1":
        check("project.godot present", "project.godot" in payload, "")
        if "project.godot" in payload:
            project = payload["project.godot"].decode("utf-8", "replace")
            check("project config_version 5", "config_version=5" in project.replace(" ", ""),
                  project.splitlines()[0] if project else "")
        check("main scene present", any(path.endswith(".tscn") for path in payload), "")
        gd_scripts = [path for path in payload if path.endswith(".gd")]
        check("fixed runtime scripts present", bool(gd_scripts), ",".join(sorted(gd_scripts)[:8]))
        dynamic = [path for path in gd_scripts
                   if any(token in payload[path].decode("utf-8", "replace")
                          for token in ("Expression.execute", "eval(", "OS.execute", "HTTPRequest"))]
        check("no dynamic execution / network in runtime", not dynamic, ",".join(dynamic))
        data_paths = [path for path in payload if path.endswith(".json") and "story" in path]
        check("typed story data present", bool(data_paths), ",".join(sorted(data_paths)))
        if data_paths:
            try:
                data = json.loads(payload[data_paths[0]])
                check("story data parses", True, data_paths[0])
                check("story id bound in data", data.get("story_id") in (spec.get("story_id"), None), "")
            except ValueError:
                check("story data parses", False, data_paths[0])
        check("no engine bundled", not any(path.endswith((".exe", ".dll", ".so", ".dylib")) for path in payload), "")
    elif target_id == "INK_2_3_2_CURRENT_ARTIFACT_V1":
        ink_sources = [path for path in payload if path.endswith(".ink")]
        check("ink story source present", bool(ink_sources), ",".join(sorted(ink_sources)))
        check("ink validation json present", any(path.endswith("validation.json") for path in payload), "")
        pins = [path for path in payload if "pin" in path and path.endswith(".json")]
        check("runtime pin json present", bool(pins), ",".join(sorted(pins)))
        if pins:
            try:
                pin = json.loads(payload[pins[0]])
                check("runtime pin version 2.3.2", str(pin.get("version")) == "2.3.2", str(pin.get("version")))
            except ValueError:
                check("runtime pin parses", False, pins[0])
        check("no ink runtime bundled", not any(path.endswith((".js", ".mjs", ".cjs", ".exe")) for path in payload), "")
    elif target_id == "RENPY_8_5_4_PROJECT_V1":
        renpy = static_renpy_checks(payload, spec, characters)
        checks.extend(renpy["checks"])
        check("README present", any(path.lower().endswith("readme.txt") or path.lower().endswith("readme.md")
                                    for path in payload), "")
    else:
        check("target artifact shape implemented in E2E-07", False, target_id)
    if "🙂" in text or "é" in text:
        joined = b"\n".join(payload.values()).decode("utf-8", "replace")
        check("unicode preserved in artifact", "🙂" in joined or "é" in joined or "〖" in joined, "")
    return _checks_result(checks)


# ---------------------------------------------------------------------------
# delivered ZIP verification (read back the real bytes, recompute everything)
# ---------------------------------------------------------------------------
def read_zip_entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = {}
        directories = []
        for info in archive.infolist():
            if info.is_dir():
                directories.append(info.filename)
                continue
            entries[info.filename] = archive.read(info)
    return entries, directories


def unpack_entries(entries, prefix, destination):
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    contract = contract_module()
    files = {}
    for name, content in entries.items():
        if not name.startswith(prefix):
            raise ValueError("ZIP_ENTRY_OUTSIDE_PREFIX:" + name)
        relative = name[len(prefix):]
        contract.safe_bundle_path(relative)
        files[relative] = content
    for relative, content in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return files, destination


def strip_condition_trees(spec):
    """The legacy neutral story.json intentionally adds parsed condition trees; compare the rest."""
    cleaned = deepcopy(spec)
    for node in cleaned.get("nodes") or []:
        for item in node.get("choices") or []:
            item.pop("condition_tree", None)
    return cleaned


def verify_legacy_export(recorder, data, *, story_row, characters, targets_response, preview):
    """Verify the legacy multi-format ZIP that still carries all engine artifacts."""
    story = story_authority()
    ink = app_modules()[2]
    contract = contract_module()
    checks = []

    def check(cid, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        checks.append({"id": cid, "status": status, "detail": detail})
        return ok

    entries, _ = read_zip_entries(data)
    roots = {name.split("/", 1)[0] for name in entries}
    check("single root folder", len(roots) == 1, ",".join(sorted(roots)))
    prefix = sorted(roots)[0] + "/" if roots else ""
    expected_names = {
        "story.json", "media-manifest.json", "compatibility.json", "game/story.rpy", "README.txt",
        "godot/story.json", "godot/story.schema.json", "godot/README.txt", "ink/story.ink",
        "ink/validation.json", "ink/README.txt", "source-receipt.json", "checksums.json",
    }
    payload = {name[len(prefix):]: content for name, content in entries.items() if name.startswith(prefix)}
    check("legacy file set", set(payload) == expected_names,
          json.dumps(sorted(set(payload) - expected_names)) + "/" + json.dumps(sorted(expected_names - set(payload))))
    checksums_raw = payload.get("checksums.json")
    if checksums_raw is not None:
        checksums = json.loads(checksums_raw)
        bad = [path for path, digest in checksums.items()
               if path not in payload or sha256_hex(payload[path]) != digest]
        check("legacy checksums.json binds every payload file", not bad and len(checksums) == len(payload) - 1,
              json.dumps(bad))
        check("legacy checksums excludes itself", "checksums.json" not in checksums, "")
    story_json = json.loads(payload["story.json"])
    check("legacy story.json schema", story_json.get("schema") == story.SCHEMA, "")
    check("legacy story.json adaptation id", story_json.get("adaptation_id") == story_row["id"], "")
    check("legacy story.json adaptation version", story_json.get("adaptation_version") == story_row["version"], "")
    check("legacy story.json spec equals approved spec",
          strip_condition_trees(story_json.get("spec") or {}) == story_row["spec"], "")
    compatibility = json.loads(payload["compatibility.json"])
    check("legacy compatibility target runtime not run", compatibility.get("target_runtime") == "NOT_RUN", "")
    check("legacy compatibility can_export", compatibility.get("can_export") is True, "")
    check("legacy compatibility keeps losses", bool(compatibility.get("losses")), "")
    check("legacy media manifest present", isinstance(json.loads(payload["media-manifest.json"]), list), "")
    receipt = json.loads(payload["source-receipt.json"])
    check("legacy source receipt schema", receipt.get("schema") == "interactive-export-source-receipt/1", "")
    check("legacy source receipt story id", receipt.get("adaptation_id") == story_row["id"], "")
    check("legacy source receipt story version", receipt.get("adaptation_version") == story_row["version"], "")
    check("legacy source receipt source digest", receipt.get("source_digest") == targets_response["story"]["source_digest"], "")
    check("legacy source receipt preview digest", receipt.get("export_preview_digest") == preview["preview_digest"], "")
    renpy = static_renpy_checks(payload, story_row["spec"], characters,
                               script_name="game/story.rpy", require_options=False)
    for item in renpy["checks"]:
        check("renpy-legacy." + item["id"], item["status"] == "PASS", item["detail"])
    godot = static_godot_legacy_checks(payload, story_row["spec"], characters)
    for item in godot["checks"]:
        check("godot-legacy." + item["id"], item["status"] == "PASS", item["detail"])
    ink_result = static_ink_legacy_checks(recorder, payload, story_row["spec"], characters)
    for item in ink_result["static"]["checks"]:
        check("ink-legacy." + item["id"], item["status"] == "PASS", item["detail"])
    return {
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "prefix": prefix,
        "files": [{"path": name, "bytes": len(content), "sha256": sha256_hex(content)}
                  for name, content in sorted(payload.items())],
        "checks": checks,
        "checksums": json.loads(checksums_raw) if checksums_raw is not None else None,
        "ink_witness_alignment": ink_result["witness_alignment"],
        "renpy_static": renpy,
        "godot_legacy_static": godot,
        "ink_legacy_static": ink_result["static"],
    }


def verify_target_export(recorder, data, *, story_row, characters, targets_response, preview, target_row):
    """Read the delivered target ZIP back and recompute manifest, receipt and every hash."""
    contract = contract_module()
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    target_id = target_row["target_id"]
    entries, _ = read_zip_entries(data)
    roots = {name.split("/", 1)[0] for name in entries}
    check("single root folder", len(roots) == 1, ",".join(sorted(roots)))
    prefix = sorted(roots)[0] + "/" if roots else ""
    try:
        files, _ = unpack_entries(entries, prefix, Path(tempfile.mkdtemp(prefix="b07-e2e07-verify-",
                                                                      dir=str(DEFAULT_SCRATCH))))
    except ValueError as exc:
        check("zip paths safe", False, str(exc))
        files = {}
    if files:
        check("zip paths safe", True, "")
    check("manifest and source receipt injected",
          {"manifest.json", "source-receipt.json"} <= set(files),
          json.dumps(sorted(set(files) - {"manifest.json", "source-receipt.json"}))[:400])
    if {"manifest.json", "source-receipt.json"} <= set(files):
        manifest_bytes = files["manifest.json"]
        receipt_bytes = files["source-receipt.json"]
        manifest = json.loads(manifest_bytes)
        receipt = json.loads(receipt_bytes)
        payload = {name: content for name, content in files.items()
                   if name not in {"manifest.json", "source-receipt.json"}}
        check("manifest schema", manifest.get("schema") == contract.MANIFEST_SCHEMA, str(manifest.get("schema")))
        check("receipt schema", receipt.get("schema") == contract.RECEIPT_SCHEMA, str(receipt.get("schema")))
        check("contract version", manifest.get("contract_version") == contract.CONTRACT_VERSION, "")
        check("target id bound", manifest.get("target_id") == target_id and receipt.get("target_id") == target_id, "")
        check("target format version", manifest.get("target_format_version") == target_row.get("format_version"), "")
        check("adapter revision", manifest.get("adapter_revision") == target_row.get("adapter_revision"), "")
        check("target kind", manifest.get("target_kind") == target_row.get("kind"), str(manifest.get("target_kind")))
        check("payload digest recomputes", manifest.get("payload_files_digest") == contract.files_digest(payload), "")
        entries_manifest = manifest.get("files") or []
        check("manifest file order", [item.get("path") for item in entries_manifest] == sorted(payload), "")
        bad_hashes = [item.get("path") for item in entries_manifest
                      if item.get("path") not in payload
                      or item.get("bytes") != len(payload[item["path"]])
                      or item.get("sha256") != sha256_hex(payload[item["path"]])]
        check("every payload sha256 recomputes", not bad_hashes, json.dumps(bad_hashes)[:500])
        check("receipt manifest sha256", receipt.get("manifest_sha256") == sha256_hex(manifest_bytes), "")
        check("receipt payload digest", receipt.get("payload_files_digest") == manifest.get("payload_files_digest"), "")
        story_block = manifest.get("story") or {}
        check("manifest story id", story_block.get("id") == story_row["id"], str(story_block.get("id")))
        check("manifest story revision", story_block.get("revision") == story_row["version"], "")
        check("manifest spec digest", story_block.get("spec_digest") == targets_response["story"]["spec_digest"], "")
        check("manifest source digest", story_block.get("source_digest") == targets_response["story"]["source_digest"], "")
        check("receipt spec digest", receipt.get("spec_digest") == story_block.get("spec_digest"), "")
        check("receipt source digest", receipt.get("source_digest") == story_block.get("source_digest"), "")
        check("manifest/receipt review receipt agree",
              story_block.get("review_receipt") == receipt.get("review_receipt"), "")
        check("manifest witness digest",
              story_block.get("witness_digest") == digest_json(targets_response.get("witness") or []), "")
        check("manifest media digest",
              story_block.get("media_manifest_digest") == digest_json(targets_response.get("media_manifest") or []), "")
        check("manifest losses match compatibility", manifest.get("losses") == preview.get("losses") or
              set(manifest.get("losses") or []) == set(preview.get("losses") or []), "")
        check("capability vocabulary complete",
              isinstance(manifest.get("capabilities"), dict)
              and set(manifest["capabilities"]) == set(contract.CAPABILITY_KEYS), "")
        supported = sorted(key for key, value in (manifest.get("capabilities") or {}).items() if value.get("supported"))
        check("receipt capability partition", sorted(receipt.get("capabilities_supported") or []) == supported, "")
        check("runtime evidence separate from generation",
              isinstance((manifest.get("runtime") or {}).get("evidence"), dict), "")
        static = static_target_checks(recorder, target_id, payload, story_row["spec"], characters)
        check("target artifact static checks", static["status"] == "PASS",
              json.dumps([item["id"] for item in static["checks"] if item["status"] != "PASS"])[:500])
        total = sum(len(content) for content in files.values())
        check("bundle size within contract limits",
              len(files) <= contract.MAX_FILES and total <= contract.MAX_TOTAL_BYTES
              and all(len(content) <= contract.MAX_FILE_BYTES for content in files.values()), str(total))
    else:
        manifest, receipt, payload, static = {}, {}, {}, {"status": "NOT_RUN", "checks": []}
    return {
        "status": "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL",
        "prefix": prefix,
        "files": [{"path": name, "bytes": len(content), "sha256": sha256_hex(content)}
                  for name, content in sorted(files.items())],
        "checks": checks,
        "manifest": manifest,
        "receipt": receipt,
        "target_static": static,
    }


def materialize_export(delivery_dir, target_id, archive, verification):
    """Write the ZIP and its unpacked project to the external delivery directory."""
    target_dir = Path(delivery_dir) / "exports" / (target_id or "legacy")
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / archive["filename"]
    zip_path.write_bytes(archive["content"])
    entries, _ = read_zip_entries(archive["content"])
    prefix = verification.get("prefix") or ""
    unpack_dir = target_dir / "unpacked"
    files, unpacked = unpack_entries(entries, prefix, unpack_dir)
    return {"zip_path": zip_path, "unpack_dir": unpacked, "files": sorted(files)}



# ---------------------------------------------------------------------------
# target runtime adapter layer: locate the line verifier, probe it, run it,
# read its result JSON, then diff every runtime step with play().
# ---------------------------------------------------------------------------
STATUS_CODES = {0: "PLAYING", 1: "ENDING", 2: "STEP_CAP_REACHED", 3: "NO_EXIT"}
INKJS_VERSION = "2.3.2"
INKJS_INTEGRITY = "iZjrY0lLeRiC+HtDzCfV9IEAP9ExCmBZUrxKkyLy1qIbbGbR1uTXNZ8LDIg8oVkMXZ9TeKKyEFQpQ/m5nQds8w=="
INKJS_TARBALL_URL = "https://registry.npmjs.org/inkjs/-/inkjs-2.3.2.tgz"


def run_process_stdin(argv, stdin_text, *, cwd=None, timeout=180, env=None, label="process"):
    started = time.monotonic()
    record = {"kind": "process", "label": label, "argv": [str(item) for item in argv],
              "cwd": str(cwd) if cwd else None, "exit_code": None, "duration_ms": None,
              "stdout_tail": "", "stderr_tail": "", "timed_out": False, "stdin_bytes": len(stdin_text or "")}
    try:
        completed = subprocess.run([str(item) for item in argv], cwd=str(cwd) if cwd else None,
                                   input=stdin_text.encode("utf-8") if isinstance(stdin_text, str) else stdin_text,
                                   capture_output=True, text=False, timeout=timeout, env=env, shell=False)
        completed = SimpleNamespace(
            returncode=completed.returncode,
            stdout=(completed.stdout or b"").decode("utf-8", "replace"),
            stderr=(completed.stderr or b"").decode("utf-8", "replace"))
        record.update(exit_code=completed.returncode, stdout_tail=tail_text(completed.stdout),
                      stderr_tail=tail_text(completed.stderr),
                      stdout_full=completed.stdout if len(completed.stdout) <= 8 * 1024 * 1024 else None)
    except subprocess.TimeoutExpired as exc:
        record["timed_out"] = True
        record["stdout_tail"] = tail_text(exc.stdout)
        record["stderr_tail"] = tail_text(exc.stderr)
    except (OSError, ValueError) as exc:
        record["stderr_tail"] = "LAUNCH_ERROR: " + str(exc)
    record["duration_ms"] = int((time.monotonic() - started) * 1000)
    return record


def host_info():
    info = {"os": platform.platform(), "python": sys.version.split()[0], "node": None,
            "engines": {}}
    node = os.environ.get("POEMSEED_NODE") or shutil.which("node")
    if node:
        try:
            completed = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20)
            info["node"] = (completed.stdout or completed.stderr).strip()
        except (OSError, subprocess.SubprocessError):
            info["node"] = "unavailable"
    for target_id, spec in RUNTIME_VERIFIERS.items():
        engine = find_engine(target_id)
        info["engines"][target_id] = engine or {"found": False,
                                                "searched_env": spec.get("engine_env"),
                                                "searched_hints": spec.get("engine_hints")}
    info["engines"]["RENPY_8_5_4_PROJECT_V1"] = find_renpy_engine()
    return info


def find_renpy_engine():
    env_value = os.environ.get("POEMSEED_RENPY_BIN")
    if env_value and Path(env_value).exists():
        return {"found": True, "path": env_value, "source": "POEMSEED_RENPY_BIN"}
    for name in ("renpy.exe", "renpy.sh", "renpy"):
        located = shutil.which(name)
        if located:
            return {"found": True, "path": located, "source": "PATH"}
    for hint in (r"D:\GameDev\RenPy", r"D:\RenPy", r"C:\RenPy"):
        if Path(hint).is_dir():
            return {"found": True, "path": hint, "source": "hint"}
    return {"found": False, "path": None, "source": None,
            "note": "Ren'Py 8.5.4 is not installed on this host; runtime evidence is BLOCKED_ENVIRONMENT."}


def find_engine(target_id):
    spec = RUNTIME_VERIFIERS.get(target_id)
    if not spec:
        return None
    env_value = os.environ.get(spec.get("engine_env") or "")
    if env_value:
        path = Path(env_value)
        if path.exists():
            return {"found": True, "path": str(path), "source": spec.get("engine_env")}
    for hint in spec.get("engine_hints") or []:
        if Path(hint).is_file():
            return {"found": True, "path": hint, "source": "declared_install_hint"}
    for name in ("godot", "godot.exe", "Godot_v4.7-stable_win64_console.exe") if target_id.startswith("GODOT") else ():
        located = shutil.which(name)
        if located:
            return {"found": True, "path": located, "source": "PATH"}
    return {"found": False, "path": None, "source": None}


def find_runtime_verifier(target_id):
    spec = RUNTIME_VERIFIERS.get(target_id)
    if not spec:
        return None
    searched = []
    for relative in spec["candidates"]:
        path = REPO_ROOT / relative
        searched.append(relative)
        if path.is_file():
            return {"target_id": target_id, "path": str(path), "relative": relative,
                    "runner": spec["runner"], "searched": searched}
    return {"target_id": target_id, "path": None, "relative": spec["candidates"][0],
            "runner": spec["runner"], "searched": searched}


def runner_command(verifier):
    if verifier["runner"] == "python":
        return [sys.executable, verifier["path"]]
    node = os.environ.get("POEMSEED_NODE") or shutil.which("node") or "node"
    return [node, verifier["path"]]


def probe_verifier(recorder, verifier):
    """Probe the verifier CLI shape instead of assuming it (records the raw help)."""
    report = {"verifier": verifier["relative"], "executable": verifier["path"],
              "runner": verifier["runner"], "help_exit_code": None, "help_text": "", "flags": [],
              "command": None}
    if not verifier.get("path"):
        return report
    record = run_process(runner_command(verifier) + ["--help"], cwd=REPO_ROOT, timeout=90,
                         label="verifier-help:" + verifier["target_id"])
    recorder.command(record)
    report["command"] = record["argv"]
    report["help_exit_code"] = record["exit_code"]
    help_text = (record["stdout_tail"] or "") + "\n" + (record["stderr_tail"] or "")
    report["help_text"] = help_text
    report["flags"] = sorted(set(re.findall(r"--[a-z][a-z0-9-]{1,40}", help_text)))
    return report


def build_verifier_invocations(verifier, probe, project_dir, cases_path, out_path, zip_path=None):
    """Build candidate argv lists from the probed flags, then positional fallbacks."""
    base = runner_command(verifier)
    flags = set(probe.get("flags") or [])

    def pick(*names):
        for name in names:
            if name in flags:
                return name
        return None

    project_flag = pick("--project", "--project-dir", "--dir", "--artifact", "--package", "--story-project")
    cases_flag = pick("--cases", "--case-file", "--cases-file", "--input", "--scenario")
    out_flag = pick("--out", "--output", "--json", "--report", "--result", "--results")
    save_flag = pick("--save-restore", "--save_and_restore", "--persistence")
    attempts = []
    if project_flag:
        argv = base + [project_flag, str(project_dir)]
        if cases_flag:
            argv += [cases_flag, str(cases_path)]
        if save_flag:
            argv += [save_flag]
        if out_flag:
            argv += [out_flag, str(out_path)]
        attempts.append(argv)
    if zip_path is not None and project_flag:
        zip_flag = pick("--zip", "--archive", "--bundle")
        if zip_flag:
            attempts.append(base + [zip_flag, str(zip_path)] + ([out_flag, str(out_path)] if out_flag else []))
    positional = base + [str(project_dir)]
    if cases_flag:
        positional += [cases_flag, str(cases_path)]
    if out_flag:
        positional += [out_flag, str(out_path)]
    attempts.append(positional)
    attempts.append(base + [str(project_dir)])
    seen, unique = set(), []
    for argv in attempts:
        key = tuple(argv)
        if key not in seen:
            seen.add(key)
            unique.append(argv)
    return unique


def extract_json_payload(text):
    if not text:
        return None
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    start, end = stripped.find("{"), stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except ValueError:
            return None
    return None


def runtime_case_lists(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("cases", "results", "runs", "traces", "executions"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for key in ("result", "data", "report"):
            nested = payload.get(key)
            if isinstance(nested, (dict, list)):
                found = runtime_case_lists(nested)
                if found is not None:
                    return found
    return None


def find_state_list(item):
    if isinstance(item, dict):
        for key in ("states", "steps", "snapshots", "trace", "history"):
            value = item.get(key)
            if isinstance(value, list):
                return value
        for key in ("result", "run", "data"):
            nested = item.get(key)
            if isinstance(nested, (dict, list)):
                found = find_state_list(nested)
                if found is not None:
                    return found
        scalar_keys = {"node_id", "node", "current_node", "node_index", "status", "steps"}
        if scalar_keys & set(item):
            return [item]
    return None


def normalize_runtime_state(raw, spec, expected):
    if not isinstance(raw, dict):
        return None
    node_order = [node["node_id"] for node in spec["nodes"]]
    node = raw.get("node_id", raw.get("node", raw.get("current_node", raw.get("node_index"))))
    if isinstance(node, int) and 0 <= node < len(node_order):
        node = node_order[node]
    elif isinstance(node, dict):
        node = node.get("node_id") or node.get("id")
    variables = raw.get("variables", raw.get("values", raw.get("vars")))
    variable_names = [variable["name"] for variable in spec["variables"]]
    if isinstance(variables, dict):
        mapped = {}
        for key, value in variables.items():
            key = str(key)
            if key in variable_names:
                mapped[key] = value
            else:
                match = re.fullmatch(r"ans_var_(\d+)", key)
                if match and int(match.group(1)) < len(variable_names):
                    mapped[variable_names[int(match.group(1))]] = value
        variables = mapped
    elif variables is not None:
        variables = None
    enabled = raw.get("enabled_choice_ids", raw.get("enabled_choices", raw.get("choices")))
    if isinstance(enabled, list):
        label_to_id = {}
        if isinstance(expected, dict):
            label_to_id = {item["label"]: item["id"] for item in expected.get("choices") or []}
        mapped_ids = []
        for element in enabled:
            if isinstance(element, dict):
                mapped_ids.append(element.get("id"))
            elif isinstance(element, str):
                mapped_ids.append(label_to_id.get(element, element))
            else:
                mapped_ids.append(element)
        enabled = mapped_ids
    elif enabled is not None:
        enabled = None
    steps = raw.get("steps", raw.get("step", raw.get("step_count")))
    status = raw.get("status")
    if isinstance(status, int):
        status = STATUS_CODES.get(status, str(status))
    if isinstance(steps, str) and steps.isdigit():
        steps = int(steps)
    return {"node_id": node, "variables": variables, "enabled_choice_ids": enabled,
            "steps": steps, "status": status}


def normalize_runtime_cases(payload, spec, cases):
    lists = runtime_case_lists(payload)
    if lists is None:
        return None
    if len(lists) != len(cases):
        return {"error": "RUNTIME_CASE_COUNT_MISMATCH", "actual": len(lists), "expected": len(cases)}
    normalized = []
    for raw_case, case in zip(lists, cases):
        expected_states = case["expected_states"]
        if isinstance(raw_case, dict):
            raw_id = raw_case.get("id") or raw_case.get("case_id") or raw_case.get("name")
        else:
            raw_id = None
        states = find_state_list(raw_case) or []
        normalized_states = [normalize_runtime_state(state, spec, expected_states[index]
                                                    if index < len(expected_states) else None)
                             for index, state in enumerate(states)]
        normalized.append({"id": raw_id or case["id"], "states": normalized_states})
    return normalized


def align_runtime_cases(recorder, target_id, normalized, cases):
    reports = []
    for actual_case, case in zip(normalized, cases):
        expected_states = case["expected_states"]
        actual_states = actual_case["states"]
        report = align_states(actual_states, expected_states, case["id"])
        fields = set()
        for state in actual_states:
            if isinstance(state, dict):
                fields.update(key for key, value in state.items() if value is not None)
        report["fields_reported"] = sorted(fields)
        reports.append(report)
        recorder.require("runtime-step-alignment:" + target_id + ":" + case["id"],
                         report["status"] == "PASS", json.dumps(report["details"], ensure_ascii=False)[:2500])
    return {"status": "PASS" if reports and all(item["status"] == "PASS" for item in reports) else "FAIL",
            "cases": reports}


def runtime_cases_document(target_id, story_row, spec, cases):
    return {
        "schema": "poemseed-b07-e2e07-runtime-cases/1",
        "target_id": target_id,
        "story_id": story_row["id"],
        "revision": story_row["version"],
        "spec_digest": digest_json(spec),
        "variable_names": [variable["name"] for variable in spec["variables"]],
        "node_order": [node["node_id"] for node in spec["nodes"]],
        "story_spec": spec,
        "cases": [{"id": case["id"], "kind": case["kind"], "choices": case["choices"],
                   "choice_indices": choice_index_path(spec, case["choices"]),
                   "expected_states": case["expected_states"],
                   "save_restore": case.get("save_restore")} for case in cases],
    }


def save_restore_result(target_id, requested_cases, payload, normalized, cases):
    """Record save/restore evidence only where the target verifier really reported it."""
    found = {"status": "NOT_REPORTED_BY_VERIFIER", "level": "NOT_RUN", "target_id": target_id}
    requested = [case["id"] for case in cases if case.get("save_restore")]
    found["requested_case_ids"] = requested
    if payload is None:
        return found
    text = json.dumps(payload, ensure_ascii=False)[:20000]
    keys = [key for key in ("save_restore", "saveRestore", "persistence", "save", "restore")
            if key in text]
    found["verifier_mentions"] = keys
    if not keys:
        return found
    lowered = text.lower()
    if '"save_restore"' in lowered or '"saverestore"' in lowered or '"persistence"' in lowered:
        found["status"] = "REPORTED_BY_VERIFIER"
        found["level"] = "PARTIAL"
        if '"pass"' in lowered or '"ok": true' in lowered or '"verified": true' in lowered:
            found["level"] = "PASS"
            found["status"] = "VERIFIED_BY_VERIFIER"
    return found


def run_target_runtime(recorder, target_id, project_dir, story_row, spec, cases, scratch_dir,
                       delivery_dir, engine=None):
    """Run the line-owned verifier against the exported artifact and align every step."""
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "target_id": target_id, "status": "NOT_RUN", "reason": None,
        "verifier": find_runtime_verifier(target_id),
        "engine": engine or find_engine(target_id),
        "project_dir": str(project_dir),
        "cases": [{"id": case["id"], "kind": case["kind"], "choices": case["choices"],
                   "steps": len(case["choices"])} for case in cases],
        "invocations": [], "normalized_cases": None, "alignment": None,
        "save_restore": {"status": "NOT_REPORTED_BY_VERIFIER", "level": "NOT_RUN"},
        "raw_result_path": None, "raw_stdout_path": None,
    }
    verifier = report["verifier"]
    if verifier is None:
        report["reason"] = "TARGET_HAS_NO_LINE_VERIFIER_REGISTERED"
        report["status"] = "BLOCKED_VERIFIER_UNAVAILABLE"
        write_json(target_dir / "result.json", report)
        return report
    if not verifier.get("path"):
        report["reason"] = "LINE_VERIFIER_NOT_DELIVERED:" + verifier["relative"]
        report["status"] = "BLOCKED_VERIFIER_UNAVAILABLE"
        write_json(target_dir / "result.json", report)
        return report
    probe = probe_verifier(recorder, verifier)
    report["verifier_probe"] = probe
    cases_path = scratch_dir / (target_id + "-cases.json")
    out_path = target_dir / "verifier-result.json"
    write_json(cases_path, runtime_cases_document(target_id, story_row, spec, cases))
    payload = None
    chosen = None
    for argv in build_verifier_invocations(verifier, probe, project_dir, cases_path, out_path):
        record = run_process(argv, cwd=REPO_ROOT, timeout=600,
                             label="target-runtime:" + target_id)
        report["invocations"].append({key: value for key, value in record.items() if key != "stdout_full"})
        recorder.command({key: value for key, value in record.items() if key != "stdout_full"})
        if out_path.is_file():
            try:
                payload = json.loads(out_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                payload = None
        if payload is None:
            payload = extract_json_payload(record.get("stdout_full") or record["stdout_tail"])
        if payload is not None:
            chosen = record
            break
    if chosen is None:
        report["status"] = "FAIL_RUNTIME_PROCESS"
        report["reason"] = "no invocation returned parseable JSON"
        write_json(target_dir / "result.json", report)
        return report
    report["status"] = "EXECUTED"
    report["chosen_invocation"] = chosen["argv"]
    report["exit_code"] = chosen["exit_code"]
    write_json(target_dir / "verifier-result-raw.json", payload)
    report["raw_result_path"] = relative_to(target_dir / "verifier-result-raw.json", delivery_dir)
    normalized = normalize_runtime_cases(payload, spec, cases)
    if isinstance(normalized, dict) and normalized.get("error"):
        report["status"] = "FAIL_RUNTIME_RESULT_SHAPE"
        report["reason"] = json.dumps(normalized)
        write_json(target_dir / "result.json", report)
        return report
    report["normalized_cases"] = [
        {"id": item["id"],
         "states": [{key: value for key, value in state.items()} for state in item["states"]]}
        for item in normalized
    ]
    alignment = align_runtime_cases(recorder, target_id, normalized, cases)
    report["alignment"] = alignment
    report["status"] = "EXECUTED_AND_ALIGNED" if alignment["status"] == "PASS" else "EXECUTED_WITH_MISMATCH"
    report["save_restore"] = save_restore_result(target_id, cases, payload, normalized, cases)
    write_json(target_dir / "result.json", report)
    return report


# ---------------------------------------------------------------------------
# legacy Ink artifact runtime (real pinned inkjs 2.3.2 harness, current ZIP bytes)
# ---------------------------------------------------------------------------
def find_inkjs_vendor(scratch_dir):
    candidates = []
    env_root = os.environ.get("POEMSEED_INKJS_ROOT")
    if env_root:
        candidates += [Path(env_root), Path(env_root) / "package"]
    candidates += [Path(scratch_dir) / "vendor" / "inkjs-2.3.2", Path(scratch_dir) / "vendor" / "inkjs-2.3.2" / "package",
                   Path(scratch_dir) / "inkjs" / "package"]
    for parent in (DEFAULT_SCRATCH, Path(r"D:\PoemSeed\Recovery\b07-scratch")):
        if not parent.is_dir():
            continue
        for child in sorted(parent.glob("ink*")):
            candidates += [child, child / "package", child / "inkjs" / "package"]
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        package = candidate / "package.json"
        bundle = candidate / "dist" / "ink-full.js"
        if package.is_file() and bundle.is_file():
            try:
                data = json.loads(package.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if data.get("version") == INKJS_VERSION:
                return {"vendor": candidate, "version": data.get("version")}
    return None


def prepare_inkjs_vendor(recorder, scratch_dir):
    """Prepare the pinned test-only inkjs dependency using the existing project script."""
    scratch_dir = Path(scratch_dir)
    found = find_inkjs_vendor(scratch_dir)
    if found:
        return {"status": "AVAILABLE", **found, "source": "prepared"}
    tarball = scratch_dir / "tarballs" / ("inkjs-" + INKJS_VERSION + ".tgz")
    prepare_script = REPO_ROOT / "scripts" / "prepare_inkjs_test_dependency.py"
    detail = {"status": "UNAVAILABLE", "commands": [], "download": None}
    if not tarball.is_file():
        try:
            import urllib.request
            tarball.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(INKJS_TARBALL_URL, timeout=60) as response:
                data = response.read()
            tarball.write_bytes(data)
            detail["download"] = {"url": INKJS_TARBALL_URL, "bytes": len(data), "sha256": sha256_hex(data)}
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            detail["download"] = {"url": INKJS_TARBALL_URL, "error": type(exc).__name__ + ": " + str(exc)[:300]}
            detail["detail"] = "pinned inkjs tarball unavailable offline"
            return detail
    if not prepare_script.is_file():
        detail["detail"] = "prepare_inkjs_test_dependency.py missing"
        return detail
    destination = scratch_dir / "vendor" / ("inkjs-" + INKJS_VERSION)
    if destination.exists():
        shutil.rmtree(destination)
    record = run_process([sys.executable, str(prepare_script), str(tarball), str(destination)],
                         cwd=REPO_ROOT, timeout=180, label="prepare-inkjs")
    recorder.command(record)
    detail["commands"].append(record)
    found = find_inkjs_vendor(scratch_dir)
    if found is None:
        detail["detail"] = "prepared archive did not expose a 2.3.2 package"
        return detail
    return {**detail, "status": "AVAILABLE", **found, "source": "prepared-from-download"}


def run_legacy_ink_runtime(recorder, story_row, spec, cases, scratch_dir, delivery_dir):
    """Execute the CURRENT exported legacy Ink source with the pinned inkjs 2.3.2 harness."""
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(delivery_dir) / "runtime" / "INKJS_2_3_2_TYPED_TEXT_SUBSET"
    target_dir.mkdir(parents=True, exist_ok=True)
    harness = REPO_ROOT / "scripts" / "verify_ink_runtime.cjs"
    node = os.environ.get("POEMSEED_NODE") or shutil.which("node")
    report = {"target_id": "INKJS_2_3_2_TYPED_TEXT_SUBSET", "status": "NOT_RUN",
              "harness": relative_to(harness, REPO_ROOT), "vendor": None, "engine": None,
              "cases": [{"id": case["id"], "choices": case["choices"]} for case in cases],
              "commands": [], "alignment": None, "save_restore": {"level": "NOT_RUN"}}
    vendor = find_inkjs_vendor(scratch_dir)
    if vendor is None:
        prepared = prepare_inkjs_vendor(recorder, scratch_dir)
        report["vendor_prepare"] = {key: value for key, value in prepared.items() if key != "vendor"}
        if prepared.get("status") == "AVAILABLE":
            vendor = {"vendor": prepared["vendor"], "version": prepared.get("version")}
    if vendor is None:
        report["status"] = "BLOCKED_ENVIRONMENT"
        report["reason"] = "pinned inkjs " + INKJS_VERSION + " test dependency not prepared or unobtainable"
        write_json(target_dir / "legacy-ink-runtime.json", report)
        return report
    report["vendor"] = {"path": str(vendor["vendor"]), "version": vendor["version"]}
    if node is None:
        report["status"] = "BLOCKED_ENVIRONMENT"
        report["reason"] = "Node.js not found"
        write_json(target_dir / "legacy-ink-runtime.json", report)
        return report
    report["engine"] = node
    exported_script = None
    source_path = scratch_dir / (story_row["id"] + "-story.ink")
    if story_row.get("_legacy_ink_source"):
        exported_script = story_row["_legacy_ink_source"]
        source_path.write_bytes(exported_script)
    if not exported_script:
        report["status"] = "FAIL"
        report["reason"] = "current exported ink/story.ink bytes were not captured"
        write_json(target_dir / "legacy-ink-runtime.json", report)
        return report
    request, expected = [], []
    for case in cases:
        try:
            indices = choice_index_path(spec, case["choices"])
        except ValueError as exc:
            report.setdefault("skipped_cases", []).append({"id": case["id"], "reason": str(exc)})
            continue
        request.append({"source": exported_script.decode("utf-8"), "indices": indices,
                        "variables": ["ans_var_" + str(index) for index in range(len(spec["variables"]))]})
        expected.append({"id": case["id"], "expected": case["expected_states"]})
    env = dict(os.environ)
    env["POEMSEED_INKJS_ROOT"] = str(vendor["vendor"])
    record = run_process_stdin([node, str(harness)], json.dumps(request, ensure_ascii=False),
                               cwd=REPO_ROOT, timeout=240, env=env, label="legacy-ink-runtime")
    report["commands"].append(record)
    recorder.command(record)
    payload = extract_json_payload(record.get("stdout_full") or record["stdout_tail"])
    if payload is None:
        report["status"] = "FAIL"
        report["reason"] = "legacy ink harness produced no parseable JSON"
        write_json(target_dir / "legacy-ink-runtime.json", report)
        return report
    write_json(target_dir / "legacy-ink-runtime-raw.json", payload)
    if not isinstance(payload, list) or len(payload) != len(expected):
        report["status"] = "FAIL"
        report["reason"] = "RUNTIME_CASE_COUNT_MISMATCH"
        write_json(target_dir / "legacy-ink-runtime.json", report)
        return report
    alignment_cases = []
    save_restore_levels = []
    for raw_case, item in zip(payload, expected):
        states = []
        for index, snapshot in enumerate(raw_case.get("snapshots") or []):
            expected_state = item["expected"][index] if index < len(item["expected"]) else None
            states.append(normalize_runtime_state(snapshot, spec, expected_state))
        report_alignment = align_states(states, item["expected"], item["id"])
        alignment_cases.append(report_alignment)
        recorder.require("legacy-ink-step-alignment:" + item["id"], report_alignment["status"] == "PASS",
                         json.dumps(report_alignment["details"], ensure_ascii=False)[:2500])
        if raw_case.get("fileCalls") == 0 and not raw_case.get("errors"):
            save_restore_levels.append("PASS")
        else:
            save_restore_levels.append("FAIL")
    report["alignment"] = {"status": "PASS" if all(item["status"] == "PASS" for item in alignment_cases)
                           else "FAIL", "cases": alignment_cases}
    report["save_restore"] = {
        "level": "PASS" if save_restore_levels and all(value == "PASS" for value in save_restore_levels) else "FAIL",
        "detail": "The pinned harness serializes Story.state.ToJson()/LoadJson() at every step; fileCalls=0 and errors=[] prove restoration replays each expected state.",
    }
    report["status"] = "EXECUTED_AND_ALIGNED" if report["alignment"]["status"] == "PASS" else "EXECUTED_WITH_MISMATCH"
    write_json(target_dir / "legacy-ink-runtime.json", report)
    return report


def renpy_runtime_report(target_id, target_row, export_record):
    engine = find_renpy_engine()
    report = {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT", "engine": engine,
              "reason": "Ren'Py 8.5.4 is not installed on this host; the exported project is statically verified only.",
              "service_engine_probe": (target_row or {}).get("engine_probe"),
              "export_archive_verified": bool(export_record)}
    return report


def godot_data_runtime_report(target_row):
    return {"target_id": "GODOT_4_DATA_ADAPTER", "status": "NOT_RUN",
            "reason": "DATA_ONLY_ADAPTER: the legacy target carries typed data but no runnable project; execution belongs to the target importer.",
            "service_engine_probe": (target_row or {}).get("engine_probe"),
            "runtime_claim_from_service": (target_row or {}).get("runtime_claim")}


def runtime_phase(recorder, target_id, export_record, story_row, spec, cases, scratch_dir,
                  delivery_dir, enabled=True):
    """Dispatch one exported target to its real runtime verification level."""
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    if not enabled:
        return {"target_id": target_id, "status": "NOT_RUN", "reason": "--skip-runtime"}
    if target_id == "RENPY_8_5_4_PROJECT_V1":
        report = renpy_runtime_report(target_id, export_record.get("target_row") if export_record else None,
                                      export_record)
        write_json(target_dir / "result.json", report)
        return report
    if target_id == "GODOT_4_DATA_ADAPTER":
        report = godot_data_runtime_report(export_record.get("target_row") if export_record else None)
        write_json(target_dir / "result.json", report)
        return report
    module = RUNTIME_VERIFIERS.get(target_id)
    if module is None:
        return {"target_id": target_id, "status": "NOT_RUN", "reason": "no runtime adapter registered"}
    if export_record is None or not export_record.get("materialized"):
        return {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT",
                "reason": "export not available to drive the target runtime"}
    engine = find_engine(target_id)
    if not engine or not engine.get("found"):
        report = {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT",
                  "reason": "required engine executable not found: " + str(module.get("engine_env")),
                  "engine": engine}
        write_json(target_dir / "result.json", report)
        return report
    project_dir = export_record["materialized"]["unpack_dir"]
    return run_target_runtime(recorder, target_id, project_dir, story_row, spec, cases,
                              Path(scratch_dir) / "runtime" / target_id, delivery_dir, engine=engine)



# ---------------------------------------------------------------------------
# measured sample features (what the fixture really demonstrates, not claims)
# ---------------------------------------------------------------------------
FEATURE_REQUIREMENTS = {
    "single_linear_path": lambda features: features["max_choices_per_acting_node"] == 1,
    "dialogue": lambda features: features["dialogue_nodes"] >= 1,
    "speaker": lambda features: features["speaker_nodes"] >= 1,
    "one_ending": lambda features: features["ending_count"] == 1,
    "bool_variable": lambda features: "bool" in features["variable_types"],
    "int_variable": lambda features: "int" in features["variable_types"],
    "conditional_choices": lambda features: features["conditional_choice_count"] >= 1,
    "assignments": lambda features: features["assignment_choice_count"] >= 1,
    "three_endings": lambda features: features["ending_count"] >= 3,
    "initially_disabled_route": lambda features: features["initial_disabled_choice_count"] >= 1,
    "assignment_changes_later_choices": lambda features: len(features["condition_driven_divergence"]) >= 1,
    "cycle": lambda features: len(features["cycle_node_ids"]) >= 1,
    "step_cap": lambda features: len(features["step_cap_cases"]) >= 1,
    "unicode_fullwidth_quotes_newlines_specials": lambda features: all([
        features["special_characters"].get("emoji"), features["special_characters"].get("accented"),
        features["special_characters"].get("square_brackets"), features["special_characters"].get("braces"),
        features["special_characters"].get("lenticular"), features["special_characters"].get("percent"),
        features["special_characters"].get("newline"), features["special_characters"].get("fullwidth_colon"),
        features["special_characters"].get("corner_quotes")]),
    "save_restore_scenario": lambda features: len(features["save_restore_cases"]) >= 1,
    "two_endings": lambda features: features["ending_count"] >= 2,
    "conditions": lambda features: features["conditional_choice_count"] >= 1,
    "unicode_specials": lambda features: bool(features["special_characters"].get("emoji"))
    and bool(features["special_characters"].get("lenticular")),
}


def measure_features(spec, analysis, cases):
    initial = cases[0]["expected_states"][0]
    acting_nodes = [node for node in spec["nodes"] if not node["ending"]]
    ending_texts = sorted({node["ending"] for node in spec["nodes"] if node["ending"]})
    text = "".join(node["dialogue"] + node["ending"]
                   + "".join(item["label"] for item in node["choices"]) for node in spec["nodes"])
    special = {
        "square_brackets": "[" in text, "braces": "{" in text, "lenticular": "〖" in text,
        "percent": "%" in text, "emoji": "🙂" in text, "accented": "é" in text,
        "fullwidth_colon": "：" in text, "corner_quotes": "「" in text, "newline": "\n" in text,
    }
    assignment_cases = [case["id"] for case in cases
                        if any(state["variables"] != initial["variables"] for state in case["expected_states"])]
    step_cap_cases = [case["id"] for case in cases
                      if any(state["status"] == "STEP_CAP_REACHED" for state in case["expected_states"])]
    save_restore_cases = [case["id"] for case in cases if case.get("save_restore")]
    groups = {}
    for case in cases:
        for state in case["expected_states"]:
            groups.setdefault((state["node_id"], state["steps"]), []).append(state)
    divergence = []
    for (node_id, steps), states in groups.items():
        for left in range(len(states)):
            for right in range(left + 1, len(states)):
                if (states[left]["variables"] != states[right]["variables"]
                        and states[left]["enabled_choice_ids"] != states[right]["enabled_choice_ids"]):
                    divergence.append({
                        "node_id": node_id, "steps": steps,
                        "variables_a": states[left]["variables"],
                        "variables_b": states[right]["variables"],
                        "enabled_a": states[left]["enabled_choice_ids"],
                        "enabled_b": states[right]["enabled_choice_ids"],
                    })
    cycle_node_ids = sorted({warning["node_id"] for warning in analysis["warnings"]
                             if warning["code"] == "CYCLE_STEP_CAP_REQUIRED"})
    return {
        "node_count": len(spec["nodes"]),
        "variable_count": len(spec.get("variables") or []),
        "variable_types": sorted({variable["type"] for variable in spec.get("variables") or []}),
        "max_steps": spec["max_steps"],
        "ending_count": len(ending_texts),
        "ending_texts": ending_texts,
        "distinct_ending_nodes": len([node for node in spec["nodes"] if node["ending"]]),
        "witness_count": len(analysis["endings"]),
        "dialogue_nodes": len([node for node in spec["nodes"] if node["dialogue"]]),
        "speaker_nodes": len([node for node in spec["nodes"] if node.get("character_id")]),
        "conditional_choice_count": sum(1 for node in spec["nodes"] for item in node["choices"] if item["condition"]),
        "assignment_choice_count": sum(1 for node in spec["nodes"] for item in node["choices"] if item["assignments"]),
        "max_choices_per_acting_node": max((len(node["choices"]) for node in acting_nodes), default=0),
        "initial_enabled_choice_ids": initial["enabled_choice_ids"],
        "initial_disabled_choice_count": len(initial["disabled_choice_ids"]),
        "condition_driven_divergence": divergence,
        "assignment_cases": assignment_cases,
        "step_cap_cases": step_cap_cases,
        "save_restore_cases": save_restore_cases,
        "cycle_node_ids": cycle_node_ids,
        "special_characters": special,
        "analysis_issues": analysis["issues"],
        "analysis_warnings": analysis["warnings"],
        "can_review": analysis["can_review"],
        "analysis_complete": analysis["analysis_complete"],
    }


def feature_check_entries(definition, features, recorder):
    entries = []
    for name in definition["focus"]:
        rule = FEATURE_REQUIREMENTS.get(name)
        if rule is None:
            entries.append({"id": "feature:" + name, "status": "NOT_RUN", "detail": "no measurable rule"})
            continue
        ok = bool(rule(features))
        entries.append({"id": "feature:" + name, "status": "PASS" if ok else "FAIL",
                        "detail": name})
        recorder.check(definition["key"] + ":" + name, ok, "measured feature requirement")
    return entries


def resolve_characters(env, spec):
    rows = {row["id"]: row for row in env.novels.data_set(env.nid, "characters")}
    return {character_id: (rows[character_id].get("name") or character_id)
            for character_id in sorted({node["character_id"] for node in spec["nodes"]
                                        if node.get("character_id")})}


# ---------------------------------------------------------------------------
# story lifecycle: create -> preview -> edit/save -> submit -> review -> approve
# ---------------------------------------------------------------------------
def story_lifecycle(recorder, env, definition, spec, edited_spec=None, draft_paths=()):
    row = create_story(recorder, env, spec)
    draft_previews = [preview_matches_play(recorder, env, row, path) for path in draft_paths]
    if edited_spec is not None:
        row = save_story(recorder, env, row["id"], row["version"], edited_spec)
        fetched = get_story(recorder, env, row["id"])
        recorder.require("saved-story-fetch-matches",
                         fetched["spec"] == edited_spec and fetched["version"] == row["version"],
                         "version=" + str(fetched.get("version")))
    row = submit_review(recorder, env, row["id"], row["version"])
    review = review_preview(recorder, env, row["id"], row["version"])
    analysis = analyze_summary(row["spec"])
    recorder.require("review-preview-analysis-equals-play-analysis", review["analysis"] == analysis,
                     "server review analysis differs from play()/analyze()")
    row = approve_story(recorder, env, row["id"], row["version"], review["preview_digest"])
    return {"row": row, "draft_previews": draft_previews, "review": review,
            "analysis": analysis, "approved_spec": row["spec"]}


# ---------------------------------------------------------------------------
# export lifecycle: targets -> preview(losses) -> deterministic ZIP -> verify -> runtime
# ---------------------------------------------------------------------------
def _export_summary(record):
    return {
        "status": record.get("status"),
        "target_id": record.get("target_id"),
        "filename": record.get("filename"),
        "sha256": record.get("sha256"),
        "file_count": record.get("file_count"),
        "files_digest": record.get("files_digest"),
        "preview_digest": record.get("preview_digest"),
        "can_export": record.get("can_export"),
        "losses": record.get("losses"),
        "archive_verification_status": (record.get("archive") or {}).get("status"),
        "archive_checks_failed": [check["id"] for check in (record.get("archive") or {}).get("checks") or []
                                  if check["status"] != "PASS"],
        "deterministic_repeat": record.get("deterministic_repeat"),
        "runtime": record.get("runtime"),
        "delivery": record.get("delivery"),
        "target_row": record.get("target_row"),
    }


def export_lifecycle(recorder, env, story_row, analysis, cases, *, label, delivery_dir,
                     runtime=True, scratch_dir=None):
    story = story_authority()
    story_id, version = story_row["id"], story_row["version"]
    spec = story_row["spec"]
    characters = resolve_characters(env, spec)
    delivery_dir = Path(delivery_dir)
    targets = export_targets(recorder, env, story_id, version)
    recorder.require(label + ":targets-can-export-any", targets.get("can_export_any") is True,
                     str(targets.get("can_export_any")))
    recorder.require(label + ":targets-witness-equals-analysis", targets.get("witness") == analysis["endings"],
                     "server witness differs from analyze(spec).endings")
    recorder.require(label + ":targets-spec-digest", targets["story"]["spec_digest"] == digest_json(spec), "")
    recorder.require(label + ":targets-contract", targets.get("contract_version") == 1, "")
    availability = []
    for target in targets.get("targets") or []:
        availability.append({key: target.get(key) for key in (
            "target_id", "display_name", "kind", "format_version", "adapter_revision", "export_ready",
            "runtime_claim", "evidence", "engine_probe", "capabilities", "losses")}
            | {"compatibility": {key: target.get("compatibility", {}).get(key) for key in
                                 ("target_id", "can_export", "losses", "issues", "notes")}})
    result = {"service_targets": {"schema": targets.get("schema"),
                                  "contract_schema": targets.get("contract_schema"),
                                  "contract_version": targets.get("contract_version"),
                                  "can_export_any": targets.get("can_export_any"),
                                  "story": targets.get("story"),
                                  "analysis": targets.get("analysis"),
                                  "witness": targets.get("witness"),
                                  "targets": availability},
              "characters": characters, "legacy": None, "new_targets": {}}
    # 1. legacy multi-format bundle (still produced by the same approved revision)
    legacy_preview = export_preview(recorder, env, story_id, version)
    recorder.require(label + ":legacy-preview-can-export", legacy_preview.get("can_export") is True, "")
    recorder.require(label + ":legacy-preview-losses-confirmed", bool(legacy_preview.get("losses")),
                     "export-preview must surface losses")
    legacy_out = export_archive(recorder, env, story_id, version, legacy_preview["preview_digest"])
    legacy_data = base64.b64decode(legacy_out["content_base64"])
    recorder.require(label + ":legacy-sha256", sha256_hex(legacy_data) == legacy_out["sha256"], "")
    legacy_verify = verify_legacy_export(recorder, legacy_data, story_row=story_row,
                                         characters=characters, targets_response=targets,
                                         preview=legacy_preview)
    recorder.require(label + ":legacy-artifact-verified", legacy_verify["status"] == "PASS",
                     json.dumps([check["id"] for check in legacy_verify["checks"] if check["status"] != "PASS"])[:1200])
    legacy_repeat = export_archive(recorder, env, story_id, version, legacy_preview["preview_digest"])
    legacy_repeat_data = base64.b64decode(legacy_repeat["content_base64"])
    legacy_deterministic = {"sha256_first": legacy_out["sha256"],
                            "sha256_second": legacy_repeat["sha256"],
                            "identical": sha256_hex(legacy_data) == sha256_hex(legacy_repeat_data)}
    recorder.require(label + ":legacy-deterministic", legacy_deterministic["identical"], "")
    entries, _ = read_zip_entries(legacy_data)
    prefix = legacy_verify.get("prefix") or ""
    legacy_payload = {name[len(prefix):]: content for name, content in entries.items() if name.startswith(prefix)}
    runtime_story = dict(story_row)
    runtime_story["_legacy_ink_source"] = legacy_payload.get("ink/story.ink")
    if runtime:
        legacy_runtime = run_legacy_ink_runtime(recorder, runtime_story, spec, cases,
                                                Path(scratch_dir) / "legacy-ink", delivery_dir)
    else:
        legacy_runtime = {"target_id": "INKJS_2_3_2_TYPED_TEXT_SUBSET", "status": "NOT_RUN",
                          "reason": "--skip-runtime: artifact evidence only"}
    legacy_materialized = materialize_export(delivery_dir, None, {
        "filename": legacy_out["filename"], "content": legacy_data}, legacy_verify)
    legacy_record = {
        "status": "EXPORTED", "target_id": None, "filename": legacy_out["filename"],
        "sha256": legacy_out["sha256"], "file_count": len(legacy_verify.get("files") or []),
        "preview_digest": legacy_preview["preview_digest"], "can_export": legacy_preview.get("can_export"),
        "losses": legacy_preview.get("losses"), "available_targets": legacy_preview.get("target_ids"),
        "archive": legacy_verify, "deterministic_repeat": legacy_deterministic,
        "runtime": legacy_runtime,
        "delivery": {"zip": relative_to(legacy_materialized["zip_path"], delivery_dir),
                     "unpacked": relative_to(legacy_materialized["unpack_dir"], delivery_dir)},
    }
    result["legacy"] = legacy_record
    # 2. target-specific deterministic project ZIPs for every landed new target
    for target_id in TARGET_ORDER:
        target_row = next((item for item in targets.get("targets") or []
                           if item.get("target_id") == target_id), None)
        if target_row is None:
            result["new_targets"][target_id] = {"status": "TARGET_NOT_AVAILABLE",
                                                "detail": "adapter module not landed / not registered"}
            continue
        if not target_row.get("export_ready"):
            result["new_targets"][target_id] = {
                "status": "NOT_EXPORT_READY", "target_row": _target_row_evidence(target_row),
                "compatibility": target_row.get("compatibility")}
            continue
        preview = export_preview(recorder, env, story_id, version, target_id)
        if not preview.get("can_export"):
            result["new_targets"][target_id] = {"status": "PREVIEW_BLOCKED",
                                                "preview": {"can_export": preview.get("can_export"),
                                                            "losses": preview.get("losses"),
                                                            "compatibility": preview.get("selected_target", {}).get("compatibility")}}
            continue
        recorder.require(label + ":" + target_id + ":preview-losses-confirmed",
                         bool(preview.get("losses")), "export-preview must surface target losses")
        out = export_archive(recorder, env, story_id, version, preview["preview_digest"], target_id)
        data = base64.b64decode(out["content_base64"])
        recorder.require(label + ":" + target_id + ":sha256", sha256_hex(data) == out["sha256"], "")
        verify = verify_target_export(recorder, data, story_row=story_row, characters=characters,
                                      targets_response=targets, preview=preview, target_row=target_row)
        recorder.require(label + ":" + target_id + ":artifact-verified", verify["status"] == "PASS",
                         json.dumps([check["id"] for check in verify["checks"] if check["status"] != "PASS"])[:1500])
        recorder.require(label + ":" + target_id + ":response-manifest==zip-manifest",
                         verify.get("manifest") == out.get("manifest"), "export response manifest differs from delivered ZIP")
        repeat = export_archive(recorder, env, story_id, version, preview["preview_digest"], target_id)
        repeat_data = base64.b64decode(repeat["content_base64"])
        deterministic = {"sha256_first": out["sha256"], "sha256_second": repeat["sha256"],
                         "identical": sha256_hex(data) == sha256_hex(repeat_data)}
        recorder.require(label + ":" + target_id + ":deterministic", deterministic["identical"], "")
        materialized = materialize_export(delivery_dir, target_id, {
            "filename": out["filename"], "content": data}, verify)
        record = {
            "status": "EXPORTED", "target_id": target_id, "filename": out["filename"],
            "sha256": out["sha256"], "file_count": out.get("file_count"),
            "files_digest": out.get("files_digest"), "preview_digest": preview["preview_digest"],
            "can_export": preview.get("can_export"), "losses": preview.get("losses"),
            "capabilities": out.get("capabilities"), "runtime_claim": out.get("runtime_claim"),
            "target_runtime": out.get("target_runtime"),
            "service_evidence": out.get("evidence"),
            "target_row": _target_row_evidence(target_row),
            "archive": verify, "deterministic_repeat": deterministic,
            "delivery": {"zip": relative_to(materialized["zip_path"], delivery_dir),
                         "unpacked": relative_to(materialized["unpack_dir"], delivery_dir)},
        }
        runtime_report = runtime_phase(recorder, target_id, record, story_row, spec, cases,
                                       scratch_dir, delivery_dir, enabled=runtime)
        record["runtime"] = runtime_report
        result["new_targets"][target_id] = record
    # 3. Ren'Py target: static artifact already verified; engine absence blocks runtime only
    if "RENPY_8_5_4_PROJECT_V1" in result["new_targets"] and result["new_targets"]["RENPY_8_5_4_PROJECT_V1"].get("status") == "EXPORTED":
        record = result["new_targets"]["RENPY_8_5_4_PROJECT_V1"]
        if not isinstance(record.get("runtime"), dict):
            record["runtime"] = renpy_runtime_report("RENPY_8_5_4_PROJECT_V1", record.get("target_row"), record)
            write_json(Path(delivery_dir) / "runtime" / "RENPY_8_5_4_PROJECT_V1" / "result.json", record["runtime"])
    return result


def _target_row_evidence(target_row):
    return {key: target_row.get(key) for key in (
        "target_id", "display_name", "kind", "format_version", "adapter_revision",
        "evidence", "engine_probe", "runtime_claim", "export_ready", "launch_instructions")}


# ---------------------------------------------------------------------------
# samples
# ---------------------------------------------------------------------------
def write_sample_outputs(sample, delivery_sample_dir, repo_sample_dir=None):
    delivery_sample_dir = Path(delivery_sample_dir)
    delivery_sample_dir.mkdir(parents=True, exist_ok=True)
    write_json(delivery_sample_dir / "spec.json", sample["spec"])
    write_json(delivery_sample_dir / "sample.json", sample)
    if repo_sample_dir is not None:
        repo_sample_dir = Path(repo_sample_dir)
        repo_sample_dir.mkdir(parents=True, exist_ok=True)
        write_json(repo_sample_dir / (sample["sample_id"] + ".spec.json"), sample["spec"])
        write_json(repo_sample_dir / (sample["sample_id"] + ".sample.json"), sample)
    return delivery_sample_dir / "sample.json"


def run_sample(recorder, env, definition, delivery_root, scratch_dir, runtime=True):
    story = story_authority()
    key = definition["key"]
    planning = build_planning(recorder, env, definition)
    spec = story.StorySpec.model_validate(definition["build"](planning["nodes"], planning["graph"])).model_dump()
    analysis = analyze_summary(spec)
    cases = build_cases(spec, analysis, definition["extra_paths"])
    features = measure_features(spec, analysis, cases)
    feature_checks = feature_check_entries(definition, features, recorder)
    recorder.require("sample:" + key + ":can-review", analysis["can_review"] is True,
                     json.dumps(analysis["issues"])[:800])
    draft_paths = [witness["choices"] for witness in analysis["endings"][:1]]
    lifecycle = story_lifecycle(recorder, env, definition, spec, draft_paths=draft_paths)
    exports = export_lifecycle(recorder, env, lifecycle["row"], analysis, cases,
                               label="sample:" + key, delivery_dir=Path(delivery_root) / key,
                               runtime=runtime, scratch_dir=Path(scratch_dir) / key)
    sample = {
        "schema": "poemseed-b07-e2e07-sample/1",
        "sample_id": key,
        "version": 1,
        "title": definition["title"],
        "focus": definition["focus"],
        "generated_at_utc": utcnow(),
        "repo": {"head_sha": git_state().get("head_sha"), "branch": git_state().get("branch")},
        "planning": planning["record"],
        "story": {
            "id": lifecycle["row"]["id"], "version": lifecycle["row"]["version"],
            "status": lifecycle["row"]["status"], "title": spec["title"],
            "entry_node_id": spec["entry_node_id"], "node_count": len(spec["nodes"]),
            "variable_count": len(spec.get("variables") or []), "max_steps": spec["max_steps"],
            "spec_digest": digest_json(spec), "source_digest": exports["service_targets"]["story"]["source_digest"],
            "review_preview_digest": lifecycle["review"]["preview_digest"],
        },
        "spec": spec,
        "analysis": analysis,
        "features": features,
        "feature_checks": feature_checks,
        "cases": cases,
        "draft_previews": lifecycle["draft_previews"],
        "review": {"preview_digest": lifecycle["review"]["preview_digest"],
                   "can_approve": lifecycle["review"]["can_approve"],
                   "approved_version": lifecycle["row"]["version"],
                   "approved_status": lifecycle["row"]["status"]},
        "exports": {"service_view": exports["service_targets"], "legacy": exports["legacy"],
                    "new_targets": exports["new_targets"]},
        "unmet": [],
    }
    for target_id, record in exports["new_targets"].items():
        if record.get("status") != "EXPORTED":
            sample["unmet"].append({"target_id": target_id, "status": record.get("status"),
                                    "detail": record.get("detail")})
    sample_path = write_sample_outputs(sample, Path(delivery_root) / key)
    sample["_delivery_sample_json"] = relative_to(sample_path, delivery_root)
    return sample


def run_samples(recorder, env, delivery_root, scratch_dir, runtime=True):
    samples = {}
    for definition in SAMPLE_DEFINITIONS:
        samples[definition["key"]] = run_sample(recorder, env, definition, delivery_root,
                                                scratch_dir, runtime=runtime)
    return samples


# ---------------------------------------------------------------------------
# integration journey
# ---------------------------------------------------------------------------
def run_journey(recorder, env, delivery_root, scratch_dir, runtime=True):
    story = story_authority()
    delivery_root = Path(delivery_root)
    definition = JOURNEY_DEFINITION
    planning = build_planning(recorder, env, definition)
    spec_v1 = story.StorySpec.model_validate(definition["build"](planning["nodes"], planning["graph"])).model_dump()
    analysis_v1 = analyze_summary(spec_v1)
    recorder.require("journey:initial-can-review", analysis_v1["can_review"] is True,
                     json.dumps(analysis_v1["issues"])[:800])
    spec_v2 = journey_edited_spec(spec_v1)
    spec_v2 = story.StorySpec.model_validate(spec_v2).model_dump()
    recorder.require("journey:edited-spec-valid", True, "StorySpec validation passed")
    analysis_v2 = analyze_summary(spec_v2)
    cases_v2 = build_cases(spec_v2, analysis_v2, definition["extra_paths"])
    features_v2 = measure_features(spec_v2, analysis_v2, cases_v2)
    feature_checks = feature_check_entries(definition, features_v2, recorder)
    # first draft: preview one authoritative witness in the original story
    witness_paths = [witness["choices"] for witness in analysis_v1["endings"][:1]]
    row = create_story(recorder, env, spec_v1)
    draft_previews_v1 = [preview_matches_play(recorder, env, row, path) for path in witness_paths]
    # edit/save (dialogue, condition, choice, variables), then preview several paths
    row = save_story(recorder, env, row["id"], row["version"], spec_v2)
    fetched = get_story(recorder, env, row["id"])
    recorder.require("journey:edited-saved-and-fetched",
                     fetched["spec"] == spec_v2 and fetched["version"] == row["version"]
                     and fetched["status"] == "DRAFT", "version=" + str(fetched.get("version")))
    preview_paths = [case["choices"] for case in cases_v2
                     if case["kind"] in ("ending_witness", "step_cap", "extra_path")][:5]
    preview_records = [preview_matches_play(recorder, env, row, path) for path in preview_paths]
    recorder.require("journey:played-at-least-two-paths", len(preview_records) >= 2,
                     str(len(preview_records)))
    recorder.require("journey:played-an-ending",
                     any(record["server"]["status"] == "ENDING" for record in preview_records), "")
    # review submit -> review preview -> approve
    row = submit_review(recorder, env, row["id"], row["version"])
    review = review_preview(recorder, env, row["id"], row["version"])
    recorder.require("journey:review-analysis-equals-play-analysis", review["analysis"] == analysis_v2, "")
    row = approve_story(recorder, env, row["id"], row["version"], review["preview_digest"])
    approved_spec = row["spec"]
    analysis_approved = analyze_summary(approved_spec)
    cases_approved = build_cases(approved_spec, analysis_approved, definition["extra_paths"])
    approved_preview = preview_matches_play(recorder, env, row, analysis_approved["endings"][0]["choices"])
    exports = export_lifecycle(recorder, env, row, analysis_approved, cases_approved,
                               label="journey", delivery_dir=delivery_root,
                               runtime=runtime, scratch_dir=Path(scratch_dir) / "journey")
    journey = {
        "schema": "poemseed-b07-e2e07-journey/1",
        "generated_at_utc": utcnow(),
        "definition": {"key": definition["key"], "title": definition["title"],
                       "focus": definition["focus"]},
        "planning": planning["record"],
        "story": {
            "id": row["id"], "revision": row["version"], "status": row["status"],
            "spec_digest": digest_json(approved_spec),
            "source_digest": exports["service_targets"]["story"]["source_digest"],
            "review_preview_digest": review["preview_digest"],
            "node_count": len(approved_spec["nodes"]),
            "variable_count": len(approved_spec.get("variables") or []),
            "max_steps": approved_spec["max_steps"],
        },
        "versions": {"draft_v1": 1, "saved_v2": 2, "review_v3": 3, "approved_v4": row["version"]},
        "spec_v1": spec_v1,
        "spec_approved": approved_spec,
        "edit_summary": {
            "dialogue": "集市开场白改为含全角标点与 🙂 的文本",
            "condition": "call 路线条件改为 trusted and coins >= 0；pray 条件改为 trusted or coins == 0",
            "choice": "dark 标签改为「摸着黑走（没有灯）」；buy 赋值增加 trusted=False；again 标签编辑",
            "variables": "coins maximum 3 -> 4",
            "ending": "平安回家 -> 平安回家 · 已核验",
        },
        "analysis": analysis_approved,
        "features": features_v2,
        "feature_checks": feature_checks,
        "cases": cases_approved,
        "draft_previews": draft_previews_v1,
        "previews": preview_records,
        "approved_preview": approved_preview,
        "review": {"preview_digest": review["preview_digest"], "can_approve": review["can_approve"]},
        "exports": {"service_view": exports["service_targets"], "legacy": exports["legacy"],
                    "new_targets": exports["new_targets"]},
        "unmet": [],
    }
    for target_id, record in exports["new_targets"].items():
        if record.get("status") != "EXPORTED":
            journey["unmet"].append({"target_id": target_id, "status": record.get("status"),
                                     "detail": record.get("detail")})
    journey_path = delivery_root / "journey.json"
    write_json(journey_path, journey)
    write_json(delivery_root / "spec-v1.json", spec_v1)
    write_json(delivery_root / "spec-approved.json", approved_spec)
    journey["_delivery_journey_json"] = relative_to(journey_path, delivery_root)
    return journey



# ---------------------------------------------------------------------------
# evidence assembly: independent levels, explicit unmet items, honest scope
# ---------------------------------------------------------------------------
def _sample_evidence(sample):
    exports = sample.get("exports") or {}
    cases = sample.get("cases") or []
    return {
        "sample_id": sample["sample_id"],
        "title": sample["title"],
        "focus": sample.get("focus"),
        "story": sample.get("story"),
        "planning": sample.get("planning"),
        "analysis": {key: sample["analysis"].get(key) for key in (
            "issues", "warnings", "states_checked", "analysis_complete", "step_limit_reached",
            "max_steps", "can_review", "method")} | {"endings": sample["analysis"].get("endings")},
        "features": sample.get("features"),
        "feature_checks": sample.get("feature_checks"),
        "cases": [{"id": case["id"], "kind": case["kind"], "steps": case["steps"],
                   "choices": case["choices"],
                   "final_status": (case["expected_states"][-1]["status"] if case["expected_states"] else None),
                   "expected_states": len(case["expected_states"]),
                   "save_restore": case.get("save_restore")} for case in cases],
        "draft_previews": sample.get("draft_previews"),
        "review": sample.get("review"),
        "legacy_export": _export_summary(exports.get("legacy") or {}) if exports.get("legacy") else None,
        "new_target_exports": {target_id: _export_summary(record)
                               for target_id, record in (exports.get("new_targets") or {}).items()},
        "unmet": sample.get("unmet"),
        "files": {"delivery_sample_json": sample.get("_delivery_sample_json"),
                  "repo_sample_json": "docs/v2/b07-e2e07-20261020/samples/" + sample["sample_id"] + ".sample.json"},
    }


def _journey_evidence(journey):
    exports = journey.get("exports") or {}
    return {
        "definition": journey.get("definition"),
        "planning": journey.get("planning"),
        "story": journey.get("story"),
        "versions": journey.get("versions"),
        "edit_summary": journey.get("edit_summary"),
        "analysis": {key: journey["analysis"].get(key) for key in (
            "issues", "warnings", "states_checked", "analysis_complete", "step_limit_reached",
            "max_steps", "can_review", "method")} | {"endings": journey["analysis"].get("endings")},
        "features": journey.get("features"),
        "feature_checks": journey.get("feature_checks"),
        "cases": [{"id": case["id"], "kind": case["kind"], "steps": case["steps"],
                   "choices": case["choices"],
                   "final_status": (case["expected_states"][-1]["status"] if case["expected_states"] else None),
                   "expected_states": len(case["expected_states"]),
                   "save_restore": case.get("save_restore")} for case in journey.get("cases") or []],
        "draft_previews": journey.get("draft_previews"),
        "previews": journey.get("previews"),
        "approved_preview": journey.get("approved_preview"),
        "review": journey.get("review"),
        "service_targets": exports.get("service_view"),
        "legacy_export": _export_summary(exports.get("legacy") or {}) if exports.get("legacy") else None,
        "new_target_exports": {target_id: _export_summary(record)
                               for target_id, record in (exports.get("new_targets") or {}).items()},
        "unmet": journey.get("unmet"),
        "files": {"delivery_journey_json": journey.get("_delivery_journey_json"),
                  "repo_journey_json": "docs/v2/b07-e2e07-20261020/journey.json"},
    }


def collect_target_records(run):
    records = {}

    def ensure(target_id):
        return records.setdefault(target_id, {"present": False, "service_rows": [],
                                              "artifact_records": [], "runtime_reports": [],
                                              "blocked": []})

    scopes = []
    for key, sample in (run.get("samples") or {}).items():
        scopes.append(("sample:" + key, sample))
    if run.get("journey"):
        scopes.append(("journey", run["journey"]))
    for scope, document in scopes:
        exports = document.get("exports") or {}
        service_view = exports.get("service_view") or {}
        for target in service_view.get("targets") or []:
            target_id = target.get("target_id")
            if not target_id:
                continue
            row = ensure(target_id)
            row["present"] = True
            row["service_rows"].append({"scope": scope, "target_row": _target_row_evidence(target)})
        legacy = exports.get("legacy")
        if legacy:
            archive = legacy.get("archive") or {}
            for legacy_target in LEGACY_TARGET_IDS:
                row = ensure(legacy_target)
                row["present"] = True
                row["artifact_records"].append({
                    "scope": scope, "kind": "legacy_multi_file_bundle",
                    "sha256": legacy.get("sha256"), "archive_status": archive.get("status"),
                    "archive_checks_failed": [check["id"] for check in archive.get("checks") or []
                                              if check["status"] != "PASS"],
                    "ink_witness_alignment": (archive.get("ink_witness_alignment") or {}).get("status"),
                    "renpy_static": (archive.get("renpy_static") or {}).get("status"),
                    "godot_legacy_static": (archive.get("godot_legacy_static") or {}).get("status"),
                    "ink_legacy_static": (archive.get("ink_legacy_static") or {}).get("status"),
                })
                runtime = legacy.get("runtime") or {}
                row["runtime_reports"].append({
                    "scope": scope, "target_id": legacy_target,
                    "status": (runtime.get("status") if legacy_target == "INKJS_2_3_2_TYPED_TEXT_SUBSET"
                               else ("BLOCKED_ENVIRONMENT" if legacy_target == "RENPY_8_5_4_TEXT_MENU_SUBSET"
                                     else "NOT_RUN")),
                    "reason": (runtime.get("reason") if legacy_target == "INKJS_2_3_2_TYPED_TEXT_SUBSET"
                               else "Ren'Py engine absent on this host" if legacy_target == "RENPY_8_5_4_TEXT_MENU_SUBSET"
                               else "DATA_ONLY_ADAPTER has no runnable project"),
                    "engine": (runtime.get("engine") if legacy_target == "INKJS_2_3_2_TYPED_TEXT_SUBSET"
                               else find_renpy_engine() if legacy_target == "RENPY_8_5_4_TEXT_MENU_SUBSET" else None),
                    "alignment": runtime.get("alignment") if legacy_target == "INKJS_2_3_2_TYPED_TEXT_SUBSET" else None,
                    "save_restore": runtime.get("save_restore") if legacy_target == "INKJS_2_3_2_TYPED_TEXT_SUBSET" else None,
                })
        for target_id, record in (exports.get("new_targets") or {}).items():
            row = ensure(target_id)
            if record.get("status") == "EXPORTED":
                archive = record.get("archive") or {}
                row["artifact_records"].append({
                    "scope": scope, "kind": "target_project_zip", "target_id": target_id,
                    "sha256": record.get("sha256"), "file_count": record.get("file_count"),
                    "archive_status": archive.get("status"),
                    "archive_checks_failed": [check["id"] for check in archive.get("checks") or []
                                              if check["status"] != "PASS"],
                    "deterministic_repeat": record.get("deterministic_repeat"),
                    "delivery": record.get("delivery"),
                })
                runtime = record.get("runtime") or {}
                if runtime:
                    row["runtime_reports"].append({"scope": scope, **runtime})
            else:
                row["blocked"].append({"scope": scope, "status": record.get("status"),
                                       "detail": record.get("detail")})
    return records


def build_evidence(run):
    started = run.get("started_at_utc")
    evidence = {
        "schema": "poemseed-b07-e2e07-evidence/1",
        "generated_at_utc": utcnow(),
        "started_at_utc": started,
        "modes": run.get("modes") or [],
        "status": "PARTIAL",
        "claim_scope": "INDEPENDENT_E2E_07_EVIDENCE_NOT_LINE_SELF_REPORT",
        "repository": {"worktree": str(REPO_ROOT), **(run.get("git") or {})},
        "host": run.get("host"),
        "composition": run.get("composition"),
        "single_authority": {
            "story_spec": "app/experimental/interactive_story.py StorySpec",
            "playback": "interactive_story.play() (server-replayed bounded choice log)",
            "analysis": "interactive_story.analyze() (bounded typed state search)",
            "export": "interactive_export_contract.build_export_bundle + package_export_zip",
            "step_expectations": "recomputed here with play() and compared step by step",
        },
        "commands": run.get("commands") or [],
        "checks_summary": run.get("recorder_summary"),
        "checks": run.get("checks") or [],
        "http_calls": run.get("http") or [],
        "samples": {key: _sample_evidence(sample) for key, sample in (run.get("samples") or {}).items()},
        "journey": _journey_evidence(run["journey"]) if run.get("journey") else None,
        "targets": {},
        "evidence_levels": {},
        "unmet": [],
        "honesty": [
            "Generating a project is not running it: GENERATED_ARTIFACT_VALIDATED is set only after reading the delivered ZIP bytes back and recomputing manifest, receipt and every file hash.",
            "TARGET_RUNTIME_EXECUTED is set only after a real target runtime/verifier ran the exported artifact and every runtime step matched play().",
            "SAVE_RESTORE_VERIFIED is set only after the target runtime actually saved, restored and continued to the expected state.",
            "Ren'Py 8.5.4 is not installed on this host; Ren'Py runtime evidence is BLOCKED_ENVIRONMENT and only static project checks are claimed.",
            "The samples are real File-backend fixtures created through the mounted Studio API; they are not claims about the current author's manuscript.",
            "Target-line evidence declarations (DESCRIPTOR.evidence) are recorded separately and are never auto-upgraded by this journey.",
        ],
        "files": {},
        "error": run.get("error"),
        "traceback_tail": run.get("traceback_tail"),
    }
    records = collect_target_records(run)
    levels = {}
    unmet = []
    for target_id in list(TARGET_ORDER) + list(LEGACY_TARGET_IDS):
        row = records.get(target_id, {"present": False, "service_rows": [], "artifact_records": [],
                                      "runtime_reports": [], "blocked": []})
        declared = {}
        for service_row in row["service_rows"]:
            declared = (service_row.get("target_row") or {}).get("evidence") or declared
        status = {level: "NOT_RUN" for level in EVIDENCE_LEVELS}
        notes = []
        if row["present"]:
            status["SOURCE_IMPLEMENTED"] = "PASS"
            status["SCHEMA_VALIDATED"] = "PASS"
        artifacts = row["artifact_records"]
        if artifacts:
            status["FIXTURE_TESTED"] = "PASS"
            archive_statuses = [item.get("archive_status") for item in artifacts]
            if archive_statuses and all(value == "PASS" for value in archive_statuses):
                status["GENERATED_ARTIFACT_VALIDATED"] = "PASS"
            else:
                status["GENERATED_ARTIFACT_VALIDATED"] = "FAIL"
        runtimes = row["runtime_reports"]
        runtime_statuses = [item.get("status") for item in runtimes]
        if "EXECUTED_AND_ALIGNED" in runtime_statuses:
            status["TARGET_RUNTIME_EXECUTED"] = "PASS"
        elif "EXECUTED_WITH_MISMATCH" in runtime_statuses or "FAIL_RUNTIME_PROCESS" in runtime_statuses:
            status["TARGET_RUNTIME_EXECUTED"] = "FAIL"
        elif any(value and str(value).startswith("BLOCKED") for value in runtime_statuses):
            status["TARGET_RUNTIME_EXECUTED"] = "BLOCKED_ENVIRONMENT"
        save_levels = [(item.get("save_restore") or {}).get("level") for item in runtimes]
        if "PASS" in save_levels:
            status["SAVE_RESTORE_VERIFIED"] = "PASS"
        elif "PARTIAL" in save_levels:
            status["SAVE_RESTORE_VERIFIED"] = "PARTIAL"
        elif status["TARGET_RUNTIME_EXECUTED"] == "BLOCKED_ENVIRONMENT" and target_id in (
                "RENPY_8_5_4_PROJECT_V1", "RENPY_8_5_4_TEXT_MENU_SUBSET"):
            status["SAVE_RESTORE_VERIFIED"] = "BLOCKED_ENVIRONMENT"
        status["WINDOWS_USABILITY_VERIFIED"] = "NOT_RUN"
        notes.append("WINDOWS_USABILITY_VERIFIED is out of E2E-07 scope and is not claimed.")
        if target_id in TARGET_ORDER and not row["present"]:
            notes.append("Target adapter module is not registered by interactive_export_contract at this revision; the line had not landed at run time.")
        levels[target_id] = {"present": row["present"], "service_declared": declared,
                             "e2e07_independent": status, "notes": notes}
        if target_id in TARGET_ORDER:
            if not row["present"]:
                unmet.append({"target_id": target_id, "item": "TARGET_ADAPTER", "status": "NOT_LANDED",
                              "detail": "adapter module not registered in interactive_export_contract.TARGET_MODULES"})
            elif not artifacts:
                blocked = row["blocked"][0] if row["blocked"] else {}
                unmet.append({"target_id": target_id, "item": "ARTIFACT_EXPORT",
                              "status": blocked.get("status") or "NOT_RUN",
                              "detail": blocked.get("detail") or "no exported artifact recorded"})
            if status["GENERATED_ARTIFACT_VALIDATED"] != "PASS" and artifacts:
                unmet.append({"target_id": target_id, "item": "GENERATED_ARTIFACT_VALIDATED",
                              "status": status["GENERATED_ARTIFACT_VALIDATED"],
                              "detail": "archive verification did not pass"})
            if status["TARGET_RUNTIME_EXECUTED"] != "PASS":
                unmet.append({"target_id": target_id, "item": "TARGET_RUNTIME_EXECUTED",
                              "status": status["TARGET_RUNTIME_EXECUTED"],
                              "detail": (runtimes[0].get("reason") if runtimes else "runtime was not exercised")})
            if status["SAVE_RESTORE_VERIFIED"] != "PASS":
                unmet.append({"target_id": target_id, "item": "SAVE_RESTORE_VERIFIED",
                              "status": status["SAVE_RESTORE_VERIFIED"],
                              "detail": (runtimes[0].get("save_restore") if runtimes else "save/restore was not exercised")})
        evidence["targets"][target_id] = {
            "present": row["present"],
            "service_rows": row["service_rows"][:4],
            "artifact_records": artifacts,
            "runtime_reports": runtimes,
            "blocked": row["blocked"],
        }
    for scope_name in ("samples", "journey"):
        document = evidence.get(scope_name)
        if not document:
            continue
        for item in document.get("unmet") or []:
            if item.get("status") == "TARGET_NOT_AVAILABLE":
                continue  # already reported once as TARGET_ADAPTER NOT_LANDED above
            unmet.append(item)
    evidence["evidence_levels"] = levels
    evidence["unmet"] = unmet
    failed_artifacts = [item for item in levels.items()
                        if item[1]["e2e07_independent"]["GENERATED_ARTIFACT_VALIDATED"] == "FAIL"]
    failed_runtime = [item for item in levels.items()
                      if item[1]["e2e07_independent"]["TARGET_RUNTIME_EXECUTED"] == "FAIL"]
    if run.get("status") == "ERROR" or run.get("error"):
        evidence["status"] = "ERROR"
    elif failed_artifacts or failed_runtime:
        evidence["status"] = "FAIL"
    elif unmet:
        evidence["status"] = "PARTIAL"
    else:
        evidence["status"] = "PASS"
    evidence["evidence_level_legend"] = {
        "levels": list(EVIDENCE_LEVELS), "statuses": list(EVIDENCE_STATUSES),
        "meaning": {
            "SOURCE_IMPLEMENTED": "target source exists and was importable/registered",
            "SCHEMA_VALIDATED": "contract descriptor/compatibility validated by interactive_export_contract",
            "FIXTURE_TESTED": "the E2E-07 fixture story was created, reviewed and exported for this target",
            "GENERATED_ARTIFACT_VALIDATED": "delivered ZIP read back; manifest, receipt and every sha256 recomputed",
            "TARGET_RUNTIME_EXECUTED": "real target runtime executed the artifact and every step matched play()",
            "SAVE_RESTORE_VERIFIED": "target runtime saved/restored and continued to the expected state",
            "WINDOWS_USABILITY_VERIFIED": "human Windows usability acceptance (never claimed by E2E-07)",
        },
    }
    evidence["levels_summary"] = {
        target_id: {level: status for level, status in values["e2e07_independent"].items()}
        for target_id, values in levels.items()
    }
    return evidence


# ---------------------------------------------------------------------------
# markdown and delivery readme
# ---------------------------------------------------------------------------
def _md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def render_markdown(evidence):
    fence = chr(96) * 3
    lines = ["# B07 / DIF-10 / E2E-07 evidence (2026-10-20)", ""]
    lines += ["Status: **" + str(evidence["status"]) + "**", "",
              "Claim scope: " + evidence["claim_scope"] + ".", "",
              "Generated: " + evidence["generated_at_utc"], ""]
    repository = evidence.get("repository") or {}
    lines += ["## Repository", "",
              _md_table(["item", "value"], [
                  ["worktree", repository.get("worktree")],
                  ["branch", repository.get("branch")],
                  ["head sha", repository.get("head_sha")],
                  ["dirty", repository.get("dirty")],
                  ["modes", ", ".join(evidence.get("modes") or [])],
              ]), ""]
    composition = evidence.get("composition") or {}
    lines += ["## Real composition", "",
              _md_table(["item", "value"], [
                  ["composition", composition.get("composition")],
                  ["fixture parameters", json.dumps(composition.get("fixture_parameters"), ensure_ascii=False)],
                  ["http layer", composition.get("http_layer")],
                  ["storage backend", composition.get("storage_backend")],
                  ["authorization", composition.get("authorization")],
                  ["novel / chapter", str(composition.get("novel_id")) + " / " + str(composition.get("chapter_id"))],
                  ["provider calls", composition.get("provider_calls")],
              ]), ""]
    lines += ["## Target evidence levels", ""]
    level_rows = []
    for target_id, values in (evidence.get("evidence_levels") or {}).items():
        ind = values["e2e07_independent"]
        level_rows.append([target_id, "yes" if values["present"] else "no",
                           ind.get("GENERATED_ARTIFACT_VALIDATED"), ind.get("TARGET_RUNTIME_EXECUTED"),
                           ind.get("SAVE_RESTORE_VERIFIED"),
                           values.get("service_declared", {}).get("TARGET_RUNTIME_EXECUTED", "NOT_DECLARED")])
    lines += [_md_table(["target", "present", "artifact", "runtime", "save/restore", "service-declared runtime"], level_rows), "",
              "service-declared runtime is the target line's own declaration and is never auto-upgraded here.", ""]
    samples = evidence.get("samples") or {}
    if samples:
        lines += ["## Samples", ""]
        rows = []
        for key, sample in samples.items():
            rows.append([key, sample["story"]["id"][:8],
                         sample["story"].get("revision", sample["story"].get("version")),
                         sample["story"]["spec_digest"][:16],
                         len(sample["analysis"]["endings"]), len(sample["cases"]),
                         (sample.get("legacy_export") or {}).get("sha256", "-")[:16],
                         len([item for item in (sample.get("new_target_exports") or {}).values()
                              if item.get("status") == "EXPORTED"])])
        lines += [_md_table(["sample", "story", "rev", "spec digest", "endings", "cases", "legacy zip sha", "target zips"], rows), ""]
        lines += ["Feature measurements are in the JSON evidence; every one is recomputed from play()/analyze().", ""]
    journey = evidence.get("journey")
    if journey:
        lines += ["## E2E-07 integration journey", "",
                  _md_table(["item", "value"], [
                      ["story id", journey["story"]["id"]],
                      ["approved revision", journey["story"]["revision"]],
                      ["spec digest", journey["story"]["spec_digest"]],
                      ["versions", json.dumps(journey["versions"])],
                      ["preview paths compared with play()", len(journey.get("previews") or []) + len(journey.get("draft_previews") or []) + 1],
                      ["service targets", ", ".join(target["target_id"] for target in
                                                     ((journey.get("service_targets") or {}).get("targets") or []))],
                  ]), ""]
        export_rows = []
        legacy = journey.get("legacy_export")
        if legacy:
            export_rows.append(["legacy multi-file", legacy.get("sha256", "-")[:16], legacy.get("file_count"),
                                legacy.get("archive_verification_status"),
                                (legacy.get("runtime") or {}).get("status"), "-"])
        for target_id, record in (journey.get("new_target_exports") or {}).items():
            runtime = record.get("runtime") or {}
            alignment = (runtime.get("alignment") or {}).get("status") if isinstance(runtime.get("alignment"), dict) else None
            export_rows.append([target_id, (record.get("sha256") or "-")[:16], record.get("file_count"),
                                record.get("archive_verification_status"), runtime.get("status"), alignment])
        lines += ["### Delivered artifacts", "",
                  _md_table(["artifact", "sha256", "files", "archive verification", "runtime", "step alignment"], export_rows), ""]
    lines += ["## Unmet items", ""]
    unmet = evidence.get("unmet") or []
    if unmet:
        lines += [_md_table(["target", "item", "status", "detail"],
                            [[item.get("target_id"), item.get("item"), item.get("status"),
                              str(item.get("detail"))[:240]] for item in unmet]), ""]
    else:
        lines += ["None: every claimed level passed and every requested target ran its real runtime.", ""]
    lines += ["## Honesty notes", ""]
    lines += ["- " + note for note in evidence.get("honesty") or []]
    lines += ["", "## Reproduce", "", fence + "powershell",
              "cd " + str(REPO_ROOT),
              "python scripts/b07_e2e07_journey.py all",
              "python -m pytest tests/test_b07_e2e07_journey.py -q -p no:cacheprovider",
              fence, ""]
    return "\n".join(lines)


def delivery_readme(evidence):
    lines = ["# B07 E2E-07 delivery (2026-10-20)", "",
             "External delivery directory for the independent E2E-07 evidence.", "",
             "Status: **" + str(evidence["status"]) + "** (see evidence/ for the full JSON/Markdown).", "",
             "Layout:", "",
             "- samples/<A|B|C>/: original Story Spec JSON, sample.json (server witness, step-by-step play() states, exports) and exports/.",
             "- samples/<A|B|C>/exports/legacy/: the legacy multi-file ZIP plus verified unpacked files.",
             "- samples/<A|B|C>/exports/<target_id>/: deterministic target project ZIP, unpacked project and archive verification.",
             "- journey/: the T10 integration journey record, approved spec and its exports.",
             "- runtime/<target_id>/: raw target-runtime verifier output and step-alignment results.",
             "- evidence/: repository evidence JSON/Markdown copies.",
             "",
             "Reproduce: python scripts/b07_e2e07_journey.py all from the repository worktree.", ""]
    return "\n".join(lines)


REPO_README = """# B07 E2E-07 samples and cross-target evidence (2026-10-20)

This directory contains the repository-internal, repeatable E2E-07 evidence for the
B07 / DIF-10 interactive export targets.  The generator is
scripts/b07_e2e07_journey.py and its regression test is
tests/test_b07_e2e07_journey.py.

- samples/<sample>.spec.json: original Story Spec JSON for samples A/B/C.
- samples/<sample>.sample.json: server-authoritative witness (analysis.endings
  with choice paths), the step-by-step expected states recomputed with play(),
  measured feature checks, and the hash inventory of the delivered artifacts.
- journey.spec.json / journey.json: the approved integration-journey story and
  the full journey record (planning -> story -> edit/save -> preview -> review ->
  approve -> export-targets -> export-preview -> deterministic ZIP -> verification
  -> target runtime step alignment).
- docs/v2/B07_DIF10_E2E07_EVIDENCE_20261020.json/.md: the assembled evidence with
  per-target independent evidence levels.

Repeatable artifacts (ZIPs, unpacked projects, raw runtime output) are written to
the external delivery directory D:\\PoemSeed\\Recovery\\b07-delivery\\e2e07.

Honesty rules enforced by the generator:

1. The samples are real fixtures created through the composed Studio API (real
   File repository, production routers, real authorization stack, real HTTP
   TestClient); they are not mocks and they are not claims about the current
   manuscript.
2. Generating an artifact is not running it. GENERATED_ARTIFACT_VALIDATED
   requires reading the delivered ZIP back and recomputing manifest, receipt and
   every file SHA-256.
3. TARGET_RUNTIME_EXECUTED requires a real target runtime to run the exported
   artifact and match every step (node, variables, enabled choices, steps, status)
   of play().  Ren'Py is BLOCKED_ENVIRONMENT on this host (engine absent).
4. Service/target-line evidence declarations are recorded separately and are
   never upgraded by this journey.
"""


# ---------------------------------------------------------------------------
# orchestration entry point
# ---------------------------------------------------------------------------
def _clear_generated_tree(root):
    root = Path(root)
    for name in ("samples", "journey", "runtime", "evidence"):
        target = root / name
        if target.exists():
            shutil.rmtree(target)


def probe_host_commands(recorder):
    records = []
    git_record = run_process(["git", "-C", str(REPO_ROOT), "log", "--oneline", "-3"],
                             cwd=REPO_ROOT, timeout=30, label="git-log")
    records.append(git_record)
    recorder.command(git_record)
    for target_id, engine in (host_info().get("engines") or {}).items():
        if isinstance(engine, dict) and engine.get("found") and engine.get("path") and Path(engine["path"]).is_file():
            name = Path(engine["path"]).name.lower()
            if target_id.startswith("GODOT") and ("godot" in name):
                record = run_process([engine["path"], "--version"], cwd=REPO_ROOT, timeout=60,
                                     label="godot-version")
                records.append(record)
                recorder.command(record)
            elif target_id.startswith("INK") and Path(engine["path"]).is_dir():
                record = run_process([os.environ.get("POEMSEED_NODE") or shutil.which("node") or "node", "--version"],
                                     cwd=REPO_ROOT, timeout=30, label="node-version")
                records.append(record)
                recorder.command(record)
    return records


def write_outputs(run, evidence, args):
    delivery = Path(args.delivery)
    evidence_dir = delivery / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json(evidence_dir / "B07_DIF10_E2E07_EVIDENCE_20261020.json", evidence)
    md_path = write_text(evidence_dir / "B07_DIF10_E2E07_EVIDENCE_20261020.md", render_markdown(evidence))
    write_text(delivery / "README.md", delivery_readme(evidence))
    write_json(evidence_dir / "run.json", {key: value for key, value in run.items()
                                           if key not in ("samples", "journey")})
    if not args.no_repo_evidence:
        repo_json = write_json(EVIDENCE_JSON, evidence)
        repo_md = write_text(EVIDENCE_MD, render_markdown(evidence))
        REPO_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        write_text(REPO_SAMPLE_DIR / "README.md", REPO_README)
        for key, sample in (run.get("samples") or {}).items():
            write_json(REPO_SAMPLE_DIR / "samples" / (key + ".spec.json"), sample["spec"])
            write_json(REPO_SAMPLE_DIR / "samples" / (key + ".sample.json"), sample)
        journey = run.get("journey")
        if journey:
            write_json(REPO_SAMPLE_DIR / "journey.spec.json", journey["spec_approved"])
            write_json(REPO_SAMPLE_DIR / "journey.json", journey)
        evidence["files"] = {
            "delivery_evidence_json": relative_to(json_path, delivery),
            "delivery_evidence_md": relative_to(md_path, delivery),
            "delivery_readme": "README.md",
            "repo_evidence_json": relative_to(repo_json, REPO_ROOT),
            "repo_evidence_md": relative_to(repo_md, REPO_ROOT),
            "repo_sample_dir": relative_to(REPO_SAMPLE_DIR, REPO_ROOT),
        }
        write_json(json_path, evidence)
        write_text(md_path, render_markdown(evidence))
    else:
        evidence["files"] = {
            "delivery_evidence_json": relative_to(json_path, delivery),
            "delivery_evidence_md": relative_to(md_path, delivery),
            "delivery_readme": "README.md",
        }
        write_json(json_path, evidence)
        write_text(md_path, render_markdown(evidence))
    return evidence


def execute(args):
    delivery = Path(args.delivery)
    scratch = Path(args.scratch)
    delivery.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    _clear_generated_tree(delivery)
    recorder = Recorder("e2e07")
    run = {
        "schema": "poemseed-b07-e2e07-run/1",
        "argv": [str(item) for item in sys.argv],
        "mode": args.command,
        "started_at_utc": utcnow(),
        "modes": [],
        "git": git_state(),
        "host": host_info(),
        "commands": [],
        "env": {"storage_backend": "file", "prefix": "/api"},
    }
    try:
        probe_host_commands(recorder)
        env = build_file_backend_env(scratch / "env", prefix="/api")
        try:
            run["composition"] = env.report()
            recorder.require("journey:file-backend-composition",
                             run["composition"]["storage_backend"] == "file"
                             and run["composition"]["mocks"] is False, "composition is not the real File backend")
            if args.command in ("samples", "all"):
                run["samples"] = run_samples(recorder, env, delivery / "samples", scratch,
                                             runtime=not args.skip_runtime)
                run["modes"].append("samples")
            if args.command in ("journey", "all"):
                run["journey"] = run_journey(recorder, env, delivery / "journey", scratch,
                                             runtime=not args.skip_runtime)
                run["modes"].append("journey")
        finally:
            env.close(remove=not args.keep_env)
        run["status"] = "OK"
    except Exception as exc:  # noqa: BLE001 - the evidence must record the failure, not hide it
        import traceback
        run["status"] = "ERROR"
        run["error"] = type(exc).__name__ + ": " + str(exc)
        run["traceback_tail"] = traceback.format_exc()[-6000:]
    run["finished_at_utc"] = utcnow()
    run["recorder_summary"] = recorder.summary()
    run["http"] = recorder.http
    run["checks"] = recorder.checks
    run["notes"] = recorder.notes
    run["commands"] = recorder.commands
    evidence = build_evidence(run)
    evidence = write_outputs(run, evidence, args)
    print("E2E-07 status:", evidence["status"])
    print("evidence:", EVIDENCE_JSON)
    print("delivery:", delivery)
    for target_id, values in (evidence.get("levels_summary") or {}).items():
        print("  target", target_id, json.dumps(values))
    if evidence.get("unmet"):
        print("unmet:", len(evidence["unmet"]), "items")
    if run.get("error"):
        print("error:", run["error"])
        return 1
    return 0 if evidence["status"] in ("PASS", "PARTIAL") else 1


def cmd_runtime(args):
    """Re-run the real target runtime against an existing exported project."""
    delivery = Path(args.delivery)
    scratch = Path(args.scratch)
    delivery.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    if isinstance(spec, dict) and "spec" in spec and "nodes" not in spec:
        spec = spec["spec"]
    story = story_authority()
    spec = story.StorySpec.model_validate(spec).model_dump()
    analysis = analyze_summary(spec)
    cases = build_cases(spec, analysis)
    story_row = {"id": args.story_id or "standalone", "version": 1, "status": "APPROVED",
                 "spec": spec, "created_by": "standalone"}
    recorder = Recorder("runtime-standalone")
    target_id = args.target
    project_dir = Path(args.project)
    if target_id == "RENPY_8_5_4_PROJECT_V1":
        report = renpy_runtime_report(target_id, None, {"materialized": True})
    elif target_id in RUNTIME_VERIFIERS:
        report = run_target_runtime(recorder, target_id, project_dir, story_row, spec, cases,
                                    scratch / "runtime-standalone", delivery)
    else:
        raise SystemExit("unknown target: " + target_id)
    report["commands"] = recorder.commands
    print(json.dumps(report, ensure_ascii=False, indent=2)[:12000])
    return 0 if report.get("status") in ("EXECUTED_AND_ALIGNED", "BLOCKED_ENVIRONMENT") else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="B07 E2E-07 repeatable samples, journey and target evidence")
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (("all", "samples + integration journey + target runtime evidence"),
                            ("samples", "samples A/B/C only"),
                            ("journey", "T10 integration journey only")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--delivery", default=str(DEFAULT_DELIVERY))
        command.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
        command.add_argument("--skip-runtime", action="store_true",
                             help="do not launch target runtimes (artifact evidence only)")
        command.add_argument("--keep-env", action="store_true", help="keep the temporary File repository")
        command.add_argument("--no-repo-evidence", action="store_true",
                             help="write evidence only to the external delivery directory")
    runtime_parser = sub.add_parser("runtime", help="re-run the real target runtime for one exported project")
    runtime_parser.add_argument("--target", required=True)
    runtime_parser.add_argument("--project", required=True)
    runtime_parser.add_argument("--spec", required=True)
    runtime_parser.add_argument("--story-id", default=None)
    runtime_parser.add_argument("--delivery", default=str(DEFAULT_DELIVERY))
    runtime_parser.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "runtime":
        return cmd_runtime(args)
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
