import { KeyRound, Plug, ShieldCheck } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./PluginInspector.css";

export type PluginInspection = { id:string; name:string; version?:string; status?:string; capabilities?:string[]; requestedPermissions?:string[]; grantedPermissions?:string[]; executionSupported?:boolean; sandbox?:string; isolation?:string };
export function PluginInspector({inspection}:{inspection?:PluginInspection}){
  if(!inspection)return <section className="plugin-inspector" aria-label="插件检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="未选择插件" detail="从插件治理列表选择一个 manifest 以查看能力与权限。"/></section>;
  const active=inspection.status==='MANIFEST_ACTIVE';
  return <section className="plugin-inspector" aria-label="插件检查面板"><div className="workspace-inspector__eyebrow">Plugin Inspector</div><header><Plug aria-hidden="true"/><div><strong>{inspection.name}</strong><span>{inspection.id}{inspection.version?` · v${inspection.version}`:''}</span></div><Badge tone={active?'success':'warning'}>{active?'清单已激活':inspection.status||'待审核'}</Badge></header><div className="plugin-inspector__boundary"><ShieldCheck aria-hidden="true" size={15}/><span>代码执行：{inspection.executionSupported?'允许运行':'当前禁止'} · 沙箱：{inspection.sandbox||'未读取'}</span></div><dl className="plugin-inspector__facts"><div><dt>能力</dt><dd>{inspection.capabilities?.join('、')||'无'}</dd></div><div><dt>请求权限</dt><dd>{inspection.requestedPermissions?.join('、')||'无'}</dd></div><div><dt>已授予</dt><dd>{inspection.grantedPermissions?.join('、')||'无'}</dd></div><div><dt>隔离策略</dt><dd>{inspection.isolation||'未读取'}</dd></div></dl><p className="novel-help">密钥、插件代码和运行时响应不会在此面板展示。</p></section>;
}
