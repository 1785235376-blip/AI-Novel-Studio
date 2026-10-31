"""Deterministic, persisted lexical reference index. No model or embeddings.

The capability service supplies only approved, integrity-checked records.
This index is a disposable local cache: its source fingerprint is verified on
all searches and corrupt/stale caches are rebuilt from authoritative metadata.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from ..storage import atomic_write


class VisualMemoryIndex:
    SCHEMA_VERSION = 1
    MODE = "LEXICAL_METADATA"

    def __init__(self, root: Path, novel_id: str, branch_id: str | None = None):
        scope = json.dumps([novel_id, branch_id], ensure_ascii=False)
        self.path = root / "v1_capabilities" / "visual_memory_indexes" / (hashlib.sha256(scope.encode()).hexdigest() + ".json")

    @staticmethod
    def terms(text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text).casefold()
        tokens = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
        output: list[str] = []
        for token in tokens:
            output.append(token)
            # CJK metadata remains searchable without an external tokenizer.
            for run in re.findall(r"[\u3400-\u9fff]+", token):
                output.extend(run)
                output.extend(run[i:i + 2] for i in range(len(run) - 1))
        return output

    def synchronize(self, documents: list[dict]) -> dict:
        canonical = json.dumps(documents, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if (isinstance(cached, dict) and cached.get("schema_version") == self.SCHEMA_VERSION
                and cached.get("source_fingerprint") == fingerprint
                and cached.get("documents") == documents):
            # Re-derive postings too: tampering with scores/membership must not
            # bypass the approved source set simply by preserving its digest.
            expected = self._postings(documents)
            if cached.get("postings") == expected:
                return cached
        snapshot = {"schema_version": self.SCHEMA_VERSION, "mode": self.MODE,
                    "source_fingerprint": fingerprint, "documents": documents,
                    "postings": self._postings(documents)}
        atomic_write(self.path, json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
        return snapshot

    def _postings(self, documents: list[dict]) -> dict:
        postings: dict[str, dict[str, int]] = {}
        for document in documents:
            text = json.dumps(document["searchable"], ensure_ascii=False, sort_keys=True)
            for term, count in Counter(self.terms(text)).items():
                postings.setdefault(term, {})[document["id"]] = count
        return postings

    def search(self, snapshot: dict, query: str, *, limit: int = 20) -> list[dict]:
        terms = sorted(set(self.terms(query)))
        scores: dict[str, int] = {}
        matches: dict[str, list[str]] = {}
        for term in terms:
            for identifier, count in snapshot["postings"].get(term, {}).items():
                scores[identifier] = scores.get(identifier, 0) + min(count, 8)
                matches.setdefault(identifier, []).append(term)
        documents = {item["id"]: item for item in snapshot["documents"]}
        candidates = list(scores) if terms else list(documents)
        candidates.sort(key=lambda identifier: (-scores.get(identifier, 0), identifier))
        return [{**documents[identifier], "score": scores.get(identifier, 0),
                 "matched_terms": matches.get(identifier, [])} for identifier in candidates[:limit]]
