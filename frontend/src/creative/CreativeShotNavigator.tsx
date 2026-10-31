import {useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Button} from '../ui/primitives';
import type {CreativeInput} from './types';
type Props={draft:CreativeInput;selectedId?:string;busy:boolean;onSelect:(shotId:string,sceneId:string)=>void};
const fold=(value:string)=>value.normalize('NFKC').toLowerCase();
export function CreativeShotNavigator(props:Props){
 const [queryState,setQueryState]=useState<{draft:CreativeInput;value:string}>(),alive=useRef(true),live=useRef(props);live.current=props;
 const owner=useRef({draft:props.draft,busy:props.busy,token:{}});if(owner.current.draft!==props.draft||owner.current.busy!==props.busy)owner.current={draft:props.draft,busy:props.busy,token:{}};const token=owner.current.token;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const query=queryState?.draft===props.draft?queryState.value:'';
 const setQuery=(value:string)=>setQueryState({draft:props.draft,value});
 const index=useMemo(()=>props.draft.shots.map(shot=>({shot,scene:props.draft.scenes.find(s=>s.id===shot.scene_id),text:fold([shot.id,String(shot.number),shot.frame_prompt,shot.action,shot.shot_size,shot.camera_angle,shot.camera_motion,shot.lens,shot.emotion,shot.sound,shot.sound_effect,...(shot.characters||[]),...shot.dialogue.flatMap(d=>Object.values(d).filter(v=>typeof v==='string')),props.draft.scenes.find(s=>s.id===shot.scene_id)?.heading].join('\n'))})),[props.draft.shots,props.draft.scenes]);
 const terms=fold(query.trim()).split(/\s+/).filter(Boolean),rows=index.filter(r=>terms.every(t=>r.text.includes(t)));
 const current=()=>alive.current&&!live.current.busy&&owner.current.token===token;
 return <section aria-label="镜头导航与筛选"><label>搜索当前文档镜头<input type="search" maxLength={200} value={query} disabled={props.busy} onChange={e=>{if(current())setQuery(e.target.value);}}/></label><Button disabled={props.busy||!query} onClick={()=>{if(current())setQuery('');}}>清除镜头筛选</Button><p aria-live="polite">匹配 {rows.length} / {index.length} 个镜头；只定位镜头及所属场景，不修改顺序或内容。</p>
 {query.trim()&&props.selectedId&&!rows.some(r=>r.shot.id===props.selectedId)&&<p>当前镜头未匹配，原镜头预览仍保留。</p>}
 <div className="creative-scene-strip">{rows.map(({shot,scene})=><button key={shot.id} type="button" disabled={props.busy||!scene} aria-pressed={shot.id===props.selectedId} onClick={()=>{if(current()&&live.current.draft.shots.some(s=>s.id===shot.id&&s.scene_id===shot.scene_id)&&live.current.draft.scenes.some(s=>s.id===shot.scene_id))live.current.onSelect(shot.id,shot.scene_id);}}><strong>定位镜头 {shot.number} · {scene?.heading||'场景待核对'}</strong><small>{Array.from(shot.frame_prompt||shot.action||'尚无画面描述').slice(0,80).join('')}</small></button>)}</div>
 </section>;
}
