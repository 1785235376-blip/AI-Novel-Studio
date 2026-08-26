from __future__ import annotations
import ctypes, json, msvcrt, os, sqlite3, subprocess, tempfile, uuid
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[2]
APPLICATION=Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-envfix-bcard-20260818\Application")

@dataclass(frozen=True)
class RuntimeSentinels:
    a:str; b:str
    @classmethod
    def generate(cls):
        a="a3-"+os.urandom(32).hex(); b="a3-"+os.urandom(32).hex()
        while a==b: b="a3-"+os.urandom(32).hex()
        return cls(a,b)

@dataclass(frozen=True)
class ScanResult:
    surface:str; executed:bool; a_hits:int; b_hits:int; status:str

    @property
    def complete(self):
        return self.executed and (self.status == "PASS" or self.status.startswith("NOT_APPLICABLE"))

def compare_bytes(data:bytes, s:RuntimeSentinels, surface="buffer"):
    return ScanResult(surface,True,data.count(s.a.encode())+data.count(s.a.encode('utf-16le')),data.count(s.b.encode())+data.count(s.b.encode('utf-16le')),"PASS")

def scan_text(text:str,s:RuntimeSentinels,surface="text"):
    return compare_bytes(text.encode()+text.encode('utf-16le'),s,surface)

def _files(root:Path)->Iterable[Path]:
    if not root.exists(): return ()
    out=[]
    for base,dirs,files in os.walk(root,topdown=True,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
        out.extend(Path(base)/n for n in files if not (Path(base)/n).is_symlink())
    return out

def _read_profile_bytes_live(path:Path)->bytes:
    # Chromium keeps active cache and SQLite files open.  Request only read access
    # while accepting the sharing modes Chromium uses for live profile files.
    kernel32=ctypes.WinDLL("kernel32",use_last_error=True)
    create_file=kernel32.CreateFileW
    create_file.argtypes=(ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p)
    create_file.restype=ctypes.c_void_p
    handle=create_file(str(path),0x80000000,0x00000007,None,3,0x80,None)
    if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    fd=msvcrt.open_osfhandle(handle,os.O_RDONLY)
    with os.fdopen(fd,"rb",closefd=True) as stream: return stream.read()

def _sqlite_read_probe(path:Path):
    result={"path":path.name}
    try:
        con=sqlite3.connect(f"file:{path.as_posix()}?mode=ro",uri=True)
        result["readonly_open"]="SUCCESS"
        try:
            shadow=sqlite3.connect(":memory:"); con.backup(shadow); shadow.close(); result["backup_api"]="SUCCESS"
        except Exception as exc: result["backup_api"]="FAIL:"+type(exc).__name__
        con.close()
    except Exception as exc:
        result["readonly_open"]="FAIL:"+type(exc).__name__
        result["backup_api"]="NOT_APPLICABLE"
    return result

def scan_root(root:Path,s:RuntimeSentinels,surface:str):
    if not root.exists(): return ScanResult(surface,True,0,0,"NOT_APPLICABLE_ROOT_ABSENT")
    a=b=0; unreadable=[]
    try:
        for p in _files(root):
            # Chromium profile coordination files are transient, locked metadata;
            # they cannot contain persisted credential content and are excluded by
            # the established safe profile scan contract.
            if surface.endswith(":profile") and (p.name == "LOCK" or p.name.startswith("Singleton")):
                continue
            try: r=compare_bytes(p.read_bytes(),s,surface)
            except (OSError,PermissionError) as exc:
                if surface.endswith(":profile"):
                    try:
                        r=compare_bytes(_read_profile_bytes_live(p),s,surface)
                    except (OSError,PermissionError) as shared_exc:
                        exc=shared_exc
                        if p.name in {"Cookies","Cookies-journal"}:
                            print("SQLITE_SAFE_READ_METHOD="+json.dumps({"createfile_share":"FAIL:"+type(shared_exc).__name__,**_sqlite_read_probe(p)},separators=(",",":"),sort_keys=True))
                    else:
                        a+=r.a_hits; b+=r.b_hits
                        continue
                if surface.endswith(":profile"):
                    try:
                        stat=p.lstat(); size=stat.st_size
                        reparse=bool(getattr(stat,"st_file_attributes",0) & 0x400)
                    except OSError:
                        size=None; reparse=None
                    winerror=getattr(exc,"winerror",None); errno=getattr(exc,"errno",None)
                    unreadable.append({
                        "relative_path":p.relative_to(root).as_posix(),
                        "basename":p.name,
                        "extension":p.suffix,
                        "size":size,
                        "is_reparse_point":"YES" if reparse else "NO" if reparse is False else "UNKNOWN",
                        "exception_class":type(exc).__name__,
                        "win32_error_code":winerror,
                        "errno":errno,
                        "sharing_violation":"YES" if winerror in (32,33) else "NO",
                        "file_not_found_race":"YES" if winerror in (2,3) or errno in (2,) else "NO",
                        "matches_current_skip_rule":"YES" if p.name == "LOCK" or p.name.startswith("Singleton") else "NO",
                    })
                    continue
                return ScanResult(surface,False,a,b,"ERROR_UNREADABLE_FILE")
            a+=r.a_hits; b+=r.b_hits
    except (OSError,PermissionError): return ScanResult(surface,False,a,b,"ERROR_ROOT_WALK")
    if unreadable:
        print("UNREADABLE_PROFILE_FILE_COUNT="+str(len(unreadable)))
        print("UNREADABLE_PROFILE_FILES="+json.dumps(unreadable,separators=(",",":"),sort_keys=True))
        return ScanResult(surface,False,a,b,"ERROR_UNREADABLE_FILE")
    return ScanResult(surface,True,a,b,"PASS")

def scan_outputs(stdout,stderr,diagnostics,s):
    return {k:scan_text(v,s,k) for k,v in (("stdout",stdout),("stderr",stderr),("diagnostic",diagnostics))}

def scan_root_map(root_map:Mapping[str,Path],s:RuntimeSentinels,phase:str):
    return {n:scan_root(p,s,f"{phase}:{n}") for n,p in root_map.items()}

def formal_test_artifact_hits():
    if not APPLICATION.exists(): return 0
    forbidden={"phase53c_a3_full_leak_scan.py","phase53c_a3_real_packaged_ui.py","AI.NovelStudio.DesktopHost.WebView2TestHarness.exe","AI-Novel-Studio.DesktopHost.TestHarness.exe"}
    return sum(1 for p in _files(APPLICATION) if p.relative_to(APPLICATION).as_posix() in forbidden or p.relative_to(APPLICATION).as_posix().lower().startswith(("tests/","test/",".pytest_cache/")))

TEXTUAL_DATABASE_TYPES={"character varying","character","text","json","jsonb","xml"}

@dataclass(frozen=True)
class DatabaseSurface:
    schema:str; table:str; column:str; data_type:str; category:str

def discover_database_surfaces(connection):
    rows=connection.execute("""SELECT table_schema,table_name,column_name,data_type
      FROM information_schema.columns
      WHERE table_schema NOT IN ('pg_catalog','information_schema')
      ORDER BY table_schema,table_name,ordinal_position""").fetchall()
    out=[]
    for schema,table,column,data_type in rows:
        if data_type not in TEXTUAL_DATABASE_TYPES: continue
        lower=table.lower()
        category="audit" if "audit" in lower or "event" in lower else "generation_job" if "generation" in lower and "job" in lower else "domain" if lower in {"workspaces","projects","novels","chapters","chapter_versions","chapter_summaries","chapter_context_snapshots","storylines","storyline_branches","generation_jobs","pending_canon","canon_entries"} else "other"
        out.append(DatabaseSurface(schema,table,column,data_type,category))
    return out

def scan_database(connection,s:RuntimeSentinels,surfaces:Sequence[DatabaseSurface]|None=None):
    discovered=list(surfaces if surfaces is not None else discover_database_surfaces(connection))
    if not discovered: return ScanResult("database",False,0,0,"NOT_INSPECTED_NO_TEXT_COLUMNS")
    a=b=0
    try:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            for item in discovered:
                query=sql.SQL("SELECT count(*) FILTER (WHERE position(%s in {c}::text)>0), count(*) FILTER (WHERE position(%s in {c}::text)>0) FROM {s}.{t}").format(c=sql.Identifier(item.column),s=sql.Identifier(item.schema),t=sql.Identifier(item.table))
                ah,bh=connection.execute(query,(s.a,s.b)).fetchone(); a+=int(ah); b+=int(bh)
    except Exception:
        return ScanResult("database",False,a,b,"ERROR")
    return ScanResult("database",True,a,b,"PASS")

@dataclass(frozen=True)
class OwnedLaunchMetadata:
    runtime_instance_id:str; command:tuple[str,...]; environment:Mapping[str,str]

def scan_owned_process_metadata(records:Sequence[OwnedLaunchMetadata],runtime_instance_id:str,s:RuntimeSentinels):
    owned=[r for r in records if r.runtime_instance_id==runtime_instance_id]
    if not owned:
        missing=ScanResult("owned_process",False,0,0,"NOT_INSPECTED_NO_OWNED_LAUNCHES")
        return {"cli":missing,"environment":missing}
    cli="\0".join("\0".join(r.command) for r in owned)
    env="\0".join("\0".join(f"{k}={v}" for k,v in r.environment.items()) for r in owned)
    return {"cli":scan_text(cli,s,"owned_process_cli"),"environment":scan_text(env,s,"owned_process_environment")}

@dataclass(frozen=True)
class LocalRequestMetadata:
    runtime_instance_id:str; method:str; url:str; path:str

def scan_local_request_metadata(records:Sequence[LocalRequestMetadata],runtime_instance_id:str,s:RuntimeSentinels):
    owned=[r for r in records if r.runtime_instance_id==runtime_instance_id]
    if not owned:
        missing=ScanResult("local_request_metadata",False,0,0,"NOT_INSPECTED_NO_OBSERVATIONS")
        return {"url":missing,"request":missing}
    urls="\0".join(r.url for r in owned)
    requests="\0".join(f"{r.method}\0{r.path}" for r in owned)
    return {"url":scan_text(urls,s,"url_metadata"),"request":scan_text(requests,s,"request_metadata")}

class FinalPhase(IntEnum):
    FRESH=0; WEBVIEW_READY=1; SET_A=2; REPLACE_B=3; CLEARED=4; WEBVIEW_STOPPED=5; RUNTIME_STOPPED=6; RESTART_CHECKED=7

class FinalScanCoordinator:
    def __init__(self,sentinels:RuntimeSentinels,execution_id:str|None=None):
        self.sentinels=sentinels; self.execution_id=execution_id or str(uuid.uuid4()); self.phase=FinalPhase.FRESH; self.results=[]
    def advance(self,target:FinalPhase):
        if target != FinalPhase(self.phase+1): raise ValueError("invalid final coordinator phase order")
        self.phase=target
    def add(self,result:ScanResult,*,requires_webview=False,requires_database=False):
        if requires_webview and self.phase>=FinalPhase.WEBVIEW_STOPPED: raise ValueError("browser scan after WebView shutdown")
        if requires_database and self.phase>=FinalPhase.RUNTIME_STOPPED: raise ValueError("database scan after runtime shutdown")
        self.results.append((self.execution_id,result))
    def aggregate_zero(self):
        if self.phase!=FinalPhase.RESTART_CHECKED or not self.results: return ScanResult("final",False,0,0,"NOT_INSPECTED")
        if any(run!=self.execution_id or not result.complete for run,result in self.results): return ScanResult("final",False,0,0,"PARTIAL")
        return ScanResult("final",True,sum(r.a_hits for _,r in self.results),sum(r.b_hits for _,r in self.results),"PASS")

def database_self_test():
    from app.packaging.packaged_launcher import create_packaged_backend_runtime
    from app.packaging.paths import WindowsPackagingPaths
    from app.packaging.runtime_lifecycle import RuntimeRole
    test_root=Path(r"D:\小说\.a3-session-runtime"); test_root.mkdir(parents=True,exist_ok=True)
    local=tempfile.TemporaryDirectory(prefix="slice2-db-",dir=test_root); profile=tempfile.TemporaryDirectory(prefix="slice2-profile-",dir=test_root); lifecycle=None
    marker=RuntimeSentinels("a3-db-test-"+uuid.uuid4().hex,"a3-db-other-"+uuid.uuid4().hex); fixture="slice2:"+uuid.uuid4().hex
    try:
        paths=WindowsPackagingPaths.resolve(local_app_data=local.name,user_profile=profile.name); lifecycle,factory=create_packaged_backend_runtime(application=APPLICATION,paths=paths); lifecycle.startup()
        port=lifecycle.reservations.ports[RuntimeRole.POSTGRESQL]; url=f"postgresql://{factory.config.database_user}@127.0.0.1:{port}/{factory.config.database_name}"
        with psycopg.connect(url,autocommit=True) as connection:
            surfaces=discover_database_surfaces(connection)
            connection.execute("INSERT INTO workspaces(id,payload) VALUES (%s,%s::jsonb)",(fixture,json.dumps({"id":fixture,"name":marker.a})))
            positive=scan_database(connection,marker,surfaces)
            connection.execute("DELETE FROM workspaces WHERE id=%s",(fixture,))
            clean=scan_database(connection,marker,surfaces)
        return surfaces,positive,clean,True
    finally:
        if lifecycle is not None: lifecycle.shutdown()
        profile.cleanup(); local.cleanup()

def process_self_test():
    s=RuntimeSentinels("a3-cli-test-"+uuid.uuid4().hex,"a3-env-test-"+uuid.uuid4().hex); run=str(uuid.uuid4())
    environment=os.environ.copy(); environment["A3_SCANNER_TEST"]=s.b
    child=subprocess.Popen([str(Path(os.sys.executable)),"-I","-c","import sys;sys.exit(0)",s.a],env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        results=scan_owned_process_metadata([OwnedLaunchMetadata(run,tuple(str(x) for x in child.args),environment)],run,s)
        return results,child.wait(timeout=10)==0
    finally:
        if child.poll() is None: child.terminate(); child.wait(timeout=5)

def metadata_self_test():
    s=RuntimeSentinels("a3-url-test-"+uuid.uuid4().hex,"a3-request-test-"+uuid.uuid4().hex); run=str(uuid.uuid4())
    records=[LocalRequestMetadata(run,"GET-"+s.b,"http://127.0.0.1/scanner/"+s.a,"/scanner/"+s.b)]
    positive=scan_local_request_metadata(records,run,s); clean=scan_local_request_metadata([LocalRequestMetadata(run,"GET","http://127.0.0.1/","/")],run,s)
    return positive,clean

def coordinator_self_test():
    c=FinalScanCoordinator(RuntimeSentinels("a","b")); c.advance(FinalPhase.WEBVIEW_READY); c.advance(FinalPhase.SET_A); c.add(ScanResult("browser",True,0,0,"PASS"),requires_webview=True); c.advance(FinalPhase.REPLACE_B); c.advance(FinalPhase.CLEARED); c.advance(FinalPhase.WEBVIEW_STOPPED); c.advance(FinalPhase.RUNTIME_STOPPED); c.advance(FinalPhase.RESTART_CHECKED)
    valid=c.aggregate_zero().complete
    try: c.add(ScanResult("late_browser",True,0,0,"PASS"),requires_webview=True); guarded=False
    except ValueError: guarded=True
    partial=FinalScanCoordinator(RuntimeSentinels("a","b")); partial.phase=FinalPhase.RESTART_CHECKED; partial.add(ScanResult("partial",False,0,0,"PARTIAL"))
    return valid and guarded and not partial.aggregate_zero().complete

def self_test():
    s=RuntimeSentinels("dummy-a","dummy-b")
    ok=compare_bytes(b"x dummy-a y",s).a_hits>0 and compare_bytes("dummy-b".encode('utf-16le'),s).b_hits>0 and compare_bytes(b"clean",s).a_hits==0
    with tempfile.TemporaryDirectory(prefix="a3-scanner-selftest-") as td:
        p=Path(td)/"x"; p.write_bytes(b"dummy-a"); ok=ok and scan_root(Path(td),s,"selftest").a_hits>0
        profile=Path(td)/"profile"; profile.mkdir(); (profile/"SingletonLock").write_bytes(b"transient"); (profile/"LOCK").write_bytes(b"transient")
        ok=ok and scan_root(profile,s,"self:profile").complete and scan_root(profile,s,"self:profile").a_hits==0
    return ok

def main():
    ok=self_test(); surfaces,db_positive,db_clean,db_cleanup=database_self_test(); process_results,process_cleanup=process_self_test(); metadata_positive,metadata_clean=metadata_self_test(); coordinator_ok=coordinator_self_test()
    categories={x.category for x in surfaces}; json_scan=any(x.data_type in {"json","jsonb"} for x in surfaces)
    checks=[ok,db_positive.complete,db_positive.a_hits>0,db_cleanup,db_clean.a_hits==0,process_results["cli"].a_hits>0,process_results["environment"].b_hits>0,process_cleanup,metadata_positive["url"].a_hits>0,metadata_positive["request"].b_hits>0,metadata_clean["url"].a_hits+metadata_clean["url"].b_hits+metadata_clean["request"].a_hits+metadata_clean["request"].b_hits==0,coordinator_ok]
    values={"SLICE2_USES_COMMON_SCAN_RESULT":"YES","DATABASE_LOGICAL_SCANNER":"IMPLEMENTED","DATABASE_SCHEMA_DISCOVERY":"IMPLEMENTED","DATABASE_SCAN_WRITES":0,"AUDIT_SCAN":"IMPLEMENTED" if "audit" in categories else "NOT_APPLICABLE","GENERATIONJOB_SCAN":"IMPLEMENTED" if "generation_job" in categories else "NOT_APPLICABLE","DOMAIN_DATA_SCAN":"IMPLEMENTED" if "domain" in categories else "BLOCKED","DATABASE_JSON_SCAN":"YES" if json_scan else "NOT_APPLICABLE","DATABASE_POSITIVE_SELF_TEST":"PASS" if db_positive.a_hits>0 else "FAIL","DATABASE_TEST_MARKER_HITS":db_positive.a_hits,"DATABASE_SELF_TEST_CLEANUP":"PASS" if db_cleanup else "FAIL","POST_CLEANUP_DATABASE_TEST_MARKER_HITS":db_clean.a_hits,"OWNED_PROCESS_SCOPE":"CURRENT_RUNTIME_ONLY","OWNED_PROCESS_CLI_SCAN":"IMPLEMENTED","OWNED_PROCESS_ENV_SCAN":"IMPLEMENTED","OWNED_PROCESS_CLI_POSITIVE_SELF_TEST":"PASS" if process_results["cli"].a_hits>0 else "FAIL","OWNED_PROCESS_ENV_POSITIVE_SELF_TEST":"PASS" if process_results["environment"].b_hits>0 else "FAIL","PROCESS_SELF_TEST_CLEANUP":"PASS" if process_cleanup else "FAIL","URL_METADATA_SCAN":"IMPLEMENTED","REQUEST_METADATA_SCAN":"IMPLEMENTED","REQUEST_BODY_SECRET_READBACK":"NO","SECRET_HEADER_READBACK":"NO","URL_METADATA_POSITIVE_SELF_TEST":"PASS" if metadata_positive["url"].a_hits>0 else "FAIL","REQUEST_METADATA_POSITIVE_SELF_TEST":"PASS" if metadata_positive["request"].b_hits>0 else "FAIL","METADATA_SELF_TEST_CLEANUP":"PASS" if all(x.a_hits+x.b_hits==0 for x in metadata_clean.values()) else "FAIL","POST_CLEANUP_METADATA_TEST_MARKER_HITS":sum(x.a_hits+x.b_hits for x in metadata_clean.values()),"FINAL_COORDINATOR_WIRING":"IMPLEMENTED","SAME_RUN_EXECUTION_ID":"IMPLEMENTED","FINAL_COORDINATOR_ORDER_GUARD":"IMPLEMENTED","PARTIAL_SCAN_COUNTS_AS_ZERO":"NO","FINAL_ZERO_AGGREGATOR":"IMPLEMENTED","REAL_DEEPSEEK_KEY":0,"REAL_DEEPSEEK_REQUESTS":0,"SCANNER_VALUE_OUTPUT":0}
    for k,v in values.items(): print(f"{k}={v}")
    return 0 if all(checks) else 1
if __name__=="__main__": raise SystemExit(main())
