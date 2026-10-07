"""Original two PostgreSQL shards against isolated native Linux databases."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import time

parser=argparse.ArgumentParser()
parser.add_argument('--sha',required=True)
parser.add_argument('--fingerprint',required=True)
args=parser.parse_args()
windows_root=Path(__file__).resolve().parents[2]
metadata=json.loads((windows_root/'.runtime/full-recovery/wsl/native-environment.json').read_text())
native=Path(metadata['native'])
project=native/'project'
python=native/'venv/bin/python'
manifest_raw=(project/'.github/ci/coverage_manifest.json.gz').read_bytes()
manifest=json.loads(gzip.decompress(manifest_raw))
assert manifest['full_recovery_inventory']['source_files_fingerprint_sha256']==args.fingerprint
font=windows_root/'.runtime/full-recovery/fonts/NotoSansSC-Regular.ttf'
assert font.is_file() and python.is_file()
receipt_root=native/'receipts'
export_root=windows_root/'docs/delivery/full-recovery/candidate-linux-v2-receipts'
identity={'CI_COVERAGE_SHA':args.sha,'GITHUB_SHA':args.sha,
          'CI_COVERAGE_TREE':'local-working-source-'+args.fingerprint,
          'GITHUB_RUN_ID':'local-recovery-20261007-linux-final-v2',
          'GITHUB_RUN_ATTEMPT':'1','GITHUB_REPOSITORY':'1785235376-blip/AI-Novel-Studio'}

def run_shard(index):
    receipt=receipt_root/f'postgres-{index}'
    runtime=native/f'final-pg-sandbox-{index}'
    if receipt.exists() or runtime.exists():
        raise RuntimeError('Final receipt/sandbox must be fresh')
    receipt.mkdir(parents=True)
    runtime.mkdir()
    for name in ('home','appdata','localappdata','config','cache','data','state','tmp'):
        (runtime/name).mkdir()
    database='novel_recovery_ci' if index==0 else 'novel_recovery_shard1_ci'
    url='postgresql://recovery@127.0.0.1:55446/'+database
    environment=dict(os.environ)
    for name in ('AI_NOVEL_STUDIO_PDF_FONT','AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT'):
        environment.pop(name,None)
    environment.update(identity)
    environment.update(STORAGE_BACKEND='postgres',DATABASE_URL=url,TEST_POSTGRES_DATABASE_URL=url,
                       MOCK_PROVIDER='true',ENABLE_CLOUD='false',MOCK_STREAM_DELAY_MS='0',
                       CREDENTIAL_VAULT_BACKEND='memory',CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK='true',
                       PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                       PYTHONPATH=str(project/'.github/ci')+':'+str(project),PROJECT_ROOT=str(project),
                       PATH=str(native/'venv/bin')+':'+metadata['path'],LD_LIBRARY_PATH=metadata['ld_library_path'],LC_ALL='C.UTF-8',
                       HOME=str(runtime/'home'),USERPROFILE=str(runtime/'home'),APPDATA=str(runtime/'appdata'),
                       LOCALAPPDATA=str(runtime/'localappdata'),XDG_CONFIG_HOME=str(runtime/'config'),
                       XDG_CACHE_HOME=str(runtime/'cache'),XDG_DATA_HOME=str(runtime/'data'),XDG_STATE_HOME=str(runtime/'state'),
                       TMPDIR=str(runtime/'tmp'),TMP=str(runtime/'tmp'),TEMP=str(runtime/'tmp'),
                       NOVEL_DATA_PATH=str(runtime/'data/novels'),KNOWLEDGE_SOURCE_PATH=str(runtime/'data/novels'),
                       BACKUP_PATH=str(runtime/'data/backups'),DATABASE_BACKUP_PATH=str(runtime/'data/database-backups'),
                       R2_TEST_FONT_FILE=str(font))
    migration_code='''import os,json
from pathlib import Path
import psycopg
with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as connection:
    assert connection.execute('SELECT 1').fetchone()==(1,)
    print(connection.execute('SELECT version()').fetchone()[0],flush=True)
    tables=connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    assert tables==[], ('Fresh isolated database already has tables',tables)
    for migration in sorted(Path('database/migrations').glob('*.sql')):
        connection.execute(migration.read_text(encoding='utf-8'))
        print('Applied',migration.name,flush=True)
'''
    with (receipt/'migrations.log').open('wb') as output:
        migration=subprocess.run([str(python),'-c',migration_code],cwd=project,env=environment,stdout=output,stderr=subprocess.STDOUT)
    if migration.returncode:
        raise RuntimeError('Fresh database migration failed; see original output')
    arguments=[str(python),'-m','pytest','-p','postgres_gate','-p','suite_coverage','-p','no:cacheprovider',
               '--basetemp='+str(runtime/'pytest'),'-q','-ra','--tb=short','--ci-scope=backend',
               '--ci-shard-index='+str(index),'--ci-shard-count=2','--ci-coverage-dir='+str(receipt),
               '--junitxml='+str(receipt/'backend.xml')]
    record={'evidence_boundary':'Local native WSL/Linux Python 3.12.3; NOT hosted GitHub Actions',
            'start_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
            'python_version':platform.python_version(),'arguments':arguments,'timeout_seconds':3300,
            'identity_environment':identity,'database':url,'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),
            'source_files_fingerprint_sha256':args.fingerprint,'font_sha256':hashlib.sha256(font.read_bytes()).hexdigest()}
    (receipt/'local-run.json').write_text(json.dumps(record,indent=2)+'\n')
    started=time.monotonic()
    with (receipt/'backend.log').open('wb') as output:
        process=subprocess.Popen(arguments,cwd=project,env=environment,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        print('STARTED PostgreSQL shard',index,'pid',process.pid,'receipt',receipt,flush=True)
        try:
            code=process.wait(timeout=3300)
            record['timed_out']=False
        except subprocess.TimeoutExpired:
            record['timed_out']=True
            os.killpg(process.pid,signal.SIGTERM)
            try: code=process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                code=process.wait()
    record.update(elapsed_seconds=round(time.monotonic()-started,3),process_exitcode=code,
                  end_utc=datetime.now(timezone.utc).isoformat())
    (receipt/'local-run.json').write_text(json.dumps(record,indent=2)+'\n')
    destination=export_root/receipt.name
    shutil.copytree(receipt,destination,dirs_exist_ok=True)
    print('FINISHED PostgreSQL shard',index,json.dumps(record),flush=True)
    return code

with ThreadPoolExecutor(max_workers=2) as executor:
    results=list(executor.map(run_shard,(0,1)))
raise SystemExit(any(results))
