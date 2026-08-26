from app.services.screenplay_service import ScreenplayService

class Novels:
    def __init__(self): self.rows=[{"id":"sp","asset_tasks":[{"id":"a","status":"PENDING","provider_id":"p","attempts":0,"history":[]},{"id":"b","status":"PENDING","provider_id":"q","attempts":0,"history":[]}]}]
    def list_screenplays(self,n): return self.rows
    def save_screenplay(self,n,row): self.rows=[row]; return row

def test_claim_is_bounded_and_filters_provider():
    repo=Novels(); result=ScreenplayService(repo, object()).claim_asset_tasks("n", limit=1, provider_id="p")
    assert result["count"] == 1
    task=repo.rows[0]["asset_tasks"][0]
    assert task["status"] == "RUNNING" and task["attempts"] == 1
    assert repo.rows[0]["asset_tasks"][1]["status"] == "PENDING"
