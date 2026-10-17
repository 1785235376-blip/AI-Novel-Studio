from __future__ import annotations
from ..runtime_events import committed_change
import json, os
from pathlib import Path, PureWindowsPath
from contextlib import contextmanager, ExitStack
from uuid import UUID
from ..storage import atomic_write


class GenerationProjectIdentityError(ValueError):
    """A graph job may never be adopted by a replacement project owner."""


def graph_job_binding(item):
    from ..creative.director_binding import is_creative_director_job, creative_director_job_binding
    # Classify the disjoint passive domain before either existing executable
    # branch. A mixed or incomplete identity never chooses a fallback engine.
    if is_creative_director_job(item):
        try:
            return creative_director_job_binding(item)
        except ValueError:
            raise GenerationProjectIdentityError("GENERATION_CREATIVE_DIRECTOR_BINDING_INVALID") from None
    # Keep the existing project-owner persistence fence for a source-bound
    # Creative proposal as well. This is not a synthetic Graph identity.
    if item.get("adaptation_binding") is not None or item.get("experimental_origin") == "creative_adaptation_model":
        from ..creative.adaptation_models import AdaptationJobBinding
        try:
            binding = AdaptationJobBinding.model_validate(item.get("adaptation_binding")).model_dump(exclude_none=True)
            from ..experimental.store import ExperimentalStore
            ExperimentalStore.key(item["novel_id"], binding["scope"])
            if binding["scope"].get("mode") == "collaboration":
                from ..services.branch_manuscript_service import experimental_scope
                if (item.get("actor_id") != binding["actor_id"]
                        or experimental_scope(item.get("scope") or {}) != binding["scope"]):
                    raise ValueError("different adaptation authority")
            elif item.get("scope") is not None or item.get("actor_id") is not None:
                raise ValueError("unexpected local author authority")
            if (item.get("experimental_origin") != "creative_adaptation_model" or item.get("operation") != "brainstorm"
                    or item.get("chapter_id") != binding["chapter_id"] or item.get("graph_binding") is not None
                    or item.get("novel_id") != binding["project_id"]
                    or str(UUID(item["id"])) != item["id"]):
                raise ValueError("invalid adaptation job")
        except (ValueError, TypeError, KeyError, AttributeError):
            raise GenerationProjectIdentityError("GENERATION_ADAPTATION_BINDING_INVALID") from None
        return binding
    graph = (item.get("graph_binding") is not None or item.get("operation") == "graph_text"
             or item.get("experimental_origin") == "creative_graph_model")
    if not graph:
        return None
    from ..model_execution import GraphRequestBinding
    try:
        binding = GraphRequestBinding.model_validate(item.get("graph_binding")).model_dump()
        if (item.get("operation") != "graph_text" or item.get("experimental_origin") != "creative_graph_model"
                or item.get("chapter_id") is not None or not isinstance(item.get("novel_id"), str)
                or not item["novel_id"] or (item.get("scope") or {}).get("novel_id") != item["novel_id"]
                or not isinstance(item.get("actor_id"), str) or not item["actor_id"]
                or str(UUID(item["id"])) != item["id"]):
            raise ValueError("invalid graph job")
    except (ValueError, TypeError, KeyError, AttributeError):
        raise GenerationProjectIdentityError("GENERATION_GRAPH_BINDING_INVALID") from None
    return binding


def check_graph_job_update(previous, item):
    from ..creative.director_binding import is_creative_director_job
    keys = ("novel_id", "actor_id", "scope", "graph_binding", "adaptation_binding", "expected_request_digest")
    if is_creative_director_job(item) or (previous is not None and is_creative_director_job(previous)):
        keys += ("creative_director_binding", "operation", "experimental_origin", "chapter_id")
    if previous is not None and (graph_job_binding(previous) is None or any(
            previous.get(key) != item.get(key) for key in keys)):
        raise GenerationProjectIdentityError("GENERATION_GRAPH_JOB_BINDING_CHANGED")


class GenerationRepository:
    def __init__(self,root:Path):self.root=root/"runtime/jobs";self.root.mkdir(parents=True,exist_ok=True)

    def _job_path(self, jid):
        # Ordinary legacy basename IDs remain valid; path-bearing aliases must
        # fail before lock creation, filesystem reads, or writes.
        if (not isinstance(jid, str) or not jid or jid in {".", ".."}
                or any(character in jid for character in ("/", "\\", "\x00"))
                or PureWindowsPath(jid).drive):
            raise ValueError("GENERATION_JOB_ID_INVALID")
        return self.root / f"{jid}.json"

    @staticmethod
    def _write_key(path):
        # Windows case aliases must share the same leaf lock as well. This is
        # cooperating-writer identity, not protection against hostile symlinks.
        return "generation-write:" + os.path.normcase(str(path.resolve()))

    @contextmanager
    def _graph_owner(self, item, binding):
        from ..file_project_lifecycle import project_operation
        from ..creative.project_store import _read_marker, BINDING
        data = self.root.parent.parent
        with ExitStack() as owners:
            try:
                owners.enter_context(project_operation(data, item["novel_id"]))
                # Read the original owner's marker; never call incarnation(),
                # whose first-use behavior can provision a missing marker.
                marker = _read_marker(data / "novels" / item["novel_id"] / "creative_project_v2.json")
                if (not isinstance(marker, dict) or set(marker) != {"schema_version", BINDING}
                        or type(marker["schema_version"]) is not int or marker["schema_version"] != 1
                        or not isinstance(marker[BINDING], str)):
                    raise ValueError("invalid project marker")
                identity = UUID(marker[BINDING])
                if (identity.version != 4 or str(identity) != marker[BINDING]
                        or binding["project_incarnation"] != "file:" + str(identity)):
                    raise ValueError("different project owner")
            except (FileNotFoundError, ValueError, TypeError, KeyError, OSError):
                raise GenerationProjectIdentityError("GENERATION_GRAPH_PROJECT_OWNER_CHANGED") from None
            # Preserve unrelated IO/persistence errors rather than calling a
            # disk-write failure a changed project identity.
            yield

    @committed_change("TASK")
    def save(self,item:dict):
        from .file.mutation_coordinator import workspace_mutation
        from ..creative.director_terminal_evidence import preserve_evidence
        path = self._job_path(item["id"])
        binding = graph_job_binding(item)
        if binding is None:
            with workspace_mutation(self.root, self._write_key(path)):
                previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
                if previous is not None and graph_job_binding(previous) is not None:
                    raise GenerationProjectIdentityError("GENERATION_GRAPH_JOB_BINDING_CHANGED")
                saved = preserve_evidence(previous, item)
                atomic_write(path,json.dumps(saved,ensure_ascii=False,indent=2))
            return
        with self._graph_owner(item, binding), workspace_mutation(self.root, self._write_key(path)):
            previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            check_graph_job_update(previous, item)
            saved = preserve_evidence(previous, item)
            atomic_write(path,json.dumps(saved,ensure_ascii=False,indent=2))

    def _publish_director_terminal(self, job, capability, evidence):
        """Original live worker only. All authority callbacks precede the leaf lock."""
        path = self._job_path(job.id)
        from threading import get_ident
        from .file.mutation_coordinator import workspace_mutation
        from ..model_execution import _CreativeDirectorCapability
        from ..creative.director_terminal_evidence import FIELD, validate_evidence, digest, _PublicationAcknowledgment
        if type(capability) is not _CreativeDirectorCapability:
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OWNER_REQUIRED")
        capability._check(job, started=True)
        repository = getattr(capability.manager.persistence, "repository", capability.manager.persistence)
        if (repository is not self or not capability.worker_claimed
                or capability.publication_state != "PUBLISHING"
                or capability.publication_thread != get_ident()
                or capability._publication_binding is None
                or capability._publication_binding[1] is not self
                or capability._publication_binding[2] != job.expected_request_digest
                or capability.terminal_publication is not capability._publication_binding[0]):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OWNER_REQUIRED")
        item = job.public()
        if (item.get("status") != "COMPLETED" or item.get("execution_outcome") != "COMPLETED"
                or item.get("terminal_hook_status") != "COMPLETED" or not job.output.strip()):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_RESULT_REQUIRED")
        import hashlib
        evidence = validate_evidence(evidence, item)
        if (evidence["output_digest"] != hashlib.sha256(job.output.encode("utf-8")).hexdigest()
                or evidence["output_bytes"] != len(job.output.encode("utf-8"))
                or evidence["route"]["fingerprint"] != capability.route_fingerprint
                or evidence["route"]["provider_id"] != job.requested_provider or job.provider != job.requested_provider
                or evidence["route"]["model_id"] != job.requested_model or job.model != job.requested_model):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OUTPUT_CHANGED")
        binding = graph_job_binding(item)
        # The coordinator already holds raw scope and original owner. Reenter
        # only that owner, then the distinct write leaf; never call back here.
        with self._graph_owner(item, binding), workspace_mutation(self.root, self._write_key(path)):
            if not path.exists():
                raise ValueError("CREATIVE_DIRECTOR_TERMINAL_ORIGINAL_JOB_REQUIRED")
            previous = json.loads(path.read_text(encoding="utf-8"))
            check_graph_job_update(previous, item)
            if FIELD in previous:
                raise ValueError("CREATIVE_DIRECTOR_TERMINAL_ALREADY_ATTEMPTED")
            if any(previous.get(key) != item.get(key) for key in (
                    "status", "execution_outcome", "terminal_hook_status", "output", "provider", "model",
                    "requested_provider", "requested_model", "generation_deadline", "generation_max_output_bytes")):
                raise ValueError("CREATIVE_DIRECTOR_TERMINAL_ORIGINAL_JOB_CHANGED")
            item[FIELD] = evidence
            atomic_write(path, json.dumps(item, ensure_ascii=False, indent=2))
        return _PublicationAcknowledgment(capability, self, job, digest(evidence))

    def load_all(self):
        out=[]
        for p in self.root.glob("*.json"):
            try:
                item = json.loads(p.read_text(encoding="utf-8"))
                binding = graph_job_binding(item)
                if binding is None:
                    out.append(item)
                else:
                    with self._graph_owner(item, binding): out.append(item)
            except Exception:continue
        return out

    def get(self,jid):
        path=self._job_path(jid)
        if not path.exists():raise KeyError(jid)
        item = json.loads(path.read_text(encoding="utf-8"))
        binding = graph_job_binding(item)
        if binding is None: return item
        try:
            with self._graph_owner(item, binding): return item
        except GenerationProjectIdentityError:
            raise KeyError(jid) from None
