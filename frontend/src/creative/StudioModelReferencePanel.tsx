import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import { MODEL_REFERENCE_MAX_BYTES, checkedModelReferenceInspection, type ModelReferenceInspection } from './studioModelReferenceContract';
type Input={filename:string;content_base64:string};
type Props={scope:object;assets:StudioAsset[];blocked:boolean;canImport:boolean;isCurrent:()=>boolean;onImport:(input:Input)=>Promise<StudioAsset>;onInspect:(asset:StudioAsset)=>Promise<ModelReferenceInspection>};
export function StudioModelReferencePanel(props:Props){
 const [input,setInput]=useState<Input>(),[selected,setSelected]=useState(''),[pending,setPending]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[unknown,setUnknown]=useState(false);
 const [receipt,setReceipt]=useState<{scope:object;asset:StudioAsset;value:ModelReferenceInspection}>();
 const fileInput=useRef<HTMLInputElement>(null);
 const live=useRef(props);live.current=props;const alive=useRef(true),busy=useRef(false),epoch=useRef(0),selection=useRef(0);
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;};},[]);
 useLayoutEffect(()=>{epoch.current++;selection.current++;busy.current=false;setPending(false);setInput(undefined);setSelected('');setReceipt(undefined);setUnknown(false);setError('');setNotice('');if(fileInput.current)fileInput.current.value='';},[props.scope]);
 const current=()=>alive.current&&live.current.scope===props.scope&&live.current.isCurrent();
 const asset=props.assets.find(row=>row.id===selected&&row.kind==='model'&&!row.deleted_at);
 const visible=receipt&&receipt.scope===props.scope&&asset&&receipt.asset.id===asset.id&&receipt.asset.version===asset.version&&receipt.asset.sha256===asset.sha256?receipt.value:undefined;
 async function choose(file?:File){
  if(!current()||busy.current||props.blocked||!props.canImport||unknown)return;
  setInput(undefined);setError('');setNotice('');if(!file)return;
  if(!file.name.toLowerCase().endsWith('.glb')||!file.size||file.size>MODEL_REFERENCE_MAX_BYTES){setError('请选择不超过 8 MiB 的 GLB 文件；不支持外部资源、动画、骨骼或压缩扩展。');return;}
  const ticket=++epoch.current;busy.current=true;setPending(true);
  try{const bytes=new Uint8Array(await file.arrayBuffer());if(!current()||ticket!==epoch.current)return;if(bytes.byteLength!==file.size)throw new Error('文件长度已变化。');let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));setInput({filename:file.name,content_base64:btoa(binary)});}
  catch{if(current()&&ticket===epoch.current)setError('文件读取失败，未上传。');}finally{if(ticket===epoch.current){busy.current=false;if(alive.current)setPending(false);}}
 }
 async function upload(){
  if(!current()||busy.current||props.blocked||!props.canImport||!input)return;
  const ticket=++epoch.current;busy.current=true;setPending(true);setError('');setNotice('');
  try{const result=await props.onImport(input);if(!current()||ticket!==epoch.current)return;setUnknown(false);setInput(undefined);if(fileInput.current)fileInput.current.value='';setSelected(result.id);selection.current++;setReceipt(undefined);setNotice('GLB 文件已保存。可明确读取几何检查；许可与来源声明请在原素材面板核对。');}
  catch(reason){if(current()&&ticket===epoch.current){setUnknown(!(reason instanceof ApiError && reason.status===422));setError(apiErrorView(reason,'导入结果未确认。请核对素材目录；重试沿用同一请求，不会自动发送。').message);}}
  finally{if(ticket===epoch.current){busy.current=false;if(alive.current)setPending(false);}}
 }
 async function inspect(){
  if(!current()||busy.current||props.blocked||!asset)return;const chosen=asset,ticket=++epoch.current,selectionTicket=selection.current;busy.current=true;setPending(true);setError('');setReceipt(undefined);
  try{const value=await props.onInspect(chosen);const latest=live.current.assets.find(row=>row.id===chosen.id&&!row.deleted_at);if(current()&&ticket===epoch.current&&selectionTicket===selection.current&&latest?.version===chosen.version&&latest.sha256===chosen.sha256)setReceipt({scope:props.scope,asset:chosen,value:checkedModelReferenceInspection(value,chosen)});}
  catch(reason){if(current()&&ticket===epoch.current)setError(apiErrorView(reason,'几何检查失败，未生成预览。').message);}finally{if(ticket===epoch.current){busy.current=false;if(alive.current)setPending(false);}}
 }
 if(!props.isCurrent())return null;
 return <Panel title="3D 参考素材 · 静态 GLB"><p>仅导入嵌入式、未压缩三角网格 GLB，最多 8 MiB。不需要模型或 FFmpeg。当前提供原文件保存和网格局部几何检查；还没有三维视口、节点变换、材质预览、帧导出或生成执行。</p>
  <label>选择静态 GLB 文件<input ref={fileInput} type="file" accept=".glb,model/gltf-binary" disabled={props.blocked||pending||!props.canImport||unknown} onChange={event=>void choose(event.target.files?.[0])}/></label>
  {input&&<><p>待保存：{input.filename}。仅选择文件尚未上传。</p><Button disabled={props.blocked||pending||!props.canImport} onClick={()=>void upload()}>{unknown?'使用同一请求重试 GLB 导入':'明确导入并保存 GLB 参考素材'}</Button><Button disabled={pending||props.blocked} onClick={()=>{if(current()&&!busy.current){epoch.current++;setInput(undefined);if(fileInput.current)fileInput.current.value='';setUnknown(false);setNotice(unknown?'已结束本地输入；先前文件是否保存仍须核对素材目录。':'已清除本地文件选择。');}}}>清除本地 GLB 输入</Button></>}
  <label>已保存 GLB 参考<select value={selected} disabled={props.blocked||pending} onChange={event=>{if(current()&&!busy.current){selection.current++;setSelected(event.target.value);setReceipt(undefined);setError('');}}}><option value="">明确选择原素材版本</option>{props.assets.filter(row=>row.kind==='model'&&!row.deleted_at).map(row=><option key={row.id} value={row.id}>{row.filename} · v{row.version}</option>)}</select></label>
  <Button disabled={props.blocked||pending||!asset} onClick={()=>void inspect()}>读取当前 GLB 几何检查</Button>
  {pending&&<StatusMessage>正在处理明确选择的 GLB 操作…</StatusMessage>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}{notice&&<StatusMessage>{notice}</StatusMessage>}
  {visible&&<section aria-label="GLB 原素材几何回执"><p>原素材 {visible.asset_snapshot.id} · v{visible.asset_snapshot.version} · {visible.inspection.byte_count} 字节</p><p>{visible.inspection.mesh_count} 个网格 · {visible.inspection.primitive_count} 个图元 · 按图元计 {visible.inspection.position_count_per_primitive} 个位置、{visible.inspection.triangle_count_per_primitive} 个三角形</p><p>网格局部包围盒：[{visible.inspection.bounds.min.join(', ')}] 至 [{visible.inspection.bounds.max.join(', ')}]</p><p>未应用场景节点变换，不是实例化后的场景总量；不代表完整 glTF 合规、许可授权或渲染验收。原文件下载与来源声明继续使用现有素材入口。</p></section>}
 </Panel>;
}
