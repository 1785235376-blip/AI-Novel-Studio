"""Instrumented request bytes/Python peaks and observable Windows working set.

Windows PeakWorkingSetSize is a process-lifetime high water mark. The sampled
working set is observation only, not a per-request RSS bound or memory limit.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from threading import Event, Thread

import pytest
from studio_asset_usage_fixture import usage_rig, graph_create, create_timeline, snapshot
from studio_asset_usage_resource_meter import measured_cost

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.skipif(os.name != "nt", reason="Windows working set observations")]


def process_memory():
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                        "PagefileUsage", "PeakPagefileUsage")]]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"working_set_bytes": counters.WorkingSetSize,
            "process_lifetime_peak_working_set_bytes": counters.PeakWorkingSetSize,
            "pagefile_usage_bytes": counters.PagefileUsage}


def test_combined_source_first_continuation_replay_memory_and_actual_bytes(usage_rig, monkeypatch):
    e = usage_rig
    graph_create(e, 3, "combined-memory-graph")
    create_timeline(e)
    before = snapshot(e.rig.root)
    records, cursor, continuation = [], None, None
    for phase in ("initialized_first", "continuation", "replay_continuation", "repeat_first"):
        params = {"limit": 2}
        if phase in {"continuation", "replay_continuation"}:
            params["cursor"] = cursor
        stop, samples = Event(), [process_memory()]

        def sample():
            while not stop.wait(.005):
                samples.append(process_memory())

        sampler = Thread(target=sample)
        sampler.start()
        try:
            response, metrics = measured_cost(e.rig.root, monkeypatch,
                lambda: e.client.get(e.usage_base + "/studio-asset-usages", params=params, headers=e.headers))
        finally:
            stop.set()
            sampler.join(5)
        samples.append(process_memory())
        assert not sampler.is_alive()
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["other_dependencies"] == "UNKNOWN" and len(body["items"]) == 2
        if phase == "initialized_first":
            cursor = body["next_cursor"]
            assert cursor
        elif phase == "continuation":
            continuation = body["items"]
        elif phase == "replay_continuation":
            assert body["items"] == continuation
        assert len(metrics["usage_budgets"]) == 1
        assert metrics["read_bytes"] == metrics["usage_budgets"][0]["charged_read_bytes"]
        assert all(row["physical_input_via_usage_budget"] for row in metrics["rows"] if row["read_calls"])
        assert metrics["write_calls"] == metrics["created_directories"] == 0
        records.append({"phase": phase, "response_bytes": len(response.content), **metrics,
                        "memory_before": samples[0], "memory_after": samples[-1],
                        "sampled_working_set_peak_bytes": max(s["working_set_bytes"] for s in samples),
                        "working_set_samples": len(samples),
                        "memory_scope": "5ms samples can miss peaks; lifetime process high-water includes setup/import; not RSS hard bound"})
    assert snapshot(e.rig.root) == before
    output = Path(os.environ["STUDIO_TEST_RUN_ROOT"]) / "combined-windows-memory.json"
    output.write_text(json.dumps({"scenario": "1 saved graph 3 pins and 1 timeline pin; original integrated main.app HTTP",
                                  "os_cache": "not cleared", "records": records}, indent=2), encoding="utf-8")
    print("COMBINED_WINDOWS_MEMORY_JSON", output)
