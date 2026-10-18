import { checkedModelClay, type ModelClayExport } from './studioModelClayContract';
import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { checkedModelDepth, modelDepthBlob, type ModelDepthCamera, type ModelDepthExport } from './studioModelDepthContract';
import { modelReferenceError } from './studioModelReferenceContract';
import type { StudioAsset } from './studioClient';
export type ModelDepthRequest=(asset:StudioAsset,camera:ModelDepthCamera,signal:AbortSignal)=>Promise<ModelDepthExport>;
export type ModelClayRequest=(asset:StudioAsset,camera:ModelDepthCamera,signal:AbortSignal)=>Promise<ModelClayExport>;
type Props={scope:object;asset:StudioAsset;yaw:number;pitch:number;disabled:boolean;canExport?:boolean;isCurrent:()=>boolean}&({kind?:'depth';request:ModelDepthRequest}|{kind:'clay';request:ModelClayRequest});
export function StudioModelDepthExport(props:Props){
 const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256,props.yaw,props.pitch,props.kind||'depth',props.disabled,props.canExport===true,props.isCurrent()]);
 const owner=useRef({scope:props.scope,key,token:{}}),active=useRef<AbortController>(),alive=useRef(true),live=useRef(props);live.current=props;
 if(owner.current.scope!==props.scope||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};}
 const token=owner.current.token;
 const [state,setState]=useState<{token:object;pending?:boolean;error?:string;done?:boolean;preview?:Blob}>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const current=()=>alive.current&&owner.current.token===token&&live.current.isCurrent()&&!live.current.disabled&&live.current.canExport===true;
 async function download(previewOnly=false){if(!current()||active.current)return;const abort=new AbortController();active.current=abort;setState({token,pending:true});
  try{const camera={yaw:props.yaw,pitch:props.pitch},asset=structuredClone(props.asset);const result=await props.request(asset,camera,abort.signal);if(!current()||abort.signal.aborted)return;const checked=props.kind==='clay'?await checkedModelClay(result,asset,camera):await checkedModelDepth(result,asset,camera);if(!current()||abort.signal.aborted)return;if(previewOnly){setState({token,preview:modelDepthBlob(checked)});return;}downloadPortableBlob(modelDepthBlob(checked),`scene-${props.kind==='clay'?'clay':'depth'}-${asset.id}.png`);setState({token,done:true});}
  catch(reason){if(current()&&!abort.signal.aborted)setState({token,error:modelReferenceError(reason,props.kind==='clay'?'灰模图导出失败，可明确重试。':'深度图导出失败，可明确重试。')});}
  finally{if(active.current===abort){active.current=undefined;if(alive.current&&owner.current.token===token)setState(value=>value?.token===token?{...value,pending:false}:value);}}
 }
 if(!props.isCurrent())return null;
 const visible=state?.token===token?state:undefined,clay=props.kind==='clay';
 function downloadPreview(){if(!current()||active.current||!visible?.preview)return;downloadPortableBlob(visible.preview,`scene-${clay?'clay':'depth'}-${props.asset.id}.png`);setState({...visible,done:true});}
 return <section aria-label={clay?'静态场景灰模参考导出':'静态场景深度参考导出'}><p>{clay?'256 × 192 正交灰模参考：白色背景，双面平面头灯明暗，真实逐像素遮挡。无材质、纹理、阴影或物理灯光；不调用模型，不创建正式图片资产。':'256 × 192 正交深度参考：背景为 0，远处为 1，近处为 255。按当前场景归一化，不是物理距离、姿态估计或最终渲染；不调用模型，不创建正式图片资产。'}</p><Button disabled={props.disabled||props.canExport!==true||!!visible?.pending} onClick={()=>void download()}>{clay?'导出当前视角灰模参考 PNG':'导出当前视角深度参考 PNG'}</Button><Button disabled={props.disabled||props.canExport!==true||!!visible?.pending} onClick={()=>void download(true)}>{clay?'预览当前视角灰模 PNG':'预览当前视角深度 PNG'}</Button>{visible?.preview&&<><DiagnosticPreview blob={visible.preview} label={clay?'已校验的灰模参考 PNG':'已校验的深度参考 PNG'}/><Button disabled={props.disabled||props.canExport!==true||!!visible.pending} onClick={downloadPreview}>下载这张已校验的预览</Button><Button onClick={()=>{if(current()&&!active.current)setState(undefined);}}>关闭 PNG 预览</Button></>}{visible?.pending&&<StatusMessage>{clay?'正在校验原素材并计算灰模参考…':'正在校验原素材并计算深度参考…'}</StatusMessage>}{visible?.error&&<StatusMessage tone="warning">{visible.error}</StatusMessage>}{visible?.done&&<StatusMessage>PNG 校验通过，已发起下载。</StatusMessage>}</section>;
}

function DiagnosticPreview({blob,label}:{blob:Blob;label:string}){
 const [url,setUrl]=useState<string>();
 useEffect(()=>{const next=URL.createObjectURL(blob);setUrl(next);return()=>URL.revokeObjectURL(next);},[blob]);
 return url?<figure><img src={url} alt={label} width={256} height={192}/><figcaption>{label} · 256 × 192，仅当前会话；没有创建素材或调用模型。</figcaption></figure>:null;
}
