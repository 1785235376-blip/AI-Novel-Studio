"""Captured-output reporting must never crash the verification runner (D-22 class).

scripts/run_v2_checks.py captured child output and printed it through the caller's
console encoding. On a cp936 console an unrepresentable character (for example a
replacement character in a fixture name) raised UnicodeEncodeError *after* the
checks had already run, losing the suite result and masking real pytest failures.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_v2_checks_under_test",
                                                  ROOT / "scripts" / "run_v2_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_captured_output_falls_back_to_utf8_bytes(monkeypatch):
    runner = _load_runner()
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="gbk", errors="strict", newline="\n")
    monkeypatch.setattr(sys, "stdout", stream)
    runner._print_captured("prefix \ufffd suffix")
    stream.flush()
    payload = buffer.getvalue().decode("utf-8", errors="replace")
    assert "prefix" in payload
    assert "suffix" in payload


def test_captured_output_uses_normal_print_when_encodable(monkeypatch, capsys):
    runner = _load_runner()
    runner._print_captured("plain ascii output")
    captured = capsys.readouterr()
    assert "plain ascii output" in captured.out
