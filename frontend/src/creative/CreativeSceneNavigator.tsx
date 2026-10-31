import {useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Button} from '../ui/primitives';
import type {CreativeInput} from './types';
type Props={draft:CreativeInput;selectedId?:string;busy:boolean;onSelect:(id:string)=>void};
const fold=(text:string)=>text.normalize('NFKC').toLowerCase();
/** Read-only local navigation over the already-visible original document. */
export function CreativeSceneNavigator(props:Props){
 const [queryState,setQueryState]=useState<{draft:CreativeInput;value:string}>(),alive=useRef(true),live=useRef(props);live.current=props;
 const owner=useRef({draft:props.draft,busy:props.busy,token:{}});if(owner.current.draft!==props.draft||owner.current.busy!==props.busy)owner.current={draft:props.draft,busy:props.busy,token:{}};const token=owner.current.token;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const query=queryState?.draft===props.draft?queryState.value:'';
 const setQuery=(value:string)=>setQueryState({draft:props.draft,value});
 const index=useMemo(()=>props.draft.scenes.map(scene=>({scene,text:fold([scene.id,String(scene.sequence),scene.heading,scene.location,scene.time,scene.emotion,scene.action,...scene.characters,...scene.dialogue.flatMap(row=>Object.values(row).filter(v=>typeof v==='string')),...scene.director_notes.map(n=>n.note),...props.draft.director_notes.filter(n=>n.scene_id===scene.id).flatMap(n=>[n.note,n.blocking,n.performance,n.emotion,n.pacing])].join('\n'))})),[props.draft.scenes,props.draft.director_notes]);
 const terms=fold(query.trim()).split(/\s+/).filter(Boolean),matches=index.filter(row=>terms.every(term=>row.text.includes(term)));
 const current=()=>alive.current&&!live.current.busy&&owner.current.token===token;
 return <section aria-label="场景导航与筛选"><label>搜索当前文档场景<input type="search" maxLength={200} value={query} disabled={props.busy} onChange={event=>{if(current())setQuery(event.target.value);}}/></label><Button disabled={props.busy||!query} onClick={()=>{if(current())setQuery('');}}>清除场景筛选</Button><p aria-live="polite">匹配 {matches.length} / {index.length} 个场景。搜索标题、地点、时间、人物、动作、对白和导演调度；不会修改文档或自动切换场景。</p>
 {query.trim()&&props.selectedId&&!matches.some(row=>row.scene.id===props.selectedId)&&<p>当前选中场景未匹配，正文仍保留在下方。</p>}
 <div className="creative-scene-strip" aria-label="场景选择">{matches.map(({scene})=><button type="button" key={scene.id} disabled={props.busy} aria-pressed={props.selectedId===scene.id} onClick={()=>{if(current()&&live.current.draft.scenes.some(row=>row.id===scene.id))live.current.onSelect(scene.id);}}><small>SCENE {String(scene.sequence).padStart(2,'0')}</small><strong>{scene.heading}</strong></button>)}</div>
 </section>;
}
