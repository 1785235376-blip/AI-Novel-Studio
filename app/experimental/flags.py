"""Server-owned experimental flags, disabled unless explicitly opted in.

No wildcard enable: an accidental environment value cannot expand scope.
"""
from __future__ import annotations
import os
from fastapi import HTTPException

LEGACY_FLAGS = (
    "advanced_planning_v2", "semantic_import_v2", "world_character_engines_v2",
    "unified_review_inbox", "agent_team_recipes", "media_adapter_registry",
    "cover_storyboard_generation", "visual_embeddings", "audiobook_v2",
)


# Package-order dependencies are in capabilities.py. Runtime dependencies below
# must all be explicitly allowlisted; this registry never auto-enables a feature.
NEW_FLAGS = ("local_tutor_interop_v1", "writing_recovery_v2", "workspace_tools_v2", "local_ai_workflow_inspector_v2", "author_context_inspector_v2", "writing_focus_v2", "temporal_story_graph_v2", "character_mind_v2", "model_broker_v2", "model_benchmark_v2", "asset_lineage_v2", "production_manifest_v2", "style_dna_v2", "narrative_quality_judge_v2", "change_impact_v2", "story_simulator_v2", "research_library_v2", "revision_intelligence_v2", "selection_assistant_v2", "reader_preflight_v2", "writing_sessions_v2", "ai_director_v2", "timeline_exchange_v2", "voice_direction_v2", "subtitle_timeline_v2", "portable_projects_v2", "safe_batches_v2", "multilingual_editions_v2", "template_library_v2", "declarative_agents_v2", "comic_layouts_v2", "interactive_story_v2", "writer_room_v2", "project_forks_v2", "offline_sync_v2")
# Keep the published forty-package opt-in list stable for older clients.
# New product surfaces require their own explicit opt-in; discovery reports all.
FLAGS = LEGACY_FLAGS + NEW_FLAGS
SURFACE_FLAGS = ('branch_manuscript_v1', 'realtime_collaboration_v1', 'production_sync_v1', 'workspace_interaction_v1', 'finding_review_v1', 'story_record_versions_v1', 'adaptation_lifecycle_v1', 'narrative_production_v2')
RUNTIME_FLAGS = FLAGS + SURFACE_FLAGS
FLAG_DEPENDENCIES: dict[str, tuple[str, ...]] = {name: () for name in FLAGS}
FLAG_DEPENDENCIES.update(temporal_story_graph_v2=('world_character_engines_v2',),
                         character_mind_v2=('temporal_story_graph_v2',),
                         model_broker_v2=('author_context_inspector_v2',),
                         model_benchmark_v2=('model_broker_v2',),
                         production_manifest_v2=('asset_lineage_v2', 'cover_storyboard_generation', 'media_adapter_registry'),
                         narrative_quality_judge_v2=('advanced_planning_v2', 'world_character_engines_v2', 'unified_review_inbox'),
                         change_impact_v2=('temporal_story_graph_v2', 'asset_lineage_v2'),
                         story_simulator_v2=('advanced_planning_v2', 'temporal_story_graph_v2', 'character_mind_v2'),
                         research_library_v2=('semantic_import_v2', 'temporal_story_graph_v2'),
                         selection_assistant_v2=('revision_intelligence_v2', 'author_context_inspector_v2'),
                         writing_sessions_v2=('workspace_tools_v2',),
                         timeline_exchange_v2=('asset_lineage_v2',),
                         voice_direction_v2=('audiobook_v2',),
                         subtitle_timeline_v2=('voice_direction_v2',),
                         safe_batches_v2=('reader_preflight_v2',),
                         declarative_agents_v2=('model_broker_v2', 'agent_team_recipes', 'media_adapter_registry'),
                         comic_layouts_v2=('asset_lineage_v2', 'ai_director_v2'),
                         interactive_story_v2=('advanced_planning_v2', 'temporal_story_graph_v2'),
                         writer_room_v2=('unified_review_inbox',),
                         project_forks_v2=('revision_intelligence_v2', 'asset_lineage_v2'),
                         offline_sync_v2=('project_forks_v2',))
SURFACE_FLAG_DEPENDENCIES = {
    'branch_manuscript_v1': (),
    'realtime_collaboration_v1': ('writer_room_v2', 'branch_manuscript_v1'),
    'production_sync_v1': ('offline_sync_v2',),
    'workspace_interaction_v1': ('workspace_tools_v2',),
    'finding_review_v1': (),
    'story_record_versions_v1': (),
    'adaptation_lifecycle_v1': (),
    'narrative_production_v2': (),
}


def runtime_dependencies():
    return {**FLAG_DEPENDENCIES, **SURFACE_FLAG_DEPENDENCIES}


def enabled_flags() -> frozenset[str]:
    if os.getenv("V1_ACCEPTANCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return frozenset()
    configured = {v.strip().removeprefix("experimental.") for v in os.getenv("EXPERIMENTAL_FEATURES", "").split(",") if v.strip()}
    enabled = configured.intersection(RUNTIME_FLAGS)
    dependencies = runtime_dependencies()
    while True:
        supported = {name for name in enabled if set(dependencies[name]).issubset(enabled)}
        if supported == enabled:
            return frozenset(enabled)
        enabled = supported


def require_flag(name: str) -> None:
    if name not in enabled_flags():
        raise HTTPException(404, {"code": "EXPERIMENTAL_FEATURE_DISABLED", "feature": name})


def flag_status() -> dict:
    enabled = enabled_flags()
    dependencies = runtime_dependencies()
    # `features` is the established forty-package client contract. Extending
    # that map would change the meaning of an older client's complete opt-in.
    # New clients use the explicitly complete versioned runtime inventory; every
    # disabled new surface remains discoverable without being implicitly enabled.
    return {"schema_version": 2, "experimental": True, "default_enabled": False,
            "features": {f"experimental.{name}": name in enabled for name in FLAGS},
            "surface_features": {f"experimental.{name}": name in enabled for name in SURFACE_FLAGS},
            "runtime_features": {f"experimental.{name}": name in enabled for name in RUNTIME_FLAGS},
            "dependencies": {f"experimental.{name}": list(dependencies[name]) for name in RUNTIME_FLAGS}}
