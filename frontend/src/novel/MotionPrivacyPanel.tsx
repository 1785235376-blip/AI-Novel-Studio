import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,getCollaborationContext} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
export function MotionPrivacyPanel({novelId,screenplayId,taskId}:{novelId?:string;screenplayId?:string;taskId:string}){
 const [record,setRecord]=useState<any>(),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const context=getCollaborationContext(),key=JSON.stringify([novelId,screenplayId,taskId,context.scope?.branchId,context.actor?.id,context.sessionToken]),scope=useRef<string|null>(key);scope.current=key;
 useEffect(()=>{scope.current=key;setRecord(undefined);setError('');setBusy(false);return()=>{scope.current=null}},[key]);
 if(!novelId||!screenplayId)return null;
 const review=async()=>{setBusy(true);setError('');try{const row=await api.motionPrivacy(novelId,screenplayId,taskId);if(scope.current===key)setRecord(row)}catch(reason){if(scope.current===key)setError(apiErrorView(reason,'隐私审核读取失败').message)}finally{if(scope.current===key)setBusy(false)}};
 const update=async(level:string)=>{if(!record||busy)return;setBusy(true);setError('');try{const row=await api.updateMotionPrivacy(novelId,screenplayId,taskId,level,record.prompt_sha256,record.request_sha256);if(scope.current===key)setRecord(row)}catch(reason){if(scope.current===key)setError(apiErrorView(reason,'隐私策略保存失败，请重新审核当前提示。').message)}finally{if(scope.current===key)setBusy(false)}};
 return <section aria-label="视频提示隐私审核"><Button variant="ghost" disabled={busy} onClick={()=>void review()}>审核云端发送内容</Button>{error&&<StatusMessage tone="error">{error}</StatusMessage>}{record&&<><p className="novel-help">当前提示：{record.prompt}</p><p className="novel-help">策略：{record.privacy_level} · 目标：{record.provider_id}/{record.model_id}。允许云端仅适用于这份提示、帧引用与参数；本地参考图继续遵守独立隐私限制。</p><p className="novel-help">帧引用与参数：{JSON.stringify({start_frame:record.start_frame,end_frame:record.end_frame,constraints:record.constraints})}</p><Button disabled={busy||!['PENDING','FAILED','CANCELLED'].includes(record.status)} onClick={()=>void update('CLOUD_ALLOWED')}>允许向所选云 Provider 发送此提示</Button><Button variant="ghost" disabled={busy||!['PENDING','FAILED','CANCELLED'].includes(record.status)} onClick={()=>void update('LOCAL_ONLY')}>仅本地处理</Button></>}</section>;
}
