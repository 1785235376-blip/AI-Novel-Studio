"""Read archived backend receipts for timing diagnostics, never coverage approval.

No network calls, pytest execution, receipt repair, test assignment or gate writes.
Push and pull-request runs are intentionally separate analysis units.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

JOB = re.compile(r"Backend execution / (file|postgres) / shard (\d+)\Z")
PROGRESS = re.compile(r"^(\S+) ([.sFExX]+) +\[ *\d+%\]$")
EXECUTION = "Complete backend collection / assigned shard execution"


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def identify(node):
    # Raw parameter IDs can exceed 4 MiB. Never normalize their identity.
    return {"preview": node[:240], "preview_truncated": len(node) > 240,
            "utf8_sha256": sha256(node.encode("utf-8"))}


def seconds(start, end):
    require(bool(start) and bool(end), "timing is missing a boundary")
    value = (datetime.fromisoformat(end.replace("Z", "+00:00")) -
             datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
    require(value >= 0, "negative time interval")
    return round(value, 6)


def terminal_event(row):
    when, outcome = row["when"], row["outcome"]
    if when == "call":
        return {"passed": ".", "failed": "F", "skipped": "s"}[outcome]
    if outcome == "failed":
        return "E"
    if outcome == "skipped":
        return "s"
    return ""


def analyze_events(receipt, rows):
    assigned = receipt["assigned"]
    require(len(assigned) == len(set(assigned)), "duplicate assigned identity")
    allowed = set(assigned)
    phases = defaultdict(list)
    failures, terminal = [], []
    call_outcomes = Counter()
    setup_skips = 0
    for row in rows:
        node, when, outcome = row["nodeid"], row["when"], row["outcome"]
        require(node in allowed, "event belongs to a different assignment")
        require(when in {"setup", "call", "teardown"}, "unknown event phase")
        require(outcome in {"passed", "failed", "skipped"}, "unknown event outcome")
        require(not row.get("wasxfail"), "xfail/xpass cannot be timed as normal evidence")
        previous = phases[node]
        require(when not in previous, "duplicate node phase")
        require((not previous and when == "setup") or
                (previous == ["setup"] and when in {"call", "teardown"}) or
                (previous == ["setup", "call"] and when == "teardown"),
                "invalid event phase order")
        previous.append(when)
        if when == "call":
            call_outcomes[outcome] += 1
        if when == "setup" and outcome == "skipped":
            setup_skips += 1
        if outcome == "failed":
            failures.append({"node": identify(node), "phase": when})
        char = terminal_event(row)
        if char:
            terminal.append((char, node))
    summary = {
        "assigned_nodes": len(assigned), "event_rows": len(rows),
        "observed_event_nodes": len(phases),
        "nodes_with_teardown_event": sum(p[-1] == "teardown" for p in phases.values()),
        "unobserved_nodes": len(allowed - set(phases)),
        "observed_call_outcomes": dict(sorted(call_outcomes.items())),
        "observed_setup_skips": setup_skips,
        "failed_events": failures,
        "last_observed_node": identify(rows[-1]["nodeid"]) if rows else None,
        "boundary": "Event observations only; teardown presence is not gate acceptance.",
    }
    return summary, terminal


def progress_windows(log, terminal, step_start):
    """Attribute only exact matched progress chunks, not individual test durations."""
    expected = "".join(char for char, _ in terminal)
    offset, previous, windows = 0, step_start, []
    for line in log.splitlines():
        match = PROGRESS.fullmatch(line)
        if not match:
            continue
        stamp, chars = match.groups()
        # This job also runs infrastructure pytest before the product suite.
        # Those earlier progress lines are not product execution evidence.
        if datetime.fromisoformat(stamp.replace("Z", "+00:00")) < datetime.fromisoformat(step_start.replace("Z", "+00:00")):
            continue
        require(expected[offset:offset + len(chars)] == chars,
                "progress output does not match original ordered event statuses")
        nodes = [node for _, node in terminal[offset:offset + len(chars)]]
        windows.append({
            "seconds": seconds(previous, stamp),
            "start_utc": previous, "end_utc": stamp,
            "first_terminal_ordinal": offset + 1,
            "last_terminal_ordinal": offset + len(chars),
            "first_node": identify(nodes[0]), "last_node": identify(nodes[-1]),
            "module_status_counts": dict(sorted(Counter(n.split("::", 1)[0] for n in nodes).items())),
        })
        offset += len(chars)
        previous = stamp
    return {"matched_terminal_statuses": offset,
            "unmatched_tail_statuses": len(terminal) - offset,
            "largest_windows": sorted(windows, key=lambda row: -row["seconds"])[:12],
            "boundary": "Timestamped progress chunks include inter-test overhead; the first includes collection/startup. No per-node duration is inferred."}


def junit_timings(path, assigned):
    root = ET.fromstring(path.read_bytes())
    modules = defaultdict(float)
    nodes, longest = [], []
    for case in root.iter("testcase"):
        ids = [p.get("value") for p in case.findall("./properties/property") if p.get("name") == "ci_nodeid"]
        require(len(ids) == 1 and ids[0] in assigned, "JUnit lacks an exact assigned node identity")
        node = ids[0]
        duration = float(case.get("time", "0"))
        require(0 <= duration < float("inf"), "invalid JUnit duration")
        nodes.append(node)
        modules[node.split("::", 1)[0]] += duration
        longest.append({"node": identify(node), "seconds": duration})
    require(len(nodes) == len(set(nodes)) and set(nodes) == set(assigned),
            "JUnit timing inventory is incomplete or duplicated")
    return {"summed_testcase_seconds": round(sum(modules.values()), 3),
            "slowest_modules": [{"module": name, "seconds": round(duration, 3)}
                                for name, duration in sorted(modules.items(), key=lambda row: -row[1])[:15]],
            "slowest_cases": sorted(longest, key=lambda row: -row["seconds"])[:15],
            "boundary": "JUnit durations are observed testcase totals, not an independent coverage verdict."}


def analyze_run(folder):
    inputs = {}

    def read(path):
        raw = path.read_bytes()
        inputs[path.relative_to(folder).as_posix()] = sha256(raw)
        return raw

    run = json.loads(read(folder / "run-final.json"))
    jobs = json.loads(read(folder / "jobs-final.json"))["jobs"]
    artifacts = json.loads(read(folder / "artifacts-final.json"))["artifacts"]
    require(run["name"] == "Cloud CI", "expected Cloud CI archive")
    repository = run["repository"]["full_name"]
    expected = {"run_id": str(run["id"]), "run_attempt": str(run["run_attempt"]),
                "repository": repository}
    reports, identities, job_keys = [], set(), set()
    for job in jobs:
        match = JOB.fullmatch(job["name"])
        if not match:
            continue
        backend, index_text = match.groups()
        index = int(index_text)
        require((backend, index) not in job_keys, "duplicate backend execution job")
        job_keys.add((backend, index))
        require(job["run_id"] == run["id"] and job["run_attempt"] == run["run_attempt"] and
                job["head_sha"] == run["head_sha"], "job belongs to another run/source/attempt")
        steps = [{"name": step["name"], "conclusion": step["conclusion"],
                  "seconds": seconds(step["started_at"], step["completed_at"])}
                 for step in job["steps"] if step.get("started_at") and step.get("completed_at")]
        execution = [step for step in job["steps"] if step["name"] == EXECUTION]
        require(len(execution) == 1, "missing or ambiguous complete-suite step")
        report = {"job_id": job["id"], "name": job["name"], "conclusion": job["conclusion"],
                  "html_url": job["html_url"], "job_seconds": seconds(job["started_at"], job["completed_at"]),
                  "steps": steps, "budget_seconds": 1200 if backend == "file" else 3300}
        prefix = f"backend-{backend}-shard-{index}-"
        matches = [a for a in artifacts if a["name"].startswith(prefix) and
                   a["name"].endswith(f"-attempt-{run['run_attempt']}")]
        require(len(matches) <= 1, "ambiguous artifact for a shard")
        if not matches:
            report["receipt_status"] = "MISSING"
            reports.append(report)
            continue
        artifact = matches[0]
        require(artifact["workflow_run"]["id"] == run["id"] and
                artifact["workflow_run"]["head_sha"] == run["head_sha"],
                "artifact belongs to another run/source")
        directory = folder / f"artifact-{int(artifact['id'])}"
        receipt = json.loads(read(directory / "coverage.json"))
        identity = receipt["identity"]
        require(all(str(identity.get(key)) == value for key, value in expected.items()),
                "receipt identity belongs to another run/attempt/repository")
        require(artifact["name"] == prefix + identity["event_sha"] + f"-attempt-{run['run_attempt']}",
                "artifact event SHA differs from receipt")
        if run["event"] in {"push", "workflow_dispatch"}:
            require(identity["checked_out_sha"] == run["head_sha"] == identity["event_sha"],
                    "push/dispatch receipt source differs from run head")
        require(receipt["backend"] == backend and receipt["shard"] ==
                {"index": index, "count": 1 if backend == "file" else 2},
                "receipt backend/shard differs from frozen contract")
        identities.add((identity["checked_out_sha"], identity["source_tree"], identity["event_sha"]))
        rows = [json.loads(line) for line in read(directory / "coverage-events.jsonl").splitlines() if line]
        events, terminal = analyze_events(receipt, rows)
        report.update(receipt_status="OBSERVED", identity=identity,
                      receipt_complete=receipt["complete"], pytest_exitstatus=receipt["pytest_exitstatus"],
                      artifact_id=artifact["id"], events=events)
        logfile = folder / f"job-{job['id']}.log"
        if logfile.is_file():
            lines = read(logfile).decode("utf-8").splitlines()
            starts = [i for i, line in enumerate(lines) if "PYTHONPATH=" in line and
                      "python -m pytest -p postgres_gate -p suite_coverage" in line]
            require(len(starts) == 1, "missing or ambiguous original suite command in log")
            # API step timestamps have whole-second precision; the preceding
            # infrastructure suite can finish within that same second.
            product_log = "\n".join(lines[starts[0] + 1:])
            report["progress_timing"] = progress_windows(product_log, terminal,
                                                          execution[0]["started_at"])
        xml = directory / "backend.xml"
        if xml.is_file():
            read(xml)
            report["junit_timing"] = junit_timings(xml, set(receipt["assigned"]))
        else:
            report["junit_timing"] = {"status": "MISSING", "per_case_durations": "UNKNOWN"}
        reports.append(report)
    require(bool(reports), "archive has no backend execution jobs")
    require(len(identities) <= 1, "mixed source/tree/event identities within one run")
    return {"schema_version": 1, "status": "DIAGNOSTIC_ONLY", "coverage_verdict": "NOT_EVALUATED",
            "tool_sha256": sha256(Path(__file__).read_bytes()),
            "run_id": run["id"], "run_attempt": run["run_attempt"], "event": run["event"],
            "head_sha": run["head_sha"], "repository": repository, "jobs": reports,
            "input_sha256": dict(sorted(inputs.items())),
            "limits": ["Does not execute or replace the frozen coverage reconciler.",
                       "Does not merge push, PR, attempts or backend profiles.",
                       "No runtime is extrapolated from partial completion.",
                       "Cancellation and observed failed phases remain separate facts.",
                       "Input digests identify local archive bytes; this tool does not independently authenticate GitHub downloads."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze_run(args.run_dir.resolve())
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
    except (EvidenceError, OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        print(f"Capacity evidence rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
