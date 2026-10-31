import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {previewSourceBoundsRepair} from './timelineSourceBoundsRepair';
import type {TimelineSourceBounds} from './studioTimelineSourceBounds';
import type {StudioTimelineDraft,StudioTimelineRow} from './studioTimelineTypes';
type Props={scope:object;source:StudioTimelineRow;draft:StudioTimelineDraft;observation:TimelineSourceBounds;disabled:boolean;isCurrent:()=>boolean;getRevision:()=>string;onApply:(next:StudioTimelineDraft)=>boolean};
export function StudioTimelineSourceBoundsRepair(props:Props){
 const alive=useRef(true),consentRef=useRef<object>();
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;consentRef.current=undefined;};},[]);
 const live=useRef(props);live.current=props;const revision=props.getRevision(),key=JSON.stringify([revision,props.source.id,props.source.version,props.source.timeline_digest,props.observation,props.disabled,props.isCurrent()]);
 const owner=useRef({scope:props.scope,key,token:{}});if(owner.current.scope!==props.scope||owner.current.key!==key)owner.current={scope:props.scope,key,token:{}};const token=owner.current.token;
 const [consent,setConsent]=useState<object>(),[error,setError]=useState<{token:object;text:string}>();
 let preview:ReturnType<typeof previewSourceBoundsRepair>|undefined,reason='';try{preview=previewSourceBoundsRepair(props.draft,props.source,props.observation);}catch(value){reason=value instanceof Error?value.message:'当前片段不能直接收短。';}
 const current=()=>alive.current&&owner.current.token===token&&live.current.isCurrent()&&!live.current.disabled&&live.current.getRevision()===revision;
 if(!props.isCurrent()||props.observation.within_source)return null;
 if(!preview)return <StatusMessage tone="warning">{reason}</StatusMessage>;
 return <section aria-label="实测出点修正预览"><p>片段 {preview.clipId} 的素材出点：{preview.before} → {preview.after} ms。只收短本片段，其他片段、字幕和素材文件不变；不会自动保存。</p>
 <label><input type="checkbox" checked={consent===token} disabled={props.disabled} onChange={event=>{if(current()){consentRef.current=event.target.checked?token:undefined;setConsent(consentRef.current);}}}/>确认仅收短出点，保留其他位置</label>
 <Button disabled={props.disabled||consent!==token} onClick={()=>{if(!current()||consent!==token||consentRef.current!==token)return;consentRef.current=undefined;setConsent(undefined);try{const next=previewSourceBoundsRepair(live.current.draft,live.current.source,live.current.observation);if(!live.current.onApply(next.draft))setError({token,text:'当前输入或权限已改变，未应用修正。'});}catch(value){setError({token,text:value instanceof Error?value.message:'未应用修正。'});}}}>将实测出点应用到本地草稿</Button>
 {error?.token===token&&<StatusMessage tone="warning">{error.text}</StatusMessage>}
 </section>;
}
