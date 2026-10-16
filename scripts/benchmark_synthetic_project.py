"""Bounded, synthetic-only authoring/extraction/export benchmark.

Creates a new temporary File profile and removes only that owned fixture.
It never reads an existing novel directory, database or provider credential.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import tempfile
import time
import tracemalloc
from pathlib import Path
from dataclasses import replace
from app.config import settings

from app.repository import FileRepository
from app.repositories.factory import create_repository_bundle
from app.services.novel_service import NovelService
from app.knowledge_extraction import extract_knowledge_candidates


def run(chapter_count=200, characters_per_chapter=5000):
    if not 1 <= chapter_count <= 500 or not 100 <= characters_per_chapter <= 20000:
        raise ValueError("benchmark bounds exceeded")
    started=time.perf_counter();tracemalloc.start()
    with tempfile.TemporaryDirectory(prefix='ai-novel-r2-synthetic-') as directory:
        bundle=create_repository_bundle(replace(settings,storage_backend='file'), data_root=Path(directory))
        service=NovelService(bundle.novels,bundle.chapters)
        novel=service.create({'id':'synthetic-scale','title':'R2 synthetic performance fixture'})
        base='林默说道：“这是合成测试，不是真实文稿。”他们来到云港。秘密只是测试标记。\n'
        body=(base*((characters_per_chapter//len(base))+1))[:characters_per_chapter]
        for index in range(chapter_count):
            bundle.chapters.create(novel['id'],{'title':f'合成第{index+1}章','content':body})
        created=time.perf_counter()
        chapters=bundle.chapters.list(novel['id'])
        candidates=extract_knowledge_candidates(chapters)
        extracted=time.perf_counter()
        snapshot=service.export_snapshot(novel['id'])
        result=service.export_snapshot_result(snapshot,'txt')
        text=str(result.get('content',''))
        assert '合成第1章' in text and f'合成第{chapter_count}章' in text
        reread=bundle.chapters.list(novel['id'])
        assert len(reread)==chapter_count
        finished=time.perf_counter();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        return {'synthetic_only':True,'backend':'file','platform':platform.system(),'python':platform.python_version(),
            'chapters':chapter_count,'requested_characters_per_chapter':characters_per_chapter,
            'actual_characters':sum(len(x['content']) for x in chapters),'candidate_count':sum(map(len,candidates.values())),
            'create_seconds':round(created-started,3),'extract_seconds':round(extracted-created,3),
            'snapshot_export_reopen_seconds':round(finished-extracted,3),'total_seconds':round(finished-started,3),
            'python_tracemalloc_peak_bytes':peak,'export_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'external_model_calls':0,'performance_acceptance':'MEASURED_ONLY; no universal hardware target asserted'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--chapters',type=int,default=200);parser.add_argument('--characters',type=int,default=5000)
    args=parser.parse_args();print(json.dumps(run(args.chapters,args.characters),ensure_ascii=False,indent=2))
