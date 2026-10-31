"""Supplementary authored geometry over the original Creative document snapshot.

No geometry inference, model call, write path, independent checker or store.
"""
from copy import deepcopy

from ..experimental.director import camera_checks

CONTRACT = "studio-director-authored-camera-evidence/1"


def project_camera_geometry(document, document_digest):
    """Only opt-in authored fields extend the legacy workspace wire shape."""
    field = "director_notes" if document.get("mode") == "DIRECTOR" else "shots"
    rows = sorted(document.get(field, []), key=lambda row: (row["number"], row["id"]))
    if not any(row.get("camera_grammar") is not None for row in rows):
        return None
    # Preserve exact IDs, scene association and authored order. Missing geometry
    # stays missing; the original checker returns INSUFFICIENT_EVIDENCE.
    scenes = {row["id"] for row in document.get("scenes", []) if row.get("id")}
    adapted = [{**deepcopy(row), "director": deepcopy(row.get("camera_grammar")),
                # Unbound scenes must not compare equal, even in a malformed
                # internal projection call. A unique sentinel is never output.
                "scene_id": row.get("scene_id") if row.get("scene_id") in scenes else object()} for row in rows]
    return {
        "contract": CONTRACT, "schema_version": 1,
        "evidence_kind": "SUPPLEMENTARY_AUTHORED_GEOMETRY",
        "model_called": False, "visual_analysis": False, "auto_modify": False,
        "document_snapshot": {"id": document["id"], "version": document["version"], "digest": document_digest},
        "source_field": field,
        "rows": [{"id": row["id"], "number": row["number"], "scene_id": row.get("scene_id") or "",
                  "geometry_authored": row.get("camera_grammar") is not None,
                  "camera_grammar": deepcopy(row.get("camera_grammar"))} for row in rows],
        "findings": camera_checks(adapted),
    }
