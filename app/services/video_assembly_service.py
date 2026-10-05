"""Local-only, bounded video cut assembly from verified project assets."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4
from ..media_files import inspect_media, MediaValidationError
from ..repository import now
from ..storage import atomic_write


class VideoAssemblyService:
    def __init__(self, root, assets):
        self.root=Path(root)/'video-assemblies';self.assets=assets;self._active=set()

    def _scope_dir(self, novel_id, branch_id, actor_id):
        return self.root/hashlib.sha256(json.dumps([novel_id,branch_id,actor_id]).encode()).hexdigest()

    def list(self,novel_id,branch_id,actor_id):
        rows=sorted([json.loads(path.read_text()) for path in self._scope_dir(novel_id,branch_id,actor_id).glob('*.json')],key=lambda row:row['created_at'],reverse=True)
        return [{**row,'recoverable':row.get('status')=='RUNNING' and row['id'] not in self._active} for row in rows]

    def create(self,novel_id,branch_id,actor_id,screenplay_id,clips):
        if not 1<=len(clips)<=30:raise ValueError('select between 1 and 30 video clips')
        decoder=shutil.which('ffmpeg')
        if not decoder:raise MediaValidationError('MEDIA_VALIDATOR_NOT_CONFIGURED')
        verified=[];total=0
        for clip in clips:
            asset=self.assets.get(clip['asset_id'],branch_id=branch_id)
            if asset['novel_id']!=novel_id or not asset['media_type'].startswith('video/'):raise ValueError('video asset does not belong to this project and branch')
            data=self.assets.content(asset['id'],branch_id=branch_id);measured=inspect_media(data,'video')
            start=int(clip.get('start_ms') or 0);end=int(clip.get('end_ms') or measured['duration_ms'])
            if start<0 or end<=start or end>measured['duration_ms']:raise ValueError('clip trim is outside measured media duration')
            total+=end-start
            if total>600000:raise ValueError('assembly exceeds the ten-minute limit')
            verified.append((data,{**clip,'start_ms':start,'end_ms':end,'source_sha256':asset['sha256'],'source_version':asset.get('version',1)}))
        job={'id':str(uuid4()),'novel_id':novel_id,'branch_id':branch_id,'owner_actor_id':actor_id,'screenplay_id':screenplay_id,'status':'RUNNING','created_at':now(),'updated_at':now(),'audio_policy':'VIDEO_ONLY','clips':[row for _,row in verified],'requested_duration_ms':total}
        path=self._scope_dir(novel_id,branch_id,actor_id)/(job['id']+'.json');atomic_write(path,json.dumps(job,ensure_ascii=False));self._active.add(job['id'])
        try:
            with tempfile.TemporaryDirectory(prefix='novel-video-cut-') as directory:
                directory=Path(directory);command=[decoder,'-nostdin','-v','error','-xerror','-threads','1'];filters=[]
                for index,(data,clip) in enumerate(verified):
                    source=directory/f'clip-{index}.bin';source.write_bytes(data)
                    command+=['-protocol_whitelist','file,pipe','-i',str(source)]
                    # Fixed review rendition; originals are retained byte-for-byte.
                    filters.append(f"[{index}:v:0]trim=start={clip['start_ms']/1000}:end={clip['end_ms']/1000},setpts=PTS-STARTPTS,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{index}]")
                filters.append(''.join(f'[v{index}]' for index in range(len(verified)))+f'concat=n={len(verified)}:v=1:a=0[out]')
                output=directory/'assembly.mp4';command+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','mpeg4','-q:v','4','-fs',str(self.assets.MAX_BYTES+1),'-y',str(output)]
                subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120,check=True)
                data=output.read_bytes()
                if len(data)>self.assets.MAX_BYTES:raise MediaValidationError('assembled video exceeds asset limit')
                measured=inspect_media(data,'video')
                # Rounding to 24 fps may alter the end by one frame per segment.
                if abs(measured['duration_ms']-total)>50*len(verified):raise MediaValidationError('assembled duration differs from requested trims')
                asset=self.assets.create(novel_id,f"assembly-{job['id']}.mp4",base64.b64encode(data).decode(),'video/mp4','video','video-assembly:'+job['id'],branch_id=branch_id)
                asset=self.assets.update_metadata(asset['id'],{'source_job_id':job['id'],'source_asset_ids':list(dict.fromkeys(clip['asset_id'] for _,clip in verified))},branch_id=branch_id)
                job.update(status='SUCCEEDED',asset_id=asset['id'],duration_ms=measured['duration_ms'],sha256=asset['sha256'],updated_at=now(),render_profile='REVIEW_640x360_24FPS_VIDEO_ONLY')
        except Exception:
            job.update(status='FAILED',error='VIDEO_ASSEMBLY_FAILED',updated_at=now())
        try:atomic_write(path,json.dumps(job,ensure_ascii=False,indent=2))
        finally:self._active.discard(job['id'])
        return job
