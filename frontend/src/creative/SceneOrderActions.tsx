import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import type {CreativeInput} from './types';
import {moveAuthorScene} from './sceneOrdering';
type Props={draft:CreativeInput;sceneId:string;disabled:boolean;onChange:(draft:CreativeInput)=>void};
export function SceneOrderActions(props:Props){
 const live=useRef(props);live.current=props;const alive=useRef(true);
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const owner=useRef({draft:props.draft,sceneId:props.sceneId,disabled:props.disabled,token:{}});
 if(owner.current.draft!==props.draft||owner.current.sceneId!==props.sceneId||owner.current.disabled!==props.disabled)owner.current={draft:props.draft,sceneId:props.sceneId,disabled:props.disabled,token:{}};
 const token=owner.current.token,[error,setError]=useState<{token:object;text:string}>();
 const rows=[...props.draft.scenes].sort((a,b)=>a.sequence-b.sequence),index=rows.findIndex(row=>row.id===props.sceneId);
 const apply=(direction:'earlier'|'later')=>{if(!alive.current||live.current.disabled||owner.current.token!==token)return;try{const next=moveAuthorScene(props.draft,props.sceneId,direction);if(next!==props.draft)live.current.onChange(next);}catch(reason){setError({token,text:reason instanceof Error?reason.message:'场景排序未完成。'});}};
 return <section aria-label="当前场景排序"><div className="creative-actions"><Button disabled={props.disabled||index<=0} onClick={()=>apply('earlier')}>前移当前场景</Button><Button disabled={props.disabled||index<0||index>=rows.length-1} onClick={()=>apply('later')}>后移当前场景</Button></div><p>只调整本地剧本或导演场景顺序，保留场景 ID、文字与调度关联；仍需保存，不自动改排已生成的分镜或时间线。</p>{error?.token===token&&<StatusMessage tone="warning">{error.text}</StatusMessage>}</section>;
}
