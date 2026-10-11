"""Explicit transfer on the original Studio timeline, source and CAS owner.

This adapter owns no store, queue, media files or runtime. Preview is detached;
only a reviewed IMPORT writes through the original timeline transaction. The
source text and attachment bytes are never duplicated in timeline history.
"""
from __future__ import annotations

import copy
import hashlib

from ..experimental.common import StaleSourceError, change_row
from ..services.studio_timeline_render import studio_sources
from .production_execution_models import TimelineTransferPreview, TimelineTransferImport, TimelineTransferDownload


class TimelineTransfer:
    def __init__(self, owner):
        self.owner = owner

    @staticmethod
    def _input(body):
        return body.model_dump(include=set(TimelineTransferPreview.model_fields))

    def _prepare(self, nid, scope, actor, tid, body, context, document, guard):
        from .production_execution import digest
        row = self.owner._owned_timeline(nid, scope, actor, tid, context, document)
        if (row["version"], row["timeline_digest"]) != (body.expected_version, body.reviewed_timeline_digest):
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        report, bindings, attachment = [], [], None
        timeline = copy.deepcopy(row["timeline"])
        if body.format == "OTIO":
            from ..experimental.timeline_exchange import read_otio, write_otio
            from ..services.studio_timeline_exchange import studio_timeline_to_exchange, exchange_to_studio_timeline
            if body.direction == "IMPORT":
                exchange, losses = read_otio(body.content)
                converted = exchange_to_studio_timeline(exchange,
                    media_bindings=[item.model_dump() for item in body.media_bindings],
                    canvas={key: timeline[key] for key in ("width", "height", "fps")})
                timeline, report = converted["timeline"], losses + converted["report"]
                bindings = [item.model_dump() for item in body.media_bindings]
            else:
                converted = studio_timeline_to_exchange(timeline, title=row["title"])
                report, bindings = converted["report"], converted["media_bindings"]
                attachment = write_otio(converted["document"])
        else:
            from ..services.studio_timeline_subtitles import import_subtitles, export_subtitles
            if body.direction == "IMPORT":
                timeline = import_subtitles(timeline, body.content, body.format)
                if row["timeline"]["captions"] and row["timeline"]["captions"] != timeline["captions"]:
                    report.append({"path": "captions", "code": "EXISTING_CAPTIONS_REPLACED", "severity": "LOSS"})
            else:
                attachment = export_subtitles(timeline, body.format)
        # Never trust source references from an exchange document as authority.
        # Mapping is explicit and every final asset remains formal and current.
        if body.direction == "IMPORT":
            from ..services.studio_timeline_edit import require_timeline_lock_preservation
            timeline = require_timeline_lock_preservation(row["timeline"], timeline)
        self.owner._timeline_sources_current(nid, scope, timeline, guard)
        result = {"contract": "studio-timeline-transfer-preview/1", "direction": body.direction, "format": body.format,
            "timeline_snapshot": {"id": tid, "version": row["version"], "digest": row["timeline_digest"]},
            "input_digest": digest(self._input(body)), "timeline": timeline, "timeline_digest": digest(timeline),
            "sources": studio_sources(timeline), "media_bindings": bindings, "loss_report": report,
            "requires_loss_acknowledgment": bool(report), "output_sha256": hashlib.sha256(attachment).hexdigest() if attachment is not None else None,
            "output_bytes": len(attachment) if attachment is not None else None,
            "external_media_access": False, "model_called": False, "automatic_replay": False,
            "product_acceptance": "LOCAL_REQUIRED", "target_applications": {"Resolve": "NOT_RUN", "Premiere": "NOT_RUN"}}
        result["preview_digest"] = digest([context, result])
        guard()
        return row, result, attachment

    def preview(self, nid, scope, actor, tid, value, guard):
        body = TimelineTransferPreview.model_validate(value)
        context = self.owner._base(nid, scope, actor, guard)
        with self.owner.timeline_inputs.phase(nid, scope, actor, guard) as document:
            _, result, _ = self._prepare(nid, scope, actor, tid, body, context, document, guard)
        return result

    @staticmethod
    def _review(body, preview):
        if body.reviewed_preview_digest != preview["preview_digest"]:
            raise StaleSourceError("STUDIO_TRANSFER_PREVIEW_CHANGED")
        if preview["requires_loss_acknowledgment"] and not body.acknowledge_losses:
            raise ValueError("STUDIO_TRANSFER_REVIEW_LOSS_REPORT_REQUIRED")

    def apply(self, nid, scope, actor, tid, value, guard):
        from .production_execution import digest
        body = TimelineTransferImport.model_validate(value)
        if body.direction != "IMPORT":
            raise ValueError("STUDIO_TRANSFER_IMPORT_REQUIRED")
        context = self.owner._base(nid, scope, actor, guard)
        request_digest = digest(body.model_dump())
        with self.owner.timeline_inputs.transaction(nid, scope, actor, guard) as document:
            row = self.owner._owned_timeline(nid, scope, actor, tid, context, document)
            prior = row.get("last_edit") or {}
            if (prior.get("operation") == "TRANSFER_IMPORT" and prior.get("request_id") == body.request_id
                    and prior.get("request_digest") == request_digest and prior.get("input_version") == body.expected_version
                    and prior.get("input_digest") == body.reviewed_timeline_digest
                    and row["version"] == body.expected_version + 1 and prior.get("output_digest") == row["timeline_digest"]):
                self.owner._timeline_sources_current(nid, scope, row["timeline"], guard)
            else:
                if prior.get("request_id") == body.request_id or any(
                        (entry.get("last_edit") or {}).get("request_id") == body.request_id for entry in row["history"]):
                    raise ValueError("STUDIO_TIMELINE_EDIT_IDEMPOTENCY_CONFLICT")
                _, preview, _ = self._prepare(nid, scope, actor, tid, body, context, document, guard)
                self._review(body, preview)
                if len(row["history"]) >= 100 or row["version"] >= 2**53 - 1:
                    raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
                receipt = {"operation": "TRANSFER_IMPORT", "request_id": body.request_id, "request_digest": request_digest,
                    "input_version": row["version"], "input_digest": row["timeline_digest"], "output_digest": preview["timeline_digest"],
                    "preview_digest": preview["preview_digest"], "format": body.format, "transfer_input_digest": preview["input_digest"],
                    "loss_report_digest": digest(preview["loss_report"]), "acknowledge_losses": body.acknowledge_losses}
                change_row(row, actor, body.expected_version, lambda current: current.update(timeline=copy.deepcopy(preview["timeline"]),
                    timeline_digest=preview["timeline_digest"], last_edit=receipt))
                self.owner._capacity(document)
            result = self.owner._timeline_view(row, scope)
            guard()
        return result

    def attachment(self, nid, scope, actor, tid, value, guard):
        body = TimelineTransferDownload.model_validate(value)
        if body.direction != "EXPORT":
            raise ValueError("STUDIO_TRANSFER_EXPORT_REQUIRED")
        context = self.owner._base(nid, scope, actor, guard)
        with self.owner.timeline_inputs.phase(nid, scope, actor, guard) as document:
            _, preview, attachment = self._prepare(nid, scope, actor, tid, body, context, document, guard)
            self._review(body, preview)
            if not isinstance(attachment, bytes):
                raise ValueError("STUDIO_TRANSFER_ATTACHMENT_REQUIRED")
            guard()
            return attachment, preview["output_sha256"], body.format
