import type {ModelClayExport} from './studioModelClayContract';
import { StudioModelDepthExport, type ModelDepthRequest, type ModelClayRequest } from './StudioModelDepthExport';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { checkedModelMeshPreview, checkedModelScenePreview, modelReferenceError, type ModelMeshPreview, type ModelScenePreview } from './studioModelReferenceContract';
import { meshFacePoints, modelMeshSvg, projectModelMesh } from './modelMeshProjection';
import { modelSceneHighlightFaces, modelSceneStructure } from './studioModelSceneStructure';
import type { StudioAsset } from './studioClient';
type Props={scope:object;asset:StudioAsset;disabled:boolean;canExport?:boolean;canSaveClay?:boolean;onSaveClay?:(asset:StudioAsset,review:ModelClayExport)=>Promise<void>;isCurrent:()=>boolean;read:(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelMeshPreview>;onDepth?:ModelDepthRequest;onClay?:ModelClayRequest;readScene?:(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelScenePreview>};
const diagnosticViews=[
 {id:'default',label:'默认斜视',yaw:35,pitch:25},
 {id:'positive-z',label:'+Z 侧',yaw:0,pitch:0},
 {id:'negative-z',label:'−Z 侧',yaw:180,pitch:0},
 {id:'negative-x',label:'−X 侧',yaw:90,pitch:0},
 {id:'positive-x',label:'+X 侧',yaw:-90,pitch:0},
];
export function StudioModelMeshPreview(props:Props){
 const [space,setSpace]=useState<'mesh'|'scene'>('mesh');
 const [state,setState]=useState<{token:object;value?:ModelMeshPreview|ModelScenePreview;error?:string;pending?:boolean}>(),[view,setView]=useState({yaw:35,pitch:25}),[wire,setWire]=useState(true);
 const {yaw,pitch}=view;
 const alive=useRef(true),active=useRef<AbortController>();const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256,space]);
 const owner=useRef({scope:props.scope,key,token:{}});if(owner.current.scope!==props.scope||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};}const token=owner.current.token;
 const live=useRef(props);live.current=props;const current=()=>alive.current&&owner.current.token===token&&live.current.isCurrent();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const receipt=state?.token===token?state.value:undefined,pending=state?.token===token&&!!state.pending;
 const sceneReceipt=receipt&&'scene_preview' in receipt?receipt:undefined;
 const structure=useMemo(()=>sceneReceipt?modelSceneStructure(sceneReceipt):undefined,[sceneReceipt]);
 const sourceCurrent=props.isCurrent();
 const selectionOwner=useRef({token,receipt,sourceCurrent});
 if(selectionOwner.current.token!==token||selectionOwner.current.receipt!==receipt||selectionOwner.current.sourceCurrent!==sourceCurrent)selectionOwner.current={token,receipt,sourceCurrent};
 const selectionToken=selectionOwner.current;
 const [selection,setSelection]=useState<{owner:object;key:string}>();
 const selectionKey=selection?.owner===selectionToken?selection.key:'all';
 const selected=structure&&[structure.all,...structure.instances,...structure.meshes].find(entry=>entry.key===selectionKey);
 const highlightFaces=useMemo(()=>sceneReceipt?modelSceneHighlightFaces(sceneReceipt,selected,yaw,pitch):[],[sceneReceipt,selected,yaw,pitch]);
 function chooseStructure(key:string){if(!current()||live.current.disabled||active.current||selectionOwner.current!==selectionToken||!structure||![structure.all,...structure.instances,...structure.meshes].some(entry=>entry.key===key))return;setSelection({owner:selectionToken,key});}
 const preset=diagnosticViews.find(value=>value.yaw===yaw&&value.pitch===pitch)?.id??'custom';
 function chooseView(id:string){if(!current()||live.current.disabled||active.current)return;const next=diagnosticViews.find(value=>value.id===id);if(next)setView({yaw:next.yaw,pitch:next.pitch});}
 const faces=useMemo(()=>receipt?projectModelMesh(receipt,yaw,pitch):[],[receipt,yaw,pitch]);const rendered=useRef({faces,wire});rendered.current={faces,wire};
 async function read(){if(!current()||props.disabled||active.current||space==='scene'&&!props.readScene)return;const abort=new AbortController();active.current=abort;setState({token,pending:true});
  try{const result=space==='scene'?await props.readScene!(props.asset,abort.signal):await props.read(props.asset,abort.signal);if(current()&&!abort.signal.aborted)setState({token,value:space==='scene'?checkedModelScenePreview(result,props.asset):checkedModelMeshPreview(result,props.asset)});}
  catch(reason){if(current()&&!abort.signal.aborted)setState({token,error:modelReferenceError(reason,'网格诊断读取失败。')});}
  finally{if(active.current===abort){active.current=undefined;if(current())setState(value=>value?.token===token?{...value,pending:false}:value);}}
 }
 if(!sourceCurrent)return null;
 return <section aria-label="GLB 网格局部诊断视图"><h4>{space==='scene'?'静态场景诊断视图':'网格局部诊断视图'}</h4><p>正交线框或灰阶示意，最多 4096 个位置、2048 个三角形。{space==='scene'?'应用默认或唯一场景的节点层级与静态变换，不含材质、纹理和动画。':'不应用节点变换、材质、纹理或动画。'}遮挡排序近似，不是最终场景渲染。</p>
  <label>诊断坐标空间<select value={space} disabled={props.disabled} onChange={e=>{if(current()&&!live.current.disabled&&(e.target.value==='mesh'||e.target.value==='scene'&&live.current.readScene))setSpace(e.target.value as 'mesh'|'scene');}}><option value="mesh">网格局部（原始位置）</option><option value="scene" disabled={!props.readScene}>静态场景（节点变换后）</option></select></label>
  <Button disabled={props.disabled||pending} onClick={()=>void read()}>{space==='scene'?'明确读取 GLB 静态场景':'明确读取 GLB 网格诊断'}</Button>{pending&&<StatusMessage>正在读取原素材的有限几何…</StatusMessage>}{state?.token===token&&state.error&&<StatusMessage tone="warning">{state.error}</StatusMessage>}
  {receipt&&<><label>诊断方向预设<select value={preset} disabled={props.disabled||pending} onChange={event=>chooseView(event.target.value)}><option value="custom" disabled>自定义视角</option>{diagnosticViews.map(value=><option key={value.id} value={value.id}>{value.label}</option>)}</select></label><Button disabled={props.disabled||pending} onClick={()=>chooseView('default')}>复位诊断视角</Button>
   {sceneReceipt&&structure&&selected&&<section aria-label="静态场景结构检查">
    <h5>场景结构（只读）</h5>
    <p>素材 {sceneReceipt.asset_snapshot.id} · 版本 {sceneReceipt.asset_snapshot.version} · 场景 #{sceneReceipt.scene_preview.scene_index}（{sceneReceipt.scene_preview.selection==='DECLARED_DEFAULT'?'默认场景':'唯一场景'}）</p>
    <p>已遍历 {sceneReceipt.scene_preview.traversed_nodes} 个节点 · {structure.instances.length} 个网格实例 · {structure.meshes.length} 个引用网格</p>
    <label>结构高亮<select value={selected.key} disabled={props.disabled||pending} onChange={event=>chooseStructure(event.target.value)}>
     <option value="all">完整场景（无高亮）</option>
     <optgroup label="节点实例">{structure.instances.map(entry=><option key={entry.key} value={entry.key}>{entry.label}</option>)}</optgroup>
     <optgroup label="网格的全部实例">{structure.meshes.map(entry=><option key={entry.key} value={entry.key}>{entry.label}</option>)}</optgroup>
    </select></label>
    <Button disabled={props.disabled||pending||selected.key==='all'} onClick={()=>chooseStructure('all')}>清除结构高亮</Button>
    <p role="status">{selected.label}：{selected.nodeIndices.length} 个实例 · {selected.primitiveCount} 个图元实例 · {selected.positionCount} 个位置 · {selected.triangleCount} 个三角形</p>
    <p>静态世界包围盒：最小 [{selected.bounds.min.join(', ')}] · 最大 [{selected.bounds.max.join(', ')}]</p>
    <details><summary>图元实例清单（{selected.primitiveCount}）</summary>
     <ul style={{maxHeight:'calc(var(--space-12) * 4)',overflowY:'auto'}}>{selected.primitives.map(primitive=><li key={`${primitive.nodeIndex}:${primitive.primitiveIndex}`}>节点 #{primitive.nodeIndex} · 网格 #{primitive.meshIndex} · 图元 #{primitive.primitiveIndex}：{primitive.positionCount} 个位置 · {primitive.triangleCount} 个三角形</li>)}</ul>
    </details>
    <p>编号从 0 开始。仅列出已验证场景中的几何实例，不含节点名称或父子关系。高亮轮廓用于定位，可能穿过遮挡；SVG、灰模与深度导出仍使用完整场景。</p>
   </section>}
   <p>当前诊断视角：水平 {yaw}° · 俯仰 {pitch}°。方向相对于当前诊断坐标空间，不修改源相机。</p>
   <label>诊断水平视角<input type="range" min={-180} max={180} value={yaw} disabled={props.disabled||pending} onChange={event=>{if(current()&&!live.current.disabled&&!active.current)setView(value=>({...value,yaw:Number(event.target.value)}));}}/></label><label>诊断俯仰视角<input type="range" min={-89} max={89} value={pitch} disabled={props.disabled||pending} onChange={event=>{if(current()&&!live.current.disabled&&!active.current)setView(value=>({...value,pitch:Number(event.target.value)}));}}/></label>
   <label><input type="checkbox" checked={wire} disabled={props.disabled||pending} onChange={event=>{if(current())setWire(event.target.checked);}}/>线框显示（关闭后为灰阶示意）</label>
   <svg role="img" aria-label={space==='scene'?'实际 GLB 静态场景几何示意':'实际 GLB 网格局部几何示意'} viewBox="0 0 512 384" width="100%" height="384"><title>{space==='scene'?'静态场景诊断，不含材质与动画':'网格局部诊断，不含场景变换与材质'}</title>{faces.map((face,index)=><polygon key={index} points={meshFacePoints(face)} fill={wire?'none':`rgb(${face.shade},${face.shade},${face.shade})`} stroke="currentColor" strokeWidth="0.7"/>)}{highlightFaces.length>0&&<g aria-label={`结构高亮：${selected?.label}`} pointerEvents="none">{highlightFaces.map((face,index)=><polygon key={index} points={meshFacePoints(face)} fill="none" stroke="var(--color-selection-border)" strokeWidth="3"/>)}</g>}</svg>
   <Button disabled={props.disabled||pending||props.canExport!==true} onClick={()=>{if(!current()||live.current.disabled||live.current.canExport!==true||active.current||rendered.current.faces!==faces||rendered.current.wire!==wire)return;try{downloadPortableBlob(new Blob([modelMeshSvg(faces,wire,space==='scene')],{type:'image/svg+xml'}),`${space}-diagnostic-${props.asset.id}.svg`);}catch{setState({token,value:receipt,error:'诊断图下载未完成，可明确重试。'});}}}>{space==='scene'?'下载当前场景诊断 SVG':'下载当前网格诊断 SVG'}</Button>
   {space==='scene'&&props.onClay&&<StudioModelDepthExport kind="clay" scope={props.scope} asset={props.asset} yaw={yaw} pitch={pitch} disabled={props.disabled||pending} canExport={props.canExport} isCurrent={current} request={props.onClay} canSave={props.canSaveClay} onSave={props.onSaveClay}/>}
   {space==='scene'&&props.onDepth&&<StudioModelDepthExport scope={props.scope} asset={props.asset} yaw={yaw} pitch={pitch} disabled={props.disabled||pending} canExport={props.canExport} isCurrent={current} request={props.onDepth}/>}
   <p>SVG 导出仅含这些数值几何和当前视角，不会创建正式图片资产或改写模型；不是 PNG、视频帧或最终画面。</p>
  </>}
 </section>;
}
