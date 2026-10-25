import { formatTime } from '../i18n'; // [HERMIA-FE-20261025 I18N P1] shared formatters
import { useEffect,useLayoutEffect,useRef,useState } from 'react';
import { Button,StatusMessage } from '../ui/primitives';
import { mediaCanvasDraftKey,readMediaCanvasLocalDraft,serializeMediaCanvasLocalDraft,verifyMediaCanvasRecovery,type MediaCanvasLocalDraft } from './mediaCanvasLocalDraft';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { CanvasDefinition,CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioClient } from './studioClient';
type Props={owner?:StudioGraphDraftOwner;client:StudioClient;active:boolean;denied:boolean;canMutate:boolean;busy:boolean;externalDirty:boolean;
 definition:CanvasDefinition;base?:CanvasViewRecord;dirty:boolean;uncertain:boolean;requestId:string;isCurrent:()=>boolean;
 read:<T>(work:()=>Promise<T>)=>Promise<T>;onBusy:(value:boolean)=>void;onRestore:(snapshot:MediaCanvasLocalDraft,base?:CanvasViewRecord)=>void};
export function useMediaCanvasRecovery(props:Props){
 const key=props.owner?mediaCanvasDraftKey(props.owner):undefined,firstKey=useRef<string>();if(key&&!firstKey.current)firstKey.current=key;
 const allowed=!!key&&key===firstKey.current;
 const [loaded,setLoaded]=useState<string>(),[recovery,setRecovery]=useState<MediaCanvasLocalDraft>(),[notice,setNotice]=useState(''),[error,setError]=useState(''),[savedAt,setSavedAt]=useState(''),[working,setWorking]=useState(false),[confirmed,setConfirmed]=useState<MediaCanvasLocalDraft>();
 const confirmationLive=useRef(confirmed);confirmationLive.current=confirmed;
 const alive=useRef(true),locked=useRef(false),observed=useRef<string|null>(null),live=useRef(props);live.current=props;
 const values=[key,props.client,props.active,props.denied,props.canMutate,props.externalDirty,props.definition,props.base],fence=useRef({values,token:{}});
 if(values.some((value,index)=>!Object.is(value,fence.current.values[index])))fence.current={values,token:{}};
 const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&allowed&&live.current.active&&!live.current.denied&&live.current.isCurrent();
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;props.onBusy(false);};},[]);
 useEffect(()=>{if(!current()||!key||!props.owner||loaded===key)return;try{const raw=localStorage.getItem(key);observed.current=raw;setRecovery(raw?readMediaCanvasLocalDraft(raw,props.owner):undefined);setNotice('');}catch{setNotice('本机媒体草稿无法核对，原缓存保持；当前输入仍只在本页。');}setLoaded(key);},[key,allowed,props.active,props.denied,loaded]);
 useEffect(()=>{if(!current()||!key||!props.owner||loaded!==key||recovery||notice||working||props.externalDirty)return;
  try{if(localStorage.getItem(key)!==observed.current){setNotice('其他页面已更新媒体草稿，未覆盖该缓存；请保留当前页面。');return;}
   if(!props.dirty&&!props.uncertain){if(observed.current!==null)localStorage.removeItem(key);observed.current=null;setSavedAt('');return;}
   const snapshot:MediaCanvasLocalDraft={contract:'studio-media-view-draft/1',owner:props.owner,saved_at:new Date().toISOString(),request_id:props.requestId,
    base:props.base?{id:props.base.id,version:props.base.version,definition_digest:props.base.definition_digest}:null,definition:props.definition,uncertain:props.uncertain};
   const raw=serializeMediaCanvasLocalDraft(snapshot);localStorage.setItem(key,raw);observed.current=raw;setSavedAt(snapshot.saved_at);
  }catch{setNotice('本机媒体草稿未能保存，请保留页面；服务端仍需明确保存。');}
 },[key,allowed,loaded,recovery,notice,working,props.active,props.denied,props.definition,props.base,props.dirty,props.uncertain,props.requestId,props.externalDirty]);
 const canRestore=current()&&!!recovery&&props.canMutate&&!props.busy&&!props.externalDirty&&!props.dirty&&!props.uncertain&&!working&&(!props.base||props.base.id===recovery.base?.id);
 async function restore(){if(!canRestore||!recovery||!key||locked.current)return;const candidate=recovery,raw=observed.current;locked.current=true;props.onBusy(true);setWorking(true);setError('');
  try{const base=await props.read(()=>verifyMediaCanvasRecovery(props.client,candidate,current));if(!current())return;if(localStorage.getItem(key)!==raw)throw new Error('其他页面已更新缓存，未采用旧草稿。');props.onRestore(candidate,base);setRecovery(undefined);setConfirmed(undefined);}
  catch(reason){if(current())setError(reason instanceof Error?reason.message:'媒体草稿未恢复。');}
  finally{locked.current=false;if(alive.current){props.onBusy(false);setWorking(false);}}
 }
 function discard(){if(!current()||!key||!recovery||confirmed!==recovery||confirmationLive.current!==recovery||locked.current)return;try{if(localStorage.getItem(key)!==observed.current)throw new Error();localStorage.removeItem(key);observed.current=null;setRecovery(undefined);setConfirmed(undefined);setError('');setNotice('');}catch{setError('缓存已变化或不能清除，未删除其他页面的草稿。');}}
 const panel=!props.active||props.denied?null:<section aria-label="本机媒体画布恢复">
  {!allowed&&<StatusMessage>身份和项目代次尚未核对，媒体画布只保留在本页。</StatusMessage>}{notice&&<StatusMessage tone="warning">{notice}</StatusMessage>}
  {allowed&&!recovery&&!notice&&<p>{savedAt?`媒体画布草稿已保留在本机 · ${formatTime(savedAt, undefined, { timeStyle: 'medium', timeZone: 'Asia/Shanghai', hour12: false })}`:'媒体画布修改可保留在本机；服务端保存仍需明确操作。'} 不保存媒体文件或执行许可。</p>}
  {allowed&&recovery&&<><p>发现本机媒体草稿：{recovery.definition.title} · {recovery.definition.cards.length} 张卡片。恢复会重新核对项目代次、服务端版本和每个素材引用。</p>
   {recovery.uncertain&&<StatusMessage tone="warning">上次保存结果未知。恢复后仍保持禁止重复保存，需要核对服务端记录。</StatusMessage>}
   <Button disabled={!canRestore} onClick={()=>void restore()}>核对并恢复本机媒体草稿</Button>
   <label><input type="checkbox" checked={confirmed===recovery} disabled={working} onChange={e=>{if(current()){confirmationLive.current=e.target.checked?recovery:undefined;setConfirmed(confirmationLive.current);}}}/>确认放弃此本机媒体恢复草稿</label><Button disabled={working||confirmed!==recovery} onClick={discard}>放弃本机媒体恢复草稿</Button></>}
  {working&&<StatusMessage>正在核对原画布和素材权限…</StatusMessage>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
 </section>;
 return{panel,working};
}
