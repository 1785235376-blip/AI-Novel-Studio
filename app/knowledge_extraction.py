"""Bounded deterministic extraction with exact, versioned source locations.

Heuristics produce candidates only. Repeated names in different chapters stay
separate: a spelling match is not proof that two people are the same person.
"""
import hashlib
import re
import uuid

_NAME = re.compile(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4}?)(?=(?:说道|说|道|问|回答|看见|走向|转身|点头|摇头))|\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(?=said\b|asked\b|replied\b|whispered\b)")
_LOCATION = re.compile(r"([\u4e00-\u9fff]{2,12}(?:学院|基地|大陆|城|镇|村|港|岛|宫|府|山|河))|\b(?:in|at|to)\s+([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,2})")
_FORESHADOW = re.compile(r"(?:总有一天|迟早|秘密|真相|未完|伏笔|线索)[^。！？\n]{0,80}|\b(?:one day|secret|clue|eventually)\b[^.!?\n]{0,100}", re.I)


def extract_knowledge_candidates(chapters):
    output = {key: [] for key in ("characters", "locations", "timeline_events", "foreshadowing")}
    for ordinal, chapter in enumerate(chapters, 1):
        text = str(chapter.get("content") or "")
        if len(text) > 2_000_000:
            raise ValueError("chapter exceeds bounded extraction size; split it into smaller chapters")
        number = int(chapter.get("number") or ordinal)
        chapter_id = str(chapter.get("id") or f"import-chapter-{number}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seen = {}
        def add(kind, name, start, end, confidence):
            start, end = max(0, start), min(len(text), end)
            evidence = {"chapter_id": chapter_id, "chapter_number": number, "chapter_version": chapter.get("version"),
                        "content_sha256": digest, "start": start, "end": end, "quote": text[start:end]}
            key = (kind, name)
            if key in seen:
                if len(seen[key]["source_evidence"]) < 20:
                    seen[key]["source_evidence"].append(evidence)
                return
            row = {"candidate_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chapter_id}:{digest}:{kind}:{name}")),
                   "name" if kind in {"characters", "locations"} else "title": name,
                   "evidence": evidence["quote"], "source_evidence": [evidence], "chapter_number": number,
                   "confidence": confidence, "analysis_source": "LOCAL_HEURISTIC", "privacy_level": "LOCAL_ONLY"}
            seen[key] = row
            output[kind].append(row)
        # Windows are overlapped so names and cues at a boundary are retained.
        # Stable offsets deduplicate the overlap, rather than merging unrelated names.
        matched = set()
        for offset in range(0, len(text), 16000):
            window = text[max(0, offset - 256):offset + 16256]
            base = max(0, offset - 256)
            for pattern, kind, confidence in ((_NAME, "characters", .55), (_LOCATION, "locations", .5), (_FORESHADOW, "foreshadowing", .4)):
                for match in pattern.finditer(window):
                    start, end = base + match.start(), base + match.end()
                    if (kind, start, end) in matched:
                        continue
                    matched.add((kind, start, end))
                    if kind == "foreshadowing":
                        name = match.group(0)
                    elif kind == "characters":
                        name = match.group(1) or match.group(2)
                    else:
                        name = match.group(1) or match.group(2)
                        if match.group(1):
                            suffix = re.search(r"(学院|基地|大陆|城|镇|村|港|岛|宫|府|山|河)$", name)
                            name = name[-(len(suffix.group(1)) + 2):].lstrip("了到在于往进入")
                    add(kind, name, max(0, start - 40), min(len(text), end + 80), confidence)
        if text.strip():
            add("timeline_events", str(chapter.get("title") or f"第 {number} 章"), 0, min(len(text), 240), .35)
            output["timeline_events"][-1]["description"] = text[:240]
        if sum(map(len, output.values())) > 10000:
            raise ValueError("knowledge candidate limit reached; review chapters in smaller batches")
    return output
