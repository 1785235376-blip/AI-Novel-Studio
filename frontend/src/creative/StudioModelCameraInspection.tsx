import {useEffect,useRef,useState} from 'react';
import {ApiError} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
import type {StudioAsset} from './studioClient';
import {modelReferenceError} from './studioModelReferenceContract';
import {checkedModelCameras,checkedModelCameraExport,modelCameraBlob,modelCameraSelection,type ModelCameras,type ModelCameraExport,type ModelCameraSelection} from './studioModelCameraContract';

export type ModelCameraRead=(asset:StudioAsset,signal:AbortSignal)=>Promise<ModelCameras>;
export type ModelCameraRequest=(asset:StudioAsset,selection:ModelCameraSelection,signal:AbortSignal)=>Promise<ModelCameraExport>;
type Props={scope:object;asset:StudioAsset;disabled:boolean;canExport?:boolean;isCurrent:()=>boolean;read:ModelCameraRead;request?:ModelCameraRequest};
type State={token:object;review?:ModelCameras;selected:string;pending?:'read'|'export';error?:string;done?:boolean};
function cameraError(reason:unknown,fallback:string):string {
  const messages:Record<string,string>={
    MODEL_REFERENCE_GLB_CAMERA_NONRIGID_UNSUPPORTED:'源相机或祖先节点含缩放、反射或非刚性变换，当前不能交换；未自动修正源数据。',
    MODEL_REFERENCE_GLB_CAMERA_LIMIT:'源相机数量超过 64 个实例或定义的上限，未返回部分相机。',
    MODEL_REFERENCE_GLB_CAMERA_INVALID:'源相机投影参数不受支持，未返回部分相机。',
    MODEL_REFERENCE_GLB_CAMERA_NAME_INVALID:'源相机标签过长或含控制字符，请在源文件中修正。',
    MODEL_REFERENCE_GLB_CAMERA_INDEX_INVALID:'源相机节点引用无效，请在源文件中修正。',
    MODEL_REFERENCE_GLB_CAMERA_EXTENSION_UNSUPPORTED:'源相机含不支持的扩展，未忽略扩展或近似转换。',
    MODEL_REFERENCE_GLB_CAMERA_SELECTION_CHANGED:'默认场景已变化，请重新读取并明确选择源相机。',
    MODEL_REFERENCE_GLB_CAMERA_SELECTION_INVALID:'所选相机不在当前场景中，请重新读取并选择。',
    MODEL_REFERENCE_GLB_CAMERA_EXPORT_LIMIT:'相机交换文件超过 64 KiB 上限，未下载部分文件。',
  };
  const code=reason instanceof ApiError?reason.problem.code:'';
  return Object.hasOwn(messages,code)?messages[code]:modelReferenceError(reason,fallback);
}

export function StudioModelCameraInspection(props:Props) {
  const key=JSON.stringify([props.asset.id,props.asset.version,props.asset.sha256,props.asset.novel_id,props.asset.branch_id,props.asset.kind,props.asset.media_type,props.asset.size,props.asset.deleted_at,props.disabled,props.canExport===true,props.isCurrent()]);
  const owner=useRef({scope:props.scope,key,token:{}}),active=useRef<AbortController>(),alive=useRef(true),live=useRef(props);live.current=props;
  if(owner.current.scope!==props.scope || owner.current.key!==key) {
    active.current?.abort();active.current=undefined;owner.current={scope:props.scope,key,token:{}};
  }
  const token=owner.current.token;
  const [state,setState]=useState<State>();
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
  const current=()=>alive.current && owner.current.token===token && live.current.isCurrent() && !live.current.disabled;
  const visible=state?.token===token?state:undefined;
  const inspection=visible?.review?.camera_inspection;
  const selected=inspection?.instances.find(camera=>String(camera.node_index)===visible?.selected);

  async function inspect() {
    if(!current() || active.current) return;
    const abort=new AbortController(),source=structuredClone(props.asset);active.current=abort;setState({token,selected:'',pending:'read'});
    try {
      const result=await props.read(structuredClone(source),abort.signal);
      if(!current() || abort.signal.aborted) return;
      const review=checkedModelCameras(result,source);
      setState({token,selected:'',review});
    } catch(reason) {
      if(current() && !abort.signal.aborted) setState({token,selected:'',error:cameraError(reason,'源相机读取失败，未返回部分相机。')});
    } finally {
      if(active.current===abort) {active.current=undefined;if(current()) setState(value=>value?.token===token?{...value,pending:undefined}:value);}
    }
  }
  function select(value:string) {
    if(!current() || !visible?.review || value!=='' && !inspection?.instances.some(camera=>String(camera.node_index)===value)) return;
    active.current?.abort();active.current=undefined;
    setState({token,review:visible.review,selected:value});
  }
  async function download() {
    if(!current() || active.current || live.current.canExport!==true || !props.request || !visible?.review || !selected) return;
    const abort=new AbortController(),source=structuredClone(props.asset),review=visible.review,selectedValue=visible.selected;
    active.current=abort;setState({token,review,selected:selectedValue,pending:'export'});
    try {
      const choice=modelCameraSelection(review,source,selected.node_index);
      const result=await props.request(structuredClone(source),structuredClone(choice),abort.signal);
      if(!current() || abort.signal.aborted || live.current.canExport!==true) return;
      const checked=await checkedModelCameraExport(result,source,choice);
      if(!current() || abort.signal.aborted || live.current.canExport!==true) return;
      downloadPortableBlob(modelCameraBlob(checked),`source-camera-${source.id}-node-${choice.camera.node_index}.gltf`);
      setState({token,review,selected:selectedValue,done:true});
    } catch(reason) {
      if(current() && !abort.signal.aborted) setState({token,review,selected:selectedValue,error:cameraError(reason,'源相机导出失败，可明确重试。')});
    } finally {
      if(active.current===abort) {active.current=undefined;if(current()) setState(value=>value?.token===token?{...value,pending:undefined}:value);}
    }
  }
  if(!props.isCurrent()) return null;
  return <section aria-label="GLB 源相机检查与交换">
    <h4>静态源相机 · glTF 交换</h4>
    <p>明确读取默认场景或唯一场景中的源相机，仅支持刚性节点层级。保留世界矩阵、米制右手 Y 向上坐标和原始投影；不归一化、不居中、不使用诊断视角。</p>
    <Button disabled={props.disabled || !!visible?.pending} onClick={()=>void inspect()}>明确读取 GLB 源相机</Button>
    {inspection && <>
      <p>场景 {inspection.scene_index}（{inspection.scene_selection==='DECLARED_DEFAULT'?'声明的默认场景':'唯一场景'}）· {inspection.camera_definition_count} 个相机定义 · {inspection.instances.length} 个当前场景相机实例</p>
      {inspection.instances.length===0?<StatusMessage>当前场景没有源相机实例。请在源 GLB 中添加相机后重新导入；不会自动创建或选取诊断相机。</StatusMessage>:<>
        <label>选择源相机实例<select value={visible?.selected??''} disabled={props.disabled} onChange={event=>select(event.target.value)}>
          <option value="">明确选择相机节点</option>
          {inspection.instances.map(camera=><option key={camera.node_index} value={camera.node_index}>节点 {camera.node_index} · {camera.node_name||'未命名节点'} / 相机 {camera.camera_index} · {camera.camera_name||'未命名相机'} · {camera.projection.type==='perspective'?'透视':'正交'}</option>)}
        </select></label>
        {selected && <section aria-label="已选择的源相机参数">
          <p>原素材 {props.asset.id} · v{props.asset.version} · 节点 {selected.node_index} · 相机定义 {selected.camera_index}</p>
          {selected.projection.type==='perspective'?<>
            <p>透视：垂直视场 {selected.projection.yfov} 弧度；近裁剪 {selected.projection.znear} 米；远裁剪 {selected.projection.zfar===null?'未指定，保留无限远':`${selected.projection.zfar} 米`}</p>
            <p>宽高比：{selected.projection.aspectRatio===null?'源文件未指定，取决于目标视口':selected.projection.aspectRatio}</p>
          </>:<p>正交：水平半宽 {selected.projection.xmag} 米；垂直半高 {selected.projection.ymag} 米；近裁剪 {selected.projection.znear} 米；远裁剪 {selected.projection.zfar} 米</p>}
          <details><summary>核对列主序世界矩阵</summary><p>{selected.world_matrix.join(', ')}</p></details>
        </section>}
        <Button disabled={props.disabled || props.canExport!==true || !props.request || !selected || !!visible?.pending} onClick={()=>void download()}>导出所选源相机 glTF</Button>
        {props.canExport!==true && <p>当前没有手动导出权限；仍可只读检查源相机。</p>}
      </>}
    </>}
    <p>导出仅含所选相机的 glTF 2.0 文件与来源记录，不含网格、材质或动画。Blender 目标画面取景可能不同；尚未实现 UE 原生相机导入。Blender 与 Unreal 的目标导入验收均未运行。不创建素材、任务或调用模型。</p>
    {visible?.pending && <StatusMessage>{visible.pending==='read'?'正在读取原素材的静态源相机…':'正在校验所选相机与 glTF 文件…'}</StatusMessage>}
    {visible?.error && <StatusMessage tone="warning">{visible.error}</StatusMessage>}
    {visible?.done && <StatusMessage>源相机 glTF 校验通过，已发起下载；目标软件导入尚未验收。</StatusMessage>}
  </section>;
}
