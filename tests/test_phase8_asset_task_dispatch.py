from app.services.screenplay_service import ScreenplayService

class Repo:
    def __init__(self): self.rows=[{"id":"sp","asset_tasks":[{"id":"a","status":"PENDING","provider_id":"p","model_id":"m","attempts":0,"history":[]}]}]
    def list_screenplays(self,n): return self.rows
    def save_screenplay(self,n,row): self.rows=[row]; return row

def test_dispatch_defaults_to_dry_run_without_provider_call():
    repo=Repo(); result=ScreenplayService(repo, object()).dispatch_asset_tasks("n")
    assert result["dry_run"] is True and result["count"] == 1
    assert repo.rows[0]["asset_tasks"][0]["status"] == "RUNNING"
