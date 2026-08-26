from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.runtime_identity import RuntimeRole
from app.document import document_to_markdown


APPLICATION = Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-envfix-bcard-20260818\Application")


def request(
    origin: str,
    method: str,
    path: str,
    token: str | None = None,
    body=None,
    extra_headers: dict[str, str] | None = None,
):
    headers = {"Accept": "application/json", "Origin": origin}
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if token:
        headers["X-Session-Token"] = token
    req = urllib.request.Request(origin + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
            value = json.loads(raw) if raw else None
            return response.status, value
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        value = json.loads(raw) if raw else None
        return exc.code, value


def record(results: list[dict], method: str, origin: str, path: str, request_body, status: int, response):
    results.append({
        "method": method,
        "url": origin + path,
        "request": request_body,
        "status": status,
        "response": response,
    })


def checked(results, origin, method, path, expected, token=None, body=None):
    status, response = request(origin, method, path, token, body)
    record(results, method, origin, path, body, status, response)
    if status != expected:
        raise RuntimeError(f"{method} {path}: expected {expected}, got {status}: {response}")
    return response


def main() -> int:
    runtime = None
    results: list[dict] = []
    try:
        runtime, factory = create_packaged_backend_runtime(application=APPLICATION)
        identity = runtime.startup()
        database_port = runtime.reservations.ports[RuntimeRole.POSTGRESQL]
        backend_port = runtime.reservations.ports[RuntimeRole.BACKEND]
        origin = f"http://127.0.0.1:{backend_port}"

        checked(results, origin, "GET", "/health", 200)
        checked(results, origin, "GET", "/api/health", 200)
        checked(results, origin, "GET", "/openapi.json", 501)

        secret = factory.take_bootstrap_secret()
        receipt = checked(results, origin, "POST", "/api/packaged/bootstrap", 200, body={
            "bootstrap_secret": secret,
            "runtime_instance_id": identity.runtime_instance_id,
        })
        token = receipt["session_token"]
        workspace = checked(results, origin, "POST", "/api/packaged/initial-workspace", 200, token, {})
        workspace_id = workspace["id"]

        marker = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        title = f"RC API Smoke {marker}"
        project = checked(results, origin, "POST", f"/api/collaboration/admin/workspaces/{workspace_id}/projects", 201, token, {"title": title, "genre": "verification"})
        project_id = project["id"]
        projects = checked(results, origin, "GET", f"/api/collaboration/admin/workspaces/{workspace_id}/projects", 200, token)
        if not any(row["id"] == project_id and row["title"] == title for row in projects):
            raise RuntimeError("created project missing from project list")

        storyline = checked(results, origin, "POST", f"/api/collaboration/admin/workspaces/{workspace_id}/projects/{project_id}/storylines", 201, token, {"name": "RC Storyline"})
        branch = checked(results, origin, "POST", f"/api/collaboration/admin/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline['id']}/branches", 201, token, {"name": "RC Main"})
        navigation = checked(results, origin, "GET", f"/api/collaboration/admin/workspaces/{workspace_id}/navigation", 200, token)
        if not any(row["project_id"] == project_id for row in navigation["eligible_paths"]):
            raise RuntimeError("created project missing from navigation detail")

        scope = f"/api/collaboration/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline['id']}/branches/{branch['id']}"
        chapter = checked(results, origin, "POST", scope + "/chapters", 201, token, {"title": "RC API Chapter"})
        chapter_id = chapter["id"]
        chapters = checked(results, origin, "GET", scope + "/chapters", 200, token)
        if not any(row["id"] == chapter_id for row in chapters["items"]):
            raise RuntimeError("created chapter missing from chapter list")

        headers_path = f"/api/chapters/{chapter_id}"
        status, current = request(
            origin,
            "GET",
            headers_path,
            token,
            extra_headers={"X-Branch-Id": branch["id"]},
        )
        record(results, "GET", origin, headers_path, None, status, current)
        if status != 200:
            raise RuntimeError(f"chapter detail failed: {status}: {current}")
        document = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "RC API persisted content"}]}]}
        status, updated = request(
            origin,
            "PUT",
            headers_path,
            token,
            {
                "content": "RC API persisted content",
                "document": document,
                "version": current["version"],
                "source": "MANUAL_SAVE",
            },
            extra_headers={"X-Branch-Id": branch["id"]},
        )
        record(results, "PUT", origin, headers_path, {"content": "RC API persisted content", "document": document, "version": current["version"], "source": "MANUAL_SAVE"}, status, updated)
        if status != 200 or updated["version"] <= current["version"]:
            raise RuntimeError(f"chapter update failed: {status}: {updated}")

        revisions = checked(results, origin, "GET", scope + f"/chapters/{chapter_id}/revisions", 200, token)
        if revisions["current_version"] != updated["version"] or not revisions["items"]:
            raise RuntimeError("saved revision not visible")

        dsn = f"postgresql://novel_studio@127.0.0.1:{database_port}/ai_novel_studio"
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id, slug, title, updated_at FROM novels WHERE slug = %s", (project_id,))
            project_row = cursor.fetchone()
            chapter_number = int(chapter_id.rsplit(":", 1)[-1])
            cursor.execute(
                "SELECT c.id, n.slug, c.title, c.version, c.document, c.updated_at "
                "FROM chapters c JOIN novels n ON n.id = c.novel_id "
                "WHERE n.slug = %s AND c.chapter_number = %s",
                (project_id, chapter_number),
            )
            chapter_row = cursor.fetchone()
            cursor.execute(
                "SELECT count(*) FROM chapter_versions WHERE chapter_id = %s",
                (chapter_row[0],) if chapter_row else (None,),
            )
            revision_count = cursor.fetchone()[0]
        if not project_row or project_row[2] != title:
            raise RuntimeError("project row missing from PostgreSQL")
        chapter_content = document_to_markdown(chapter_row[4] or {"type": "doc", "content": []}) if chapter_row else ""
        if not chapter_row or chapter_row[1] != project_id or "RC API persisted content" not in chapter_content:
            raise RuntimeError("chapter row missing or stale in PostgreSQL")
        if chapter_row[3] != updated["version"] or revision_count < 1:
            raise RuntimeError("chapter version persistence mismatch")

        report = {
            "runtime": {"backend_origin": origin, "backend_port": backend_port, "database_port": database_port, "application_version": "0.7.0"},
            "test_ids": {"workspace_id": workspace_id, "project_id": project_id, "chapter_id": chapter_id},
            "database": {
                "project": {"id": str(project_row[0]), "slug": project_row[1], "title": project_row[2], "updated_at": project_row[3].isoformat()},
                "chapter": {"id": str(chapter_row[0]), "project_id": chapter_row[1], "title": chapter_row[2], "version": chapter_row[3], "content": chapter_content, "document": chapter_row[4], "updated_at": chapter_row[5].isoformat()},
                "revision_count": revision_count,
            },
            "requests": [row for row in results if "/packaged/bootstrap" not in row["url"]],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        if runtime is not None:
            runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
