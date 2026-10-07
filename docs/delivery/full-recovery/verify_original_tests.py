"""Compare current original tests with the immutable PR45 Git tree."""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASELINE = "665817243cad59eef0d4140f17c2ea644f46971e"
OUTPUT = pathlib.Path(__file__).resolve().parent / "original-test-preservation.json"


def run(*args, input=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, input=input, text=True, encoding="utf-8")


tree = {}
for line in run("ls-tree", "-r", "--format=%(objectname)\t%(path)", BASELINE).splitlines():
    digest, name = line.split("\t", 1)
    if name.startswith("tests/") or ".test." in name or ".spec." in name or "/Tests/" in name:
        tree[name] = digest
paths = sorted(tree)
hashes = run("hash-object", "--stdin-paths", input="\n".join(paths) + "\n").splitlines()
changed = []
for name, digest in zip(paths, hashes):
    if tree[name] == digest:
        continue
    row = {"path": name, "baseline_git_blob": tree[name], "current_git_blob": digest}
    original_bytes = subprocess.check_output(["git", "show", BASELINE + ":" + name], cwd=ROOT)
    current_bytes = (ROOT / name).read_bytes()
    row.update(baseline_bytes=len(original_bytes), current_bytes=len(current_bytes),
               baseline_sha256=hashlib.sha256(original_bytes).hexdigest(),
               current_sha256=hashlib.sha256(current_bytes).hexdigest())
    try:
        before = original_bytes.decode("utf-8-sig")
        current = current_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        row.update(binary_fixture=True, review_scope="Explicit visual golden update; original assertion/source audit remains separate")
        changed.append(row)
        continue
    if name.endswith(".py"):
        assertions = lambda source: [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(source))
                                     if isinstance(node, ast.Assert)]
        original_assertions, current_assertions = assertions(before), assertions(current)
        row.update(assertions_identical=original_assertions == current_assertions,
                   original_assertions=len(original_assertions), current_assertions=len(current_assertions),
                   baseline_assertion_sha256=hashlib.sha256(json.dumps(original_assertions).encode()).hexdigest(),
                   current_assertion_sha256=hashlib.sha256(json.dumps(current_assertions).encode()).hexdigest())
    if name == "frontend/tests/visual/design-system.spec.ts":
        # The only declared exception is three added handlers in the existing
        # synthetic route fixture. Removing exactly those additions must
        # reproduce every byte of the complete original source.
        markers = ('if(path.endsWith(\'/writing-goal\'))',
                   'if(path.endsWith(\'/text-models\')||path.endsWith(\'/chapters/archived\'))',
                   'if(path.endsWith(\'/experimental/features\'))')
        additions = [line for line in current.splitlines(keepends=True) if any(marker in line for marker in markers)]
        reconstructed = ''.join(line for line in current.splitlines(keepends=True) if line not in additions)
        row.update(added_fixture_handlers=len(additions), all_original_test_blocks_identical=reconstructed == before,
                   baseline_test_blocks_sha256=hashlib.sha256(before.encode()).hexdigest(),
                   current_test_blocks_sha256=hashlib.sha256(reconstructed.encode()).hexdigest())
        expectations = lambda value: [line.strip() for line in value.splitlines() if re.search(r"\bexpect\s*\(", line)]
        original_expectations, current_expectations = expectations(before), expectations(current)
        remaining = iter(current_expectations)
        all_original_expectations_preserved = all(any(value == expected for value in remaining) for expected in original_expectations)
        row.update(all_original_expectation_lines_identical=original_expectations == current_expectations,
                   all_original_expectation_lines_preserved_in_order=all_original_expectations_preserved,
                   original_expectations=len(original_expectations), current_expectations=len(current_expectations),
                   baseline_expectation_sha256=hashlib.sha256(json.dumps(original_expectations).encode()).hexdigest(),
                   current_expectation_sha256=hashlib.sha256(json.dumps(current_expectations).encode()).hexdigest())
    changed.append(row)
report = {"baseline_sha": BASELINE, "original_test_fixture_files": len(paths), "byte_identical_git_blobs":len(paths)-len(changed),
          "changed_original_files": changed, "status":"EXCEPTIONS_REQUIRING_EXPLICIT_REVIEW" if changed else "ALL_ORIGINAL_FILES_PRESERVED"}
OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
