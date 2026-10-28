from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import mimetypes
import os
import re
import stat
import tempfile
import threading
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from ..repository import atomic_write, now
from ..repositories.file.mutation_coordinator import workspace_mutation
from .asset_query_budget import current_query_budget


class AssetIntegrityError(ValueError):
    """Stored content no longer agrees with the recorded digest/length."""


class AssetIdempotencyConflict(ValueError):
    """An idempotency key cannot identify two different uploads."""


class AssetLibraryService:
    """Local assets with verified reads and recoverable deletion.

    MIME is declared metadata, not a media-decoding guarantee. The generic
    upload contract intentionally accepts opaque bytes; generated media uses
    the separate strict media ingestion validator. A supplied branch is a
    trusted server scope, never a client-authorized identity.
    """

    MAX_BYTES = 25 * 1024 * 1024
    TEXT_RESULT_MAX_BYTES = 32_000
    TEXT_RESULT_CONTRACT = "creative-graph-text-asset/1"
    TEXT_RESULT_FEATURES = frozenset(("ai_execution_v2", "narrative_production_v2",
                                    "model_broker_v2", "author_context_inspector_v2"))

    @staticmethod
    def public(value):
        """Legacy response projection, retaining all persisted metadata.

        Only the new reserved field is hidden when A09 is off. Ordinary
        parameters and the pre-existing source_asset_ids contract are intact.
        Accepts nested asset response envelopes as well as one asset/list.
        """
        from ..experimental.flags import enabled_flags
        result = copy.deepcopy(value)
        lineage_enabled = "asset_lineage_v2" in enabled_flags()
        def redact(item):
            if isinstance(item, dict):
                for key in ("_required_features", "_owner_actor_id", "_origin_provenance", "_project_binding",
                            "_text_result_origin", "_text_result_review", "_text_execution_receipt", "_studio_result_origin", "_manual_mask_origin", "_model_reference_origin", "_video_reference_origin", "_prompt_write_origin", "_comic_ora_origin", "_comic_ora_review", "_comic_page_origin", "_audio_history_head", "_audio_history_restore_origin"):
                    item.pop(key, None)
                if not lineage_enabled and isinstance(item.get("parameters"), dict):
                    item["parameters"].pop("asset_lineage_v2", None)
                if isinstance(item.get("parameters"), dict):
                    # Relationships require a current, scoped target projection;
                    # raw stored IDs cannot bypass a target's later privacy.
                    item["parameters"].pop("asset_relationships_v2", None)
                for child in item.values(): redact(child)
            elif isinstance(item, list):
                for child in item: redact(child)
        redact(result)
        return result

    def __init__(self, root: Path):
        self.root = root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._scope = threading.local()
        self._page_source_lock = threading.RLock()
        self._page_source_handles = {}
        self._page_source_request = ContextVar('asset_page_source_request', default=None)
        self._page_source_grant = ContextVar('asset_page_source_grant', default=None)

    def comic_source_authority(self, comic, request, novel_id, token, branch_id=None):
        from .comic_page_source_reads import authority
        return authority(self, comic, request, novel_id, token, branch_id)

    def open_comic_page_sources(self, comic, authority, page_id, expected_version, review_digest):
        from .comic_page_source_reads import open_sources
        return open_sources(self, comic, authority, page_id, expected_version, review_digest)

    def page_source_metadata(self, grant, request, asset_id):
        from .comic_page_source_reads import metadata
        return metadata(self, grant, request, asset_id)

    def page_source_content(self, grant, request, asset_id, *, max_bytes):
        from .comic_page_source_reads import content
        return content(self, grant, request, asset_id, max_bytes)

    def revalidate_page_sources(self, grant, request):
        from .comic_page_source_reads import revalidate
        return revalidate(self, grant, request)

    def current_comic_source_authority(self, comic, novel_id, scope, actor):
        from .comic_page_source_reads import current_authority
        return current_authority(self, comic, novel_id, scope, actor)

    def open_comic_page_sources_in_phase(self, comic, authority, page_id, expected_version, review_digest):
        from .comic_page_source_reads import open_in_phase
        return open_in_phase(self, comic, authority, page_id, expected_version, review_digest)

    def render_comic_page_source(self, grant, request):
        from .comic_page_source_reads import render
        return render(self, grant, request)

    @contextmanager
    def project_scope(self, novel_id: str, branch_id: str | None, owner_lease, *, scope_key: str):
        """Lease the existing owner for new, incarnation-bound studio assets.

        This is a server-only adapter, not a client-supplied identity. The
        callable must hold the original project owner's lifecycle lease and
        yield its actual incarnation. Acquire asset -> owner, matching the
        established lineage guard's order. Never open a scope-document write
        transaction inside this lease. The old unbound asset contract remains
        unchanged outside it; neither side silently adopts the other's data.
        """
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        if not isinstance(scope_key, str) or not re.fullmatch(r"[a-f0-9]{64}", scope_key):
            raise ValueError("ASSET_PROJECT_SCOPE_INVALID")
        if getattr(self._scope, "binding", None) is not None:
            raise ValueError("ASSET_PROJECT_SCOPE_NESTED")
        with self._lock, workspace_mutation(self.root, "asset-library"), owner_lease() as incarnation:
            if not isinstance(incarnation, str) or not re.fullmatch(
                    r"(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", incarnation):
                raise ValueError("ASSET_PROJECT_IDENTITY_INVALID")
            self._scope.binding = {"novel_id": novel_id, "branch_id": branch_id,
                                   "incarnation": incarnation, "scope_key": scope_key}
            try:
                yield
            finally:
                del self._scope.binding

    @staticmethod
    def _identifier(value: str, field: str = "asset_id") -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value):
            raise ValueError(f"invalid {field}")
        return value

    def _path(self, asset_id: str, suffix: str) -> Path:
        path = self.root / f"{self._identifier(asset_id)}.{suffix}"
        # Never follow asset symlinks, including symlinks pointing inside root.
        if path.is_symlink():
            raise AssetIntegrityError("asset path is not a regular file")
        return path

    def _meta_path(self, asset_id: str) -> Path:
        return self._path(asset_id, "json")

    def _bin_path(self, asset_id: str) -> Path:
        return self._path(asset_id, "bin")

    def _load(self, asset_id: str) -> dict:
        try:
            path = self._meta_path(asset_id)
            from ..creative.asset_usage_budget import current_usage_budget
            usage_budget = current_usage_budget()
            budget = current_query_budget()
            if usage_budget is not None:
                raw = usage_budget.read(path, 1024 * 1024)
            elif budget is not None:
                budget.charge(path)
                with path.open(encoding="utf-8") as stream:
                    raw = stream.read(1024 * 1024 + 1)
                if len(raw.encode("utf-8")) > 1024 * 1024:
                    from .asset_query_index import AssetQueryBudgetExceeded
                    raise AssetQueryBudgetExceeded()
            else:
                raw = path.read_text(encoding="utf-8")
            meta = json.loads(raw)
        except FileNotFoundError:
            raise FileNotFoundError(asset_id) from None
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AssetIntegrityError("asset metadata is unreadable") from exc
        if (not isinstance(meta, dict) or meta.get("id") != asset_id
                or not isinstance(meta.get("size"), int) or isinstance(meta.get("size"), bool)
                or not 0 < meta["size"] <= self.MAX_BYTES
                or not re.fullmatch(r"[a-f0-9]{64}", str(meta.get("sha256", "")))):
            raise AssetIntegrityError("asset metadata is invalid")
        return meta

    def _in_scope(self, meta: dict, branch_id: str | None, actor_id: str | None = None) -> bool:
        binding, active = meta.get("_project_binding"), getattr(self._scope, "binding", None)
        if "_comic_ora_origin" in meta:
            from .comic_ora_origin import record
            try: record(meta)
            except (ValueError, TypeError, KeyError): return False
        if "_manual_mask_origin" in meta:
            try:
                self._manual_record(meta)
            except (ValueError, TypeError, KeyError):
                return False
        if "_model_reference_origin" in meta:
            try:
                self._model_reference_record(meta)
            except (ValueError, TypeError, KeyError, AttributeError):
                return False
        if "_video_reference_origin" in meta:
            try:
                self._video_reference_record(meta)
            except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
                return False
        from ..creative import adaptation_receipt as adaptation_contract
        origin, receipt = meta.get("_text_result_origin"), meta.get(adaptation_contract.PRIVATE_FIELD)
        if ((isinstance(origin, dict) and origin.get("contract") == adaptation_contract.ASSET_CONTRACT)
                or (isinstance(receipt, dict) and receipt.get("contract") == adaptation_contract.CONTRACT)):
            # A damaged private adaptation must never fall back to legacy public
            # asset visibility. This admission is intrinsic to all owner reads.
            owner, features = meta.get("_owner_actor_id"), meta.get("_required_features")
            if (not isinstance(owner, str) or not owner.strip() or len(owner) > 240
                    or any(ord(char) < 32 or ord(char) == 127 for char in owner)
                    or not isinstance(features, list) or any(not isinstance(item, str) for item in features)
                    or set(features) != adaptation_contract.FEATURES
                    or not isinstance(binding, dict) or type(meta.get("version")) is not int
                    or meta["version"] not in (1, 2)
                    or not isinstance(origin, dict) or origin.get("contract") != adaptation_contract.ASSET_CONTRACT
                    or not isinstance(receipt, dict) or receipt.get("contract") != adaptation_contract.CONTRACT):
                return False
        if "narrative_production_v2" in meta.get("_required_features", []) and binding is None:
            # A missing new binding is corruption, not permission to fall back
            # to the historical unbound contract or adopt a recreated owner.
            return False
        if binding is not None or active is not None:
            if (not isinstance(binding, dict) or binding != active
                    or meta.get("novel_id") != binding.get("novel_id")
                    or meta.get("branch_id") != branch_id or binding.get("branch_id") != branch_id):
                return False
        if meta.get("_required_features"):
            from ..experimental.flags import enabled_flags
            if not set(meta["_required_features"]).issubset(enabled_flags()): return False
            if meta.get("branch_id") != branch_id: return False
        if meta.get("_owner_actor_id") and meta["_owner_actor_id"] != actor_id: return False
        return branch_id is None or meta.get("branch_id") == branch_id

    def _write_meta(self, meta: dict) -> None:
        atomic_write(self._meta_path(meta["id"]), json.dumps(meta, ensure_ascii=False, indent=2))

    def create(self, novel_id: str, filename: str, content_base64: str,
               media_type: str | None = None, kind: str = "image",
               idempotency_key: str | None = None, *, branch_id: str | None = None,
               required_features: tuple[str, ...] = (), owner_actor_id: str | None = None, guard=None,
               _initial_text_result: dict | None = None, _initial_studio_result: dict | None = None,
               _initial_manual_mask: dict | None = None, _manual_expected_retry_id: str | None = None,
               _initial_prompt_write: dict | None = None,
               _initial_model_reference: dict | None = None, _model_reference_expected_retry_id: str | None = None,
               _initial_video_reference: dict | None = None, _video_reference_expected_retry_id: str | None = None,
               _initial_comic_ora: dict | None = None, _initial_comic_page: dict | None = None):
        from ..experimental.flags import RUNTIME_FLAGS, enabled_flags
        if set(required_features) - set(RUNTIME_FLAGS) or not set(required_features).issubset(enabled_flags()):
            raise ValueError("asset origin feature unavailable")
        if owner_actor_id is not None and (not isinstance(owner_actor_id, str) or not owner_actor_id or len(owner_actor_id) > 240):
            raise ValueError("invalid asset owner")
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        # Reject before decoding so an attacker cannot allocate arbitrary bytes.
        if not isinstance(content_base64, str):
            raise ValueError("content_base64 is invalid")
        if len(content_base64) > 4 * ((self.MAX_BYTES + 2) // 3):
            raise ValueError("asset exceeds the 25 MiB limit")
        try:
            data = base64.b64decode(content_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("content_base64 is invalid") from exc
        if not data:
            raise ValueError("asset content is empty")
        if len(data) > self.MAX_BYTES:
            raise ValueError("asset exceeds the 25 MiB limit")
        safe_name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name).strip().rstrip(". ")[:255]
        if not safe_name:
            raise ValueError("asset filename is empty")
        media_type = str(media_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").strip()
        if not re.fullmatch(r"[A-Za-z0-9!#$&^_.+*-]+/[A-Za-z0-9!#$&^_.+*-]+", media_type):
            raise ValueError("asset media_type is invalid")
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240):
            raise ValueError("invalid asset idempotency key")
        identity = {"filename": safe_name, "kind": str(kind or "file")[:40], "media_type": media_type,
                    "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "branch_id": branch_id}
        binding = getattr(self._scope, "binding", None)
        if "narrative_production_v2" in required_features and binding is None:
            raise ValueError("ASSET_PROJECT_BINDING_REQUIRED")
        if binding is not None:
            if binding["novel_id"] != novel_id or binding["branch_id"] != branch_id:
                raise ValueError("ASSET_PROJECT_SCOPE_MISMATCH")
            identity["_project_binding"] = copy.deepcopy(binding)
        if required_features or owner_actor_id:
            identity.update(_required_features=sorted(set(required_features)), _owner_actor_id=owner_actor_id)
        if _initial_comic_page is not None:
            from .comic_page_origin import marker, validate_png, FEATURES
            origin = marker(_initial_comic_page)
            if (binding is None or owner_actor_id is not None or not callable(guard)
                    or kind != 'image' or media_type != 'image/png' or not FEATURES.issubset(required_features)
                    or any(v is not None for v in (_initial_text_result, _initial_studio_result, _initial_manual_mask,
                        _initial_model_reference, _initial_video_reference, _initial_prompt_write, _initial_comic_ora))
                    or (origin['scope_key'], origin['incarnation'], origin['png_sha256']) !=
                       (binding['scope_key'], binding['incarnation'], identity['sha256'])
                    or idempotency_key != 'comic-page:' + origin['receipt_id'] + ':' + str(origin['index'])):
                raise ValueError('COMIC_PAGE_ORIGIN_INVALID')
            validate_png(data, origin)
            identity.update(_comic_page_origin=origin, source_asset_ids=[],
                            source_job_id=None, provider_id=None, model_id=None)
        if _initial_comic_ora is not None:
            from .comic_ora_origin import marker, FEATURES
            origin = marker(_initial_comic_ora)
            if (binding is None or owner_actor_id != origin['actor'] or not callable(guard)
                    or kind != 'image' or media_type != 'image/png' or not FEATURES.issubset(required_features)
                    or any(v is not None for v in (_initial_text_result, _initial_studio_result, _initial_manual_mask,
                        _initial_model_reference, _initial_video_reference, _initial_prompt_write))
                    or (origin['scope_key'], origin['incarnation'], origin['png_sha256']) !=
                       (binding['scope_key'], binding['incarnation'], identity['sha256'])):
                raise ValueError('COMIC_ORA_ORIGIN_INVALID')
            identity['_comic_ora_origin'] = origin
        if _initial_prompt_write is not None:
            # Server-only request provenance joins the original first metadata
            # commit and idempotency identity. No HTTP DTO exposes this field.
            origin = copy.deepcopy(_initial_prompt_write)
            fields = {"contract", "operation", "allocated_family_id", "expected_previous_asset_id",
                      "expected_revision", "request_digest"}
            if (not isinstance(origin, dict) or set(origin) != fields or binding is None
                    or not owner_actor_id or not callable(guard) or kind != "prompt" or media_type != "text/plain"
                    or "narrative_production_v2" not in required_features
                    or any(value is not None for value in (_initial_text_result, _initial_studio_result, _initial_manual_mask, _initial_model_reference))
                    or origin["contract"] != "studio-prompt-write-origin/1"
                    or origin["operation"] not in {"CREATE", "REVISE"}
                    or not isinstance(origin["allocated_family_id"], str) or not 1 <= len(origin["allocated_family_id"]) <= 240
                    or not re.fullmatch(r"[a-f0-9]{64}", str(origin["request_digest"]))):
                raise ValueError("PROMPT_WRITE_ORIGIN_INVALID")
            previous, revision = origin["expected_previous_asset_id"], origin["expected_revision"]
            if ((origin["operation"] == "CREATE" and (previous is not None or revision is not None))
                    or (origin["operation"] == "REVISE" and (not isinstance(previous, str)
                        or not 1 <= len(previous) <= 240 or type(revision) is not int or not 1 <= revision <= 100000))):
                raise ValueError("PROMPT_WRITE_ORIGIN_INVALID")
            identity["_prompt_write_origin"] = origin
        # New server-only reference inputs are exclusive of every existing origin.
        if _initial_video_reference is not None and any(v is not None for v in
                (_initial_text_result, _initial_studio_result, _initial_manual_mask, _initial_prompt_write, _initial_model_reference)):
            raise ValueError("VIDEO_REFERENCE_ORIGIN_INVALID")
        initial_review = None
        manual_lineage = None
        model_lineage = None
        video_lineage = None
        if _initial_video_reference is not None:
            from .studio_video_reference_origin import marker, FEATURES
            from .studio_video_reference_frames import validate_png
            if (binding is None or owner_actor_id is not None or not callable(guard)
                    or kind != "image" or media_type != "image/png" or not FEATURES.issubset(required_features)):
                raise ValueError("VIDEO_REFERENCE_ORIGIN_INVALID")
            origin = marker(_initial_video_reference)
            if (origin["scope_key"], origin["incarnation"], origin["png_sha256"]) != (binding["scope_key"], binding["incarnation"], identity["sha256"]):
                raise ValueError("VIDEO_REFERENCE_ORIGIN_INVALID")
            validate_png(data, origin["width"], origin["height"])
            source = self._video_reference_source(origin, novel_id, branch_id)
            if not set(source.get("_required_features", [])).issubset(required_features):
                raise ValueError("VIDEO_REFERENCE_SOURCE_FEATURES_REQUIRED")
            identity.update(_video_reference_origin=origin, source_asset_ids=[origin["source"]["id"]],
                            source_job_id=None, provider_id=None, model_id=None)
            video_lineage = {"schema": "asset-lineage-v2", "origin": "MANUAL_EDIT",
                "license": {"label": "UNSPECIFIED", "source": "", "note": ""},
                "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                "operation": "Sampled video frame reference; no semantic analysis", "declared_by": origin["actor"], "declared_at": now(),
                "sources": {}, "parents": {origin["source"]["id"]: {"version": origin["source"]["version"], "digest": origin["source"]["sha256"]}},
                "output_digest": origin["png_sha256"]}
        elif _video_reference_expected_retry_id is not None:
            raise ValueError("VIDEO_REFERENCE_ORIGIN_INVALID")
        if _initial_model_reference is not None:
            from .studio_model_reference_origin import marker, pixels
            if (any(v is not None for v in (_initial_text_result, _initial_studio_result, _initial_manual_mask, _initial_prompt_write))
                    or binding is None or owner_actor_id is not None or not callable(guard)
                    or kind != "image" or media_type != "image/png"
                    or not {"narrative_production_v2", "asset_lineage_v2"}.issubset(required_features)):
                raise ValueError("MODEL_REFERENCE_ASSET_ORIGIN_INVALID")
            origin = marker(_initial_model_reference)
            if (origin["scope_key"], origin["incarnation"], origin["png_sha256"]) != (binding["scope_key"], binding["incarnation"], identity["sha256"]):
                raise ValueError("MODEL_REFERENCE_ASSET_ORIGIN_INVALID")
            pixels(data)
            source = self._model_reference_source(origin, novel_id, branch_id)
            if not set(source.get("_required_features", [])).issubset(required_features):
                raise ValueError("MODEL_REFERENCE_SOURCE_FEATURES_REQUIRED")
            identity.update(_model_reference_origin=origin, source_asset_ids=[origin["source"]["id"]], source_job_id=None, provider_id=None, model_id=None)
            model_lineage = {"schema":"asset-lineage-v2", "origin":"MANUAL_EDIT",
                "license":{"label":"UNSPECIFIED","source":"","note":""},
                "license_verification":"AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                "operation":"Static GLB clay diagnostic reference", "declared_by":origin["actor"], "declared_at":now(),
                "sources":{}, "parents":{origin["source"]["id"]:{"version":origin["source"]["version"],"digest":origin["source"]["sha256"]}},
                "output_digest":origin["png_sha256"]}
        elif _model_reference_expected_retry_id is not None:
            raise ValueError("MODEL_REFERENCE_ASSET_ORIGIN_INVALID")
        if _initial_manual_mask is not None:
            if (_initial_text_result is not None or _initial_studio_result is not None or binding is None
                    or owner_actor_id is not None or not callable(guard) or kind != "image" or media_type != "image/png"
                    or not {"narrative_production_v2", "asset_lineage_v2"}.issubset(required_features)):
                raise ValueError("IMAGE_MASK_ORIGIN_CONFLICT")
            origin = self._manual_marker(_initial_manual_mask)
            if (origin["scope_key"], origin["incarnation"]) != (binding["scope_key"], binding["incarnation"]):
                raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
            from .studio_image_mask_authoring import verify_mask, validate_source_png
            proof = verify_mask(data)
            if any(origin[key] != value for key, value in proof.items()):
                raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
            source = self._manual_source(origin, novel_id, branch_id)
            if not set(source.get("_required_features", [])).issubset(required_features):
                raise ValueError("IMAGE_MASK_SOURCE_FEATURES_REQUIRED")
            validate_source_png(self._verified_content(source), origin["width"], origin["height"])
            identity.update(_manual_mask_origin=origin, source_asset_ids=[origin["source"]["id"]],
                            source_job_id=None, provider_id=None, model_id=None)
            manual_lineage = {"schema": "asset-lineage-v2", "origin": "MANUAL_EDIT",
                "license": {"label": "UNSPECIFIED", "source": "", "note": ""},
                "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                "operation": "Manual binary mask: white KEEP, black REMOVE", "declared_by": origin["actor"],
                "declared_at": now(), "sources": {}, "parents": {origin["source"]["id"]:
                    {"version": origin["source"]["version"], "digest": origin["source"]["sha256"]}},
                "output_digest": origin["mask_sha256"]}
        elif _manual_expected_retry_id is not None:
            raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
        if _initial_studio_result is not None:
            # Server-only media origin. Generic metadata/lineage inputs cannot
            # mint this immutable authority marker or adopt legacy job assets.
            origin = copy.deepcopy(_initial_studio_result)
            if (binding is None or not owner_actor_id or not callable(guard)
                    or "narrative_production_v2" not in required_features
                    or kind not in {"image", "video", "audio"}
                    or origin.get("contract") != "studio-production-result/1"
                    or origin.get("scope_key") != binding["scope_key"]
                    or origin.get("incarnation") != binding["incarnation"]
                    or origin.get("actor") != owner_actor_id
                    or not re.fullmatch(r"[a-f0-9]{64}", str(origin.get("request_digest", "")))
                    or len(json.dumps(origin, ensure_ascii=False).encode()) > 24 * 1024):
                raise ValueError("STUDIO_RESULT_AUTHORITY_REQUIRED")
            self._identifier(origin.get("job_id"), "job_id")
            if "storyboard_shot" in origin:
                from ..creative.production_execution_models import StoryboardShotPin
                pin = StoryboardShotPin.model_validate(origin["storyboard_shot"])
                if (not str(origin.get("operation_id", "")).startswith("m7.") or not any(
                        source.get("kind") == "CREATIVE_DOCUMENT"
                        and (source.get("id"), source.get("version"), source.get("digest")) ==
                        (pin.document_snapshot.id, pin.document_snapshot.version, pin.document_snapshot.digest)
                        for source in origin.get("sources", []))):
                    raise ValueError("STUDIO_STORYBOARD_SOURCE_PIN_REQUIRED")
            if "graph_binding" in origin:
                from ..creative.graph_media_binding import validate_graph_binding
                if origin["graph_binding"] is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
                validate_graph_binding(origin["graph_binding"], origin)
            if _initial_text_result is not None:
                raise ValueError("STUDIO_RESULT_ORIGIN_CONFLICT")
            identity.update(_studio_result_origin=origin, source_job_id=origin["job_id"],
                            provider_id=origin.get("provider_id"), model_id=origin.get("model_id"))
        if _initial_text_result is not None:
            # Server-only entry: no HTTP input model exposes this argument.
            # All immutable provenance participates in idempotency, while its
            # later review projection must not change the creation identity.
            initial = self._text_initial(_initial_text_result, data)
            from ..creative.adaptation_receipt import ASSET_CONTRACT, FEATURES
            adaptation = initial["_text_result_origin"]["contract"] == ASSET_CONTRACT
            features_valid = (set(required_features) == FEATURES if adaptation
                              else self.TEXT_RESULT_FEATURES.issubset(required_features))
            if (binding is None or not owner_actor_id or not callable(guard)
                    or not features_valid or kind != "text" or media_type != "text/plain"):
                raise ValueError("TEXT_RESULT_AUTHORITY_REQUIRED")
            identity.update(initial)
            initial_review = {"status": "DRAFT", "receipt": None, "history": []}
        with self._lock, workspace_mutation(self.root, "asset-library"):
            manual_prior = None
            if manual_lineage is not None:
                manual_prior = self.manual_mask_retry(novel_id, idempotency_key, branch_id=branch_id)
                if _manual_expected_retry_id is not None and (manual_prior is None or manual_prior["id"] != _manual_expected_retry_id):
                    raise ValueError("IMAGE_MASK_RETRY_CHANGED")
            reference_prior = None
            if model_lineage is not None:
                reference_prior = self.model_reference_retry(novel_id, idempotency_key, branch_id=branch_id)
                if _model_reference_expected_retry_id is not None and (reference_prior is None or reference_prior["id"] != _model_reference_expected_retry_id):
                    raise ValueError("MODEL_REFERENCE_RETRY_CHANGED")
            video_prior = None
            if video_lineage is not None:
                video_prior = self.video_reference_retry(novel_id, idempotency_key, branch_id=branch_id)
                if _video_reference_expected_retry_id is not None and (video_prior is None or video_prior["id"] != _video_reference_expected_retry_id):
                    raise ValueError("VIDEO_REFERENCE_RETRY_CHANGED")
            comic_orphan_verified = False
            if _initial_comic_page is not None:
                expected_id = identity['_comic_page_origin']['asset_id']
                for planned_path in (self._meta_path(expected_id), self._bin_path(expected_id)):
                    try: planned_info = planned_path.lstat()
                    except FileNotFoundError: continue
                    if (not stat.S_ISREG(planned_info.st_mode)
                            or getattr(planned_info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                        raise AssetIdempotencyConflict('COMIC_PAGE_STAGED_PATH_INVALID')
                if self._meta_path(expected_id).exists():
                    existing = self._load(expected_id)
                    if (existing.get('novel_id') != novel_id or existing.get('idempotency_key') != idempotency_key
                            or any(existing.get(k) != v for k, v in identity.items()) or existing.get('deleted_at')
                            or not self._in_scope(existing, branch_id, owner_actor_id)):
                        raise AssetIdempotencyConflict('COMIC_PAGE_STAGED_ID_CONFLICT')
                    # Indexed native Assets retain the original normal ingestion
                    # and Timeline content contract; this is not a preview read.
                    self.content(expected_id, branch_id=branch_id)
                    guard()
                    return existing
                if self._bin_path(expected_id).exists():
                    # Unindexed bytes require the original no-follow bounded
                    # reader. Windows remains explicitly unsupported here.
                    self._verified_content({'id': expected_id, 'size': len(data), 'sha256': identity['sha256']},
                                           max_bytes=self.MAX_BYTES, guard=guard)
                    comic_orphan_verified = True
            if _initial_comic_ora is not None:
                # Exact preallocated ID is journaled before this call. Never
                # discover/adopt another actor's record via a generic list.
                expected_id = identity['_comic_ora_origin']['asset_id']
                if self._meta_path(expected_id).exists():
                    existing = self._load(expected_id)
                    if (existing.get('novel_id') != novel_id or existing.get('idempotency_key') != idempotency_key
                            or any(existing.get(k) != v for k, v in identity.items()) or existing.get('deleted_at')
                            or not self._in_scope(existing, branch_id, owner_actor_id)):
                        raise AssetIdempotencyConflict('COMIC_ORA_STAGED_ID_CONFLICT')
                    self._verified_content(existing, max_bytes=self.MAX_BYTES, guard=guard)
                    guard()
                    return existing
                if self._bin_path(expected_id).exists():
                    # Exact ID was durably planned before create. Reconcile only
                    # bytes identical to the caller's newly parsed canonical PNG.
                    # Never remove a pre-existing orphan on another write failure.
                    self._verified_content({'id': expected_id, 'size': len(data), 'sha256': identity['sha256']},
                                           max_bytes=self.MAX_BYTES, guard=guard)
                    comic_orphan_verified = True
            if idempotency_key:
                candidates = ([manual_prior] if manual_prior is not None else []) if manual_lineage is not None else self.list(novel_id, branch_id=branch_id, include_deleted=True, actor_id=owner_actor_id)
                if model_lineage is not None: candidates = [reference_prior] if reference_prior is not None else []
                if video_lineage is not None: candidates = [video_prior] if video_prior is not None else []
                for existing in candidates:
                    if existing.get("idempotency_key") != idempotency_key:
                        continue
                    if any(existing.get(key) != value for key, value in identity.items()):
                        raise AssetIdempotencyConflict("asset idempotency key was used for a different upload")
                    if existing.get("deleted_at"):
                        raise AssetIdempotencyConflict("asset was deleted; restore it or use a new idempotency key")
                    self.content(existing["id"], branch_id=branch_id, actor_id=owner_actor_id)
                    if guard:
                        guard()
                    if manual_lineage is not None:
                        self._manual_source(origin, novel_id, branch_id)
                    if model_lineage is not None: self._model_reference_source(origin, novel_id, branch_id)
                    if video_lineage is not None: self._video_reference_source(origin, novel_id, branch_id)
                    return existing
            asset_id = (identity['_comic_page_origin']['asset_id'] if _initial_comic_page is not None else
                        identity['_comic_ora_origin']['asset_id'] if _initial_comic_ora is not None else str(uuid.uuid4()))
            meta = {"id": asset_id, "novel_id": novel_id, **identity, "created_at": now(), "updated_at": now(),
                    "version": 1, "deleted_at": None, "idempotency_key": idempotency_key}
            if initial_review is not None:
                meta["_text_result_review"] = initial_review
            if manual_lineage is not None:
                meta["parameters"] = {"asset_lineage_v2": manual_lineage}
            if model_lineage is not None: meta["parameters"] = {"asset_lineage_v2": model_lineage}
            if video_lineage is not None: meta["parameters"] = {"asset_lineage_v2": video_lineage}
            target = self._bin_path(asset_id)
            fd, temporary = tempfile.mkstemp(dir=self.root, prefix=asset_id + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if guard:
                    guard()
                if manual_lineage is not None:
                    self._manual_source(origin, novel_id, branch_id)
                if model_lineage is not None: self._model_reference_source(origin, novel_id, branch_id)
                if video_lineage is not None: self._video_reference_source(origin, novel_id, branch_id)
                os.replace(temporary, target)
                self._write_meta(meta)
            except Exception:
                # This UUID was allocated by this operation under the existing
                # owner lock. If metadata never committed, keep no unindexed
                # binary. A metadata commit followed by an error is recoverable
                # through the idempotency key and must retain its original bytes.
                if not self._meta_path(asset_id).exists() and not comic_orphan_verified:
                    target.unlink(missing_ok=True)
                raise
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return meta

    @staticmethod
    def _manual_marker(value):
        from .studio_image_mask_authoring import CONTRACT, DIGEST, dimensions
        fields = {"contract", "actor", "scope_key", "incarnation", "source", "width", "height",
                  "bitplane_sha256", "keep_pixels", "remove_pixels", "mask_sha256"}
        if not isinstance(value, dict) or set(value) != fields or value.get("contract") != CONTRACT:
            raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
        dimensions(value["width"], value["height"])
        source = value["source"]
        if (not isinstance(source, dict) or set(source) != {"id", "version", "sha256"}
                or not isinstance(source["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", source["id"])
                or type(source["version"]) is not int or not 1 <= source["version"] <= 2**53 - 1
                or not isinstance(value["actor"], str) or not 1 <= len(value["actor"]) <= 240
                or any(ord(c) < 32 or ord(c) == 127 for c in value["actor"])
                or not isinstance(value["incarnation"], str) or not re.fullmatch(r"(?:file|postgres):[a-f0-9-]{36}", value["incarnation"])
                or any(not isinstance(v, str) or not DIGEST.fullmatch(v) for v in
                       (source["sha256"], value["scope_key"], value["bitplane_sha256"], value["mask_sha256"]))
                or any(type(value[k]) is not int or value[k] <= 0 for k in ("keep_pixels", "remove_pixels"))
                or value["keep_pixels"] + value["remove_pixels"] != value["width"] * value["height"]):
            raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
        return copy.deepcopy(value)

    def _manual_source(self, origin, novel_id, branch_id):
        from ..experimental.common import StaleSourceError
        source = self.get(origin["source"]["id"], branch_id=branch_id)
        if (source.get("novel_id") != novel_id or source.get("branch_id") != branch_id
                or source.get("kind") != "image" or source.get("media_type") != "image/png"
                or type(source.get("version")) is not int
                or source.get("version") != origin["source"]["version"] or source.get("sha256") != origin["source"]["sha256"]):
            raise StaleSourceError("IMAGE_MASK_SOURCE_STALE")
        self._verified_content(source)
        return source

    def _manual_record(self, meta):
        origin = self._manual_marker(meta.get("_manual_mask_origin"))
        binding = meta.get("_project_binding")
        features, parameters = meta.get("_required_features"), meta.get("parameters")
        if (not isinstance(binding, dict) or origin["scope_key"] != binding.get("scope_key")
                or origin["incarnation"] != binding.get("incarnation") or meta.get("_owner_actor_id") is not None
                or not isinstance(features, list) or any(not isinstance(f, str) for f in features)
                or not {"narrative_production_v2", "asset_lineage_v2"}.issubset(features)
                or not isinstance(parameters, dict)
                or meta.get("kind") != "image" or meta.get("media_type") != "image/png"
                or meta.get("sha256") != origin["mask_sha256"] or type(meta.get("version")) is not int or not 1 <= meta["version"] <= 2**53 - 1
                or meta.get("source_asset_ids") != [origin["source"]["id"]]
                or any(meta.get(k) is not None for k in ("provider_id", "model_id", "source_job_id", "approved_at"))):
            raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
        self._manual_lineage(parameters.get("asset_lineage_v2"), origin)
        return origin

    @staticmethod
    def _manual_lineage(lineage, origin):
        source = origin["source"]
        if (not isinstance(lineage, dict) or lineage.get("schema") != "asset-lineage-v2"
                or lineage.get("origin") != "MANUAL_EDIT" or lineage.get("sources") != {}
                or lineage.get("parents") != {source["id"]: {"version": source["version"], "digest": source["sha256"]}}
                or lineage.get("output_digest") != origin["mask_sha256"]):
            raise ValueError("IMAGE_MASK_SOURCE_IMMUTABLE")

    def manual_mask_retry(self, novel_id, key, *, branch_id):
        """Strict original-owner lookup; never skip damaged receipt metadata.

        This new action conservatively fails on unreadable metadata whose scope
        cannot be established. It does not change the legacy list contract.
        """
        binding = getattr(self._scope, "binding", None)
        if binding is None or (binding["novel_id"], binding["branch_id"]) != (novel_id, branch_id) or not isinstance(key, str):
            raise ValueError("IMAGE_MASK_ORIGIN_INVALID")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            found = None
            for path in self.root.glob("*.json"):
                try:
                    row = self._load(path.stem)
                except (ValueError, OSError, RecursionError):
                    raise ValueError("IMAGE_MASK_RECEIPT_UNAVAILABLE") from None
                if (row.get("idempotency_key"), row.get("_project_binding")) != (key, binding):
                    continue
                if ((row.get("novel_id"), row.get("branch_id")) != (novel_id, branch_id)
                        or found is not None or not self._in_scope(row, branch_id) or "_manual_mask_origin" not in row):
                    raise ValueError("IMAGE_MASK_RECEIPT_UNAVAILABLE")
                found = row
            return found

    @staticmethod
    def _model_reference_record(meta):
        from .studio_model_reference_origin import record
        return record(meta)

    def _model_reference_source(self, origin, novel_id, branch_id):
        from .studio_model_reference_origin import source
        return source(self, origin, novel_id, branch_id)

    def model_reference_retry(self, novel_id, key, *, branch_id):
        binding = getattr(self._scope, "binding", None)
        if binding is None or (binding["novel_id"], binding["branch_id"]) != (novel_id, branch_id) or not isinstance(key, str):
            raise ValueError("MODEL_REFERENCE_ASSET_ORIGIN_INVALID")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            found = None
            for path in self.root.glob("*.json"):
                try: row = self._load(path.stem)
                except (ValueError, OSError, RecursionError): raise ValueError("MODEL_REFERENCE_RECEIPT_UNAVAILABLE") from None
                if (row.get("idempotency_key"), row.get("_project_binding")) != (key, binding): continue
                if ((row.get("novel_id"), row.get("branch_id")) != (novel_id, branch_id) or found is not None
                        or not self._in_scope(row, branch_id) or "_model_reference_origin" not in row):
                    raise ValueError("MODEL_REFERENCE_RECEIPT_UNAVAILABLE")
                found = row
            return found

    @staticmethod
    def _video_reference_record(meta):
        from .studio_video_reference_origin import record
        return record(meta)

    def _video_reference_source(self, origin, novel_id, branch_id):
        from .studio_video_reference_origin import source
        return source(self, origin, novel_id, branch_id)

    def video_reference_retry(self, novel_id, key, *, branch_id):
        binding = getattr(self._scope, "binding", None)
        if binding is None or (binding["novel_id"], binding["branch_id"]) != (novel_id, branch_id) or not isinstance(key, str):
            raise ValueError("VIDEO_REFERENCE_ORIGIN_INVALID")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            found = None
            for path in self.root.glob("*.json"):
                try: row = self._load(path.stem)
                except (ValueError, OSError, RecursionError): raise ValueError("VIDEO_REFERENCE_RECEIPT_UNAVAILABLE") from None
                if (row.get("idempotency_key"), row.get("_project_binding")) != (key, binding): continue
                if ((row.get("novel_id"), row.get("branch_id")) != (novel_id, branch_id) or found is not None
                        or not self._in_scope(row, branch_id) or "_video_reference_origin" not in row):
                    raise ValueError("VIDEO_REFERENCE_RECEIPT_UNAVAILABLE")
                found = row
            return found

    @staticmethod
    def _text_stamp(value):
        if not isinstance(value, str) or not 1 <= len(value) <= 64:
            raise ValueError("TEXT_RESULT_TIMESTAMP_INVALID")
        try:
            stamp = datetime.fromisoformat(value)
            if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
                raise ValueError("UTC required")
        except (ValueError, OverflowError):
            raise ValueError("TEXT_RESULT_TIMESTAMP_INVALID") from None

    @staticmethod
    def _text_digest(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("TEXT_RESULT_DIGEST_INVALID")

    @classmethod
    def _text_source(cls, receipt):
        from ..creative.adaptation_receipt import ASSET_CONTRACT, validate_source
        if isinstance(receipt, dict) and receipt.get("contract") == ASSET_CONTRACT:
            return validate_source(receipt)
        expected = {"schema_version", "contract", "graph_id", "graph_version", "graph_digest", "run_id",
                    "source_run_version", "model_node_id", "job_id", "input_digest", "output_digest",
                    "preview_digest", "produced_at"}
        if (not isinstance(receipt, dict) or set(receipt) != expected
                or type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1
                or receipt.get("contract") != cls.TEXT_RESULT_CONTRACT):
            raise ValueError("TEXT_RESULT_SOURCE_RECEIPT_INVALID")
        for key in ("graph_id", "run_id", "model_node_id", "job_id"):
            cls._identifier(receipt[key], key)
        for key in ("graph_version", "source_run_version"):
            if type(receipt[key]) is not int or not 1 <= receipt[key] <= 2**53 - 1:
                raise ValueError("TEXT_RESULT_SOURCE_VERSION_INVALID")
        for key in ("graph_digest", "input_digest", "output_digest", "preview_digest"):
            cls._text_digest(receipt[key])
        cls._text_stamp(receipt["produced_at"])
        return copy.deepcopy(receipt)

    @classmethod
    def _text_initial(cls, initial, data):
        from ..creative.adaptation_receipt import ASSET_CONTRACT, validate_initial
        if (isinstance(initial, dict) and isinstance(initial.get("_text_result_origin"), dict)
                and initial["_text_result_origin"].get("contract") == ASSET_CONTRACT):
            return validate_initial(initial, data, source_validator=cls._text_source,
                metadata_encoder=cls.text_result_metadata_bytes)
        expected = {"_text_result_origin", "source_job_id", "provider_id", "model_id", "parameters"}
        from ..creative.text_execution_receipt import PRIVATE_FIELD, MAX_BYTES, validate_receipt
        if isinstance(initial, dict) and PRIVATE_FIELD in initial:
            expected.add(PRIVATE_FIELD)
        if not isinstance(initial, dict) or set(initial) != expected:
            raise ValueError("TEXT_RESULT_METADATA_INVALID")
        origin = cls._text_source(initial["_text_result_origin"])
        if (not 0 < len(data) <= cls.TEXT_RESULT_MAX_BYTES
                or origin["output_digest"] != hashlib.sha256(data).hexdigest()):
            raise ValueError("TEXT_RESULT_CONTENT_INVALID")
        try:
            if not data.decode("utf-8").strip() or b"\x00" in data:
                raise ValueError("invalid text")
        except (UnicodeError, ValueError):
            raise ValueError("TEXT_RESULT_CONTENT_INVALID") from None
        if initial["source_job_id"] != origin["job_id"]:
            raise ValueError("TEXT_RESULT_JOB_BINDING_INVALID")
        for key in ("provider_id", "model_id"):
            value = initial[key]
            if (not isinstance(value, str) or not value.strip() or len(value) > 240
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise ValueError("TEXT_RESULT_MODEL_IDENTITY_INVALID")
        parameters = initial["parameters"]
        if not isinstance(parameters, dict) or set(parameters).intersection(
                {"asset_lineage_v2", "asset_relationships_v2", "experimental_media_lineage"}):
            raise ValueError("TEXT_RESULT_PARAMETERS_INVALID")
        if PRIVATE_FIELD in initial:
            validate_receipt(initial[PRIVATE_FIELD], source=origin, provider_id=initial["provider_id"],
                model_id=initial["model_id"], parameters=parameters)
        try:
            encoded = json.dumps(initial, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise ValueError("TEXT_RESULT_METADATA_INVALID") from None
        if len(encoded) > (MAX_BYTES if PRIVATE_FIELD in initial else 16_000):
            raise ValueError("TEXT_RESULT_METADATA_LIMIT")
        return copy.deepcopy(initial)

    @staticmethod
    def text_result_metadata_bytes(initial):
        """Exact logical metadata encoder shared by admission and persistence validation."""
        try:
            return json.dumps(initial, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ValueError("TEXT_RESULT_METADATA_INVALID") from None

    @staticmethod
    def text_result_metadata(*, source_receipt, provider_id, model_id, source_job_id, parameters,
                             execution_receipt=None):
        """The complete initial metadata shape, shared with pre-inference admission."""
        return {"_text_result_origin": source_receipt, "source_job_id": source_job_id,
            "provider_id": provider_id, "model_id": model_id, "parameters": parameters,
            **({"_text_execution_receipt": execution_receipt} if execution_receipt is not None else {})}

    def create_text_result(self, novel_id, filename, text, *, source_receipt, provider_id, model_id,
                           source_job_id, parameters, idempotency_key, branch_id, owner_actor_id,
                           required_features, guard, execution_receipt=None):
        """Archive one server-validated result in the existing asset owner.

        The caller owns source/runtime authorization. Its guard is required and
        is called at the original owner's commit boundary, including retries.
        This helper neither runs a model nor grants a review decision.
        """
        from ..creative.adaptation_receipt import ASSET_CONTRACT, MAX_OUTPUT_BYTES
        maximum = self.TEXT_RESULT_MAX_BYTES
        if isinstance(source_receipt, dict) and source_receipt.get("contract") == ASSET_CONTRACT:
            self._text_source(source_receipt)
            maximum = MAX_OUTPUT_BYTES
        if not isinstance(text, str) or len(text) > maximum:
            raise ValueError("TEXT_RESULT_CONTENT_INVALID")
        try:
            data = text.encode("utf-8")
        except UnicodeError:
            raise ValueError("TEXT_RESULT_CONTENT_INVALID") from None
        if not idempotency_key:
            raise ValueError("TEXT_RESULT_IDEMPOTENCY_REQUIRED")
        return self.create(novel_id, filename, base64.b64encode(data).decode("ascii"), "text/plain", "text",
            idempotency_key, branch_id=branch_id, owner_actor_id=owner_actor_id,
            required_features=required_features, guard=guard,
            _initial_text_result=self.text_result_metadata(source_receipt=source_receipt, source_job_id=source_job_id,
                provider_id=provider_id, model_id=model_id, parameters=parameters, execution_receipt=execution_receipt))

    def review_text_result(self, asset_id, *, actor_id, branch_id, expected_version, output_digest,
                           status, review_receipt, guard, execution_receipt=None):
        """Project an original WorkflowRun decision without publishing ownership."""
        if (type(expected_version) is not int or expected_version < 1
                or status not in {"APPROVED", "REJECTED"} or not callable(guard)):
            raise ValueError("TEXT_RESULT_REVIEW_INVALID")
        self._text_digest(output_digest)
        from ..creative import adaptation_receipt as adaptation_contract
        adaptation = (isinstance(review_receipt, dict)
                      and review_receipt.get("contract") == adaptation_contract.REVIEW_CONTRACT)
        if adaptation:
            if status != "APPROVED":
                raise ValueError("TEXT_RESULT_REVIEW_INVALID")
            receipt = copy.deepcopy(review_receipt)
        else:
            expected = {"run_id", "run_version", "review_node_id", "output_digest", "reviewed_output_digest",
                        "reviewed_by", "reviewed_at"}
            if not isinstance(review_receipt, dict) or set(review_receipt) != expected:
                raise ValueError("TEXT_RESULT_REVIEW_RECEIPT_INVALID")
            receipt = copy.deepcopy(review_receipt)
            for key in ("run_id", "review_node_id"):
                self._identifier(receipt[key], key)
            if (type(receipt["run_version"]) is not int or not 1 <= receipt["run_version"] <= 2**53 - 1
                    or receipt["reviewed_by"] != actor_id or receipt["output_digest"] != output_digest):
                raise ValueError("TEXT_RESULT_REVIEW_BINDING_INVALID")
            self._text_digest(receipt["reviewed_output_digest"])
            self._text_stamp(receipt["reviewed_at"])
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            if meta.get("_owner_actor_id") != actor_id or not actor_id:
                raise FileNotFoundError(asset_id)
            if type(meta.get("version")) is not int or meta["version"] < 1:
                raise ValueError("TEXT_RESULT_VERSION_INVALID")
            origin = self._text_source(meta.get("_text_result_origin"))
            from ..creative.text_execution_receipt import PRIVATE_FIELD, validate_receipt
            if adaptation != (origin["contract"] == adaptation_contract.ASSET_CONTRACT):
                raise ValueError("TEXT_RESULT_REVIEW_BINDING_INVALID")
            if meta.get(PRIVATE_FIELD) != execution_receipt:
                raise ValueError("TEXT_EXECUTION_RECEIPT_CHANGED")
            if adaptation:
                receipt = adaptation_contract.validate_review(receipt, source=origin,
                    actor_id=actor_id, output_digest=output_digest)
                adaptation_contract.validate_receipt(execution_receipt, source=origin,
                    provider_id=meta.get("provider_id"), model_id=meta.get("model_id"),
                    parameters=meta.get("parameters", {}))
                features_valid = set(meta.get("_required_features", [])) == adaptation_contract.FEATURES
                decision_valid = True  # The closed adaptation validator checked its distinct proposal/document binding.
            else:
                if execution_receipt is not None:
                    validate_receipt(execution_receipt, source=origin, provider_id=meta.get("provider_id"),
                        model_id=meta.get("model_id"), parameters=meta.get("parameters", {}))
                features_valid = self.TEXT_RESULT_FEATURES.issubset(meta.get("_required_features", []))
                decision_valid = (receipt["run_id"] == origin["run_id"]
                                  and receipt["run_version"] > origin["source_run_version"])
            if (meta.get("kind") != "text" or meta.get("media_type") != "text/plain"
                    or not features_valid or not meta.get("_project_binding") or origin["output_digest"] != output_digest
                    or meta["sha256"] != output_digest or not decision_valid):
                raise ValueError("TEXT_RESULT_REVIEW_BINDING_INVALID")
            review = meta.get("_text_result_review")
            if (not isinstance(review, dict) or set(review) != {"status", "receipt", "history"}
                    or review.get("status") not in {"DRAFT", "APPROVED", "REJECTED"}
                    or not isinstance(review.get("history"), list)):
                raise ValueError("TEXT_RESULT_REVIEW_STATE_INVALID")
            if adaptation and ((review["status"] == "DRAFT" and meta["version"] != 1)
                    or (review["status"] == "APPROVED" and (meta["version"] != 2
                        or review["history"] != [{"status": "DRAFT", "asset_version": 1}]))
                    or review["status"] == "REJECTED"):
                raise ValueError("TEXT_RESULT_REVIEW_STATE_INVALID")
            self._verified_content(meta)
            if (review["status"] == status and review["receipt"] == receipt
                    and expected_version in {meta["version"], meta["version"] - 1}):
                guard()
                return meta
            if meta["version"] != expected_version:
                from .v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(self.public(meta))
            if review != {"status": "DRAFT", "receipt": None, "history": []}:
                raise ValueError("TEXT_RESULT_REVIEW_ALREADY_FINAL")
            guard()
            meta.update(_text_result_review={"status": status, "receipt": receipt,
                "history": [{"status": "DRAFT", "asset_version": meta["version"]}]},
                updated_at=now(), version=meta["version"] + 1)
            if status == "APPROVED":
                meta["approved_at"] = receipt["reviewed_at"]
            self._write_meta(meta)
            return meta

    def find_text_result(self, novel_id, idempotency_key, *, branch_id, owner_actor_id, proposal_id):
        """Server-only recovery lookup that cannot mistake a hidden row for absence.

        The caller must hold the exact original project scope. Unlike generic
        discovery, corruption, deleted matches and conflicting ownership are
        hard failures. No content or identity from a different project scope is
        returned, and this method neither creates nor repairs an asset. A
        proposal identity also fences a corrupted key after an archive commit
        whose proposal pointer has not yet committed.
        """
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        if (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240
                or not isinstance(owner_actor_id, str) or not 1 <= len(owner_actor_id) <= 240):
            raise ValueError("TEXT_RESULT_LOOKUP_INVALID")
        self._identifier(proposal_id, "proposal_id")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            binding = getattr(self._scope, "binding", None)
            if (binding is None or binding.get("novel_id") != novel_id
                    or binding.get("branch_id") != branch_id):
                raise ValueError("ASSET_PROJECT_BINDING_REQUIRED")
            matches = []
            for path in self.root.glob("*.json"):
                try:
                    meta = self._load(path.stem)
                except (ValueError, OSError, RecursionError):
                    # A corrupt row might be this same key. Treating it as
                    # absent would allow a second archive after a partial commit.
                    raise AssetIntegrityError("text result lookup integrity could not be verified") from None
                if meta.get("_project_binding") != binding:
                    continue
                origin = meta.get("_text_result_origin")
                if (isinstance(origin, dict) and origin.get("proposal_id") == proposal_id
                        and meta.get("idempotency_key") != idempotency_key):
                    raise AssetIdempotencyConflict("text result lookup identity conflict")
                if meta.get("idempotency_key") != idempotency_key:
                    continue
                if (meta.get("novel_id") != novel_id or meta.get("branch_id") != branch_id
                        or meta.get("_owner_actor_id") != owner_actor_id or meta.get("deleted_at")):
                    raise AssetIdempotencyConflict("text result lookup identity conflict")
                matches.append(meta)
                if len(matches) > 1:
                    raise AssetIdempotencyConflict("text result lookup identity conflict")
            return copy.deepcopy(matches[0]) if matches else None

    def list(self, novel_id: str, *, branch_id: str | None = None, include_deleted: bool = False, actor_id: str | None = None):
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        items = []
        for path in self.root.glob("*.json"):
            try:
                meta = self._load(path.stem)
            except (ValueError, FileNotFoundError):
                # Corrupt entries cannot be treated as active, safe assets.
                continue
            if (meta.get("novel_id") == novel_id and self._in_scope(meta, branch_id, actor_id)
                    and (include_deleted or not meta.get("deleted_at"))):
                items.append(meta)
        return sorted(items, key=lambda item: (item.get("created_at", ""), item["id"]))

    def project_usage(self, novel_id: str, *, branch_id: str | None = None):
        """Server-only aggregate quota accounting, never private asset discovery.

        Actor visibility and feature flags cannot make retained bytes disappear
        from admission. The caller must already hold this exact project scope;
        old incarnations, other branches and legacy unbound assets stay separate.
        Deleted assets still occupy their original bytes and count toward quota.
        """
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            binding = getattr(self._scope, "binding", None)
            if (binding is None or binding.get("novel_id") != novel_id
                    or binding.get("branch_id") != branch_id):
                raise ValueError("ASSET_PROJECT_BINDING_REQUIRED")
            count = size = 0
            for path in self.root.glob("*.json"):
                try:
                    row = self._load(path.stem)
                except (ValueError, FileNotFoundError):
                    continue
                if (row.get("novel_id") == novel_id and row.get("branch_id") == branch_id
                        and row.get("_project_binding") == binding):
                    count += 1
                    size += row["size"]
            return {"count": count, "bytes": size}

    def get(self, asset_id: str, *, branch_id: str | None = None, include_deleted: bool = False, actor_id: str | None = None):
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        meta = self._load(asset_id)
        if not self._in_scope(meta, branch_id, actor_id) or (meta.get("deleted_at") and not include_deleted):
            raise FileNotFoundError(asset_id)
        return meta

    def _verified_content(self, meta: dict, *, max_bytes=None, guard=lambda: None) -> bytes:
        budget = current_query_budget()
        if budget is not None:
            budget.charge(self._bin_path(meta["id"]), content=True)
        if max_bytes is not None:
            return self._verified_bounded_content(meta, max_bytes, guard)
        path = self._bin_path(meta["id"])
        from ..creative.asset_usage_budget import current_usage_budget
        usage_budget = current_usage_budget()
        try:
            if usage_budget is not None:
                # Original Graph 3-5 input validation must still verify bytes.
                # Repeated integrity reads share the observation's admission.
                guard()
                data = usage_budget.read_binary(path, min(meta['size'], self.MAX_BYTES))
                guard()
            else:
                with path.open("rb") as stream:
                    if os.fstat(stream.fileno()).st_size != meta["size"]:
                        raise AssetIntegrityError("asset content size mismatch")
                    data = stream.read(self.MAX_BYTES + 1)
        except FileNotFoundError:
            raise FileNotFoundError(meta["id"]) from None
        if len(data) != meta["size"] or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), meta["sha256"]):
            raise AssetIntegrityError("asset content digest mismatch")
        return data

    def _verified_bounded_content(self, meta, max_bytes, guard):
        """Opt-in guarded read; the established default reader is unchanged.

        Windows uses the admitted native reader. Other platforms lacking safe
        nonblocking/no-follow opens stay unavailable; there is no ordinary fallback.
        The original owner's root/ancestor directories remain trusted; the
        no-follow flag protects the asset's final path component only.
        """
        if type(max_bytes) is not int or not 1 <= max_bytes <= self.MAX_BYTES:
            raise ValueError("ASSET_BOUNDED_READ_LIMIT_INVALID")
        if type(meta.get("size")) is not int or not 0 < meta["size"] <= max_bytes:
            raise ValueError("ASSET_BOUNDED_READ_LIMIT")
        if os.name == "nt":
            from .asset_bounded_file_windows import (
                WindowsBoundedAssetError, read_windows_bounded_asset,
                windows_bounded_read_supported,
            )
            if not windows_bounded_read_supported():
                raise ValueError("ASSET_BOUNDED_READ_UNSUPPORTED")
            guard()
            try:
                return read_windows_bounded_asset(
                    self._bin_path(meta["id"]), trusted_root=self.root,
                    expected_size=meta["size"], max_bytes=max_bytes,
                    expected_sha256=meta["sha256"], guard=guard,
                )
            except WindowsBoundedAssetError as error:
                guard()
                if error.code in {"ASSET_BOUNDED_CONTENT_INVALID", "ASSET_BOUNDED_CONTENT_UNAVAILABLE"}:
                    raise AssetIntegrityError(error.code) from None
                raise ValueError(error.code) from None
        if not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_NONBLOCK", 0):
            raise ValueError("ASSET_BOUNDED_READ_UNSUPPORTED")
        guard()
        path = self._bin_path(meta["id"])

        def identity(info):
            if (not stat.S_ISREG(info.st_mode) or info.st_ino <= 0
                    or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_INVALID")
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

        descriptor = None
        try:
            before = identity(path.lstat())
            if before[2] != meta["size"]:
                raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_INVALID")
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_BINARY", 0))
            if identity(os.fstat(descriptor)) != before:
                raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_INVALID")
            handle = os.fdopen(descriptor, "rb")
            descriptor = None  # ownership transferred; with closes on every path
            with handle:
                parts, total, checksum = [], 0, hashlib.sha256()
                while total <= max_bytes:
                    guard()
                    block = handle.read(min(65536, max_bytes + 1 - total))
                    guard()
                    if not block:
                        break
                    parts.append(block); total += len(block); checksum.update(block)
                guard()
                if identity(os.fstat(handle.fileno())) != before or identity(path.lstat()) != before:
                    raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_INVALID")
            if total != meta["size"] or not hmac.compare_digest(checksum.hexdigest(), meta["sha256"]):
                raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_INVALID")
            guard()
            return b"".join(parts)
        except OSError:
            # Recheck authority before projecting a fixed private read error.
            guard()
            raise AssetIntegrityError("ASSET_BOUNDED_CONTENT_UNAVAILABLE") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def content(self, asset_id: str, *, branch_id: str | None = None, actor_id: str | None = None,
                max_bytes=None, guard=lambda: None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            if max_bytes is None:
                return self._verified_content(meta)
            return self._verified_content(meta, max_bytes=max_bytes, guard=guard)

    def update_metadata(self, asset_id: str, fields: dict, *, branch_id: str | None = None,
                        expected_version: int | None = None, _lineage_write: bool = False, actor_id: str | None = None,
                        guard=None, _relationships_write: bool = False):
        allowed = {"source_job_id", "provider_id", "model_id", "parameters", "approved_at",
                   "character_id", "scene_id", "source_asset_ids"}
        if not isinstance(fields, dict) or set(fields) - allowed:
            raise ValueError("unsupported asset metadata fields")
        if len(json.dumps(fields, ensure_ascii=False).encode()) > 64 * 1024:
            raise ValueError("asset metadata exceeds 64 KiB")
        for key, value in fields.items():
            if key == "parameters":
                if not isinstance(value, dict):
                    raise ValueError("asset parameters must be an object")
            elif key == "source_asset_ids":
                if not isinstance(value, list) or len(value) > 100:
                    raise ValueError("source_asset_ids must contain at most 100 assets")
            elif value is not None and (not isinstance(value, str) or len(value) > 240
                                        or any(ord(char) < 32 for char in value)):
                raise ValueError("invalid asset metadata value")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            if expected_version is not None and meta["version"] != expected_version:
                from .v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(self.public(meta))
            if '_comic_page_origin' in meta:
                from .comic_page_origin import record
                record(meta)
                if any(meta.get(k) != v for k, v in fields.items()):
                    raise ValueError('COMIC_PAGE_METADATA_IMMUTABLE')
            if '_comic_ora_origin' in meta and any(meta.get(k) != v for k, v in fields.items()):
                raise ValueError('COMIC_ORA_STAGED_METADATA_IMMUTABLE')
            if meta.get("_text_result_origin") is not None and any(
                    key in fields and fields[key] != meta.get(key)
                    for key in ("source_job_id", "provider_id", "model_id", "parameters", "approved_at", "source_asset_ids")):
                raise ValueError("TEXT_RESULT_PROVENANCE_IMMUTABLE")
            if meta.get("kind") == "prompt" and any(
                    key in fields and fields[key] != meta.get(key)
                    for key in ("source_job_id", "provider_id", "model_id", "approved_at",
                                "source_asset_ids")):
                # A prompt revision's provenance and approval identity are fixed once the
                # revision exists. The review path (`promote_owned`) sets `approved_at`
                # directly rather than through this method, so approval still works and
                # cannot be self-granted by an ordinary metadata write. Other asset kinds
                # are untouched.
                raise ValueError("PROMPT_REVISION_IDENTITY_IMMUTABLE")
            if "_manual_mask_origin" in meta:
                origin = self._manual_record(meta)
                if any(key in fields and fields[key] != meta.get(key) for key in
                       ("source_asset_ids", "source_job_id", "provider_id", "model_id", "approved_at")):
                    raise ValueError("IMAGE_MASK_SOURCE_IMMUTABLE")
                if "parameters" in fields and _lineage_write:
                    self._manual_lineage(fields["parameters"].get("asset_lineage_v2"), origin)
            if "_model_reference_origin" in meta:
                from .studio_model_reference_origin import lineage
                origin = self._model_reference_record(meta)
                if any(key in fields and fields[key] != meta.get(key) for key in
                       ("source_asset_ids", "source_job_id", "provider_id", "model_id", "approved_at")):
                    raise ValueError("MODEL_REFERENCE_SOURCE_IMMUTABLE")
                if "parameters" in fields and _lineage_write:
                    lineage(fields["parameters"].get("asset_lineage_v2"), origin)
            if "_video_reference_origin" in meta:
                from .studio_video_reference_origin import lineage
                origin = self._video_reference_record(meta)
                if any(key in fields and fields[key] != meta.get(key) for key in
                       ("source_asset_ids", "source_job_id", "provider_id", "model_id", "approved_at")):
                    raise ValueError("VIDEO_REFERENCE_SOURCE_IMMUTABLE")
                if "parameters" in fields and _lineage_write:
                    lineage(fields["parameters"].get("asset_lineage_v2"), origin)
            if "parameters" in fields:
                # Legacy generation parameters are caller-controlled. They
                # cannot manufacture or erase the gated provenance authority.
                for name, privileged in (("asset_lineage_v2", _lineage_write),
                                         ("asset_relationships_v2", _relationships_write)):
                    if privileged:
                        continue
                    protected = meta.get("parameters", {}).get(name)
                    provided = fields["parameters"].get(name)
                    if name in fields["parameters"] and (protected is None or provided != protected):
                        raise ValueError(f"{name} requires scoped versioned annotation")
                    if protected is not None:
                        fields = {**fields, "parameters": {**fields["parameters"], name: protected}}
            self._verified_content(meta)
            inherited_features = set(meta.get("_required_features", []))
            inherited_owner = meta.get("_owner_actor_id")
            for source_id in fields.get("source_asset_ids", []):
                source = self.get(source_id, branch_id=branch_id, actor_id=actor_id)
                inherited_features.update(source.get("_required_features", []))
                if source.get("_owner_actor_id"):
                    if inherited_owner not in {None, source["_owner_actor_id"]}: raise ValueError("asset source owners differ")
                    inherited_owner = source["_owner_actor_id"]
                if (source_id == asset_id or source.get("novel_id") != meta.get("novel_id")
                        or source.get("branch_id") != meta.get("branch_id")):
                    raise ValueError("source assets must be different assets in the same project and branch")
                self._verified_content(source)
            pending, visited = list(fields.get("source_asset_ids", [])), set()
            while pending:
                source_id = pending.pop()
                if source_id == asset_id:
                    raise ValueError("asset source relationship would create a cycle")
                if source_id in visited:
                    continue
                visited.add(source_id)
                source = self.get(source_id, branch_id=branch_id, include_deleted=True, actor_id=actor_id)
                pending.extend(source.get("source_asset_ids") or [])
            origin_changed = inherited_features != set(meta.get("_required_features", [])) or inherited_owner != meta.get("_owner_actor_id")
            if guard:
                guard()
            if any(meta.get(key) != value for key, value in fields.items()) or origin_changed:
                meta.update(fields)
                if inherited_features or inherited_owner:
                    meta.update(_required_features=sorted(inherited_features), _owner_actor_id=inherited_owner)
                meta.update(updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            return meta

    def promote_owned(self, asset_id: str, *, actor_id: str, branch_id: str | None, expected_version: int, provenance: dict, guard=None, _comic_ora_review=None):
        """Server-only explicit review: retain origin, identity and bytes."""
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            if '_comic_ora_origin' in meta:
                from .comic_ora_origin import record, unseal_review
                if _comic_ora_review is None or not callable(guard):
                    raise ValueError('COMIC_ORA_EXPLICIT_IMPORT_REVIEW_NOT_IMPLEMENTED_FOR_GENERIC_CALL')
                proof = unseal_review(_comic_ora_review, record(meta))
                if (proof != provenance or proof['actor'] != actor_id
                        or meta['version'] not in (1, 2) or expected_version != 1):
                    raise ValueError('COMIC_ORA_REVIEW_INVALID')
            elif _comic_ora_review is not None:
                raise ValueError('COMIC_ORA_REVIEW_INVALID')
            if meta.get("_text_result_origin") is not None:
                raise ValueError("TEXT_RESULT_PRIVATE_OWNER_REQUIRED")
            saved_provenance = {**copy.deepcopy(provenance), "review_actor": actor_id}
            if meta.get("_owner_actor_id") is None and meta.get("_origin_provenance") == saved_provenance and expected_version in {meta["version"], meta["version"] - 1}:
                if guard: guard()
                return self.public(meta)
            if meta.get("_owner_actor_id") != actor_id:
                raise FileNotFoundError(asset_id)
            if meta["version"] != expected_version:
                from .v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(self.public(meta))
            self._verified_content(meta, max_bytes=self.MAX_BYTES, guard=guard) if _comic_ora_review is not None else self._verified_content(meta)
            if guard: guard()
            if _comic_ora_review is not None:
                meta['_comic_ora_review'] = copy.deepcopy(proof)
            meta.update(_owner_actor_id=None, _origin_provenance=saved_provenance,
                        approved_at=now(), updated_at=now(), version=meta["version"] + 1)
            self._write_meta(meta)
            return self.public(meta)

    def annotate_lineage(self, asset_id: str, declaration: dict, parent_ids: list[str], *,
                         branch_id: str | None, expected_version: int, guard=None):
        """Extend the existing DAG in its existing mutation boundary.

        The experimental caller validates the declaration and chapter scope.
        Parent revisions are measured here, under the same lock as cycle
        validation and the write, so callers cannot supply fictional digests.
        """
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id)
            manual = (self._manual_record(meta) if "_manual_mask_origin" in meta else
                      self._model_reference_record(meta) if "_model_reference_origin" in meta else
                      self._video_reference_record(meta) if "_video_reference_origin" in meta else None)
            if manual is not None and (parent_ids != [manual["source"]["id"]]
                    or declaration.get("origin") != "MANUAL_EDIT" or declaration.get("sources") != {}):
                raise ValueError("IMAGE_MASK_SOURCE_IMMUTABLE")
            parents = {}
            for parent_id in dict.fromkeys(parent_ids):
                parent = self.get(parent_id, branch_id=branch_id)
                if parent.get("novel_id") != meta.get("novel_id") or parent.get("branch_id") != meta.get("branch_id"):
                    raise FileNotFoundError(parent_id)
                self._verified_content(parent)
                # A manual mask always refers to the revision painted by its
                # author. Annotation never silently refreshes a stale source.
                parents[parent_id] = ({"version": manual["source"]["version"], "digest": manual["source"]["sha256"]}
                                      if manual is not None else {"version": parent["version"], "digest": parent["sha256"]})
            lineage = {**declaration, "parents": parents, "output_digest": meta["sha256"]}
            previous = meta.get("parameters", {}).get("asset_lineage_v2")
            if isinstance(previous, dict):
                lineage["history"] = list(previous.get("history", [])) + [
                    {**{key: value for key, value in previous.items() if key != "history"}, "asset_version": meta["version"]}]
            parameters = {**meta.get("parameters", {}), "asset_lineage_v2": lineage}
            if guard:
                guard()
            return self.update_metadata(asset_id, {"parameters": parameters, "source_asset_ids": list(parents)},
                                        branch_id=branch_id, expected_version=expected_version, _lineage_write=True, guard=guard)

    def delete(self, asset_id: str, *, branch_id: str | None = None, guard=None, actor_id: str | None = None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, include_deleted=True, actor_id=actor_id)
            if guard:
                guard()
            if not meta.get("deleted_at"):
                meta.update(deleted_at=now(), updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            # Keep original bytes and identity. Existing reads deliberately 404.
            return {"id": asset_id, "deleted": True, "recoverable": True,
                    "sha256": meta["sha256"], "version": meta["version"]}

    def restore(self, asset_id: str, *, branch_id: str | None = None, guard=None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, include_deleted=True)
            self._verified_content(meta)
            if guard:
                guard()
            if meta.get("deleted_at"):
                meta.update(deleted_at=None, updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            return meta
