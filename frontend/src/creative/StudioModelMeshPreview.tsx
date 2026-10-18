import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { checkedModelMeshPreview, checkedModelScenePreview, modelReferenceError, type ModelMeshPreview, type ModelScenePreview } from './studioModelReferenceContract';
import { meshFacePoints, modelMeshSvg, projectModelMesh } from './modelMeshProjection';
import type { StudioAsset } from './studioClient';
type Props={scope:object;asset:StudioAsset;disabled:boolean;canExport?:boolean;isCurrent:()=>boolean;read:(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelMeshPreview>;readScene?:(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelScenePreview>};
export function StudioModelMeshPreview(props:Props){
 const [space,setSpace]=useState<'mesh'|'scene'>('mesh');
 const [state,setState]=useState<{token:object;value?:ModelMeshPreview|ModelScenePreview;error?:string;pending?:boolean}>(),[yaw,setYaw]=useState(35),[pitch,setPitch]=useState(25),[wire,setWire]=useState(true);
 const alive=useRef(true),active=useRef<AbortController>();const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256,space]);
 const owner=useRef({scope:props.scope,key,token:{}});if(owner.current.scope!==props.scope||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};}const token=owner.current.token;
 const live=useRef(props);live.current=props;const current=()=>alive.current&&owner.current.token===token&&live.current.isCurrent();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const receipt=state?.token===token?state.value:undefined,pending=state?.token===token&&!!state.pending;
 const faces=useMemo(()=>receipt?projectModelMesh(receipt,yaw,pitch):[],[receipt,yaw,pitch]);const rendered=useRef({faces,wire});rendered.current={faces,wire};
 async function read(){if(!current()||props.disabled||active.current||space==='scene'&&!props.readScene)return;const abort=new AbortController();active.current=abort;setState({token,pending:true});
  try{const result=space==='scene'?await props.readScene!(props.asset,abort.signal):await props.read(props.asset,abort.signal);if(current()&&!abort.signal.aborted)setState({token,value:space==='scene'?checkedModelScenePreview(result,props.asset):checkedModelMeshPreview(result,props.asset)});}
  catch(reason){if(current()&&!abort.signal.aborted)setState({token,error:modelReferenceError(reason,'网格诊断读取失败。')});}
  finally{if(active.current===abort){active.current=undefined;if(current())setState(value=>value?.token===token?{...value,pending:false}:value);}}
 }
 if(!props.isCurrent())return null;
 return <section aria-label="GLB 网格局部诊断视图"><h4>{space==='scene'?'静态场景诊断视图':'网格局部诊断视图'}</h4><p>正交线框或灰阶示意，最多 4096 个位置、2048 个三角形。{space==='scene'?'应用默认或唯一场景的节点层级与静态变换，不含材质、纹理和动画。':'不应用节点变换、材质、纹理或动画。'}遮挡排序近似，不是最终场景渲染。</p>
  <label>诊断坐标空间<select value={space} disabled={props.disabled} onChange={e=>{if(current()&&!live.current.disabled&&(e.target.value==='mesh'||e.target.value==='scene'&&live.current.readScene))setSpace(e.target.value as 'mesh'|'scene');}}><option value="mesh">网格局部（原始位置）</option><option value="scene" disabled={!props.readScene}>静态场景（节点变换后）</option></select></label>
  <Button disabled={props.disabled||pending} onClick={()=>void read()}>{space==='scene'?'明确读取 GLB 静态场景':'明确读取 GLB 网格诊断'}</Button>{pending&&<StatusMessage>正在读取原素材的有限几何…</StatusMessage>}{state?.token===token&&state.error&&<StatusMessage tone="warning">{state.error}</StatusMessage>}
  {receipt&&<><label>诊断水平视角<input type="range" min={-180} max={180} value={yaw} disabled={props.disabled||pending} onChange={event=>{if(current())setYaw(Number(event.target.value));}}/></label><label>诊断俯仰视角<input type="range" min={-89} max={89} value={pitch} disabled={props.disabled||pending} onChange={event=>{if(current())setPitch(Number(event.target.value));}}/></label>
   <label><input type="checkbox" checked={wire} disabled={props.disabled||pending} onChange={event=>{if(current())setWire(event.target.checked);}}/>线框显示（关闭后为灰阶示意）</label>
   <svg role="img" aria-label={space==='scene'?'实际 GLB 静态场景几何示意':'实际 GLB 网格局部几何示意'} viewBox="0 0 512 384" width="100%" height="384"><title>{space==='scene'?'静态场景诊断，不含材质与动画':'网格局部诊断，不含场景变换与材质'}</title>{faces.map((face,index)=><polygon key={index} points={meshFacePoints(face)} fill={wire?'none':`rgb(${face.shade},${face.shade},${face.shade})`} stroke="currentColor" strokeWidth="0.7"/>)}</svg>
   <Button disabled={props.disabled||pending||props.canExport!==true} onClick={()=>{if(!current()||live.current.disabled||live.current.canExport!==true||active.current||rendered.current.faces!==faces||rendered.current.wire!==wire)return;try{downloadPortableBlob(new Blob([modelMeshSvg(faces,wire,space==='scene')],{type:'image/svg+xml'}),`${space}-diagnostic-${props.asset.id}.svg`);}catch{setState({token,value:receipt,error:'诊断图下载未完成，可明确重试。'});}}}>{space==='scene'?'下载当前场景诊断 SVG':'下载当前网格诊断 SVG'}</Button>
   <p>导出仅含这些数值几何和当前视角，不会创建正式图片资产或改写模型；不是 PNG、视频帧或最终画面。</p>
  </>}
 </section>;
}
