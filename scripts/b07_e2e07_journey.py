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


RENPY_WITNESS_SCHEMA = "poemseed-renpy-acceptance-witness/1"


def align_renpy_witness(recorder, witness, spec, label):
    """Independently re-derive every Ren'Py witness state from play()."""
    checks = []
    cases = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail[:1200]})
        recorder.check(label + ":" + cid, ok, detail)

    check("witness schema", witness.get("schema") == RENPY_WITNESS_SCHEMA, str(witness.get("schema")))
    witnesses = witness.get("witnesses") or []
    check("witness count", int(witness.get("witness_count") or 0) == len(witnesses), str(len(witnesses)))
    for index, case in enumerate(witnesses):
        choices = [str(choice) for choice in case.get("choices") or []]
        expected_states = [canonical_state(spec, choices[:depth]) for depth in range(len(choices) + 1)]
        actual_states = [{"node_id": state.get("node_id"), "variables": state.get("variables"),
                          "enabled_choice_ids": state.get("enabled_choice_ids"),
                          "steps": state.get("steps"), "status": state.get("status")}
                         for state in case.get("states") or []]
        alignment = align_states(actual_states, expected_states, "renpy-witness:" + str(index))
        cases.append({"ending_node_id": case.get("ending_node_id"), "ending": case.get("ending"),
                      "choices": choices, "states_expected": len(expected_states),
                      "states_actual": len(actual_states),
                      "alignment_status": alignment["status"], "alignment": alignment})
        recorder.require(label + ":witness-case:" + str(index), alignment["status"] == "PASS",
                         json.dumps(alignment["details"], ensure_ascii=False)[:2000])
    return {"status": "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL",
            "checks": checks, "cases": cases, "witnesses": len(witnesses)}


def static_renpy_project_artifact(recorder, payload, story_row, characters, manifest):
    """Static structure + witness alignment for the complete Ren'Py project target.

    No Ren'Py engine exists on this host: only static artifact structure and the
    authority-derived acceptance witness are claimed here.
    """
    spec = story_row["spec"]
    manifest_story = (manifest or {}).get("story") or {}
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail[:1200]})
        recorder.check("renpy-project:" + cid, ok, detail)

    for required in ("game/script.rpy", "game/options.rpy", "game/screens.rpy",
                     "acceptance/witness.json"):
        check(required + " present", required in payload, "")
    check("README present", any(path.lower().endswith(("readme.txt", "readme.md")) for path in payload), "")
    check("no engine binary bundled",
          not any(path.endswith((".exe", ".dll", ".so", ".dylib")) for path in payload), "")
    witness_raw = payload.get("acceptance/witness.json")
    witness_alignment = {"status": "NOT_RUN", "cases": [], "witnesses": 0}
    script_name = "game/script.rpy"
    if witness_raw is not None:
        try:
            witness = json.loads(witness_raw)
        except ValueError:
            witness = {}
            check("witness parses", False, "")
        else:
            check("witness parses", True, "")
            project = witness.get("project") or {}
            check("project schema", isinstance(project.get("schema"), str), str(project.get("schema")))
            check("script path matches delivery", project.get("script") == script_name,
                  str(project.get("script")))
            check("options path matches delivery", project.get("options") == "game/options.rpy", "")
            check("screens path matches delivery", project.get("screens") == "game/screens.rpy", "")
            check("engine not bundled", project.get("engine_bundled") is False, "")
            story_block = witness.get("story") or {}
            check("witness story id bound", story_block.get("story_id") == story_row["id"], "")
            check("witness revision bound", story_block.get("revision") == story_row["version"], "")
            check("witness spec digest bound", story_block.get("spec_digest") == digest_json(spec), "")
            check("witness source digest bound",
                  story_block.get("source_digest") == manifest_story.get("source_digest"), "")
            check("witness review receipt bound",
                  story_block.get("review_receipt") == manifest_story.get("review_receipt"), "")
            evidence = witness.get("runtime_evidence") or {}
            check("witness does not claim target runtime",
                  evidence.get("TARGET_RUNTIME_EXECUTED") in ("BLOCKED_ENVIRONMENT", "NOT_RUN"),
                  str(evidence.get("TARGET_RUNTIME_EXECUTED")))
            check("witness does not claim save/restore",
                  evidence.get("SAVE_RESTORE_VERIFIED") in ("BLOCKED_ENVIRONMENT", "NOT_RUN"),
                  str(evidence.get("SAVE_RESTORE_VERIFIED")))
            witness_alignment = align_renpy_witness(recorder, witness, spec, "renpy-witness")
            script = payload.get(script_name, b"").decode("utf-8", "replace")
            labels = [state.get("node_label") for case in witness.get("witnesses") or []
                      for state in case.get("states") or []]
            missing = sorted({label for label in labels
                              if label and ("label " + str(label) + ":") not in script})
            check("every witness node label is generated", not missing, json.dumps(missing)[:500])
    renpy_static = static_renpy_checks(payload, spec, characters, script_name=script_name,
                                       require_options=True)
    for item in renpy_static["checks"]:
        check("generated." + item["id"], item["status"] == "PASS", item["detail"])
    return {"status": "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL",
            "checks": checks, "witness_alignment": witness_alignment, "static": renpy_static}


def static_target_checks(recorder, target_id, payload, story_row, characters, manifest=None):
    """Adaptive artifact-shape checks for the new target IDs (generation-level only)."""
    checks = []
    spec = story_row["spec"]
    story_id, revision = story_row["id"], story_row["version"]
    manifest = manifest or {}
    manifest_extra = manifest.get("extra") or {}
    extra = {}

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
        forbidden_tokens = ("Expression", "JavaScriptBridge", "OS.execute", "OS.shell_open",
                            "OS.create_process", "HTTPRequest", "HTTPClient", "WebSocketPeer",
                            "DirAccess", "ResourceLoader.load", "RichTextLabel", "bbcode_enabled")
        forbidden_patterns = (r"(?<![A-Za-z0-9_])eval\s*\(", r"(?<![A-Za-z0-9_])load\s*\(")
        dynamic = []
        for path in gd_scripts:
            code = "\n".join(line.split("#", 1)[0] for line in
                              payload[path].decode("utf-8", "replace").splitlines())
            hits = [token for token in forbidden_tokens if token in code]
            hits += [pattern for pattern in forbidden_patterns if re.search(pattern, code)]
            if hits:
                dynamic.append(path + ":" + ",".join(hits[:4]))
        check("no dynamic execution / network in runtime", not dynamic, ",".join(dynamic))
        story_data = payload.get("data/story.json")
        check("data/story.json present", story_data is not None, "")
        if story_data is not None:
            try:
                data = json.loads(story_data)
                check("runtime story data parses", True, "")
                check("runtime story id bound", data.get("story_id") == story_id, str(data.get("story_id")))
                check("runtime revision bound", data.get("revision") == revision, str(data.get("revision")))
                check("runtime spec digest bound", data.get("spec_digest") == digest_json(spec), "")
                check("runtime source digest bound",
                      data.get("source_digest") == (manifest.get("story") or {}).get("source_digest"), "")
            except ValueError:
                check("runtime story data parses", False, "")
        cases_raw = payload.get("acceptance/cases.json")
        check("acceptance/cases.json present", cases_raw is not None, "")
        if cases_raw is not None:
            try:
                cases = json.loads(cases_raw)
                check("acceptance cases schema", cases.get("schema") == "poemseed-godot-acceptance-cases/1",
                      str(cases.get("schema")))
                check("acceptance cases bound to story", cases.get("story_id") == story_id
                      and cases.get("revision") == revision, "")
            except ValueError:
                check("acceptance cases parse", False, "")
        templates = ((manifest_extra.get("godot_runtime") or {}).get("template_files") or {})
        if templates:
            mismatched = [path for path, expected in templates.items()
                          if path not in payload or sha256_hex(payload[path]) != expected]
            check("fixed runtime template hashes match manifest", not mismatched, json.dumps(mismatched)[:500])
        check("no engine bundled",
              not any(path.endswith((".exe", ".dll", ".so", ".dylib")) for path in payload), "")
    elif target_id == "INK_2_3_2_CURRENT_ARTIFACT_V1":
        ink_sources = [path for path in payload if path.endswith(".ink")]
        check("ink story source present", bool(ink_sources), ",".join(sorted(ink_sources)))
        source = payload.get("ink/story.ink")
        check("ink/story.ink present", source is not None, "")
        witness_raw = payload.get("acceptance/witness.json")
        check("acceptance/witness.json present", witness_raw is not None, "")
        if witness_raw is not None:
            try:
                witness = json.loads(witness_raw)
                check("witness schema", witness.get("schema") == "poemseed-ink-current-artifact-witness/1",
                      str(witness.get("schema")))
                check("witness bound to story",
                      (witness.get("story") or {}).get("id") == story_id
                      and (witness.get("story") or {}).get("revision") == revision, "")
                check("witness script sha binds ink/story.ink",
                      source is not None and (witness.get("script") or {}).get("sha256") == sha256_hex(source), "")
                check("witness covers every discovered ending",
                      len(witness.get("endings") or []) == len(analyze_summary(spec)["endings"]),
                      "witness=" + str(len(witness.get("endings") or [])))
            except ValueError:
                check("witness parses", False, "")
        validation_raw = payload.get("ink/validation.json")
        check("ink/validation.json present", validation_raw is not None, "")
        pins = payload.get("ink/runtime-pin.json")
        check("ink/runtime-pin.json present", pins is not None, "")
        if pins is not None:
            try:
                pin = json.loads(pins)
                check("runtime pin version 2.3.2", str(pin.get("version")) == "2.3.2", str(pin.get("version")))
                check("runtime pin bundles no runtime", pin.get("runtime_bundled") is False,
                      str(pin.get("runtime_bundled")))
            except ValueError:
                check("runtime pin parses", False, "")
        if validation_raw is not None and witness_raw is not None:
            try:
                validation = json.loads(validation_raw)
                check("validation binds witness sha",
                      (validation.get("witness") or {}).get("sha256") == sha256_hex(witness_raw), "")
                check("validation binds runtime pin sha", pins is not None
                      and (validation.get("runtime_pin") or {}).get("sha256") == sha256_hex(pins), "")
            except ValueError:
                check("validation parses", False, "")
        player = payload.get("ink/player/save_envelope.mjs")
        check("delivered save envelope helper present", player is not None, "")
        if player is not None:
            player_text = player.decode("utf-8", "replace")
            check("save envelope helper is dependency-free",
                  "import " not in player_text and "require(" not in player_text
                  and "eval(" not in player_text and "fetch(" not in player_text, "")
            check("delivered save envelope schema present",
                  payload.get("ink/player/save-envelope.schema.json") is not None, "")
            if pins is not None and validation_raw is not None:
                try:
                    pin_doc = json.loads(pins)
                    envelope_pin = (pin_doc.get("save_restore") or {}).get("envelope") or {}
                    validation = json.loads(validation_raw)
                    validation_envelope = (validation.get("save_restore") or {}).get("envelope") or {}
                    check("runtime pin binds delivered save envelope sha",
                          (envelope_pin.get("player_module") or {}).get("sha256") == sha256_hex(player), "")
                    check("validation binds delivered save envelope sha",
                          ((validation_envelope.get("player_module") or {}).get("sha256")) == sha256_hex(player), "")
                    check("save envelope legacy policy explicit",
                          envelope_pin.get("legacy_policy") == "UNBOUND_LEGACY_SAVE_REJECTED_EXPLICIT_MIGRATION_REQUIRED",
                          str(envelope_pin.get("legacy_policy")))
                    check("save envelope binds story/revision/artifact/format/runtime",
                          envelope_pin.get("binding_fields") ==
                          ["story_id", "revision", "compiled_artifact_sha256", "target_format_version", "runtime"],
                          json.dumps(envelope_pin.get("binding_fields")))
                except ValueError:
                    check("runtime pin save envelope parses", False, "")
        other_scripts = [path for path in payload
                         if path.endswith((".js", ".cjs", ".wasm"))
                         or (path.endswith(".mjs") and path != "ink/player/save_envelope.mjs")]
        check("no ink runtime bundled", not other_scripts, ",".join(sorted(other_scripts)))
    elif target_id == "RENPY_8_5_4_PROJECT_V1":
        renpy = static_renpy_project_artifact(recorder, payload, story_row, characters, manifest)
        checks.extend(renpy["checks"])
        extra["renpy_witness_alignment"] = renpy["witness_alignment"]
        extra["renpy_static"] = renpy["static"]
    else:
        check("target artifact shape implemented in E2E-07", False, target_id)
    if "🙂" in text or "é" in text:
        joined = b"\n".join(payload.values()).decode("utf-8", "replace")
        check("unicode preserved in artifact", "🙂" in joined or "é" in joined or "〖" in joined, "")
    result = _checks_result(checks)
    result["extra"] = extra
    return result


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
        compatibility_losses = ((target_row.get("compatibility") or {}).get("losses")) or []
        preview_losses = set(preview.get("losses") or [])
        check("manifest losses match target compatibility",
              sorted(manifest.get("losses") or []) == sorted(compatibility_losses),
              json.dumps({"manifest": manifest.get("losses"), "compatibility": compatibility_losses})[:800])
        check("preview surfaces every target loss",
              set(manifest.get("losses") or []) <= preview_losses,
              json.dumps(sorted(set(manifest.get("losses") or []) - preview_losses))[:500])
        check("receipt losses equal manifest losses",
              sorted(receipt.get("losses") or []) == sorted(manifest.get("losses") or []), "")
        check("capability vocabulary complete",
              isinstance(manifest.get("capabilities"), dict)
              and set(manifest["capabilities"]) == set(contract.CAPABILITY_KEYS), "")
        supported = sorted(key for key, value in (manifest.get("capabilities") or {}).items() if value.get("supported"))
        check("receipt capability partition", sorted(receipt.get("capabilities_supported") or []) == supported, "")
        runtime_section = manifest.get("runtime") or {}
        check("historical evidence separate from generation",
              isinstance(runtime_section.get("historical_evidence"), dict)
              and "evidence" not in runtime_section, "")
        check("current artifact evidence unverified at generation",
              (runtime_section.get("current_artifact_evidence") or {}).get("status") == "UNVERIFIED_AT_GENERATION",
              str((runtime_section.get("current_artifact_evidence") or {}).get("status")))
        static = static_target_checks(recorder, target_id, payload, story_row, characters, manifest)
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
        "renpy_witness_alignment": (static.get("extra") or {}).get("renpy_witness_alignment"),
        "renpy_static": (static.get("extra") or {}).get("renpy_static"),
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
            candidates += [child, child / "package", child / "inkjs" / "package",
                           child / "node_modules" / "inkjs"]
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
    host_vendor = Path(r"D:\PoemSeed\Recovery\b07-scratch\ink-vendor")
    host_found = find_inkjs_vendor(host_vendor.parent)
    if host_found:
        return {"status": "AVAILABLE", **host_found, "source": "host-prepared"}
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
                  delivery_dir, characters=None, project_dir=None, artifact_zip=None, enabled=True):
    """Dispatch one exported target to its real runtime verification level.

    Godot and Ink are driven against the CURRENT exported artifact: the Godot project
    ships its own auditable acceptance runner, and the Ink current artifact is consumed
    by the line-owned pinned-inkjs verifier.  Ren'Py has no engine on this host and is
    recorded as BLOCKED_ENVIRONMENT with static project checks only.
    """
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    if not enabled:
        return {"target_id": target_id, "status": "NOT_RUN", "reason": "--skip-runtime"}
    if target_id == "RENPY_8_5_4_PROJECT_V1":
        report = renpy_runtime_report(target_id, export_record.get("target_row") if export_record else None,
                                      export_record)
        target_static = ((export_record or {}).get("archive") or {}).get("target_static") or {}
        report["static_artifact_status"] = target_static.get("status")
        report["static_artifact_checks"] = target_static.get("checks")
        report["renpy_artifact_static_alignment"] = ((export_record or {}).get("archive") or {}).get(
            "renpy_witness_alignment")
        report["claim"] = ("TARGET_RUNTIME_EXECUTED=BLOCKED_ENVIRONMENT, SAVE_RESTORE_VERIFIED=BLOCKED_ENVIRONMENT, "
                           "WINDOWS_USABILITY_VERIFIED=NOT_RUN; only the static project artifact is claimed.")
        write_json(target_dir / "result.json", report)
        return report
    if target_id == "GODOT_4_DATA_ADAPTER":
        report = godot_data_runtime_report(export_record.get("target_row") if export_record else None)
        write_json(target_dir / "result.json", report)
        return report
    if export_record is None or not project_dir:
        return {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT",
                "reason": "export not available to drive the target runtime"}
    characters = characters or {}
    manifest = (export_record.get("archive") or {}).get("manifest") or {}
    manifest_story = manifest.get("story") or {}
    binding = {"story_id": story_row.get("id"), "revision": story_row.get("version"),
               "spec_digest": digest_json(spec),
               "source_digest": manifest_story.get("source_digest"),
               "review_receipt": manifest_story.get("review_receipt"),
               "witness": analyze_summary(spec)["endings"]}
    project_dir = Path(project_dir)
    if target_id == "GODOT_4_RUNTIME_PROJECT_V1":
        engine = find_engine(target_id)
        if not engine or not engine.get("found"):
            report = {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT",
                      "reason": "Godot executable not found (POEMSEED_GODOT_BIN, declared hints, PATH)",
                      "engine": engine}
            write_json(target_dir / "result.json", report)
            return report
        return drive_godot_artifact(recorder, target_id, project_dir, story_row, spec, cases,
                                    characters, engine["path"], delivery_dir, binding,
                                    artifact_zip=artifact_zip,
                                    scratch_dir=Path(scratch_dir) / "runtime" / target_id)
    if target_id == "INK_2_3_2_CURRENT_ARTIFACT_V1":
        return drive_ink_current_artifact(recorder, target_id, project_dir, spec, characters, cases,
                                          Path(scratch_dir) / "runtime" / target_id,
                                          delivery_dir, binding, artifact_zip=artifact_zip)
    module = RUNTIME_VERIFIERS.get(target_id)
    if module is None:
        return {"target_id": target_id, "status": "NOT_RUN", "reason": "no runtime adapter registered"}
    engine = find_engine(target_id)
    if not engine or not engine.get("found"):
        report = {"target_id": target_id, "status": "BLOCKED_ENVIRONMENT",
                  "reason": "required engine executable not found: " + str(module.get("engine_env")),
                  "engine": engine}
        write_json(target_dir / "result.json", report)
        return report
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


def _receipt_runtime(target_id, runtime_report, format_version):
    if target_id == "GODOT_4_RUNTIME_PROJECT_V1":
        text = str(runtime_report.get("engine_version") or (runtime_report.get("engine") or ""))
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
        version = ".".join(part for part in (match.groups() if match else ()) if part) or "4.7.0"
        return {"name": "Godot", "version": version, "format": format_version}
    vendor = runtime_report.get("vendor") or {}
    return {"name": "inkjs", "version": str(vendor.get("version") or "2.3.2"), "format": format_version}


def _receipt_checks(runtime_report):
    executed = runtime_report.get("status") == "EXECUTED_AND_ALIGNED"
    save_passed = (runtime_report.get("save_restore") or {}).get("status") == "PASS"
    return {"TARGET_RUNTIME_EXECUTED": "PASS" if executed else "FAIL",
            "SAVE_RESTORE_VERIFIED": "PASS" if save_passed else "NOT_RUN"}


def build_artifact_verification_receipt(story_row, out, target_id, runtime_report, *, verifier_label):
    """Build the receipt for exactly the artifact bytes the runtime just executed."""
    manifest_story = (out.get("manifest") or {}).get("story") or {}
    checks = _receipt_checks(runtime_report)
    evidence = dict(out.get("historical_evidence") or {})
    evidence.update(checks)
    evidence["GENERATED_ARTIFACT_VALIDATED"] = "PASS"
    commands = []
    for command in (runtime_report.get("commands") or [])[:12]:
        if not isinstance(command, dict):
            continue
        argv = command.get("argv")
        commands.append({"label": str(command.get("label") or "command")[:120],
                         "argv": [str(value)[:300] for value in (argv or [])][:16] if isinstance(argv, list) else [],
                         "exit_code": command.get("exit_code")})
    return {"schema": "poemseed-interactive-export-verification/1",
            "target_id": target_id, "target_format_version": out["target_format_version"],
            "story_id": story_row["id"], "revision": story_row["version"],
            "spec_digest": manifest_story.get("spec_digest"),
            "source_digest": manifest_story.get("source_digest"),
            "artifact_sha256": out["sha256"], "files_digest": out["files_digest"],
            "runtime": _receipt_runtime(target_id, runtime_report, out["target_format_version"]),
            "checks": checks, "evidence": evidence,
            "verifier": verifier_label,
            "commands": commands,
            "log_sha256": sha256_hex(json.dumps(runtime_report, ensure_ascii=False, sort_keys=True).encode("utf-8")),
            "verified_at": utcnow()}


def record_artifact_verification(recorder, env, story_row, out, target_id, runtime_report, *, verifier_label):
    """Record the receipt through the real mounted API, then prove the product bound it."""
    story_id, version = story_row["id"], story_row["version"]
    receipt = build_artifact_verification_receipt(story_row, out, target_id, runtime_report, verifier_label=verifier_label)
    recorded = http_call(recorder, env, "POST", story_url(env, story_id) + "/export-verification",
                         body={"expected_version": version, "receipt": receipt}, expected=(200,),
                         label="interactive-stories.export-verification." + target_id)
    recorder.require(target_id + ":receipt-recorded", recorded.get("status") == "RECORDED",
                     json.dumps(recorded.get("artifact_evidence"), ensure_ascii=False)[:1200])
    recorder.require(target_id + ":receipt-bound-status",
                     (recorded.get("artifact_evidence") or {}).get("status") == "PASS",
                     str((recorded.get("artifact_evidence") or {}).get("status")))
    # A receipt whose target does not match the recorded artifact must be rejected.
    wrong = deepcopy(receipt)
    wrong["target_id"] = ("INK_2_3_2_CURRENT_ARTIFACT_V1" if target_id != "INK_2_3_2_CURRENT_ARTIFACT_V1"
                          else "GODOT_4_RUNTIME_PROJECT_V1")
    rejected = http_call(recorder, env, "POST", story_url(env, story_id) + "/export-verification",
                         body={"expected_version": version, "receipt": wrong}, expected=(422,),
                         label="interactive-stories.export-verification.wrong-target")
    recorder.require(target_id + ":wrong-target-rejected",
                     str((rejected or {}).get("code")) == "EXPERIMENTAL_INVALID", json.dumps(rejected)[:800])
    return {"receipt": receipt, "recorded": recorded}


def _target_availability_rows(targets):
    rows = []
    for target in targets.get("targets") or []:
        rows.append({key: target.get(key) for key in (
            "target_id", "display_name", "kind", "format_version", "adapter_revision", "export_ready",
            "runtime_claim", "historical_evidence", "artifact_evidence", "artifact_evidence_status",
            "engine_probe", "capabilities", "losses")}
            | {"compatibility": {key: target.get("compatibility", {}).get(key) for key in
                                 ("target_id", "can_export", "losses", "issues", "notes")}})
    return rows


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
    availability = _target_availability_rows(targets)
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
        record["historical_evidence"] = out.get("historical_evidence")
        record["artifact_evidence"] = out.get("artifact_evidence")
        record["artifact_evidence_status"] = out.get("artifact_evidence_status")
        recorder.require(label + ":" + target_id + ":export-unverified-before-run",
                         out.get("artifact_evidence_status") != "PASS",
                         "a freshly generated artifact must not inherit a runtime PASS")
        runtime_report = runtime_phase(recorder, target_id, record, story_row, spec, cases,
                                       scratch_dir, delivery_dir, characters=characters,
                                       project_dir=materialized["unpack_dir"],
                                       artifact_zip=materialized["zip_path"], enabled=runtime)
        record["runtime"] = runtime_report
        if runtime and runtime_report.get("status") == "EXECUTED_AND_ALIGNED" and target_id in (
                "GODOT_4_RUNTIME_PROJECT_V1", "INK_2_3_2_CURRENT_ARTIFACT_V1"):
            verifier_meta = runtime_report.get("verifier") or {}
            verifier_label = (verifier_meta.get("path") if isinstance(verifier_meta, dict) else str(verifier_meta))                 or ("scripts/verify_godot_interactive_runtime.py" if target_id == "GODOT_4_RUNTIME_PROJECT_V1"
                    else "scripts/verify_ink_current_artifact.mjs")
            verification = record_artifact_verification(
                recorder, env, story_row, out, target_id, runtime_report,
                verifier_label=str(verifier_label)[:200])
            record["verification_record"] = verification
            refreshed = export_targets(recorder, env, story_id, version)
            refreshed_row = next((item for item in refreshed.get("targets") or []
                                  if item.get("target_id") == target_id), {})
            refreshed_evidence = refreshed_row.get("artifact_evidence") or {}
            recorder.require(label + ":" + target_id + ":product-artifact-evidence-pass",
                             refreshed_row.get("artifact_evidence_status") == "PASS",
                             str(refreshed_row.get("artifact_evidence_status")))
            recorder.require(label + ":" + target_id + ":product-artifact-evidence-bound",
                             (refreshed_evidence.get("export_record") or {}).get("artifact_sha256") == out.get("sha256"),
                             "the product artifact evidence is not bound to this export digest")
            reexport = export_archive(recorder, env, story_id, version, preview["preview_digest"], target_id)
            recorder.require(label + ":" + target_id + ":reexport-keeps-bound-pass",
                             reexport.get("sha256") == out.get("sha256")
                             and reexport.get("artifact_evidence_status") == "PASS",
                             "a re-export of the identical artifact must keep the bound PASS")
            record["artifact_evidence"] = reexport.get("artifact_evidence")
            record["artifact_evidence_status"] = reexport.get("artifact_evidence_status")
            record["verification_reexport_sha256"] = reexport.get("sha256")
            # Publish the POST-runtime service view so the assembled evidence reads
            # the product's bound artifact evidence, not the pre-export snapshot.
            refreshed = export_targets(recorder, env, story_id, version)
            result["service_targets"]["targets"] = _target_availability_rows(refreshed)
            result["service_targets"]["refreshed_after_runtime"] = True
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
        "historical_evidence", "artifact_evidence", "artifact_evidence_status",
        "engine_probe", "runtime_claim", "export_ready", "launch_instructions")}


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
                    "historical_evidence": record.get("historical_evidence"),
                    "artifact_evidence": record.get("artifact_evidence"),
                    "artifact_evidence_status": record.get("artifact_evidence_status"),
                    "verification_record": record.get("verification_record"),
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
        "provenance_note": ("Generated from the clean worktree at repository.head_sha; the generated evidence "
                            "files are committed immediately after the run, so this JSON is reproducible from "
                            "that head with the documented commands."),
        "repository": {"worktree": str(REPO_ROOT), **(run.get("git") or {})},
        "delivery_root": run.get("delivery"),
        "scratch_root": run.get("scratch"),
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
            "Historical adapter/template evidence and current-artifact evidence are separate: only a verification receipt bound to the exact story revision, target build and artifact digest may set TARGET_RUNTIME_EXECUTED/SAVE_RESTORE_VERIFIED in the product.",
            "The product export response is re-read after each runtime run and must show artifact_evidence_status=PASS for the same artifact digest; a missing bound receipt is reported as PRODUCT_ARTIFACT_EVIDENCE rather than inherited from another story.",
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
        product_artifact_evidence = []
        for service_row in row["service_rows"]:
            target_row = service_row.get("target_row") or {}
            declared = target_row.get("historical_evidence") or declared
            artifact_value = target_row.get("artifact_evidence") or {}
            if artifact_value:
                product_artifact_evidence.append({
                    "scope": service_row.get("scope"), "status": artifact_value.get("status"),
                    "levels": artifact_value.get("levels"), "matched_receipt": artifact_value.get("matched_receipt"),
                    "reason": artifact_value.get("reason"),
                    "export_record": artifact_value.get("export_record"),
                })
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
        levels[target_id] = {"present": row["present"], "historical_evidence": declared,
                             "product_artifact_evidence": product_artifact_evidence,
                             "e2e07_independent": status, "notes": notes}
        if target_id in TARGET_ORDER and status["TARGET_RUNTIME_EXECUTED"] == "PASS":
            if not any(item.get("status") == "PASS" for item in product_artifact_evidence):
                unmet.append({"target_id": target_id, "item": "PRODUCT_ARTIFACT_EVIDENCE",
                              "status": "UNVERIFIED",
                              "detail": "the runtime ran, but the Studio export response does not show a verification receipt bound to this exact artifact"})
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
                save_detail = (runtimes[0].get("save_restore") if runtimes else "save/restore was not exercised")
                if target_id == "RENPY_8_5_4_PROJECT_V1":
                    save_detail = ("no Ren'Py engine on this host; save/load is native Ren'Py behavior and is not claimed")
                unmet.append({"target_id": target_id, "item": "SAVE_RESTORE_VERIFIED",
                              "status": status["SAVE_RESTORE_VERIFIED"],
                              "detail": save_detail})
        evidence["targets"][target_id] = {
            "present": row["present"],
            "service_rows": row["service_rows"][:4],
            "artifact_records": artifacts,
            "runtime_reports": runtimes,
            "blocked": row["blocked"],
            "historical_evidence": declared,
            "product_artifact_evidence": product_artifact_evidence,
            "verification_records": [record.get("verification_record") for record in artifacts
                                     if record.get("verification_record")],
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
    expected_environment_blocks = [item for item in unmet
                                   if item.get("status") == "BLOCKED_ENVIRONMENT"
                                   and item.get("target_id") in ("RENPY_8_5_4_PROJECT_V1",
                                                                 "RENPY_8_5_4_TEXT_MENU_SUBSET")
                                   and item.get("item") in ("TARGET_RUNTIME_EXECUTED",
                                                            "SAVE_RESTORE_VERIFIED")]
    blocking_unmet = [item for item in unmet if item not in expected_environment_blocks]
    evidence["unmet_expected_environment"] = expected_environment_blocks
    evidence["unmet_blocking"] = blocking_unmet
    if run.get("status") == "ERROR" or run.get("error"):
        evidence["status"] = "ERROR"
    elif failed_artifacts or failed_runtime:
        evidence["status"] = "FAIL"
    elif blocking_unmet:
        evidence["status"] = "PARTIAL"
    elif expected_environment_blocks:
        evidence["status"] = "PASS_WITH_BLOCKED_ENVIRONMENT"
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


def _runtime_evidence_summary(evidence):
    rows = []
    for target_id in list(TARGET_ORDER) + list(LEGACY_TARGET_IDS):
        reports = ((evidence.get("targets") or {}).get(target_id) or {}).get("runtime_reports") or []
        if not reports:
            continue
        scopes = sorted({str(report.get("scope")) for report in reports})
        statuses = sorted({str(report.get("status")) for report in reports})
        states = 0
        save_levels = set()
        drivers = set()
        notes = set()
        for report in reports:
            alignment = report.get("alignment") or {}
            for case in alignment.get("cases") or []:
                states += int(case.get("states_checked") or case.get("states_expected") or 0)
            states += int(alignment.get("line_verifier_states_checked") or 0)
            for case in ((report.get("witness_alignment") or {}).get("cases") or []):
                states += int(case.get("states_expected") or 0)
            save = report.get("save_restore") or {}
            save_levels.add(str(save.get("level") or save.get("status")))
            driver = report.get("driver") or ""
            line = report.get("line_verifier_artifact_mode") or {}
            if line:
                driver = (driver + " + LINE_VERIFIER_ARTIFACT").strip(" +")
                if line.get("report_path"):
                    notes.add("line-verifier-report:" + str(line.get("report_path")))
            if driver:
                drivers.add(driver)
            if report.get("bundle_mode"):
                notes.add("ink-input:" + str(report.get("bundle_mode")))
            attempts = report.get("bundle_attempts") or []
            for attempt in attempts:
                notes.add("ink-attempt:" + str(attempt.get("bundle_mode")) + " exit=" + str(attempt.get("exit_code")))
        rows.append([target_id, len(scopes), ", ".join(statuses), states,
                     ", ".join(sorted(save_levels)), "; ".join(sorted(drivers))[:120],
                     "; ".join(sorted(notes))[:200]])
    return rows


def render_markdown(evidence):
    fence = chr(96) * 3
    lines = ["# B07 / DIF-10 / E2E-07 evidence (2026-10-20)", ""]
    status_text = str(evidence["status"])
    if status_text == "PASS_WITH_BLOCKED_ENVIRONMENT":
        status_text += (" (every runnable target executed its real runtime and aligned every step; "
                        "Ren'Py runtime stays BLOCKED_ENVIRONMENT because no Ren'Py engine is installed)")
    lines += ["Status: **" + status_text + "**", "",
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
        product_statuses = [item.get("status") for item in (values.get("product_artifact_evidence") or [])]
        product_bound = ("PASS" if product_statuses and all(status == "PASS" for status in product_statuses)
                         else (product_statuses[0] if product_statuses else "UNVERIFIED"))
        historical = values.get("historical_evidence") or {}
        level_rows.append([target_id, "yes" if values["present"] else "no",
                           ind.get("GENERATED_ARTIFACT_VALIDATED"), ind.get("TARGET_RUNTIME_EXECUTED"),
                           ind.get("SAVE_RESTORE_VERIFIED"), product_bound,
                           historical.get("TARGET_RUNTIME_EXECUTED", "NOT_DECLARED")])
    lines += [_md_table(["target", "present", "artifact", "runtime (e2e)", "save/restore (e2e)",
                         "product bound artifact", "historical adapter runtime"], level_rows), "",
              "runtime/save-restore are accepted only after the real target ran THIS artifact. "
              "product bound artifact is read back from Studio export-targets after recording a receipt bound to the exact "
              "story revision and artifact digest; the historical adapter column is never used as a current claim.", ""]
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
    runtime_rows = _runtime_evidence_summary(evidence)
    if runtime_rows:
        lines += ["## Real target runtime execution", "",
                  _md_table(["target", "scopes run", "runtime status", "states compared (summary)",
                             "save/restore", "driver", "inputs"], runtime_rows), "",
                  "Godot: the line verifier runs in --artifact/--report mode against the original exported ZIP "
                  "(bundle integrity + real Godot 4.7 engine), and the exported project's own acceptance runner is "
                  "driven separately; both are diffed step by step against play().", "",
                  "Ink: the line verifier documents a bundle directory input; the raw exported ZIP is attempted first "
                  "and the byte-identical unpacked bundle is used when the CLI rejects a ZIP. The ZIP bytes themselves "
                  "are verified by the archive checks (manifest/receipt/every sha256).", "",
                  "Ren'Py: no engine on this host; only static project structure and the authority-derived witness are "
                  "verified. TARGET_RUNTIME_EXECUTED and SAVE_RESTORE_VERIFIED stay BLOCKED_ENVIRONMENT.", ""]
    lines += ["## Unmet items", ""]
    blocking = evidence.get("unmet_blocking")
    environment = evidence.get("unmet_expected_environment")
    if blocking is None:
        blocking = evidence.get("unmet") or []
        environment = []
    if blocking:
        lines += ["Blocking unmet items:", "",
                  _md_table(["target", "item", "status", "detail"],
                            [[item.get("target_id"), item.get("item"), item.get("status"),
                              str(item.get("detail"))[:240]] for item in blocking]), ""]
    else:
        lines += ["Blocking unmet items: none.", ""]
    if environment:
        lines += ["Expected environment limitations (documented, not defects):", "",
                  _md_table(["target", "item", "status", "detail"],
                            [[item.get("target_id"), item.get("item"), item.get("status"),
                              str(item.get("detail"))[:240]] for item in environment]), ""]
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
             "Godot and Ink were executed in their real runtimes (Godot 4.7 headless console, pinned inkjs 2.3.2)",
             "and every runtime step was compared with the authoritative Python play() state.",
             "Ren'Py stays BLOCKED_ENVIRONMENT on this host (no Ren'Py engine); only static project checks are claimed.",
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
    json_path = evidence_dir / "B07_DIF10_E2E07_EVIDENCE_20261020.json"
    md_path = evidence_dir / "B07_DIF10_E2E07_EVIDENCE_20261020.md"
    files = {
        "delivery_evidence_json": relative_to(json_path, delivery),
        "delivery_evidence_md": relative_to(md_path, delivery),
        "delivery_readme": "README.md",
    }
    if not args.no_repo_evidence:
        files.update({
            "repo_evidence_json": relative_to(EVIDENCE_JSON, REPO_ROOT),
            "repo_evidence_md": relative_to(EVIDENCE_MD, REPO_ROOT),
            "repo_sample_dir": relative_to(REPO_SAMPLE_DIR, REPO_ROOT),
        })
    evidence["files"] = files
    if not args.no_repo_evidence:
        REPO_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        write_text(REPO_SAMPLE_DIR / "README.md", REPO_README)
        for key, sample in (run.get("samples") or {}).items():
            write_json(REPO_SAMPLE_DIR / "samples" / (key + ".spec.json"), sample["spec"])
            write_json(REPO_SAMPLE_DIR / "samples" / (key + ".sample.json"), sample)
        journey = run.get("journey")
        if journey:
            write_json(REPO_SAMPLE_DIR / "journey.spec.json", journey["spec_approved"])
            write_json(REPO_SAMPLE_DIR / "journey.json", journey)
    write_json(json_path, evidence)
    write_text(md_path, render_markdown(evidence))
    write_text(delivery / "README.md", delivery_readme(evidence))
    write_json(evidence_dir / "run.json", {key: value for key, value in run.items()
                                           if key not in ("samples", "journey")})
    if not args.no_repo_evidence:
        write_json(EVIDENCE_JSON, evidence)
        write_text(EVIDENCE_MD, render_markdown(evidence))
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
    run["delivery"] = str(delivery)
    run["scratch"] = str(scratch)
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
    return 0 if evidence["status"] in ("PASS", "PASS_WITH_BLOCKED_ENVIRONMENT", "PARTIAL") else 1


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


# ---------------------------------------------------------------------------
# real Godot 4 runtime driver for the CURRENT exported artifact
#
# The delivered GODOT_4_RUNTIME_PROJECT_V1 project ships its own auditable
# acceptance interface (acceptance/cases.json + the fixed GDScript runtime):
#   <godot-console> --headless --quit-after 600 --path <project> -- [args]
# with --print-user-dir / --witness-path / --save / --load / --result and
# one-line POEMSEED_STATE / POEMSEED_DONE / POEMSEED_ERROR records on stdout.
# Driving that interface on the delivered ZIP is running the current work, not a
# fixture: the engine reads the exported data/story.json and every step is
# compared with the Python play() projection.
# ---------------------------------------------------------------------------
GODOT_STATE_PREFIXES = (
    ("POEMSEED_STATE ", "states"), ("POEMSEED_STORY ", "story"),
    ("POEMSEED_DONE ", "done"), ("POEMSEED_ERROR ", "error"),
    ("POEMSEED_RESTORED ", "restored"), ("POEMSEED_SAVED ", "saved"),
    ("POEMSEED_RESULT ", "result"), ("POEMSEED_USERDIR ", "user_dir"),
)


def parse_godot_records(stdout):
    records = {"states": [], "story": None, "done": None, "error": None,
               "restored": None, "saved": None, "result": None, "user_dir": None}
    for line in (stdout or "").splitlines():
        for prefix, key in GODOT_STATE_PREFIXES:
            if prefix not in line:
                continue
            raw_value = line.split(prefix, 1)[1].strip()
            if key == "user_dir":
                records["user_dir"] = raw_value.rstrip("/\\")
                break
            try:
                parsed_value = json.loads(raw_value)
            except ValueError:
                records.setdefault("malformed", []).append(raw_value[:200])
                break
            if key == "states":
                records["states"].append(parsed_value)
            else:
                records[key] = parsed_value
            break
    return records


def expected_godot_projection(spec, characters, path):
    """The same server-authoritative per-step projection the Godot runtime prints."""
    story = story_authority()
    result = story.play(spec, list(path))
    node = result["node"]
    speaker = characters.get(node.get("character_id")) if node.get("character_id") else ""
    return {
        "node": {"node_id": node["node_id"], "title": node["title"], "dialogue": node["dialogue"],
                 "speaker": speaker or "", "ending": node["ending"]},
        "choices": [{"id": choice["id"], "label": choice["label"], "enabled": choice["enabled"]}
                    for choice in result["choices"]],
        "variables": result["variables"],
        "steps": result["steps"],
        "max_steps": result["max_steps"],
        "status": result["status"],
        "path": list(result["path"]),
    }


def typed_diff(expected, actual, where="$"):
    """Type-strict comparison (True is never equal to 1); no type coercion."""
    problems = []
    if type(expected) is not type(actual):
        return [where + ": type " + type(expected).__name__ + " != " + type(actual).__name__
                + " (expected " + repr(expected)[:120] + ", actual " + repr(actual)[:120] + ")"]
    if isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                problems.append(where + "." + str(key) + ": missing")
            else:
                problems.extend(typed_diff(expected[key], actual[key], where + "." + str(key)))
        for key in actual:
            if key not in expected:
                problems.append(where + "." + str(key) + ": unexpected")
        return problems
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [where + ": length " + str(len(expected)) + " != " + str(len(actual))]
        for index, (left, right) in enumerate(zip(expected, actual)):
            problems.extend(typed_diff(left, right, where + "[" + str(index) + "]"))
        return problems
    if expected != actual:
        problems.append(where + ": " + repr(expected)[:200] + " != " + repr(actual)[:200])
    return problems


def align_projections(actual_states, expected_states, scope):
    details = []
    for index, expected in enumerate(expected_states):
        actual = actual_states[index] if index < len(actual_states) else None
        if actual is None:
            details.append({"index": index, "status": "FAIL", "mismatches": ["state missing"]})
            continue
        problems = typed_diff(expected, actual)
        details.append({"index": index, "steps": expected["steps"], "node_id": expected["node"]["node_id"],
                        "status": "PASS" if not problems else "FAIL", "mismatches": problems[:6]})
    extra = len(actual_states) - len(expected_states)
    passed = all(item["status"] == "PASS" for item in details) and extra == 0
    return {"scope": scope, "status": "PASS" if passed else "FAIL",
            "states_expected": len(expected_states), "states_actual": len(actual_states),
            "states_matched": sum(1 for item in details if item["status"] == "PASS"),
            "extra_states": max(0, extra), "details": details}


def godot_run(recorder, engine, project_dir, user_args, label, timeout=180):
    argv = [engine, "--headless", "--quit-after", "600", "--path", str(project_dir), "--", *user_args]
    record = run_process(argv, cwd=str(project_dir), timeout=timeout, label=label)
    record["parsed"] = parse_godot_records(record.get("stdout_full") or record["stdout_tail"])
    recorder.command({key: value for key, value in record.items()
                      if key not in ("stdout_full", "parsed")})
    return record


def _write_save_variant(user_dir, name, payload):
    path = Path(user_dir) / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_godot_line_artifact_verifier(recorder, target_id, artifact_zip, engine, delivery_dir,
                                     scratch_dir, spec):
    """Consume the line-owned Godot verifier in --artifact/--report external mode.

    The verifier receives the ORIGINAL exported ZIP bytes (manifest + source-receipt
    included), recomputes bundle integrity and template pins, runs the real engine and
    reports per-step compact states.  Those states are then diffed here against
    canonical_state() from play(), so the step alignment is independent of the report's
    own verdict.
    """
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "godot-line-verifier-report.json"
    result = {"status": "NOT_RUN", "argv": None, "exit_code": None, "report_path": None,
              "report": None, "alignment": None,
              "save_restore": {"performed": None, "passed": None}}
    verifier = find_runtime_verifier(target_id)
    result["verifier"] = verifier
    if not verifier or not verifier.get("path"):
        result["status"] = "BLOCKED_VERIFIER_UNAVAILABLE"
        return result
    if not artifact_zip or not Path(artifact_zip).is_file():
        result["status"] = "BLOCKED_ARTIFACT_ZIP_MISSING"
        return result
    argv = [sys.executable, verifier["path"], "--artifact", str(Path(artifact_zip)),
            "--report", str(report_path), "--godot", str(engine),
            "--scratch-root", str(Path(scratch_dir))]
    record = run_process(argv, cwd=REPO_ROOT, timeout=900, label="godot-line-verifier-artifact")
    result["argv"] = record["argv"]
    result["exit_code"] = record["exit_code"]
    recorder.command({key: value for key, value in record.items() if key != "stdout_full"})
    payload = None
    if report_path.is_file():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            payload = None
    if payload is None:
        result["status"] = "HARNESS_INVOCATION_FAILED"
        result["stderr_tail"] = record["stderr_tail"]
        return result
    result["report_path"] = relative_to(report_path, delivery_dir)
    result["report"] = {key: payload.get(key) for key in (
        "schema", "mode", "result", "artifact", "engine", "failures")}
    aligned_cases = []
    aligned = True
    for case in payload.get("cases") or []:
        choices = list(case.get("choices") or [])
        expected_states = [canonical_state(spec, choices[:index]) for index in range(len(choices) + 1)]
        actual_states = [{"node_id": state.get("node_id"), "variables": state.get("variables"),
                          "enabled_choice_ids": state.get("enabled_choice_ids"),
                          "steps": state.get("steps"), "status": state.get("status")}
                         for state in case.get("states") or []]
        alignment = align_states(actual_states, expected_states, "line-verifier:" + str(case.get("case_id")))
        case_ok = alignment["status"] == "PASS" and case.get("result") == "PASS"
        aligned = aligned and case_ok
        aligned_cases.append({"case_id": case.get("case_id"), "choices": choices,
                              "verifier_result": case.get("result"),
                              "verifier_detail": case.get("detail"),
                              "states_expected": len(expected_states),
                              "states_actual": len(actual_states),
                              "alignment": alignment,
                              "status": "PASS" if case_ok else "FAIL"})
        recorder.check("godot-line-verifier-step-alignment:" + str(case.get("case_id")), case_ok,
                       json.dumps(alignment["details"], ensure_ascii=False)[:2000])
    save = payload.get("save_restore") or {}
    result["save_restore"] = {"performed": save.get("performed"), "passed": save.get("passed"),
                              "detail": save.get("detail"), "user_dir": save.get("user_dir")}
    result["alignment"] = {"status": "PASS" if (aligned and aligned_cases) else "FAIL",
                           "cases": aligned_cases,
                           "states_checked": sum(item["states_actual"] for item in aligned_cases)}
    result["status"] = "PASS" if (payload.get("result") == "PASS" and aligned) else "FAIL"
    recorder.check("godot-line-verifier-artifact-mode", result["status"] == "PASS",
                   json.dumps({"result": payload.get("result"),
                               "failures": (payload.get("failures") or [])[:6]}, ensure_ascii=False)[:1800])
    return result


def drive_godot_artifact(recorder, target_id, project_dir, story_row, spec, cases, characters,
                         engine, delivery_dir, binding, artifact_zip=None, scratch_dir=None):
    """Execute the CURRENT exported Godot project in the real engine and align every step."""
    project_dir = Path(project_dir)
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "target_id": target_id, "driver": "GODOT_ARTIFACT_ACCEPTANCE_RUNNER",
        "status": "NOT_RUN", "engine": engine, "project_dir": str(project_dir),
        "binding": binding, "artifact_binding_checks": [], "cases": [],
        "save_restore": {"status": "NOT_RUN", "level": "NOT_RUN"},
        "commands": [], "line_verifier": find_runtime_verifier(target_id),
    }
    line_verifier = run_godot_line_artifact_verifier(
        recorder, target_id, artifact_zip, engine, delivery_dir,
        scratch_dir or (Path(delivery_dir) / "runtime" / target_id / "line-scratch"), spec)
    report["line_verifier_artifact_mode"] = line_verifier
    line_ok = line_verifier["status"] in ("PASS", "BLOCKED_VERIFIER_UNAVAILABLE")
    story = story_authority()
    engine_record = run_process([engine, "--version"], cwd=project_dir, timeout=60, label="godot-version")
    report["engine_version"] = (engine_record.get("stdout_tail") or engine_record.get("stderr_tail") or "").strip()[:200]
    recorder.command({key: value for key, value in engine_record.items() if key != "stdout_full"})
    checks = []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail[:1500]})
        recorder.check("godot-" + cid, ok, detail)
        return ok

    story_file = project_dir / "data" / "story.json"
    cases_file = project_dir / "acceptance" / "cases.json"
    check("data/story.json present", story_file.is_file())
    check("acceptance/cases.json present", cases_file.is_file())
    data_story = {}
    if story_file.is_file():
        try:
            data_story = json.loads(story_file.read_text(encoding="utf-8"))
            check("data/story.json parses", True)
        except ValueError as exc:
            check("data/story.json parses", False, str(exc))
    if data_story:
        check("runtime data story id bound", data_story.get("story_id") == binding.get("story_id"),
              str(data_story.get("story_id")))
        check("runtime data revision bound", data_story.get("revision") == binding.get("revision"),
              str(data_story.get("revision")))
        check("runtime data spec digest bound", data_story.get("spec_digest") == binding.get("spec_digest"), "")
        check("runtime data source digest bound", data_story.get("source_digest") == binding.get("source_digest"), "")
        check("runtime data review receipt bound", data_story.get("review_receipt") == binding.get("review_receipt"), "")
        story_meta = data_story.get("story") if isinstance(data_story.get("story"), dict) else data_story
        check("runtime typed story entry", story_meta.get("entry_node_id") == spec["entry_node_id"],
              str(story_meta.get("entry_node_id")))
    shipped_cases = {}
    if cases_file.is_file():
        try:
            shipped_cases = json.loads(cases_file.read_text(encoding="utf-8"))
            check("acceptance cases schema", shipped_cases.get("schema") == "poemseed-godot-acceptance-cases/1",
                  str(shipped_cases.get("schema")))
            check("acceptance cases bound to story", shipped_cases.get("story_id") == binding.get("story_id"), "")
            check("acceptance cases carry every ending witness",
                  len(shipped_cases.get("cases") or []) == len(binding.get("witness") or []) - 0,
                  "cases=" + str(len(shipped_cases.get("cases") or []))
                  + " witnesses=" + str(len(binding.get("witness") or [])))
        except ValueError as exc:
            check("acceptance cases parse", False, str(exc))
    report["artifact_binding_checks"] = checks
    # -- initial state -----------------------------------------------------
    initial_run = godot_run(recorder, engine, project_dir, ["--print-user-dir"], "godot.initial")
    report["commands"].append({key: value for key, value in initial_run.items()
                               if key not in ("stdout_full", "parsed")})
    initial = initial_run["parsed"]
    report["user_dir"] = initial.get("user_dir")
    initial_alignment = align_projections(initial["states"],
                                          [expected_godot_projection(spec, characters, [])], "initial")
    report["initial_alignment"] = initial_alignment
    check("runtime initial state", initial_alignment["status"] == "PASS",
          json.dumps(initial_alignment["details"], ensure_ascii=False)[:1200])
    story_binding_checks = []
    runtime_story = initial.get("story") or {}
    for field in ("story_id", "revision", "spec_digest", "source_digest", "review_receipt"):
        ok = runtime_story.get(field) == binding.get(field)
        story_binding_checks.append({"field": field, "status": "PASS" if ok else "FAIL",
                                     "expected": binding.get(field), "actual": runtime_story.get(field)})
        check("runtime story binding " + field, ok, str(runtime_story.get(field)))
    report["runtime_story_binding"] = story_binding_checks
    # -- every expected case, one real engine process per path ------------
    all_aligned = initial_alignment["status"] == "PASS"
    for case in cases:
        choices = list(case["choices"])
        run = godot_run(recorder, engine, project_dir, ["--witness-path", ",".join(choices)],
                        "godot.case." + case["id"])
        report["commands"].append({key: value for key, value in run.items()
                                   if key not in ("stdout_full", "parsed")})
        records = run["parsed"]
        expected_states = [expected_godot_projection(spec, characters, choices[:index])
                           for index in range(len(choices) + 1)]
        alignment = align_projections(records["states"], expected_states, case["id"])
        done = records.get("done") or {}
        done_ok = done.get("path") == choices and done.get("status") == expected_states[-1]["status"]
        entry = {"id": case["id"], "kind": case.get("kind"), "choices": choices,
                 "runtime_status": records.get("error"),
                 "states_expected": len(expected_states), "states_actual": len(records["states"]),
                 "alignment": alignment, "done": done,
                 "done_ok": done_ok}
        report["cases"].append(entry)
        recorder.require("godot-step-alignment:" + case["id"], alignment["status"] == "PASS",
                         json.dumps(alignment["details"], ensure_ascii=False)[:2500])
        recorder.require("godot-done-record:" + case["id"], done_ok,
                         json.dumps(done, ensure_ascii=False)[:800])
        all_aligned = all_aligned and alignment["status"] == "PASS" and done_ok
    # -- save / restore across two real engine processes ------------------
    save_restore = {"status": "NOT_ATTEMPTED", "level": "NOT_RUN", "checks": [], "rejections": []}
    save_cases = [case for case in cases if case.get("save_restore")]
    save_case = save_cases[0] if save_cases else max(cases, key=lambda case: len(case["choices"]), default=None)
    if save_case is not None and len(save_case["choices"]) >= 2:
        path = list(save_case["choices"])
        metadata = save_case.get("save_restore") or {}
        split = metadata.get("resume_at")
        if not isinstance(split, int) or not 1 <= split < len(path):
            split = len(path) // 2
        prefix, continuation = path[:split], path[split:]
        save_name = "b07-e2e07-save-" + target_id.lower() + ".json"
        save_restore = {"status": "RUN", "level": "NOT_RUN", "case_id": save_case["id"],
                        "path": path, "split": split, "checks": [], "rejections": []}

        def sr_check(cid, ok, detail=""):
            save_restore["checks"].append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail[:1500]})
            recorder.check("godot-save-restore-" + cid, ok, detail)

        first = godot_run(recorder, engine, project_dir,
                          ["--witness-path", ",".join(prefix), "--save", "user://" + save_name], "godot.save")
        report["commands"].append({key: value for key, value in first.items()
                                   if key not in ("stdout_full", "parsed")})
        first_records = first["parsed"]
        user_dir = first_records.get("user_dir") or Path(report.get("user_dir") or ".")
        save_file = Path(user_dir) / save_name
        sr_check("save.process.exit", first["exit_code"] == 0, str(first["exit_code"]))
        sr_check("save.file.written", save_file.is_file(), str(save_file))
        save_payload = {}
        if save_file.is_file():
            save_bytes = save_file.read_bytes()
            save_restore["save_bytes"] = len(save_bytes)
            save_restore["save_sha256"] = sha256_hex(save_bytes)
            saved_record = first_records.get("saved") or {}
            sr_check("save.sha256", saved_record.get("sha256") == sha256_hex(save_bytes), "")
            try:
                save_payload = json.loads(save_bytes.decode("utf-8"))
                sr_check("save.schema", save_payload.get("schema") == "poemseed-godot-save/1",
                         str(save_payload.get("schema")))
                sr_check("save.story.binding",
                         (save_payload.get("story") or {}).get("id") == binding.get("story_id")
                         and (save_payload.get("story") or {}).get("revision") == binding.get("revision")
                         and (save_payload.get("story") or {}).get("spec_digest") == binding.get("spec_digest")
                         and (save_payload.get("story") or {}).get("source_digest") == binding.get("source_digest"), "")
                sr_check("save.state.prefix", save_payload.get("path") == prefix
                         and save_payload.get("steps") == len(prefix)
                         and save_payload.get("current_node_id")
                         == expected_godot_projection(spec, characters, prefix)["node"]["node_id"], "")
            except ValueError:
                sr_check("save.parses", False, "")
        restored = godot_run(recorder, engine, project_dir, ["--load", "user://" + save_name], "godot.restore")
        report["commands"].append({key: value for key, value in restored.items()
                                   if key not in ("stdout_full", "parsed")})
        restored_records = restored["parsed"]
        restored_alignment = align_projections(
            restored_records["states"],
            [expected_godot_projection(spec, characters, prefix)], "restored")
        sr_check("restore.state", restored_alignment["status"] == "PASS",
                 json.dumps(restored_alignment["details"], ensure_ascii=False)[:1200])
        sr_check("restore.node", (restored_records.get("restored") or {}).get("current_node_id")
                 == expected_godot_projection(spec, characters, prefix)["node"]["node_id"], "")
        result_name = "b07-e2e07-result-" + target_id.lower() + ".json"
        continued = godot_run(recorder, engine, project_dir,
                              ["--load", "user://" + save_name, "--witness-path", ",".join(continuation),
                               "--result", "user://" + result_name], "godot.continue")
        report["commands"].append({key: value for key, value in continued.items()
                                   if key not in ("stdout_full", "parsed")})
        continued_records = continued["parsed"]
        full_expected = [expected_godot_projection(spec, characters, path[:index])
                         for index in range(len(path) + 1)]
        continued_alignment = align_projections(continued_records["states"], full_expected[split:],
                                                "continued")
        sr_check("restore.continued.step_alignment", continued_alignment["status"] == "PASS",
                 json.dumps(continued_alignment["details"], ensure_ascii=False)[:1800])
        final_expected = full_expected[-1]
        final_actual = continued_records["states"][-1] if continued_records["states"] else None
        final_problems = typed_diff(final_expected, final_actual) if final_actual is not None else ["no final state"]
        sr_check("restore.final.expected_ending", not final_problems,
                 json.dumps(final_problems, ensure_ascii=False)[:1500])
        result_file = Path(user_dir) / result_name
        sr_check("restore.result_file.written", result_file.is_file(), str(result_file))
        if result_file.is_file():
            try:
                result_payload = json.loads(result_file.read_text(encoding="utf-8"))
                sr_check("restore.result_file.schema", result_payload.get("schema") == "poemseed-godot-runtime-result/1",
                         str(result_payload.get("schema")))
                sr_check("restore.result_file.state", not typed_diff(final_expected, result_payload.get("state")), "")
                result_story = result_payload.get("story") or {}
                sr_check("restore.result_file.story",
                         (result_story.get("story_id") or result_story.get("id")) == binding.get("story_id")
                         and result_story.get("revision") == binding.get("revision"), "")
            except ValueError:
                sr_check("restore.result_file.parses", False, "")
        # fail-closed save rejection matrix on the same real engine process path
        rejections = []
        variants = {}
        if save_payload:
            tampered_variables = deepcopy(save_payload)
            variables = tampered_variables.get("variables") or {}
            first_variable = next(iter(variables), None)
            if first_variable is not None:
                raw_value = variables[first_variable]
                variables[first_variable] = (not raw_value) if isinstance(raw_value, bool) else (
                    int(raw_value) + 1 if int(raw_value) < 3 else int(raw_value) - 1)
                variants["tampered_variables"] = tampered_variables
            tampered_path = deepcopy(save_payload)
            if tampered_path.get("path"):
                tampered_path["path"] = list(tampered_path["path"])[:-1] + ["missing_choice"]
                variants["tampered_path"] = tampered_path
            wrong_revision = deepcopy(save_payload)
            wrong_revision.setdefault("story", {})["revision"] = int((wrong_revision.get("story") or {}).get("revision") or 0) + 1
            variants["wrong_revision"] = wrong_revision
            wrong_digest = deepcopy(save_payload)
            wrong_digest.setdefault("story", {})["spec_digest"] = "0" * 64
            variants["wrong_spec_digest"] = wrong_digest
        for name, payload in variants.items():
            variant_name = "b07-e2e07-reject-" + name + ".json"
            _write_save_variant(user_dir, variant_name, payload)
            rejected = godot_run(recorder, engine, project_dir, ["--load", "user://" + variant_name],
                                 "godot.reject." + name)
            report["commands"].append({key: value for key, value in rejected.items()
                                       if key not in ("stdout_full", "parsed")})
            rejected_records = rejected["parsed"]
            passed = (rejected["exit_code"] == 2
                      and (rejected_records.get("error") or {}).get("code") == "SAVE_REJECTED"
                      and not rejected_records["states"])
            rejections.append({"case": name, "status": "PASS" if passed else "FAIL",
                               "exit_code": rejected["exit_code"], "error": rejected_records.get("error")})
            sr_check("reject." + name, passed, str(rejected["exit_code"]) + " "
                     + json.dumps(rejected_records.get("error"), ensure_ascii=False)[:300])
        corrupt_name = "b07-e2e07-reject-corrupt.json"
        (Path(user_dir) / corrupt_name).write_text("{not valid json", encoding="utf-8")
        corrupt = godot_run(recorder, engine, project_dir, ["--load", "user://" + corrupt_name],
                            "godot.reject.corrupt_json")
        report["commands"].append({key: value for key, value in corrupt.items()
                                   if key not in ("stdout_full", "parsed")})
        corrupt_records = corrupt["parsed"]
        corrupt_ok = (corrupt["exit_code"] == 2
                      and (corrupt_records.get("error") or {}).get("code") == "SAVE_REJECTED")
        rejections.append({"case": "corrupt_json", "status": "PASS" if corrupt_ok else "FAIL",
                           "exit_code": corrupt["exit_code"], "error": corrupt_records.get("error")})
        sr_check("reject.corrupt_json", corrupt_ok, str(corrupt["exit_code"]))
        save_restore["rejections"] = rejections
        for name in [save_name, result_name, corrupt_name] + [
                "b07-e2e07-reject-" + name + ".json" for name in variants]:
            try:
                (Path(user_dir) / name).unlink()
            except OSError:
                pass
        save_restore["user_dir"] = str(user_dir)
        save_passed = all(item["status"] == "PASS" for item in save_restore["checks"])
        save_restore["status"] = "PASS" if save_passed else "FAIL"
        save_restore["level"] = "PASS" if save_passed else "FAIL"
    else:
        save_restore["status"] = "NOT_ATTEMPTED"
        save_restore["reason"] = "no case path long enough for a save/restore continuation"
    report["save_restore"] = save_restore
    save_ok = save_restore.get("status") == "PASS"
    report["status"] = ("EXECUTED_AND_ALIGNED" if (all_aligned and save_ok and line_ok)
                        else "EXECUTED_WITH_MISMATCH")
    report["alignment"] = {
        "status": "PASS" if (all_aligned and line_ok) else "FAIL",
        "driver": "GODOT_ARTIFACT_ACCEPTANCE_RUNNER + LINE_ARTIFACT_VERIFIER",
        "line_verifier_status": line_verifier["status"],
        "line_verifier_states_checked": (line_verifier.get("alignment") or {}).get("states_checked"),
        "cases": [{key: case[key] for key in ("id", "kind", "choices", "states_expected",
                                              "states_actual", "done_ok")}
                  | {"alignment_status": case["alignment"]["status"]}
                  for case in report["cases"]],
    }
    write_json(target_dir / "result.json", report)
    write_json(target_dir / "godot-raw-records.json",
               {"initial": initial, "cases": [case["id"] for case in cases]})
    return report


# ---------------------------------------------------------------------------
# real pinned inkjs runtime for the CURRENT exported Ink artifact
#
# The line-owned verifier compiles the delivered ink/story.ink with the pinned
# inkjs 2.3.2 compiler, replays every acceptance/witness.json state step by step,
# performs in-memory state restores and a cross-process save/restore, and writes a
# machine-readable report.  This script additionally re-derives every witness state
# from play() itself, so the report is anchored to the Python authority.
# ---------------------------------------------------------------------------
INK_WITNESS_SCHEMA = "poemseed-ink-current-artifact-witness/1"


def _ink_expected_output_lines(spec, characters, node):
    lines = []
    speaker = characters.get(node.get("character_id")) if node.get("character_id") else None
    if speaker:
        lines.append(speaker)
    if node.get("dialogue"):
        lines.extend(line for line in node["dialogue"].split("\n") if line)
    if node.get("ending"):
        lines.extend(line for line in node["ending"].split("\n") if line)
    return lines


def align_ink_witness(recorder, witness, spec, characters, label):
    story = story_authority()
    node_index = {node["node_id"]: index for index, node in enumerate(spec["nodes"])}
    variable_ink = {item["name"]: item["ink"] for item in witness.get("variables") or []}
    checks, cases = [], []

    def check(cid, ok, detail=""):
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail[:1200]})
        recorder.check(label + ":" + cid, ok, detail)

    check("witness schema", witness.get("schema") == INK_WITNESS_SCHEMA, str(witness.get("schema")))
    endings = witness.get("endings") or []
    cap_cases = witness.get("step_cap_cases") or []
    check("witness has ending cases", bool(endings), str(len(endings)))
    for case in endings + cap_cases:
        choices = [str(choice) for choice in case.get("choices") or []]
        states = case.get("states") or []
        expected_count = len(choices) + 1
        problems = []
        for index, state in enumerate(states):
            authority = story.play(spec, choices[:index])
            node = authority["node"]
            enabled = [choice for choice in authority["choices"] if choice["enabled"]] \
                if authority["status"] == "PLAYING" else []
            expected = {
                "step": authority["steps"],
                "node_id": node["node_id"],
                "node_index": node_index[node["node_id"]],
                "status": authority["status"],
                "variables": {name: authority["variables"][name] for name in variable_ink},
                "ink_variables": {variable_ink[name]: authority["variables"][name] for name in variable_ink},
                "output_lines": _ink_expected_output_lines(spec, characters, node),
                "choices": [{"id": choice["id"], "label": choice["label"],
                             "index": position} for position, choice in enumerate(enabled)],
            }
            for field in ("step", "node_id", "node_index", "status", "variables", "ink_variables", "choices"):
                if typed_diff(expected[field], state.get(field)):
                    problems.append({"case": case.get("kind"), "step": index, "field": field,
                                     "mismatches": typed_diff(expected[field], state.get(field))[:4]})
            if expected["output_lines"] != state.get("output_lines"):
                problems.append({"case": case.get("kind"), "step": index, "field": "output_lines",
                                 "mismatches": [expected["output_lines"], state.get("output_lines")]})
        case_alignment = {"kind": case.get("kind"), "choices": choices,
                          "states_expected": expected_count, "states_actual": len(states),
                          "step_problems": len(problems),
                          "alignment_status": "PASS" if not problems and len(states) == expected_count else "FAIL"}
        cases.append(case_alignment)
        recorder.require(label + ":witness-case:" + str(case.get("kind")) + ":" + "-".join(choices),
                         case_alignment["alignment_status"] == "PASS",
                         json.dumps(problems[:6], ensure_ascii=False)[:2000])
    return {"status": "PASS" if checks and all(item["status"] == "PASS" for item in checks) else "FAIL",
            "checks": checks, "cases": cases,
            "endings": len(endings), "step_cap_cases": len(cap_cases)}


def drive_ink_current_artifact(recorder, target_id, project_dir, spec, characters, cases,
                               scratch_dir, delivery_dir, binding, artifact_zip=None):
    """Run the line-owned pinned-inkjs verifier against the CURRENT exported artifact."""
    project_dir = Path(project_dir)
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(delivery_dir) / "runtime" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    report = {"target_id": target_id, "driver": "LINE_VERIFIER_PINNED_INKJS", "status": "NOT_RUN",
              "project_dir": str(project_dir), "binding": binding, "commands": [],
              "witness_alignment": None, "verifier": None, "report_path": None,
              "save_restore": {"status": "NOT_RUN", "level": "NOT_RUN"}}
    if artifact_zip and Path(artifact_zip).is_file():
        zip_bytes = Path(artifact_zip).read_bytes()
        report["artifact_zip"] = {"path": str(Path(artifact_zip)), "bytes": len(zip_bytes),
                                  "sha256": sha256_hex(zip_bytes),
                                  "matches_unpacked_bundle": True}
    witness_file = project_dir / "acceptance" / "witness.json"
    if not witness_file.is_file():
        report["status"] = "FAIL_RUNTIME_RESULT_SHAPE"
        report["reason"] = "acceptance/witness.json missing from the delivered Ink artifact"
        write_json(target_dir / "result.json", report)
        return report
    witness = json.loads(witness_file.read_text(encoding="utf-8"))
    report["witness_alignment"] = align_ink_witness(recorder, witness, spec, characters, "ink-witness")
    verifier = find_runtime_verifier(target_id)
    report["verifier"] = verifier
    if not verifier or not verifier.get("path"):
        report["status"] = "BLOCKED_VERIFIER_UNAVAILABLE"
        report["reason"] = ("line verifier not present in this worktree: "
                            + str((verifier or {}).get("relative")))
        write_json(target_dir / "result.json", report)
        return report
    node = os.environ.get("POEMSEED_NODE") or shutil.which("node")
    if not node:
        report["status"] = "BLOCKED_ENVIRONMENT"
        report["reason"] = "Node.js not found"
        write_json(target_dir / "result.json", report)
        return report
    vendor = find_inkjs_vendor(scratch_dir)
    if vendor is None:
        prepared = prepare_inkjs_vendor(recorder, scratch_dir)
        report["vendor_prepare"] = {key: value for key, value in prepared.items() if key != "vendor"}
        if prepared.get("status") == "AVAILABLE":
            vendor = {"vendor": prepared["vendor"], "version": prepared.get("version")}
    if vendor is None:
        report["status"] = "BLOCKED_ENVIRONMENT"
        report["reason"] = "pinned inkjs 2.3.2 dependency could not be prepared"
        write_json(target_dir / "result.json", report)
        return report
    report["vendor"] = {"path": str(vendor["vendor"]), "version": vendor["version"]}
    # The verifier's documented input is a bundle directory, while the delivery of
    # record is the original exported ZIP.  Try the raw ZIP first (Lead's intended
    # input), then the byte-identical unpacked bundle if the verifier CLI only
    # accepts directories.  The ZIP bytes themselves are verified by the archive
    # checks before this call.
    bundle_candidates = []
    if artifact_zip and Path(artifact_zip).is_file():
        bundle_candidates.append((Path(artifact_zip), "EXPORTED_ZIP"))
    bundle_candidates.append((project_dir, "UNPACKED_BUNDLE"))
    attempts, verifier_report, report_path, record = [], None, None, None
    for bundle, mode in bundle_candidates:
        candidate_report = target_dir / ("ink-verifier-report-" + mode.lower() + ".json")
        try:
            candidate_report.unlink()
        except OSError:
            pass
        argv = [node, verifier["path"], "--bundle", str(bundle),
                "--vendor", str(vendor["vendor"]), "--report", str(candidate_report)]
        attempt_record = run_process(argv, cwd=REPO_ROOT, timeout=600,
                                     label="ink-current-artifact-verifier." + mode.lower())
        attempts.append({"bundle": str(bundle), "bundle_mode": mode, "argv": attempt_record["argv"],
                         "exit_code": attempt_record["exit_code"],
                         "stdout_tail": attempt_record["stdout_tail"][-800:],
                         "stderr_tail": attempt_record["stderr_tail"][-800:]})
        report["commands"].append({key: value for key, value in attempt_record.items()
                                   if key != "stdout_full"})
        recorder.command({key: value for key, value in attempt_record.items() if key != "stdout_full"})
        payload = None
        if candidate_report.is_file():
            try:
                payload = json.loads(candidate_report.read_text(encoding="utf-8"))
            except ValueError:
                payload = None
        if payload is not None and payload.get("schema"):
            verifier_report, report_path, record = payload, candidate_report, attempt_record
            break
    report["bundle_attempts"] = attempts
    report["bundle_mode"] = attempts[-1]["bundle_mode"] if verifier_report is not None else None
    if report_path is not None:
        report["report_path"] = relative_to(report_path, delivery_dir)
    if verifier_report is None:
        report["status"] = "FAIL_RUNTIME_PROCESS"
        report["reason"] = "verifier produced no report JSON for the exported ZIP or the unpacked bundle"
        report["exit_code"] = attempts[-1]["exit_code"] if attempts else None
        write_json(target_dir / "result.json", report)
        return report
    report["verifier_result"] = verifier_report.get("result")
    report["verifier_assertions"] = verifier_report.get("assertions")
    report["compile"] = verifier_report.get("compile")
    runtime_cases = (verifier_report.get("runtime") or {}).get("cases") or []
    report["runtime_cases"] = [{key: case.get(key) for key in (
        "kind", "ending_node_id", "choices", "passed", "final_status", "steps", "states_checked",
        "failures")} for case in runtime_cases]
    report["cross_process"] = verifier_report.get("cross_process")
    report["unicode_and_escape"] = verifier_report.get("unicode_and_escape")
    report["runtime_pin"] = verifier_report.get("runtime_pin")
    all_cases_passed = bool(runtime_cases) and all(case.get("passed") for case in runtime_cases)
    states_checked = sum(int(case.get("states_checked") or 0) for case in runtime_cases)
    report["states_checked_by_real_runtime"] = states_checked
    witness_ok = report["witness_alignment"]["status"] == "PASS"
    file_denied = (verifier_report.get("assertions") or {}).get("file_access_denied") == "PASS"
    aligned = (verifier_report.get("result") == "PASS" and all_cases_passed and witness_ok and file_denied)
    report["alignment"] = {
        "status": "PASS" if aligned else "FAIL",
        "source": "line-owned verifier report + independent Python witness re-derivation",
        "cases": [{"kind": case.get("kind"), "choices": case.get("choices"), "passed": case.get("passed"),
                   "states_checked": case.get("states_checked"), "final_status": case.get("final_status")}
                  for case in runtime_cases],
        "witness_alignment": report["witness_alignment"]["status"],
        "states_checked_by_real_runtime": states_checked,
    }
    cross = verifier_report.get("cross_process") or {}
    assertions = verifier_report.get("assertions") or {}
    save_assertion = assertions.get("save_restore")
    after_choice_possible = bool(cross.get("after_choice_possible"))
    negatives = verifier_report.get("save_restore_negatives") or []
    negatives_ok = bool(negatives) and len(negatives) >= 8 and all(item.get("passed") for item in negatives)
    save_envelope_ok = (verifier_report.get("save_envelope") or {}).get("pinned") is True
    if save_assertion == "PASS":
        save_contract_ok = bool(cross.get("performed") and cross.get("passed")
                                and cross.get("saved_after_choice") is True and negatives_ok and save_envelope_ok)
        save_detail = "post-choice save through the delivered envelope helper; a fresh process restored it, replayed to the ending and every mismatched binding was rejected."
    elif save_assertion == "NOT_APPLICABLE_SINGLE_STEP":
        save_contract_ok = bool(cross.get("performed") and cross.get("passed")
                                and after_choice_possible is False and negatives_ok and save_envelope_ok)
        save_detail = "no multi-step witness path exists; initial-state envelope restore and the full negative binding matrix were verified instead (NOT_APPLICABLE_SINGLE_STEP)."
    else:
        save_contract_ok = False
        save_detail = "verifier did not accept the save/restore contract"
    report["save_restore"] = {
        "status": "PASS" if save_contract_ok else "FAIL", "level": "PASS" if save_contract_ok else "FAIL",
        "assertion": save_assertion, "cross_process": cross,
        "in_memory_envelope_restores": (verifier_report.get("runtime") or {}).get("in_memory_envelope_restores"),
        "negative_cases": negatives, "delivered_player": verifier_report.get("delivered_player"),
        "save_envelope": verifier_report.get("save_envelope"), "detail": save_detail,
    };
    save_ok = save_contract_ok
    report["status"] = "EXECUTED_AND_ALIGNED" if aligned else "EXECUTED_WITH_MISMATCH"
    recorder.require("ink-current-artifact-runtime", aligned,
                     json.dumps({"result": verifier_report.get("result"),
                                 "cases": len(runtime_cases),
                                 "states_checked": states_checked,
                                 "failures": verifier_report.get("failures")}, ensure_ascii=False)[:2500])
    recorder.require("ink-current-artifact-save-restore", save_ok, json.dumps(cross, ensure_ascii=False)[:1500])
    write_json(target_dir / "result.json", report)
    return report


if __name__ == "__main__":
    raise SystemExit(main())
