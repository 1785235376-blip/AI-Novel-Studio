from datetime import datetime, timezone, timedelta
from app.services.screenplay_service import ScreenplayService

class Repo:
    def __init__(self, stamp): self.rows=[{"id":"sp","asset_tasks":[{"id":"a","status":"RUNNING","attempts":1,"history":[{"status":"RUNNING","at":stamp}]}]}]
    def list_screenplays(self,n): return self.rows
    def save_screenplay(self,n,row): self.rows=[row]; return row

def test_timeout_marks_old_running_task_failed():
    stamp=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    repo=Repo(stamp); result=ScreenplayService(repo, object()).timeout_asset_tasks("n", 60)
    assert result["timed_out"] == 1
    assert repo.rows[0]["asset_tasks"][0]["status"] == "FAILED"
