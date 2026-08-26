from app.services.screenplay_service import ScreenplayService


class Novels:
    def list_screenplays(self, novel_id):
        return [{"id": "sp", "asset_tasks": [
            {"status": "PENDING", "history": [{"at": "2026-01-01T00:00:00+00:00"}]},
            {"status": "FAILED", "history": [{"at": "2026-01-02T00:00:00+00:00"}]},
            {"status": "SUCCEEDED", "history": [{"at": "2026-01-03T00:00:00+00:00"}]},
        ]}]


def test_asset_task_stats_counts_statuses_and_latest():
    stats = ScreenplayService(Novels(), object()).asset_task_stats("n")
    assert stats["total"] == 3
    assert stats["by_status"]["PENDING"] == 1
    assert stats["by_status"]["FAILED"] == 1
    assert stats["latest_at"].startswith("2026-01-03")
