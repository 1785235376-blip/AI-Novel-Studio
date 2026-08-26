import json
from pathlib import Path
from app.context import build_context
from app.privacy import cloud_safe_context
from app.review import deterministic_review
from app.router import ModelRouter,Route
from app.providers import LLMProvider,Generation,ProviderError
from app.storage import atomic_write

ROOT=Path(__file__).parents[1]/"novel_data"

def test_context_selects_relevant_characters():
    ctx=build_context(ROOT,"sample_novel",3,"林海在旧港遇到沈船长",False)
    assert {x["name"] for x in ctx["characters"]}=={"林海","沈船长"}

def test_cloud_privacy_omits_and_redacts():
    ctx=build_context(ROOT,"sample_novel",3,"林海遇见船长",True)
    encoded=json.dumps(ctx,ensure_ascii=False)
    assert "沈船长就是" not in encoded
    assert "调换了事故航海日志" not in encoded
    assert "captain-identity" in ctx["privacy_omissions"]

def test_age_dead_and_secret_review():
    ctx=build_context(ROOT,"sample_novel",3,"林海与周启",False)
    ctx["characters"].append({"name":"周启","status":"DEAD","age":51})
    issues=deterministic_review("林海已经29岁。周启走进门。沈船长就是旧港事故中失踪的引航员之子。",ctx)
    assert {x["code"] for x in issues} >= {"CANON_CONFLICT","DEAD_CHARACTER","SECRET_LEAK"}

def test_missing_character_behavior_review():
    issues = deterministic_review("周启走进门，拿起武器。", {"characters": [{"name": "周启", "status": "MISSING"}], "chapter": 4})
    assert any(item["code"] == "MISSING_CHARACTER" for item in issues)

class Fail(LLMProvider):
    name="cloud"
    def generate(self,*a,**k): raise ProviderError("offline")
    def health_check(self): return False
class Local(LLMProvider):
    name="local"
    def generate(self,prompt,model,**k): return Generation("ok",self.name,model)
    def health_check(self): return True

def test_fallback_chain():
    router=ModelRouter({"cloud":Fail(),"local":Local()},{"writer":[Route("cloud","x"),Route("local","y")]})
    assert router.generate("writer","hello").provider=="local"

def test_atomic_write(tmp_path):
    target=tmp_path/"chapter.md"; atomic_write(target,"正文"); assert target.read_text(encoding="utf-8")=="正文"
