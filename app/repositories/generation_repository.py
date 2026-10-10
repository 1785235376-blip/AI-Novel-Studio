from __future__ import annotations
from ..runtime_events import committed_change
import json
from pathlib import Path
from contextlib import contextmanager, ExitStack
from uuid import UUID
from ..storage import atomic_write


class GenerationProjectIdentityError(ValueError):
    """A graph job may never be adopted by a replacement project owner."""


def graph_job_binding(item):
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
    if previous is not None and (graph_job_binding(previous) is None or any(
            previous.get(key) != item.get(key) for key in
            ("novel_id", "actor_id", "scope", "graph_binding", "expected_request_digest"))):
        raise GenerationProjectIdentityError("GENERATION_GRAPH_JOB_BINDING_CHANGED")


class GenerationRepository:
    def __init__(self,root:Path):self.root=root/"runtime/jobs";self.root.mkdir(parents=True,exist_ok=True)

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
        binding = graph_job_binding(item)
        if binding is None:
            atomic_write(self.root/f"{item['id']}.json",json.dumps(item,ensure_ascii=False,indent=2))
            return
        with self._graph_owner(item, binding):
            path = self.root / f"{item['id']}.json"
            previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            check_graph_job_update(previous, item)
            atomic_write(path,json.dumps(item,ensure_ascii=False,indent=2))

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
        path=self.root/f"{jid}.json"
        if not path.exists():raise KeyError(jid)
        item = json.loads(path.read_text(encoding="utf-8"))
        binding = graph_job_binding(item)
        if binding is None: return item
        try:
            with self._graph_owner(item, binding): return item
        except GenerationProjectIdentityError:
            raise KeyError(jid) from None
