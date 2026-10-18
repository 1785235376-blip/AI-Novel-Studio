import {useEffect,useMemo,useRef,useState} from 'react';
import {apiErrorView} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
import {createModelCenterClient} from './modelCenterClient';
import {bailianHostPreview,type BailianPresetCatalog} from './bailianPresetContract';
import type {ModelCenterPanelProps} from './modelCenterTypes';
type Props=Pick<ModelCenterPanelProps,'projectId'|'transport'|'scope'|'identity'|'active'|'denied'|'busy'|'isCurrent'|'read'>;
export function BailianPresetPanel(props:Props){
 const scopeKey=JSON.stringify(props.scope),key=JSON.stringify([props.projectId,props.identity,scopeKey,props.active,props.denied]);
 const client=useMemo(()=>{try{return createModelCenterClient(props.projectId,props.transport,props.scope);}catch{return undefined;}},[props.projectId,props.transport,scopeKey]);
 const owner=useRef({client,key,token:{}}),active=useRef<AbortController>(),alive=useRef(true),latest=useRef(props);latest.current=props;
 if(owner.current.client!==client||owner.current.key!==key){active.current?.abort();active.current=undefined;owner.current={client,key,token:{}};}const token=owner.current.token;
 const [state,setState]=useState<{token:object;catalog?:BailianPresetCatalog;pending?:boolean;error?:string;region:string;model:string}>();
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;active.current?.abort();};},[]);
 const current=()=>alive.current&&owner.current.token===token&&latest.current.active&&!latest.current.denied&&!latest.current.busy&&latest.current.isCurrent();
 async function read(){if(!current()||active.current||!client)return;const abort=new AbortController();active.current=abort;setState({token,pending:true,region:'',model:''});try{const catalog=await props.read(()=>client.bailianPresets(abort.signal));if(current()&&!abort.signal.aborted)setState({token,catalog,region:'',model:''});}catch(reason){if(current()&&!abort.signal.aborted)setState({token,region:'',model:'',error:apiErrorView(reason,'百炼预设读取失败。').message});}finally{if(active.current===abort){active.current=undefined;if(alive.current&&owner.current.token===token)setState(v=>v?.token===token?{...v,pending:false}:v);}}}
 if(!props.active||props.denied||!props.isCurrent())return null;
 const visible=state?.token===token?state:undefined,catalog=visible?.catalog,selected=catalog?.regions.find(r=>r.id===visible?.region),preview=catalog?bailianHostPreview(catalog,visible!.region,visible!.model):undefined;
 function change(field:'region'|'model',value:string){if(!current()||active.current)return;setState(s=>s?.token===token?{...s,[field]:value}:s);}
 return <section aria-label="百炼文本连接预设"><h3>阿里百炼 · 文本连接预设</h3><p>只准备原主机启动配置提示，不应用配置、不注册或验证模型、不接收密钥、不调用云端。</p><Button disabled={!client||props.busy||!!visible?.pending} onClick={()=>void read()}>明确读取百炼文本预设</Button>{!client&&<StatusMessage tone="warning">当前项目上下文无效，预设读取已停用。</StatusMessage>}{visible?.pending&&<StatusMessage>正在读取内置预设…</StatusMessage>}{visible?.error&&<StatusMessage tone="warning">{visible.error}</StatusMessage>}{catalog&&<><label>百炼 API 地区<select disabled={props.busy} value={visible!.region} onChange={e=>change('region',e.target.value)}><option value="">按实际 API 账户选择地区</option>{catalog.regions.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select></label><label>百炼文本模型 ID<input disabled={props.busy} maxLength={200} value={visible!.model} placeholder="填写控制台实际可用的模型 ID" onChange={e=>change('model',e.target.value)}/></label>{selected&&<p>标准共享 Base URL：{selected.base_url}</p>}<p>此处使用标准按量 API，地区与凭据须匹配；Coding / Token Plan 不属于此预设。只准备非思考文本请求，未验证所填模型是否支持。</p>{preview?<label>手动主机配置预览（未应用）<textarea readOnly value={preview}/></label>:<StatusMessage>选择地区并填写有效模型 ID 后显示配置提示。模型 ID 不接受空格、引号或控制字符。</StatusMessage>}<p>配置仍通过原主机与凭据入口完成；本面板不显示当前配置或密钥状态，也不会改变本地／云端偏好。实际云端调用需要另行核对发送内容、授权和费用。</p><a href={catalog.official_reference} target="_blank" rel="noreferrer">查看百炼官方地区与计费计划说明</a></>}</section>;
}
