import {useEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import type {StudioAsset} from './studioClient';
import {checkedModelMaterials,type ModelMaterials} from './studioModelMaterialsContract';
import {modelReferenceError} from './studioModelReferenceContract';
export type ModelMaterialRead=(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelMaterials>;
type Props={scope:object;asset:StudioAsset;disabled:boolean;isCurrent:()=>boolean;read:ModelMaterialRead};
export function StudioModelMaterialInspection(props:Props){
 const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256]);const owner=useRef({scope:props.scope,key,token:{}}),active=useRef<AbortController>(),alive=useRef(true),latest=useRef(props);latest.current=props;
 if(owner.current.scope!==props.scope||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};}const token=owner.current.token;
 const [state,setState]=useState<{token:object;value?:ModelMaterials;error?:string;pending?:boolean}>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const current=()=>alive.current&&owner.current.token===token&&latest.current.isCurrent();
 async function inspect(){if(!current()||latest.current.disabled||active.current)return;const abort=new AbortController();active.current=abort;setState({token,pending:true});try{const result=await props.read(props.asset,abort.signal);if(current()&&!abort.signal.aborted&&!latest.current.disabled)setState({token,value:checkedModelMaterials(result,props.asset)});}catch(reason){if(current()&&!abort.signal.aborted)setState({token,error:modelReferenceError(reason,'材质数值读取失败。')});}finally{if(active.current===abort){active.current=undefined;if(current())setState(v=>v?.token===token?{...v,pending:false}:v);}}}
 if(!props.isCurrent())return null;const visible=state?.token===token?state:undefined;const data=visible?.value?.material_inspection;
 return <section aria-label="GLB 材质数值检查"><h4>材质数值与绑定</h4><p>只读线性基础颜色、金属度、粗糙度及透明模式；缺省字段按 glTF 默认值显示。纹理仅显示声明，不加载、校验或渲染。</p><Button disabled={props.disabled||!!visible?.pending} onClick={()=>void inspect()}>明确读取 GLB 材质数值</Button>{visible?.pending&&<StatusMessage>正在读取原素材的材质数值…</StatusMessage>}{visible?.error&&<StatusMessage tone="warning">{visible.error}</StatusMessage>}{data&&<><p>{data.materials.length} 个声明材质 · {data.primitive_bindings.length} 个网格图元绑定。未指定材质的图元采用 glTF 默认材质；这不是最终视觉效果。</p><ul>{data.materials.map(m=><li key={m.index}><details><summary>材质 {m.index} · {m.name||'未命名'}</summary><p>基础 RGBA（线性）：{m.base_color_factor.join(', ')}；金属度：{m.metallic_factor}；粗糙度：{m.roughness_factor}</p><p>自发光因子：{m.emissive_factor.join(', ')}；透明模式：{m.alpha_mode}；截断值：{m.alpha_cutoff}（仅 MASK 使用）；双面：{m.double_sided?'是':'否'}</p><p>声明纹理槽：{m.declared_texture_slots.join(', ')||'无'}</p></details></li>)}</ul><details><summary>核对网格图元与材质绑定</summary><ul>{data.primitive_bindings.map(b=><li key={`${b.mesh_index}:${b.primitive_index}`}>网格 {b.mesh_index} / 图元 {b.primitive_index} → {b.material_index===null?'默认材质':`材质 ${b.material_index}`}</li>)}</ul></details></>}</section>;
}
