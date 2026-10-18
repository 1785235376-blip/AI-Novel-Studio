import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { checkedModelDepth, modelDepthBlob, type ModelDepthCamera, type ModelDepthExport } from './studioModelDepthContract';
import { modelReferenceError } from './studioModelReferenceContract';
import type { StudioAsset } from './studioClient';
export type ModelDepthRequest=(asset:StudioAsset,camera:ModelDepthCamera,signal:AbortSignal)=>Promise<ModelDepthExport>;
type Props={scope:object;asset:StudioAsset;yaw:number;pitch:number;disabled:boolean;canExport?:boolean;isCurrent:()=>boolean;request:ModelDepthRequest};
export function StudioModelDepthExport(props:Props){
 const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256,props.yaw,props.pitch]);
 const owner=useRef({scope:props.scope,key,token:{}}),active=useRef<AbortController>(),alive=useRef(true),live=useRef(props);live.current=props;
 if(owner.current.scope!==props.scope||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};}
 const token=owner.current.token;
 const [state,setState]=useState<{token:object;pending?:boolean;error?:string;done?:boolean}>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const current=()=>alive.current&&owner.current.token===token&&live.current.isCurrent()&&!live.current.disabled&&live.current.canExport===true;
 async function download(){if(!current()||active.current)return;const abort=new AbortController();active.current=abort;setState({token,pending:true});
  try{const camera={yaw:props.yaw,pitch:props.pitch},asset=structuredClone(props.asset);const result=await props.request(asset,camera,abort.signal);if(!current()||abort.signal.aborted)return;const checked=await checkedModelDepth(result,asset,camera);if(!current()||abort.signal.aborted)return;downloadPortableBlob(modelDepthBlob(checked),`scene-depth-${asset.id}.png`);setState({token,done:true});}
  catch(reason){if(current()&&!abort.signal.aborted)setState({token,error:modelReferenceError(reason,'深度图导出失败，可明确重试。')});}
  finally{if(active.current===abort){active.current=undefined;if(alive.current&&owner.current.token===token)setState(value=>value?.token===token?{...value,pending:false}:value);}}
 }
 if(!props.isCurrent())return null;
 const visible=state?.token===token?state:undefined;
 return <section aria-label="静态场景深度参考导出"><p>256 × 192 正交深度参考：背景为 0，远处为 1，近处为 255。按当前场景归一化，不是物理距离、姿态估计或最终渲染；不调用模型，不创建正式图片资产。</p><Button disabled={props.disabled||props.canExport!==true||!!visible?.pending} onClick={()=>void download()}>导出当前视角深度参考 PNG</Button>{visible?.pending&&<StatusMessage>正在校验原素材并计算深度参考…</StatusMessage>}{visible?.error&&<StatusMessage tone="warning">{visible.error}</StatusMessage>}{visible?.done&&<StatusMessage>PNG 校验通过，已发起下载。</StatusMessage>}</section>;
}
