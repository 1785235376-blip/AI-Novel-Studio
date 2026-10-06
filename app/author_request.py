"""Single deterministic author request assembly and reviewable payload contract."""
from __future__ import annotations
import hashlib
import json
from dataclasses import asdict

from .agents import agent_runner
from .model_runtime import TextGenerationParameters, TextGenerationRequest

def author_source(job, chapter):
    """Reduced scope never falls back to an unreviewed manuscript tail."""
    scope = getattr(job, "request_scope", None) or {}
    mode = scope.get("source_mode", "AUTO")
    if mode == "NONE": return ""
    if mode == "SELECTION_ONLY":
        if not job.source: raise ValueError("AUTHOR_SELECTION_REQUIRED")
        return job.source
    return job.source or chapter["content"][-2000:]


def automatic_context_allowed(job):
    scope = getattr(job, "request_scope", None) or {}
    return (scope.get("source_mode", "AUTO") == "AUTO" and scope.get("include_automatic_context", True)
            and not any(not ref.get("include", True) for ref in (scope.get("added_sources") or [])))


AUTHOR_ROLES = {"continue": "writer", "rewrite": "writer", "polish": "editor", "brainstorm": "plot_planner", "review": "continuity_reviewer"}
AUTHOR_TASKS = {"continue": "Continue the chapter without repeating it.", "rewrite": "Rewrite only the supplied selection.", "polish": "Polish the supplied text without changing facts.", "brainstorm": "Return concise story options.", "review": "Review the chapter and list actionable issues."}


def build_author_request(job, route, chapter, context, dispatch_guard=None):
    """No routing, persistence, context discovery or provider IO occurs here."""
    context = _safe_audit_metadata(context)
    role = AUTHOR_ROLES[job.operation]
    from .experimental.character_author_context import is_character_job
    if is_character_job(job):
        if (set(context) != {"character_viewpoint"} or job.source or job.style or job.creation_records
                or context["character_viewpoint"].get("context_digest") != (job.character_viewpoint or {}).get("context_digest")):
            raise ValueError("CHARACTER_AUTHOR_CONTEXT_UNSAFE")
        style, source = "", ""  # Never fall back to omniscient manuscript tail.
    else:
        style = f"\n写作风格要求：{job.style}" if job.style else ""
        source = author_source(job, chapter)
        if not automatic_context_allowed(job):
            # NONE suppresses implicit manuscript/automatic context, while an
            # explicitly added, freshly resolved source remains an independent
            # author choice. Never trust an unbound context dictionary here.
            context = ({"explicit_sources": context["explicit_sources"]}
                       if (getattr(job, "request_scope", None) or {}).get("added_sources")
                       and callable(getattr(job, "author_context_resolver", None))
                       and "explicit_sources" in context else {})
    prompt = agent_runner.build_prompt(role, context, AUTHOR_TASKS[job.operation] + " " + job.instruction + style, source)
    return TextGenerationRequest(provider_id=route.provider, model_id=route.model, prompt=prompt, context=context,
                                 parameters=TextGenerationParameters(), metadata={"purpose": job.operation},
                                 job_id=job.id, cancellation=job.cancelled, dispatch_guard=dispatch_guard)


def request_payload(request):
    """Exact adapter-facing data; orchestration-only IDs/guards are excluded."""
    return {"provider_id": request.provider_id, "model_id": request.model_id, "prompt": request.prompt,
            "system_instruction": request.system_instruction, "context": dict(request.context),
            "parameters": {**asdict(request.parameters), "stop_sequences": list(request.parameters.stop_sequences)}, "structured_output_schema": request.structured_output_schema,
            "metadata": dict(request.metadata)}


def request_digest(request, job, cloud=False):
    # Scope and version bind a receipt even if identical text exists elsewhere.
    value = {"request": request_payload(request), "novel_id": job.novel_id, "chapter_id": job.chapter_id,
             "chapter_version": job.base_chapter_version, "chapter_digest": job.base_chapter_digest, "actor_id": job.actor_id, "workspace_id": job.workspace_id,
             "session_id": job.session_id, "scope": job.scope, "profile": job.profile,
             "creation_records": job.creation_records, "route_locality": "cloud" if cloud else "local"}
    if getattr(job, "author_input_digest", None) is not None:
        value["author_input_digest"] = job.author_input_digest
    if getattr(job, "request_scope", None) is not None:
        value["request_scope"] = job.request_scope
    if getattr(job, "reviewed_variant", None) is not None:
        value["reviewed_variant"] = job.reviewed_variant
        value["reviewed_variant_policy"] = job.reviewed_variant_policy
    if getattr(job, "character_viewpoint", None) is not None:
        value["character_viewpoint"] = job.character_viewpoint
    if getattr(job, "revision_selection_binding", None) is not None:
        value["revision_selection_binding"] = job.revision_selection_binding
        value["partial_revision_only"] = True
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _safe_audit_metadata(value):
    """Omission auditing must not leak excluded source identifiers to an adapter."""
    if isinstance(value, dict):
        return {key: (["SOURCE_PRIVACY_POLICY"] if item else [])
                if key in {"privacy_omissions", "omitted_local_only"}
                else _safe_audit_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_audit_metadata(item) for item in value]
    return value


def saved_source_matches(chapter, source):
    if source in str(chapter.get("content") or ""):
        return True
    document = chapter.get("document")
    if not isinstance(document, dict) or document.get("type") != "doc":
        return False
    # Selection uses the editor projection, while persisted content is Markdown.
    # Never accept an independently changed document under an old content review.
    from .document import document_to_markdown
    from .experimental.ux import chapter_text
    if document_to_markdown(document).strip() != str(chapter.get("content") or "").strip():
        return False
    return source in chapter_text(chapter)


def chapter_digest(chapter):
    return hashlib.sha256(json.dumps({"content": chapter.get("content"), "document": chapter.get("document")},
                                    ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
