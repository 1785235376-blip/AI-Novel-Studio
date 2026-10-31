"""Independent regression coverage for CSV spreadsheet-formula neutralisation.

CSV quoting alone keeps delimiters inside one cell but does not stop Excel,
LibreOffice or Google Sheets from evaluating text that begins with a formula
sigil. The Creative Director/Storyboard sheets already neutralised those cells;
this suite binds the same policy to every other product CSV writer and keeps the
visible text unchanged for ordinary content.

The fixtures use synthetic text only. No real project data, credential or
network target is involved.
"""
from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.csv_safety import csv_safe_cell, neutralize_formula


# ---------------------------------------------------------------------------
# 1. Shared policy
# ---------------------------------------------------------------------------

DANGEROUS_CELLS = (
    "=1+1",
    "+42",
    "-1",
    "@SUM(A1:A2)",
    " =1+1",
    "\u200b=1+1",
    "\t=1+1",
    "\ufeff=1+1",
    "＝1+1",
    "＋1",
    "－1",
    "＠cmd",
)

BENIGN_CELLS = (
    "Chapter 1",
    "a=b",
    "2-3",
    "x@y",
    "",
    "正文：他说 = 好的",
)


@pytest.mark.parametrize("text", DANGEROUS_CELLS)
def test_formula_cells_are_neutralised(text):
    assert neutralize_formula(text) == "'" + text


@pytest.mark.parametrize("text", BENIGN_CELLS)
def test_ordinary_text_is_unchanged(text):
    assert neutralize_formula(text) == text


def test_csv_safe_cell_converts_scalars_like_the_csv_module():
    assert csv_safe_cell(None) == ""
    assert csv_safe_cell(42) == "42"
    assert csv_safe_cell(-1) == "'-1"


def test_creative_sheet_policy_is_shared_not_forked():
    from app.creative.director_sheet_export import cell

    assert cell("=CMD|'/C calc'!A0") == "'=CMD|'/C calc'!A0"
    with pytest.raises(ValueError):
        cell("bad\x00text")


# ---------------------------------------------------------------------------
# 2. Industry shot-list CSV (author-controlled screenplay text)
# ---------------------------------------------------------------------------

def _screenplay() -> dict:
    return {
        "title": "Synthetic",
        "scenes": [{"id": "s1", "heading": "内景 房间 日", "location": "房间", "time": "日", "action": "=1+1"}],
        "shots": [{
            "id": "shot1", "number": 1, "scene_id": "s1",
            "action": "=cmd|' /C calc'!A0", "sound_effect": "@SUM(A1)",
            "notes": "-2+3", "duration_seconds": 5,
        }],
    }


def test_industry_shot_list_csv_neutralises_author_text():
    from app.industry_export_formats import shot_list_to_csv

    content = shot_list_to_csv(_screenplay()).decode("utf-8-sig")
    assert "'=cmd|' /C calc'!A0" in content
    assert "'@SUM(A1)" in content
    assert "'-2+3" in content


def test_industry_shot_list_csv_keeps_ordinary_text_readable():
    from app.industry_export_formats import shot_list_to_csv

    screenplay = _screenplay()
    screenplay["shots"][0]["action"] = "推门进入房间"
    content = shot_list_to_csv(screenplay).decode("utf-8-sig")
    assert "推门进入房间" in content
    assert "'推门进入房间" not in content


# ---------------------------------------------------------------------------
# 3. NovelService shot-list export
# ---------------------------------------------------------------------------

def _snapshot_with_screenplay() -> dict:
    return {
        "source": {
            "novel": {"title": "Synthetic"},
            "chapters": [],
            "screenplays": [_screenplay()],
        }
    }


def test_novel_service_shot_list_export_neutralises_author_text():
    from app.services.novel_service import NovelService

    result = NovelService(novels=None, chapters=None).export(
        "synthetic-project", "shot-list", snapshot=_snapshot_with_screenplay()
    )
    assert result["format"] == "shot-list"
    assert "'=cmd|' /C calc'!A0" in result["content"]


# ---------------------------------------------------------------------------
# 4. Agent job CSV (provider/model config strings and ids)
# ---------------------------------------------------------------------------

class _FakeAgentJobs:
    def list(self, *args, **kwargs):
        return {"items": [{
            "id": "=job",
            "agent_id": "+agent",
            "agent_name": "@name",
            "novel_id": "novel-1",
            "status": "COMPLETED",
            "execution_mode": "model",
            "provider": "-provider",
            "model": "=model",
            "created_at": "2026-10-30T00:00:00Z",
            "updated_at": "2026-10-30T00:00:00Z",
            "error_code": "",
            "retry_of": "job-0",
        }]}


def test_agent_job_export_csv_neutralises_controlled_values():
    from app.services.agent_job_service import AgentJobService

    service = AgentJobService(None, None, None)
    service.list = _FakeAgentJobs().list  # type: ignore[method-assign]
    content = service.export_csv()
    assert "'=job" in content
    assert "'+agent" in content
    assert "'@name" in content
    assert "'-provider" in content
    assert "'=model" in content
    assert "novel-1" in content


# ---------------------------------------------------------------------------
# 5. Harness access-audit CSV
# ---------------------------------------------------------------------------

def test_harness_access_audit_csv_neutralises_recorded_metadata(monkeypatch):
    from app import api
    from app.services import harness_access_audit_service as audit_module

    monkeypatch.setattr(audit_module.harness_access_audit_service, "list", lambda *args, **kwargs: [{
        "at": "2026-10-30T00:00:00Z",
        "novel_id": "=novel",
        "chapter": "@2",
        "agent_id": "+agent",
        "scopes": ["=scope"],
        "outcome": "-outcome",
    }])
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    response = TestClient(application).get("/api/harness/access-audit.csv")
    assert response.status_code == 200
    assert "'=novel" in response.text
    assert "'@2" in response.text
    assert "'+agent" in response.text
    assert "'=scope" in response.text
    assert "'-outcome" in response.text


# ---------------------------------------------------------------------------
# 6. Agent-job audit CSV
# ---------------------------------------------------------------------------

def test_agent_job_audit_csv_neutralises_actor_and_target(monkeypatch):
    from app import api

    monkeypatch.setattr(api, "agent_job_audit", lambda *args, **kwargs: {"items": [{
        "id": "=audit",
        "actor_id": "@actor",
        "action": "AGENT_JOB_EXPORT",
        "target_type": "AgentJobExport",
        "target_id": "+target",
        "timestamp": "2026-10-30T00:00:00Z",
        "metadata": {"result_count": 1, "filters": {"novel_id": "novel-1"}},
    }]})
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    response = TestClient(application).get("/api/agent-jobs/audit.csv?novel_id=novel-1&branch_id=branch-1")
    assert response.status_code == 200
    assert "'=audit" in response.text
    assert "'@actor" in response.text
    assert "'+target" in response.text
