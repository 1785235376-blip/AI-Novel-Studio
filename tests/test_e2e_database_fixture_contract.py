from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from psycopg import sql


MODULE_PATH = Path(__file__).parent / "e2e" / "database_fixture.py"
SPEC = importlib.util.spec_from_file_location("e2e_database_fixture_contract", MODULE_PATH)
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fixture
SPEC.loader.exec_module(fixture)

SAFE_NAME = "ai_novel_studio_e2e_run_42"
SAFE_URL = f"postgresql+psycopg://e2e-user:TEST_ONLY_PASSWORD@127.0.0.1:5432/{SAFE_NAME}?sslmode=require"


class FakeConnection:
    def __init__(self, statements, row=None, fail_at=None):
        self.statements=statements;self.row=row;self.fail_at=fail_at
    def __enter__(self):return self
    def __exit__(self,*_args):return False
    def execute(self,statement,params=None):
        self.statements.append((statement,params))
        if self.fail_at is not None and len(self.statements)==self.fail_at:raise RuntimeError("TEST_ONLY_FAILURE")
        return self
    def fetchone(self):return self.row


def isolate(monkeypatch,tmp_path):
    monkeypatch.delenv("E2E_DATABASE_URL",raising=False)
    monkeypatch.delenv("E2E_DATABASE_CONFIRM_DROP",raising=False)
    monkeypatch.delenv("DATABASE_URL",raising=False)
    monkeypatch.setattr(fixture,"ROOT",tmp_path)


def configure(monkeypatch,url=SAFE_URL,confirm=SAFE_NAME):
    monkeypatch.setenv("E2E_DATABASE_URL",url)
    if confirm is not None:monkeypatch.setenv("E2E_DATABASE_CONFIRM_DROP",confirm)


def test_missing_explicit_url_never_reads_generic_or_dotenv(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);monkeypatch.setenv("DATABASE_URL",SAFE_URL)
    (tmp_path/".env").write_text(f"E2E_DATABASE_URL={SAFE_URL}",encoding="utf-8")
    monkeypatch.setattr(Path,"read_text",lambda *_a,**_k:pytest.fail("dotenv read attempted"))
    calls=[];monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:calls.append(1))
    with pytest.raises(fixture.E2EDatabaseContractError,match="^E2E_DATABASE_URL_REQUIRED$"):fixture.load_database_url()
    assert calls==[]


@pytest.mark.parametrize("url",[
    SAFE_URL,
    SAFE_URL.replace("postgresql+psycopg://","postgresql://"),
])
def test_supported_schemes_preserve_safe_query(monkeypatch,tmp_path,url):
    isolate(monkeypatch,tmp_path);configure(monkeypatch,url)
    target=fixture.load_database_url()
    assert target.database_name==SAFE_NAME
    assert target.target_url.startswith("postgresql://") and target.target_url.endswith("?sslmode=require")
    assert target.maintenance_url.endswith("/postgres?sslmode=require")


@pytest.mark.parametrize("url",[
    SAFE_URL.replace("postgresql+psycopg://","mysql://"),
    SAFE_URL.replace(SAFE_NAME,"ai_novel_studio_e2e"),
    SAFE_URL.replace(SAFE_NAME,"ai_novel_studio_e2e_Upper"),
    SAFE_URL.replace(SAFE_NAME,"wrong_run"),
    SAFE_URL.replace(SAFE_NAME,"ai_novel_studio_e2e_%2fescape"),
    SAFE_URL.replace(SAFE_NAME,"ai_novel_studio_e2e_"+"x"*43),
    SAFE_URL.replace(SAFE_NAME,SAFE_NAME+"/extra"),
])
def test_unsafe_urls_fail_before_connect_without_disclosure(monkeypatch,tmp_path,url):
    isolate(monkeypatch,tmp_path);configure(monkeypatch,url);calls=[]
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:calls.append(1))
    with pytest.raises(fixture.E2EDatabaseContractError) as raised:fixture.load_database_url()
    message=str(raised.value)
    assert calls==[] and url not in message and "TEST_ONLY_PASSWORD" not in message and "127.0.0.1" not in message


@pytest.mark.parametrize("confirmation",[None,"wrong_database"])
def test_confirmation_is_required_before_destructive_connection(monkeypatch,tmp_path,confirmation):
    isolate(monkeypatch,tmp_path);configure(monkeypatch,confirm=confirmation);calls=[]
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:calls.append(1))
    with pytest.raises(fixture.E2EDatabaseContractError):fixture.prepare()
    assert calls==[]


def test_prepare_uses_maintenance_then_target_and_safe_identifiers(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);configure(monkeypatch);connections=[];statements=[]
    def connect(url,**kwargs):connections.append((url,kwargs));return FakeConnection(statements)
    monkeypatch.setattr(fixture.psycopg,"connect",connect)
    fixture.prepare()
    assert len(connections)==2 and connections[0][0].endswith("/postgres?sslmode=require")
    assert connections[1][0].endswith(f"/{SAFE_NAME}?sslmode=require")
    composed=[statement for statement,_params in statements if isinstance(statement,sql.Composed)]
    assert len(composed)==2 and all("Identifier" in repr(statement) for statement in composed)
    assert any(params==(SAFE_NAME,) for _statement,params in statements)


def test_cleanup_drops_confirmed_database_and_propagates_failure(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);configure(monkeypatch);statements=[]
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:FakeConnection(statements,fail_at=2))
    with pytest.raises(RuntimeError,match="TEST_ONLY_FAILURE"):fixture.cleanup()
    assert len(statements)==2


def test_probe_needs_no_drop_confirmation_and_preserves_business_output(monkeypatch,tmp_path,capsys):
    isolate(monkeypatch,tmp_path);configure(monkeypatch,confirm=None);statements=[]
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:FakeConnection(statements,row=("novel",1,2,3,4,5)))
    fixture.probe("novel")
    assert capsys.readouterr().out.strip()=="novel|1|2|3|4|5"


def test_cli_has_no_url_action_and_redacts_database_failures(monkeypatch,tmp_path,capsys):
    isolate(monkeypatch,tmp_path);configure(monkeypatch)
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:(_ for _ in ()).throw(RuntimeError(SAFE_URL)))
    assert "url" not in fixture.CLI_ACTIONS
    assert fixture.main(["prepare"])==1
    captured=capsys.readouterr()
    assert captured.out=="" and captured.err.strip()=="E2E_DATABASE_PREPARE_FAILED"
    assert SAFE_URL not in captured.err and "TEST_ONLY_PASSWORD" not in captured.err


def test_cleanup_cli_failure_is_nonzero_and_redacted(monkeypatch,tmp_path,capsys):
    isolate(monkeypatch,tmp_path);configure(monkeypatch)
    monkeypatch.setattr(fixture.psycopg,"connect",lambda *_a,**_k:(_ for _ in ()).throw(RuntimeError(SAFE_URL)))
    assert fixture.main(["cleanup"])==1
    captured=capsys.readouterr()
    assert captured.out=="" and captured.err.strip()=="E2E_DATABASE_CLEANUP_FAILED"
    assert SAFE_URL not in captured.err and "TEST_ONLY_PASSWORD" not in captured.err
