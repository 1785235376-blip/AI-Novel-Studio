import {useEffect,useRef,useState} from 'react';
import {ApiError} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
import type {CreativeDocument} from './types';
import type {ScreenplayDownload} from './client';
type Props={document:CreativeDocument;available:boolean;isCurrent:()=>boolean;request:(source:CreativeDocument,signal?:AbortSignal)=>Promise<ScreenplayDownload>;onDenied:()=>void};
export function DirectorSheetExportPanel(props:Props){
 const alive=useRef(true),pending=useRef<AbortController>(),live=useRef(props);live.current=props;
 const key=JSON.stringify([props.document.id,props.document.version,props.available,props.isCurrent()]);
 const owner=useRef({key,request:props.request,token:{}});
 if(owner.current.key!==key||owner.current.request!==props.request){pending.current?.abort();pending.current=undefined;owner.current={key,request:props.request,token:{}};}
 const token=owner.current.token,[state,setState]=useState<{token:object;busy?:boolean;error?:string;done?:boolean}>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;pending.current?.abort();};},[]);
 const current=()=>alive.current&&owner.current.token===token&&live.current.available&&live.current.isCurrent();
 async function download(){if(!current()||pending.current)return;const abort=new AbortController();pending.current=abort;setState({token,busy:true});
  try{const result=await props.request(props.document,abort.signal);if(!current()||abort.signal.aborted)return;downloadPortableBlob(result.blob,result.filename);setState({token,done:true});}
  catch(error){if(current()&&!abort.signal.aborted){setState({token,error:error instanceof ApiError?error.message:'导演调度表导出未完成，原草稿保持不变。'});if(error instanceof ApiError&&[401,403].includes(error.status))live.current.onDenied();}}
  finally{if(pending.current===abort){pending.current=undefined;if(alive.current&&owner.current.token===token)setState(value=>value?.token===token?{...value,busy:false}:value);}}}
 const value=state?.token===token?state:undefined;
 return <section aria-label="导演调度表导出"><p>导出已保存 v{props.document.version} 的场景、调度、摄影与表演规划为 UTF-8 CSV。可能被表格软件解释为公式的文字会加前导单引号；完整原文和来源请保留 JSON。不同表格软件及另存后重开可能改变转义，请勿启用不信任的公式或外部链接。这不是成片或剪辑工程。</p><Button disabled={!props.available||!!value?.busy} onClick={()=>void download()}>导出已保存导演调度 CSV</Button>{value?.busy&&<StatusMessage>正在核对版本并导出导演调度表…</StatusMessage>}{value?.error&&<StatusMessage tone="warning">{value.error}</StatusMessage>}{value?.done&&<StatusMessage>导演调度表摘要校验通过，已发起下载。</StatusMessage>}</section>;
}
