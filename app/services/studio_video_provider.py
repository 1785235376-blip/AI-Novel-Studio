"""Guarded asynchronous local adapter for the existing VideoProvider protocol."""
from __future__ import annotations

import base64
import copy
import hashlib
import re
from urllib.parse import quote

from ..asset_providers import VideoGenerationResult, _verified_inline_image
from .studio_video_provider_recipes import build_workflow, project_comfy_video_recipe, timing
from .studio_image_provider_recipes import validate_workflow

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,239}$")


class ComfyUIVideoProvider:
    supports_dispatch_guard = True
    supports_status_guard = True

    def __init__(self, transport, endpoint, recipe):
        self.transport, self.endpoint, self.recipe = transport, endpoint.rstrip("/"), copy.deepcopy(recipe)

    def capabilities(self):
        return {"text_to_video": "t2v" in self.recipe["operations"], "image_to_video": "i2v" in self.recipe["operations"],
            "video_to_video": False, "start_frame": "i2v" in self.recipe["operations"], "end_frame": False,
            "polling": True, "cancellation": False}

    def health_check(self):
        try: return self.transport.get(self.endpoint + "/system_stats", timeout=1.5).status_code == 200
        except Exception: return False

    def execution_recipe(self, request):
        operation = "i2v" if request.start_frame else "t2v"
        if request.source_video_uri is not None or request.end_frame:
            raise ValueError("STUDIO_VIDEO_LOCAL_REFERENCE_UNSUPPORTED")
        return {"video_recipe_id": self.recipe["recipe_id"], "timing": timing(self.recipe, request.parameters),
            "workflow": build_workflow(self.recipe, request.prompt, request.parameters, operation=operation,
                upload="VERIFIED_SOURCE_UPLOAD_RECEIPT" if request.start_frame else None),
            "structural_only": True, "inference_verified": False, "reference_video_execution": False}

    @staticmethod
    def _guard(guard):
        if guard is not None: guard()

    def _observed(self, guard):
        self._guard(guard)
        response = self.transport.get(self.endpoint + "/object_info", timeout=10, dispatch_guard=guard)
        response.raise_for_status()
        info = response.json()
        family = {"comfy-ltx095-video-v1": "LTX", "comfy-wan22-ti2v5b-v1": "WAN", "comfy-hunyuan10-t2v-v1": "HUNYUAN_VIDEO"}[self.recipe["recipe_id"]]
        if project_comfy_video_recipe(info, self.recipe["components"]["model"], family) != self.recipe:
            raise ValueError("STUDIO_VIDEO_RECIPE_METADATA_CHANGED")
        self._guard(guard)
        return info

    def generate(self, request):
        self.execution_recipe(request)  # Bounds and unsupported inputs before any I/O.
        guard, upload = request.dispatch_guard, None
        info = self._observed(guard)
        if request.start_frame:
            data, measured = _verified_inline_image(request.start_frame)
            if max(measured["width"], measured["height"]) > 2048:
                raise ValueError("STUDIO_VIDEO_IMAGE_REFERENCE_LIMIT")
            name = "studio-video-" + hashlib.sha256(request.task_id.encode()).hexdigest() + "." + measured["extension"]
            self._guard(guard)
            response = self.transport.post(self.endpoint + "/upload/image", files={"image": (name, data, measured["media_type"])},
                data={"type": "input", "overwrite": "false"}, timeout=30, dispatch_guard=guard)
            response.raise_for_status()
            receipt = response.json()
            upload = receipt.get("name")
            if (not isinstance(upload, str) or not SAFE_NAME.fullmatch(upload) or ".." in upload
                    or receipt.get("subfolder", "") or receipt.get("type", "input") != "input"):
                raise ValueError("STUDIO_VIDEO_UPLOAD_RECEIPT_INVALID")
            self._guard(guard)
            info = self._observed(guard)
        graph = build_workflow(self.recipe, request.prompt, request.parameters,
            operation="i2v" if upload is not None else "t2v", upload=upload)
        validate_workflow(info, graph)
        self._guard(guard)
        response = self.transport.post(self.endpoint + "/prompt", json={"prompt": graph}, timeout=15, dispatch_guard=guard)
        response.raise_for_status()
        self._guard(guard)
        remote = response.json().get("prompt_id")
        if not isinstance(remote, str) or not SAFE_NAME.fullmatch(remote) or ".." in remote:
            raise ValueError("STUDIO_VIDEO_PROMPT_RECEIPT_INVALID")
        return VideoGenerationResult(request.provider_id, request.model_id, remote_task_id=remote, status="RUNNING")

    def get_status(self, remote_task_id, *, dispatch_guard=None):
        if not isinstance(remote_task_id, str) or not SAFE_NAME.fullmatch(remote_task_id) or ".." in remote_task_id:
            raise ValueError("STUDIO_VIDEO_PROMPT_RECEIPT_INVALID")
        self._observed(dispatch_guard)
        response = self.transport.get(self.endpoint + "/history/" + quote(remote_task_id, safe=""), timeout=10, dispatch_guard=dispatch_guard)
        response.raise_for_status()
        self._guard(dispatch_guard)
        payload = response.json()
        entry = payload.get(remote_task_id, {}) if isinstance(payload, dict) else None
        if not isinstance(entry, dict): raise ValueError("STUDIO_VIDEO_HISTORY_INVALID")
        status = entry.get("status", {})
        if not isinstance(status, dict): raise ValueError("STUDIO_VIDEO_HISTORY_INVALID")
        if status.get("status_str") in {"error", "failed"}:
            return {"status": "FAILED", "error": "STUDIO_VIDEO_REMOTE_FAILED"}
        if status.get("completed") is not True:
            return {"status": "RUNNING"}
        if status.get("status_str") != "success":
            raise ValueError("STUDIO_VIDEO_TERMINAL_STATUS_INVALID")
        # Only our closed output node can supply a result. Other previews cannot.
        outputs = entry.get("outputs", {})
        if not isinstance(outputs, dict): raise ValueError("STUDIO_VIDEO_HISTORY_INVALID")
        output = outputs.get("9", {})
        if not isinstance(output, dict): raise ValueError("STUDIO_VIDEO_HISTORY_INVALID")
        values = output.get("images", [])
        if not values:
            raise ValueError("STUDIO_VIDEO_OUTPUT_MISSING")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
            raise ValueError("STUDIO_VIDEO_OUTPUT_RECEIPT_INVALID")
        item = values[0]
        name = item.get("filename")
        if (not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or ".." in name or not name.endswith(".webm")
                or item.get("subfolder", "") or item.get("type", "output") != "output"):
            raise ValueError("STUDIO_VIDEO_OUTPUT_RECEIPT_INVALID")
        self._guard(dispatch_guard)
        response = self.transport.get(self.endpoint + "/view", params={"filename": name, "subfolder": "", "type": "output"},
            timeout=30, dispatch_guard=dispatch_guard)
        response.raise_for_status()
        self._guard(dispatch_guard)
        data = response.content
        if not data or len(data) > 25 * 1024 * 1024:
            raise ValueError("STUDIO_VIDEO_OUTPUT_SIZE_INVALID")
        return {"status": "SUCCEEDED", "url": "data:video/webm;base64," + base64.b64encode(data).decode("ascii")}
