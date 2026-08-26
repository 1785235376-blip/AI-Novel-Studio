import pytest

from app.context_pack_v2 import ContextPackCandidate, ContextPackV2Builder
from app.services.context_service import ContextService
from app.repositories.factory import create_repository_bundle
from app.services.novel_service import NovelService
from app.services.chapter_service import ChapterService


def candidate(source_id, source_type, content, **kwargs):
    return ContextPackCandidate(source_id=source_id, source_type=source_type, content=content, **kwargs)


def test_disabled_is_strict_empty_compatibility_path():
    result = ContextPackV2Builder().build([{"invalid": "never parsed"}], enabled=False)
    assert result.enabled is False
    assert result.chunks == []


def test_ranking_is_deterministic_and_recent_has_priority():
    values = [candidate("l", "LORE", "lore relevance"), candidate("r", "RECENT_CHAPTER", "recent relevance")]
    builder = ContextPackV2Builder(token_budget=1000)
    first = builder.build(values, enabled=True)
    second = builder.build(reversed(values), enabled=True)
    assert [x.source_id for x in first.chunks] == ["r", "l"]
    assert first == second


def test_character_and_lore_relevance_affect_ranking():
    values = [
        candidate("c-other", "CHARACTER", "unrelated other", character_ids=["other"]),
        candidate("c-hit", "CHARACTER", "unrelated hero", character_ids=["hero"]),
        candidate("l-hit", "LORE", "the obsidian gate", keywords=["gate"]),
        candidate("l-other", "LORE", "a river"),
    ]
    result = ContextPackV2Builder(token_budget=1000).build(
        values, enabled=True, query="gate", character_ids=["hero"]
    )
    ids = [x.source_id for x in result.chunks]
    assert ids.index("c-hit") < ids.index("c-other")
    assert ids.index("l-hit") < ids.index("l-other")


def test_deduplication_uses_canonical_content():
    result = ContextPackV2Builder(token_budget=1000).build([
        candidate("b", "LORE", {"b": 2, "a": 1}),
        candidate("a", "TIMELINE", {"a": 1, "b": 2}),
    ], enabled=True)
    assert len(result.chunks) == 1
    assert result.deduplicated_count == 1


def test_budget_and_oversized_source_are_stable():
    builder = ContextPackV2Builder(token_budget=20, chunk_token_limit=10)
    result = builder.build([candidate("huge", "LORE", "".join(chr(0x4e00 + i % 1000) for i in range(1000)))], enabled=True)
    assert result.estimated_tokens <= 20
    assert result.truncated_sources == ["huge"]
    assert len(result.chunks) <= 2


def test_empty_input():
    result = ContextPackV2Builder(token_budget=100).build([], enabled=True)
    assert result.enabled and result.chunks == [] and result.estimated_tokens == 0


def test_local_only_is_rejected_before_cloud_pack_processing():
    private = candidate("secret", "CHARACTER", object(), locality="LOCAL_ONLY")
    result = ContextPackV2Builder().build([private], enabled=True, cloud=True)
    assert result.chunks == []
    assert result.omitted_local_only == ["secret"]


def test_local_only_remains_available_for_local_execution():
    private = candidate("secret", "LORE", "local fact", locality="LOCAL_ONLY")
    result = ContextPackV2Builder(token_budget=100).build([private], enabled=True, cloud=False)
    assert [x.source_id for x in result.chunks] == ["secret"]


def test_candidate_extraction_covers_all_foundation_sources():
    values = ContextPackV2Builder.extract_candidates(
        characters=[{"id": "c", "text": "hero"}], lore=[{"id": "l", "content": "law"}],
        timeline=[{"id": "t", "text": "event"}], recent_chapters=[{"id": "r", "text": "chapter"}],
    )
    assert {x.source_type for x in values} == {"CHARACTER", "LORE", "TIMELINE", "RECENT_CHAPTER"}


def test_context_service_flag_off_is_unchanged_and_enabled_is_cloud_safe():
    base = {"novel_id": "n", "chapter": 1, "current_story_state": {}, "lore_memory": {"short_memory": [{"id": "secret", "content": "private", "locality": "LOCAL_ONLY"}]}}
    off = ContextService(object(), object(), enable_context_pack_v2=False)
    assert off._attach_context_pack_v2(dict(base), cloud=True) == base
    enabled = ContextService(object(), object(), enable_context_pack_v2=True)
    result = enabled._attach_context_pack_v2(dict(base), cloud=True)
    assert result["context_pack_v2"]["omitted_local_only"] == ["secret"]


def test_same_source_id_across_types_has_unique_chunk_identity():
    result = ContextPackV2Builder(token_budget=100).build([
        candidate("shared", "LORE", "lore"), candidate("shared", "TIMELINE", "timeline")
    ], enabled=True)
    assert len({chunk.chunk_id for chunk in result.chunks}) == 2


@pytest.mark.file_backend_only
def test_context_service_public_build_flag_matrix(tmp_path):
    bundle = create_repository_bundle(data_root=tmp_path)
    project = NovelService(bundle.novels, bundle.chapters).create({"id": "pack-project", "title": "Pack"})["id"]
    ChapterService(bundle.chapters).create(project, {"title": "One", "content": "Text"})
    plain = ContextService(bundle.novels, bundle.chapters, enable_context_pack_v2=False).build(project, 1, "hero")
    enabled = ContextService(bundle.novels, bundle.chapters, enable_context_pack_v2=True).build(project, 1, "hero")
    assert "context_pack_v2" not in plain
    assert enabled["context_pack_v2"]["enabled"] is True
