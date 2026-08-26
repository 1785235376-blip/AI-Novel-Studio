from __future__ import annotations

import logging

from ..config import settings
from ..lore.continuity import CharacterKnowledge, CharacterLocationState, TimelineEvent
from ..lore.continuity_engine import ContinuityRuleContext, registry

logger = logging.getLogger(__name__)


class ContinuityFindingService:
    """Runs advisory deterministic checks without changing authoritative state."""

    def __init__(self, repository, enabled: bool | None = None):
        self.repository = repository
        self.enabled = settings.enable_continuity_rules if enabled is None else enabled

    def run_checks(self, project_id: str, *, events=None, locations=None, relationships=None, knowledge=None, used_subject_ids=None, travel_times=None, canon_facts=None, asserted_facts=None, evidence_required_subjects=None, evidence_present_subjects=None):
        if not self.enabled:
            return []
        try:
            findings = registry.evaluate(ContinuityRuleContext(project_id=project_id,events=[e for e in (events or []) if e.project_id == project_id],locations=[s for s in (locations or []) if s.project_id == project_id],relationships=[r for r in (relationships or []) if r.project_id == project_id],knowledge=[k for k in (knowledge or []) if k.project_id == project_id],used_subject_ids=used_subject_ids or set(),travel_times=travel_times or {},canon_facts=canon_facts or {},asserted_facts=asserted_facts or {},evidence_required_subjects=evidence_required_subjects or set(),evidence_present_subjects=evidence_present_subjects or set()))
            for finding in findings:
                stored=self.repository.create("findings", finding.model_dump(mode="json"))
                if stored.get("status")=="RESOLVED": self.repository.set_finding_status(finding.id,"OPEN")
            return findings
        except Exception:
            logger.exception("CONTINUITY_CHECK failed for project %s", project_id)
            return []

    def get_finding(self, finding_id: str):
        return self.repository.get_by_id("findings", finding_id)

    def list_findings(self, project_id: str):
        return self.repository.list_by_project("findings", project_id)

    def resolve(self, project_id: str, finding_id: str):
        finding=self.get_finding(finding_id)
        if finding.get("project_id")!=project_id: raise KeyError(finding_id)
        return self.repository.set_finding_status(finding_id,"RESOLVED")
