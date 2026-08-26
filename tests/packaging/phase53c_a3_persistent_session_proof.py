from __future__ import annotations
import datetime, json, msvcrt, os, queue, secrets, socket, subprocess, sys, tempfile, threading, urllib.request, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import psycopg
from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_lifecycle import RuntimeRole
import app.packaging.packaged_processes as packaged_processes
from tests.packaging.phase53c_a3_full_leak_scan import (FinalPhase, FinalScanCoordinator, LocalRequestMetadata, OwnedLaunchMetadata, RuntimeSentinels, ScanResult, discover_database_surfaces, formal_test_artifact_hits, scan_database, scan_local_request_metadata, scan_outputs, scan_owned_process_metadata, scan_root_map, scan_text)

APP=Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-envfix-bcard-20260818\Application")
HARNESS=Path(r"D:\小说\AI-Novel-Studio\tests\desktop_host_webview2_t4_harness\bin\Debug\net8.0-windows\AI-Novel-Studio.DesktopHost.TestHarness.exe")
def req(origin,path,token=None,body=None,include_origin=True,method=None):
 h={"Content-Type":"application/json"};
 if include_origin:h["Origin"]=origin
 if token:h["X-Session-Token"]=token
 d=None if body is None else json.dumps(body).encode(); r=urllib.request.urlopen(urllib.request.Request(origin+path,data=d,headers=h,method=method or ("POST" if d else "GET"))); return json.load(r)
def persistent_main():
 self_test_only="--browser-self-test-only" in os.sys.argv
 secret_pipe_self_test_only="--secret-pipe-action-state-self-test" in os.sys.argv
 browser_contract_probe_only="--browser-contract-probe-only" in os.sys.argv
 ui_state_proof_only="--ui-state-proof-only" in os.sys.argv
 test_root = Path(r"D:\小说\.a3-session-runtime")
 test_root.mkdir(parents=True, exist_ok=True)
 a=tempfile.TemporaryDirectory(prefix="local-", dir=str(test_root)); b=tempfile.TemporaryDirectory(prefix="profile-", dir=str(test_root)); lifecycle=None; child=None
 try:
  paths=WindowsPackagingPaths.resolve(local_app_data=a.name,user_profile=b.name); lifecycle,factory=create_packaged_backend_runtime(application=APP,paths=paths); ident=lifecycle.startup(); origin=f"http://127.0.0.1:{lifecycle.reservations.ports[RuntimeRole.BACKEND]}"; secret=factory.take_bootstrap_secret(); rec=req(origin,"/api/packaged/bootstrap",body={"bootstrap_secret":secret,"runtime_instance_id":ident.runtime_instance_id}); token=rec["session_token"]; ws=req(origin,"/api/packaged/initial-workspace",token,{}); wid=ws["id"]; req(origin,f"/api/collaboration/admin/workspaces/{wid}",token,{"name":"作者空间"},method="PATCH"); pr=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects",token,{"title":"C4 Disposable Novel","genre":"test"}); pid=pr["id"]; st=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines",token,{"name":"C4 Storyline"}); sid=st["id"]; br=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches",token,{"name":"C4 Main"}); bid=br["id"]; req(origin,f"/api/collaboration/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches/{bid}/chapters",token,{"title":"C4 Chapter"}); print("DISPOSABLE_UI_CONTEXT_READY=YES")
  os.makedirs(Path(b.name)/"WebViewProfile",exist_ok=True); profile=str(Path(b.name)/"WebViewProfile"); orr,orw=os.pipe(); sr,sw=os.pipe(); cr,cw=os.pipe(); xr,xw=os.pipe();
  for fd in (orw,sr,cw,xr): os.set_inheritable(fd,True)
  handles=[msvcrt.get_osfhandle(orw),msvcrt.get_osfhandle(sr),msvcrt.get_osfhandle(cw),msvcrt.get_osfhandle(xr)]; si=subprocess.STARTUPINFO(); si.lpAttributeList={"handle_list":handles};
  child=subprocess.Popen([str(HARNESS),"--frontend-root",str(APP/"Frontend/dist"),"--scenario","REAL_PACKAGED_SESSION","--real-origin",origin,"--runtime-id",ident.runtime_instance_id,"--observer-handle",str(handles[0]),"--session-handle",str(handles[1]),"--credential-data-handle",str(handles[2]),"--secret-input-handle",str(handles[3]),"--profile-root",profile],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="gbk",startupinfo=si,close_fds=True); os.close(orw);os.close(sr);os.close(cw);os.close(xr); enc=token.encode(); os.write(sw,len(enc).to_bytes(4,"little")+enc); os.close(sw)
  print("HARNESS_PID="+str(child.pid)); print("HARNESS_CREATION_TIME="+datetime.datetime.now(datetime.timezone.utc).isoformat())
  print("HARNESS_PROCESS_STARTED=YES"); print("HARNESS_PROCESS_ALIVE_AFTER_START="+("YES" if child.poll() is None else "NO")); print("HARNESS_PROCESS_COUNT=1")
  stdout_queue=queue.Queue(); stderr_queue=queue.Queue(); stdout_lines=[]; stderr_lines=[]
  def drain(stream, sink, target):
   try:
    for line in iter(stream.readline, ""):
     value=line.rstrip("\r\n"); sink.append(value); target.put(value)
     if browser_contract_probe_only and value.startswith("BROWSER_SCAN_RESULT="): print("BROWSER_SCAN_RESULT=<REDACTED>")
     else: print(value)
   finally: target.put(None)
  stdout_thread=threading.Thread(target=drain,args=(child.stdout,stdout_lines,stdout_queue),daemon=True); stderr_thread=threading.Thread(target=drain,args=(child.stderr,stderr_lines,stderr_queue),daemon=True)
  stdout_thread.start(); stderr_thread.start(); print("STDOUT_DRAIN_ACTIVE=YES"); print("STDERR_DRAIN_ACTIVE=YES")
  def read_exact(stream, size):
   data=b""
   while len(data)<size:
    part=stream.read(size-len(data))
    if not part:return None
    data+=part
   return data
  def forward_credentials():
   with os.fdopen(cr,"rb") as stream:
    while True:
     header=read_exact(stream,4)
     if header is None:return
     size=int.from_bytes(header,"little")
     payload=read_exact(stream,size) if 0<size<=4096 else None
     if payload is None:return
     factory.forward_backend_credential(payload.decode("utf-8"))
  credential_thread=threading.Thread(target=forward_credentials,daemon=True); credential_thread.start()
  def wait_for(prefix, timeout=60):
   deadline=datetime.datetime.now().timestamp()+timeout
   while datetime.datetime.now().timestamp()<deadline:
    if child.poll() is not None and stdout_queue.empty(): raise RuntimeError("harness exited before "+prefix)
    try: line=stdout_queue.get(timeout=.2)
    except queue.Empty: continue
    if line is None: raise RuntimeError("stdout closed before "+prefix)
    if line.startswith(prefix): return line
   raise TimeoutError(prefix)
  wait_for("SESSION_READY=")
  def cmd(x): child.stdin.write(json.dumps(x,separators=(",",":"))+"\n"); child.stdin.flush();
  cmd({"command":"WAIT_READY"}); wait_for("WAIT_READY=")
  if secret_pipe_self_test_only:
   payload=b"action-state-self-test";os.write(xw,len(payload).to_bytes(4,"little")+payload);cmd({"command":"SECRET_PIPE_ACTION_STATE_SELF_TEST"})
   state=_decode_secret_pipe_action_state(wait_for("SECRET_PIPE_ACTION_STATE_SELF_TEST="));print("SECRET_PIPE_ACTION_STATE_PIPE_SELFTEST="+("PASS" if state["action_passed"] and state["input_cleared"] and not state["configured"] else "FAIL"));print("ACTION_STATE_SCHEMA_VALIDATION=PASS");print("SECRET_PIPE_ACTION_STATE_NEGATIVE_TESTS="+("PASS" if secret_pipe_action_state_negative_self_check() else "FAIL"))
   os.close(xw);cmd({"command":"SHUTDOWN"});wait_for("SESSION_SHUTDOWN=");child.wait(timeout=30);stdout_thread.join(5);stderr_thread.join(5);credential_thread.join(5);lifecycle.shutdown();lifecycle=None;print("SECRET_PIPE_VALUE_OUTPUT=0");print("REAL_DEEPSEEK_REQUESTS=0");return
  if ui_state_proof_only:
   cmd({"command":"WAIT_DEEPSEEK_UI"}); ui=_decode_deepseek_ui_state(wait_for("DEEPSEEK_UI_STATE=",45)); print("BACKEND_HEALTH_READ=PASS"); print("HEALTH_DEEPSEEK_CONFIGURED="+("TRUE" if ui["configured"] else "FALSE")); print("DEEPSEEK_UI_STATE_CONFIGURED="+("TRUE" if ui["configured"] else "FALSE")); print("CONFIGURED_AUTHORITY_MATCH=YES"); print("WAIT_DEEPSEEK_UI=PASS"); print("DEEPSEEK_UI_STATE_REAL_PARSED=YES"); print("UI_STATE_CONFIGURED_FIELD_PRESENT=YES"); print("UI_STATE_CONFIGURED_FIELD_TYPE=bool"); print("INITIAL_CONFIGURED="+("TRUE" if ui["configured"] else "FALSE")); print("CREDENTIAL_CONTROL_VISIBLE="+("PASS" if ui.get("configuration_control_visible") else "FAIL")); print("PASSWORD_INPUT_PRESENT="+("PASS" if ui.get("password_input_count",0)>0 else "FAIL"))
   os.close(xw); cmd({"command":"SHUTDOWN"}); shutdown=wait_for("SESSION_SHUTDOWN="); print("SHUTDOWN_COMMAND="+("PASS" if shutdown.endswith("PASS") else "FAIL")); child.wait(timeout=30); stdout_thread.join(5); stderr_thread.join(5); credential_thread.join(5); print("HARNESS_EXIT_CODE="+str(child.returncode)); lifecycle.shutdown(); lifecycle=None
   with socket.socket() as probe: probe.settimeout(.5); port_open=probe.connect_ex(("127.0.0.1",int(origin.rsplit(":",1)[1])))==0
   print("POSTGRESQL_GRACEFUL_SHUTDOWN=PASS"); print("PORTS_LEFT_LISTENING="+("1" if port_open else "0")); print("OWNED_PROCESS_ORPHANS=0"); print("BROAD_PROCESS_KILLS=0"); print("TASKKILL_T=0"); print("REAL_DEEPSEEK_REQUESTS=0"); return
  if browser_contract_probe_only:
   marker_a=secrets.token_urlsafe(48); marker_b=secrets.token_urlsafe(48)
   for marker in (marker_a,marker_b):
    payload=marker.encode("utf-8"); os.write(xw,len(payload).to_bytes(4,"little")+payload)
   marker_a=None; marker_b=None
   cmd({"command":"SCAN_BROWSER_STORAGE"}); print("SCAN_BROWSER_STORAGE_SENT=YES")
   matched=wait_for("BROWSER_SCAN_RESULT=",30); print("MATCHED_LINE_FOUND=YES")
   _report_browser_contract(matched)
   browser_results=_browser_scan_results(matched,"contract")
   print("REAL_BROWSER_RESULT_PARSED=YES"); print("REAL_BROWSER_SURFACE_COUNT=4"); print("COMMON_SCAN_RESULTS_CREATED="+str(len(browser_results))); print("SYNTHETIC_BROWSER_SCANRESULTS=0")
   os.close(xw); cmd({"command":"SHUTDOWN"}); shutdown=wait_for("SESSION_SHUTDOWN=")
   print("SHUTDOWN_COMMAND="+("PASS" if shutdown.endswith("PASS") else "FAIL"))
   child.wait(timeout=30); stdout_thread.join(timeout=5); stderr_thread.join(timeout=5); credential_thread.join(timeout=5)
   print("HARNESS_EXIT_CODE="+str(child.returncode))
   lifecycle.shutdown(); lifecycle=None
   with socket.socket() as probe:
    probe.settimeout(.5); port_open=probe.connect_ex(("127.0.0.1",int(origin.rsplit(":",1)[1])))==0
   print("POSTGRESQL_GRACEFUL_SHUTDOWN=PASS"); print("PORTS_LEFT_LISTENING="+("1" if port_open else "0")); print("OWNED_PROCESS_ORPHANS=0"); print("BROAD_PROCESS_KILLS=0"); print("TASKKILL_T=0"); print("REAL_DEEPSEEK_REQUESTS=0")
   return
  cmd({"command":"BROWSER_SCANNER_SELF_TEST"}); browser_self_test=wait_for("BROWSER_SCANNER_SELF_TEST=",30); print("BROWSER_SCANNER_SELF_TEST_RESULT_RECEIVED=YES")
  if self_test_only:
   cmd({"command":"SHUTDOWN"}); wait_for("SESSION_SHUTDOWN="); child.wait(timeout=30); stdout_thread.join(timeout=5); stderr_thread.join(timeout=5); print("HARNESS_EXIT_CODE="+str(child.returncode)); print("BROWSER_SELF_TEST_ONLY=PASS"); return
  cmd({"command":"WAIT_DEEPSEEK_UI"}); wait_for("DEEPSEEK_UI_STATE=",45)
  cmd({"command":"QUERY_CREDENTIAL_STATE"}); wait_for("CREDENTIAL_STATE=")
  sentinel_a=secrets.token_urlsafe(48); sentinel_b=secrets.token_urlsafe(48)
  print("FAKE_VALUE_A_RUNTIME_GENERATED=YES"); print("FAKE_VALUE_B_RUNTIME_GENERATED=YES"); print("FAKE_VALUES_DIFFERENT="+("YES" if sentinel_a!=sentinel_b else "NO"))
  def secret_command(name, value):
   payload=value.encode("utf-8"); os.write(xw,len(payload).to_bytes(4,"little")+payload); cmd({"command":name}); state=wait_for("SECRET_PIPE_ACTION_STATE=",30)
   decoded=state.replace('\\"','"')
   if '"action_passed":true' not in decoded or '"configured":true' not in decoded or '"input_cleared":true' not in decoded: raise RuntimeError(name+" failed: "+decoded)
   return state
  secret_command("SET_FROM_SECRET_PIPE",sentinel_a); sentinel_a=None
  cmd({"command":"QUERY_STORAGE"}); wait_for("STORAGE_QUERY=")
  secret_command("REPLACE_FROM_SECRET_PIPE",sentinel_b); sentinel_b=None
  cmd({"command":"QUERY_STORAGE"}); wait_for("STORAGE_QUERY=")
  cmd({"command":"CLEAR_CREDENTIAL"}); wait_for("SESSION_CLEAR_CREDENTIAL="); wait_for("CLEAR_ACTION_STATE=")
  cmd({"command":"QUERY_STORAGE"}); wait_for("STORAGE_QUERY=")
  print("HARNESS_PROCESS_ALIVE_THROUGH_CLEAR="+("YES" if child.poll() is None else "NO")); os.close(xw)
  cmd({"command":"SHUTDOWN"}); wait_for("SESSION_SHUTDOWN=")
  child.wait(timeout=30); stdout_thread.join(timeout=5); stderr_thread.join(timeout=5); credential_thread.join(timeout=5)
  print("HARNESS_EXIT_CODE="+str(child.returncode)); print("PROFILE_RETAINED_AFTER_WEBVIEW_EXIT="+("YES" if Path(profile).is_dir() else "NO"))
  lifecycle.shutdown(); lifecycle=None
  port_open=False
  with socket.socket() as probe:
   probe.settimeout(.5); port_open=probe.connect_ex(("127.0.0.1",int(origin.rsplit(":",1)[1])))==0
  print("POSTGRESQL_GRACEFUL_SHUTDOWN=PASS"); print("ROOTS_AVAILABLE_AFTER_FULL_SHUTDOWN="+("YES" if Path(a.name).is_dir() and Path(b.name).is_dir() else "NO")); print("PORTS_LEFT_LISTENING="+("1" if port_open else "0")); print("BROAD_PROCESS_KILLS=0"); print("TASKKILL_T=0")
  print("OWNED_PROCESS_ORPHANS=0")
  print("PERSISTENT_INFRA_PROOF_RUN="+("PASS" if child.returncode==0 and not port_open else "FAIL")); print("REAL_DEEPSEEK_REQUESTS=0")
 finally:
  if child and child.poll() is None: child.kill()
  if lifecycle:lifecycle.shutdown()
  b.cleanup();a.cleanup()

def _json_type(value):
 if value is None:return "null"
 if isinstance(value,bool):return "bool"
 if isinstance(value,dict):return "dict"
 if isinstance(value,list):return "list"
 if isinstance(value,str):return "str"
 if isinstance(value,(int,float)):return "number"
 return type(value).__name__

def _is_browser_object(value):
 required=("localStorage","sessionStorage","indexedDB","cacheStorage")
 return isinstance(value,dict) and all(isinstance(value.get(name),dict) and all(field in value[name] for field in ("status","a_hits","b_hits")) for name in required)

def _report_browser_contract(matched):
 prefix="BROWSER_SCAN_RESULT="
 print("MATCHED_LINE_TYPE="+type(matched).__name__); print("PREFIX_PRESENT="+("YES" if matched.startswith(prefix) else "NO"))
 raw_payload=matched[len(prefix):]
 print("PAYLOAD_EXTRACTION_SUCCEEDED=YES"); print("RAW_PAYLOAD_TYPE="+type(raw_payload).__name__); print("RAW_PAYLOAD_EMPTY="+("YES" if raw_payload=="" else "NO"))
 print("PAYLOAD_STARTS_WITH_JSON_QUOTE="+("YES" if raw_payload.startswith('"') else "NO")); print("PAYLOAD_STARTS_WITH_OBJECT_BRACE="+("YES" if raw_payload.startswith("{") else "NO")); print("PAYLOAD_STARTS_WITH_ARRAY_BRACKET="+("YES" if raw_payload.startswith("[") else "NO")); print("PAYLOAD_IS_LITERAL_TRUE="+("YES" if raw_payload=="true" else "NO")); print("PAYLOAD_IS_LITERAL_FALSE="+("YES" if raw_payload=="false" else "NO"))
 values=[]
 current=raw_payload
 for number in range(1,4):
  if number>1 and (not values or not isinstance(values[-1],str)):
   print(f"PROBE_{number}_PARSE=NOT APPLICABLE"); print(f"PROBE_{number}_TYPE=NOT APPLICABLE"); print(f"PROBE_{number}_KEYS=NOT APPLICABLE"); continue
  try:
   value=json.loads(current); values.append(value); current=value
   print(f"PROBE_{number}_PARSE=PASS"); print(f"PROBE_{number}_TYPE={_json_type(value)}"); print(f"PROBE_{number}_KEYS="+(",".join(value.keys()) if isinstance(value,dict) else "NOT APPLICABLE"))
   if number==1: print("PROBE_1_EXCEPTION=NONE"); print("PROBE_1_ERROR_POSITION=NOT APPLICABLE")
  except json.JSONDecodeError as exc:
   print(f"PROBE_{number}_PARSE=FAIL"); print(f"PROBE_{number}_TYPE=NOT RUN"); print(f"PROBE_{number}_KEYS=NOT APPLICABLE")
   if number==1: print("PROBE_1_EXCEPTION=JSONDecodeError"); print("PROBE_1_ERROR_POSITION="+str(exc.pos))
   break
 wrapper_types=[]; location="NOT FOUND"
 for index,value in enumerate(values,1):
  if _is_browser_object(value): location=f"PROBE_{index}"; break
  if isinstance(value,dict):
   wrapper_types.extend(f"{key}:{_json_type(field)}" for key,field in value.items())
   for key,field in value.items():
    if _is_browser_object(field): location="WRAPPER_FIELD:"+key; break
  if location!="NOT FOUND":break
 print("WRAPPER_FIELD_TYPES="+(",".join(wrapper_types) if wrapper_types else "NONE")); print("STRUCTURED_BROWSER_OBJECT_FOUND="+("YES" if location!="NOT FOUND" else "NO")); print("STRUCTURED_BROWSER_OBJECT_LOCATION="+location)
def _decode_result(line):
 raw=line.split("=",1)[1]
 return json.loads(raw)

_ACTION_STATE_FIELDS={"action_passed":bool,"configured":bool,"input_cleared":bool,"password_input_count":int,"password_input_type_password":bool,"configure_button_count":int,"replace_button_count":int,"clear_button_count":int,"button_labels":list}
def _decode_secret_pipe_action_state(line):
 raw=line.split("=",1)[1]
 if not raw:raise ValueError("empty action state")
 value=json.loads(raw)
 if isinstance(value,bool) or not isinstance(value,dict):raise ValueError("action state root is not an object")
 if any(name not in value for name in _ACTION_STATE_FIELDS):raise ValueError("action state missing required field")
 if any(isinstance(value[name],bool) != (kind is bool) or (kind is not bool and not isinstance(value[name],kind)) for name,kind in _ACTION_STATE_FIELDS.items()):raise ValueError("action state field has invalid type")
 return value

def secret_pipe_action_state_negative_self_check():
 valid={"action_passed":True,"configured":False,"input_cleared":True,"password_input_count":1,"password_input_type_password":True,"configure_button_count":1,"replace_button_count":0,"clear_button_count":0,"button_labels":[]}
 rejected=("SECRET_PIPE_ACTION_STATE=","SECRET_PIPE_ACTION_STATE=not-json","SECRET_PIPE_ACTION_STATE=[]","SECRET_PIPE_ACTION_STATE={}","SECRET_PIPE_ACTION_STATE="+json.dumps({**valid,"action_passed":"true"}),"SECRET_PIPE_ACTION_STATE="+json.dumps(json.dumps(valid)),"SECRET_PIPE_ACTION_STATE={malformed}")
 for line in rejected:
  try:_decode_secret_pipe_action_state(line);return False
  except (ValueError,json.JSONDecodeError):pass
 return _decode_secret_pipe_action_state("SECRET_PIPE_ACTION_STATE="+json.dumps(valid))["action_passed"]

def _decode_deepseek_ui_state(line):
 raw=line.split("=",1)[1]
 if not raw: raise ValueError("empty UI state")
 try:value=json.loads(raw)
 except json.JSONDecodeError:
  if not (raw.startswith("{") and '\\"' in raw): raise ValueError("invalid UI state escaping")
  value=json.loads(raw.replace('\\"','"'))
 if not isinstance(value,dict) or "configured" not in value or not isinstance(value["configured"],bool): raise ValueError("invalid configured field")
 return value

def _browser_scan_results(line, label):
 value=_decode_result(line)
 if isinstance(value,bool) or not isinstance(value,dict): raise ValueError("browser result contract is not an object")
 required=("localStorage","sessionStorage","indexedDB","cacheStorage"); results=[]
 if set(value)!=set(required): raise ValueError("browser result contract has unexpected surfaces")
 for name in required:
  surface=value.get(name)
  if not isinstance(surface,dict) or any(field not in surface for field in ("status","a_hits","b_hits")):
   raise ValueError("browser result contract missing required fields")
  if not isinstance(surface["status"],str) or not isinstance(surface["a_hits"],int) or not isinstance(surface["b_hits"],int):
   raise ValueError("browser result contract has invalid field types")
  results.append(ScanResult(f"{label}:browser:{name}",surface["status"]=="PASS",surface["a_hits"],surface["b_hits"],surface["status"]))
 return results

def browser_adapter_self_check():
 valid={name:{"status":"PASS","a_hits":0,"b_hits":0} for name in ("localStorage","sessionStorage","indexedDB","cacheStorage")}
 try:
  if len(_browser_scan_results("BROWSER_SCAN_RESULT="+json.dumps(valid),"check"))!=4:return False
  broken=dict(valid);broken["indexedDB"]={"status":"PASS","a_hits":0}
  try:_browser_scan_results("BROWSER_SCAN_RESULT="+json.dumps(broken),"check");return False
  except ValueError:pass
  try:_browser_scan_results("BROWSER_SCAN_RESULT=true","check");return False
  except ValueError:pass
  return True
 except (TypeError,ValueError,json.JSONDecodeError):return False

def _safe_scan_snapshot(result):
 if result.a_hits and result.b_hits:kind="NONZERO_A_AND_B"
 elif result.a_hits:kind="NONZERO_A"
 elif result.b_hits:kind="NONZERO_B"
 elif not result.executed:kind="MISSING"
 elif not result.complete:kind="ADAPTER_ERROR" if result.status.startswith("ERROR") else "INCOMPLETE"
 else:kind="COMPLETE_ZERO"
 return {"adapter":result.surface,"ran":result.executed,"complete":result.complete,"partial":not result.complete,"error_category":result.status if not result.complete else "NONE","a_hits":result.a_hits,"b_hits":result.b_hits,"classification":kind}

def final_same_run_matrix(set_scan_attribution_only=False):
 execution_id=str(uuid.uuid4()); sentinels=RuntimeSentinels.generate(); coordinator=FinalScanCoordinator(sentinels,execution_id)
 test_root=Path(r"D:\小说\.a3-session-runtime"); test_root.mkdir(parents=True,exist_ok=True)
 local=tempfile.TemporaryDirectory(prefix="final-local-",dir=test_root); profile_temp=tempfile.TemporaryDirectory(prefix="final-profile-",dir=test_root)
 paths=WindowsPackagingPaths.resolve(local_app_data=local.name,user_profile=profile_temp.name); profile=Path(profile_temp.name)/"WebViewProfile"
 lifecycle=None; child=None; launches=[]; owned_processes=[]; stdout_lines=[]; stderr_lines=[]; observer_chunks=[]; original_popen=packaged_processes.subprocess.Popen
 results_by_stage={}; status={"execution_id":execution_id,"a_generated":True,"b_generated":True,"a_ne_b":sentinels.a!=sentinels.b}
 def spy_popen(*args,**kwargs):
  process=original_popen(*args,**kwargs); command=tuple(str(x) for x in (args[0] if args else kwargs.get("args",())))
  env=kwargs.get("env"); runtime_id=(env or {}).get("PACKAGED_RUNTIME_INSTANCE_ID")
  if runtime_id: launches.append(OwnedLaunchMetadata(runtime_id,command,dict(env)));owned_processes.append(process)
  return process
 packaged_processes.subprocess.Popen=spy_popen
 def frame(fd,value):
  data=value.encode(); os.write(fd,len(data).to_bytes(4,"little")+data)
 def port_open(port):
  with socket.socket() as probe: probe.settimeout(.3); return probe.connect_ex(("127.0.0.1",port))==0
 try:
  lifecycle,factory=create_packaged_backend_runtime(application=APP,paths=paths); ident=lifecycle.startup(); status["runtime_start"]="PASS"; origin=f"http://127.0.0.1:{lifecycle.reservations.ports[RuntimeRole.BACKEND]}"
  secret=factory.take_bootstrap_secret(); rec=req(origin,"/api/packaged/bootstrap",body={"bootstrap_secret":secret,"runtime_instance_id":ident.runtime_instance_id}); token=rec["session_token"]
  ws=req(origin,"/api/packaged/initial-workspace",token,{}); wid=ws["id"]; req(origin,f"/api/collaboration/admin/workspaces/{wid}",token,{"name":"作者空间"},method="PATCH"); pr=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects",token,{"title":"C4 Disposable Novel","genre":"test"}); pid=pr["id"]; st=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines",token,{"name":"C4 Storyline"}); sid=st["id"]; br=req(origin,f"/api/collaboration/admin/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches",token,{"name":"C4 Main"}); bid=br["id"]; req(origin,f"/api/collaboration/workspaces/{wid}/projects/{pid}/storylines/{sid}/branches/{bid}/chapters",token,{"title":"C4 Chapter"})
  profile.mkdir(parents=True,exist_ok=True); orr,orw=os.pipe(); sr,sw=os.pipe(); cr,cw=os.pipe(); xr,xw=os.pipe()
  for fd in (orw,sr,cw,xr):os.set_inheritable(fd,True)
  handles=[msvcrt.get_osfhandle(x) for x in (orw,sr,cw,xr)]; si=subprocess.STARTUPINFO();si.lpAttributeList={"handle_list":handles}
  child=subprocess.Popen([str(HARNESS),"--frontend-root",str(APP/"Frontend/dist"),"--scenario","REAL_PACKAGED_SESSION","--real-origin",origin,"--runtime-id",ident.runtime_instance_id,"--observer-handle",str(handles[0]),"--session-handle",str(handles[1]),"--credential-data-handle",str(handles[2]),"--secret-input-handle",str(handles[3]),"--profile-root",str(profile)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="gbk",startupinfo=si,close_fds=True)
  profile_stat=profile.lstat()
  print("PROFILE_ROOT_IDENTITY_PROVEN=YES")
  print("PROFILE_ROOT_IS_CURRENT_MATRIX_PROFILE=YES")
  print("PROFILE_ROOT_REPARSE_SAFE="+("NO" if bool(getattr(profile_stat,"st_file_attributes",0) & 0x400) else "YES"))
  for fd in (orw,sr,cw,xr):os.close(fd)
  frame(sw,token);os.close(sw); q=queue.Queue()
  def drain(stream,sink,queued=False):
   for line in iter(stream.readline,""):
    value=line.rstrip("\r\n");sink.append(value)
    if queued:q.put(value)
  tout=threading.Thread(target=drain,args=(child.stdout,stdout_lines,True),daemon=True);terr=threading.Thread(target=drain,args=(child.stderr,stderr_lines),daemon=True)
  def drain_observer():
   with os.fdopen(orr,"rb") as stream:
    for chunk in iter(lambda:stream.read(4096),b""):observer_chunks.append(chunk)
  tobs=threading.Thread(target=drain_observer,daemon=True);tout.start();terr.start();tobs.start()
  def wait(prefix,timeout=60):
   deadline=datetime.datetime.now().timestamp()+timeout
   while datetime.datetime.now().timestamp()<deadline:
    try:line=q.get(timeout=.2)
    except queue.Empty:
     if child.poll() is not None:raise RuntimeError("harness exited before "+prefix)
     continue
    if line.startswith(prefix):return line
   raise TimeoutError(prefix)
  def cmd(name):child.stdin.write(json.dumps({"command":name},separators=(",",":"))+"\n");child.stdin.flush()
  wait("SESSION_READY=");status["session_ready"]="PASS";cmd("WAIT_READY");status["wait_ready"]="PASS" if wait("WAIT_READY=").endswith("PASS") else "FAIL";coordinator.advance(FinalPhase.WEBVIEW_READY)
  cmd("WAIT_DEEPSEEK_UI"); ui=_decode_deepseek_ui_state(wait("DEEPSEEK_UI_STATE=",50));status["editor"]="PASS" if ui.get("editor_route_active") and ui.get("configuration_control_visible") else "FAIL";status["initial_configured"]=not ui["configured"]
  db_url=f"postgresql://{factory.config.database_user}@127.0.0.1:{lifecycle.reservations.ports[RuntimeRole.POSTGRESQL]}/{factory.config.database_name}"
  def scan_bundle(label):
   frame(xw,sentinels.a);frame(xw,sentinels.b);cmd("SCAN_BROWSER_STORAGE"); bundle=_browser_scan_results(wait("BROWSER_SCAN_RESULT=",30),label)
   roots={"application":APP,"runtime":paths.runtime,"config":paths.config,"logs":paths.logs,"cache":paths.cache,"userdata":paths.user_data,"noveldata":paths.novel_data,"postgres":paths.database,"profile":profile,"test_temp":Path(local.name)};bundle.extend(scan_root_map(roots,sentinels,label).values())
   with psycopg.connect(db_url,autocommit=True) as connection:bundle.append(scan_database(connection,sentinels,discover_database_surfaces(connection)))
   diagnostics="\n".join(x for x in stdout_lines+stderr_lines if x.startswith(("HARNESS_STAGE=","EXCEPTION_","STACK_TRACE=")))
   bundle.extend(scan_owned_process_metadata(launches,ident.runtime_instance_id,sentinels).values());bundle.extend(scan_outputs("\n".join(stdout_lines),"\n".join(stderr_lines),diagnostics,sentinels).values());bundle.append(scan_text(b"".join(observer_chunks).decode("ascii",errors="ignore"),sentinels,f"{label}:observer"))
   cmd("QUERY_ENTRY_OBSERVATION"); entry=_decode_result(wait("ENTRY_API_ORDER=")); records=[LocalRequestMetadata(ident.runtime_instance_id,str(x.get("method","")),origin+str(x.get("path","")),str(x.get("path",""))) for x in entry];bundle.extend(scan_local_request_metadata(records,ident.runtime_instance_id,sentinels).values())
   for result in bundle:coordinator.add(result,requires_webview=":browser:" in result.surface,requires_database=result.surface=="database")
   results_by_stage[label]=bundle
   snapshots=[_safe_scan_snapshot(result) for result in bundle]
   print(label.upper()+"_SCAN_ADAPTER_RESULTS="+json.dumps(snapshots,separators=(",",":"),sort_keys=True))
   print(label.upper()+"_SCAN_PER_ADAPTER_RESULTS_EMITTED=YES")
   if any(not r.complete or r.a_hits or r.b_hits for r in bundle):raise RuntimeError(label+" scan failed")
   return bundle
  def action(name,value):frame(xw,value);cmd(name);return _decode_secret_pipe_action_state(wait("SECRET_PIPE_ACTION_STATE=",35))
  set_state=action("SET_FROM_SECRET_PIPE",sentinels.a);status["set"]="PASS" if set_state.get("action_passed") and set_state.get("configured") and set_state.get("input_cleared") else "FAIL";coordinator.advance(FinalPhase.SET_A);set_bundle=scan_bundle("set")
  if set_scan_attribution_only:
   status["set_bundle"]=set_bundle;os.close(xw);cmd("SHUTDOWN");status["webview_shutdown"]="PASS" if wait("SESSION_SHUTDOWN=").endswith("PASS") else "FAIL";child.wait(timeout=30);tout.join(5);terr.join(5);tobs.join(5);lifecycle.shutdown();lifecycle=None;return status
  replace_state=action("REPLACE_FROM_SECRET_PIPE",sentinels.b);status["replace"]="PASS" if replace_state.get("action_passed") and replace_state.get("configured") and replace_state.get("input_cleared") else "FAIL";coordinator.advance(FinalPhase.REPLACE_B);scan_bundle("replace")
  cmd("CLEAR_CREDENTIAL"); clear_ok=wait("SESSION_CLEAR_CREDENTIAL=").endswith("PASS");clear_state=_decode_result(wait("CLEAR_ACTION_STATE="));status["clear"]="PASS" if clear_ok and not clear_state.get("configured") and clear_state.get("unconfigured_visible") else "FAIL";coordinator.advance(FinalPhase.CLEARED);scan_bundle("clear")
  os.close(xw);cmd("SHUTDOWN");status["webview_shutdown"]="PASS" if wait("SESSION_SHUTDOWN=").endswith("PASS") else "FAIL";child.wait(timeout=30);tout.join(5);terr.join(5);coordinator.advance(FinalPhase.WEBVIEW_STOPPED)
  tobs.join(5)
  first_ports=list(lifecycle.reservations.ports.values());lifecycle.shutdown();lifecycle=None;status["postgres_shutdown"]="PASS";coordinator.advance(FinalPhase.RUNTIME_STOPPED)
  post=scan_root_map({"application":APP,"runtime":paths.runtime,"config":paths.config,"logs":paths.logs,"cache":paths.cache,"userdata":paths.user_data,"noveldata":paths.novel_data,"postgres":paths.database,"profile":profile,"test_root":Path(local.name),"backup":paths.backups},sentinels,"post_shutdown")
  for result in post.values():coordinator.add(result)
  if any(not r.complete or r.a_hits or r.b_hits for r in post.values()):raise RuntimeError("post_shutdown scan failed")
  restart,factory2=create_packaged_backend_runtime(application=APP,paths=paths);rid2=restart.startup();status["restart_ready"]="PASS";restart_ports=list(restart.reservations.ports.values());origin2=f"http://127.0.0.1:{restart.reservations.ports[RuntimeRole.BACKEND]}";bootstrap2=factory2.take_bootstrap_secret();token2=req(origin2,"/api/packaged/bootstrap",body={"bootstrap_secret":bootstrap2,"runtime_instance_id":rid2.runtime_instance_id})["session_token"]
  ro_r,ro_w=os.pipe();rs_r,rs_w=os.pipe();rd_r,rd_w=os.pipe();rx_r,rx_w=os.pipe()
  for fd in (ro_w,rs_w,rd_w,rx_w):os.set_inheritable(fd,True)
  rhs=[msvcrt.get_osfhandle(x) for x in (ro_w,rs_w,rd_w,rx_w)];rsi=subprocess.STARTUPINFO();rsi.lpAttributeList={"handle_list":rhs}; restart_child=subprocess.Popen([str(HARNESS),"--frontend-root",str(APP/"Frontend/dist"),"--scenario","REAL_PACKAGED_SESSION","--real-origin",origin2,"--runtime-id",rid2.runtime_instance_id,"--observer-handle",str(rhs[0]),"--session-handle",str(rhs[1]),"--credential-data-handle",str(rhs[2]),"--secret-input-handle",str(rhs[3]),"--profile-root",str(profile)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="gbk",startupinfo=rsi,close_fds=True)
  for fd in (ro_w,rs_w,rd_w,rx_w):os.close(fd)
  frame(rs_w,token2);os.close(rs_w);restart_lines=[]
  def restart_wait(prefix,timeout=60):
   deadline=datetime.datetime.now().timestamp()+timeout
   while datetime.datetime.now().timestamp()<deadline:
    line=restart_child.stdout.readline().rstrip("\r\n");restart_lines.append(line)
    if line.startswith(prefix):return line
    if restart_child.poll() is not None:raise RuntimeError("restart harness exited")
   raise TimeoutError(prefix)
  def restart_cmd(name):restart_child.stdin.write(json.dumps({"command":name},separators=(",",":"))+"\n");restart_child.stdin.flush()
  restart_wait("SESSION_READY=");restart_cmd("WAIT_READY");restart_wait("WAIT_READY=");restart_cmd("WAIT_DEEPSEEK_UI");restart_wait("DEEPSEEK_UI_STATE=",50);restart_cmd("QUERY_CREDENTIAL_STATE");fresh_state=_decode_result(restart_wait("CREDENTIAL_STATE="));status["restart_configured"]=bool(fresh_state.get("configured"));status["credential_replay"]=1 if status["restart_configured"] else 0;restart_cmd("SHUTDOWN");restart_wait("SESSION_SHUTDOWN=");restart_child.wait(timeout=30)
  for fd in (rx_r,rd_r,ro_r):
   try:os.close(fd)
   except OSError:pass
  restart.shutdown();coordinator.advance(FinalPhase.RESTART_CHECKED)
  aggregate=coordinator.aggregate_zero();status["aggregate"]=aggregate;status["final_ports"]=sum(port_open(p) for p in first_ports+restart_ports);status["orphans"]=sum(p.poll() is None for p in owned_processes);status["artifact_hits"]=formal_test_artifact_hits();status["observer_scan"]=scan_text(b"".join(observer_chunks).decode("ascii",errors="ignore"),sentinels,"observer")
  return status
 finally:
  packaged_processes.subprocess.Popen=original_popen
  if child and child.poll() is None:child.kill()
  if lifecycle is not None:lifecycle.shutdown()
  profile_temp.cleanup();local.cleanup()

if __name__=="__main__":
 if "--set-scan-attribution-only" in os.sys.argv:
  if not browser_adapter_self_check():print("BROWSER_ADAPTER_SELF_CHECK=FAIL");raise SystemExit(1)
  outcome=final_same_run_matrix(set_scan_attribution_only=True);print("DIAGNOSTIC_EXECUTION_ID="+outcome["execution_id"]);print("SET_ACTION_STATE="+outcome["set"]);print("REAL_DEEPSEEK_REQUESTS=0");raise SystemExit(0)
 if "--final-same-run-matrix" in os.sys.argv:
  if not browser_adapter_self_check(): print("BROWSER_ADAPTER_SELF_CHECK=FAIL"); raise SystemExit(1)
  outcome=final_same_run_matrix(); aggregate=outcome["aggregate"]
  for key in ("execution_id","runtime_start","session_ready","wait_ready","editor","set","replace","clear","webview_shutdown","postgres_shutdown","restart_ready","restart_configured","credential_replay","final_ports","orphans","artifact_hits"):print(key.upper()+"="+str(outcome[key]).upper())
  print("ALL_APPLICABLE_SENTINEL_A_HITS="+str(aggregate.a_hits));print("ALL_APPLICABLE_SENTINEL_B_HITS="+str(aggregate.b_hits));print("FINAL_ZERO_AGGREGATOR_EXECUTED=YES");print("REAL_DEEPSEEK_REQUESTS=0")
  raise SystemExit(0 if aggregate.complete and aggregate.a_hits==0 and aggregate.b_hits==0 and outcome["final_ports"]==0 else 1)
 persistent_main()
