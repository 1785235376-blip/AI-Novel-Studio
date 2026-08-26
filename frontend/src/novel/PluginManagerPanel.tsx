import { useEffect, useMemo, useState } from "react";
import { CircleOff, Plug, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Badge, Button, EmptyState, Panel, StatusMessage } from "../ui/primitives";
import "./PluginManagerPanel.css";
import type {PluginInspection} from "./PluginInspector";

export type DiscoveredPlugin = { path: string; error?: string; manifest?: { id: string; name: string; version: string; capabilities?: string[]; requested_permissions?: string[] } };
export type RegisteredPlugin = { id: string; name: string; version?: string; status?: string; requested_permissions?: string[]; granted_permissions?: string[] };
const statusLabel = (status?: string) => status === "MANIFEST_ACTIVE" ? "清单已激活" : status === "DISABLED" ? "已停用" : "待审核";

export function PluginManagerPanel({onInspect}:{onInspect?:(inspection?:PluginInspection)=>void} = {}) {
  const [items, setItems] = useState<DiscoveredPlugin[]>([]);
  const [registered, setRegistered] = useState<RegisteredPlugin[]>([]);
  const [health, setHealth] = useState<any>();
  const [runtime, setRuntime] = useState<any>();
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState("");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string }>();
  const refresh = async () => {
    setLoading(true); setMessage(undefined);
    try {
      const [found, current, status, runtimeStatus] = await Promise.all([api.discoverPlugins(), api.plugins(), api.multimodalHealth(), api.pluginRuntimeStatus()]);
      setItems(found.items || []); setRegistered(current.items || []); setHealth(status); setRuntime(runtimeStatus);
    } catch { setMessage({ tone: "error", text: "插件状态读取失败，请检查本地服务后重新扫描。" }); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);
  const visibleItems = useMemo(() => { const value = query.trim().toLocaleLowerCase(); return value ? items.filter((item) => [item.manifest?.name, item.manifest?.id, item.path].filter(Boolean).some((field) => String(field).toLocaleLowerCase().includes(value))) : items; }, [items, query]);
  const runAction = async (key: string, success: string, action: () => Promise<unknown>) => {
    setPending(key); setMessage(undefined);
    try { await action(); await refresh(); setMessage({ tone: "success", text: success }); }
    catch { setMessage({ tone: "error", text: "操作未完成。权限、插件版本或本地服务状态可能已变化，请刷新后重试。" }); }
    finally { setPending(""); }
  };
  const activeCount = registered.filter((item) => item.status === "MANIFEST_ACTIVE").length;
  const inspect=(item:any)=>onInspect?.({id:item.id,name:item.name,version:item.version,status:item.status,capabilities:item.capabilities,requestedPermissions:item.requested_permissions,grantedPermissions:item.granted_permissions,executionSupported:runtime?.execution_supported,sandbox:runtime?.sandbox,isolation:runtime?.isolation});
  return <Panel title="插件治理" className="plugin-manager" actions={<Button variant="ghost" loading={loading} onClick={refresh}><RefreshCw aria-hidden="true" size={15}/>{loading ? "扫描中" : "重新扫描"}</Button>}>
    <div className="plugin-manager__summary" aria-label="插件状态摘要"><div><span>本地发现</span><strong>{items.length}</strong></div><div><span>已注册</span><strong>{registered.length}</strong></div><div><span>清单激活</span><strong>{activeCount}</strong></div><div><span>代码执行</span><strong>{runtime?.execution_supported ? "允许" : "禁止"}</strong></div></div>
    <section className="plugin-manager__runtime" aria-labelledby="plugin-runtime-title"><div><h3 id="plugin-runtime-title">运行边界</h3><p>插件默认拒绝权限。当前激活仅表示清单可用，不代表插件代码能够执行。</p></div><dl><div><dt>沙箱</dt><dd>{runtime?.sandbox || "未读取"}</dd></div><div><dt>隔离策略</dt><dd>{runtime?.isolation || "未读取"}</dd></div><div><dt>图片 Provider</dt><dd>{health ? health.image_providers?.length || 0 : "未读取"}</dd></div><div><dt>视频配置</dt><dd>{health ? health.video_provider_configs || 0 : "未读取"}</dd></div></dl></section>
    {message && <StatusMessage tone={message.tone}>{message.text}</StatusMessage>}
    <section className="plugin-manager__section" aria-labelledby="discovered-title"><header><div><h3 id="discovered-title">本地发现</h3><p>扫描本地插件目录并验证 manifest，注册不会自动授权。</p></div><label className="plugin-manager__search"><Search aria-hidden="true" size={15}/><span className="sr-only">筛选本地插件</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="筛选名称、ID 或路径"/></label></header>
      {!visibleItems.length && !loading ? <EmptyState title={query ? "没有匹配的插件" : "未发现本地插件"} detail={query ? "调整筛选条件后重试。" : "将有效插件放入本地插件目录，然后重新扫描。"}/> : <div className="plugin-manager__rows">{visibleItems.map((item, index) => { const manifest = item.manifest; const isRegistered = manifest && registered.some((plugin) => plugin.id === manifest.id); return <article className="plugin-manager__row" key={`${item.path}-${index}`}><div className="plugin-manager__identity"><Plug aria-hidden="true" size={17}/><div><strong>{manifest?.name || "无效插件"}</strong><span title={item.path}>{item.path}</span></div></div>{item.error ? <p className="plugin-manager__error" role="alert">{item.error}</p> : <><div className="plugin-manager__meta"><span>v{manifest?.version}</span><span>{manifest?.capabilities?.length || 0} 项能力</span><span>{manifest?.requested_permissions?.length || 0} 项权限请求</span></div><Button variant="ghost" disabled={Boolean(isRegistered)} loading={pending === `register:${manifest?.id}`} onClick={() => manifest && runAction(`register:${manifest.id}`, `${manifest.name} 已注册，权限仍保持默认拒绝。`, () => api.registerPlugin(manifest))}>{isRegistered ? "已注册" : "注册"}</Button></>}</article>; })}</div>}
    </section>
    <section className="plugin-manager__section" aria-labelledby="registered-title"><header><div><h3 id="registered-title">已注册插件</h3><p>审核权限后才能激活清单；运行时执行策略仍独立生效。</p></div></header>
      {!registered.length ? <EmptyState title="暂无已注册插件" detail="从本地发现列表选择一个有效插件进行注册。"/> : <div className="plugin-manager__rows">{registered.map((item) => { const requested = item.requested_permissions || []; const granted = item.granted_permissions || []; const reviewed = requested.length === granted.length && requested.every((permission) => granted.includes(permission)); const active = item.status === "MANIFEST_ACTIVE"; return <article className="plugin-manager__row plugin-manager__row--registered" key={item.id}><button type="button" className="plugin-manager__identity plugin-manager__identity--select" onClick={()=>inspect(item)} aria-label={`检查插件 ${item.name}`}>{reviewed ? <ShieldCheck aria-hidden="true" size={17}/> : <CircleOff aria-hidden="true" size={17}/>}<div><strong>{item.name}</strong><span>{item.id}{item.version ? ` · v${item.version}` : ""}</span></div></button><Badge tone={active ? "success" : reviewed ? "info" : "warning"}>{statusLabel(item.status)}</Badge><div className="plugin-manager__permissions"><span>请求权限</span><strong>{requested.join("、") || "无"}</strong></div>{!reviewed && <Button variant="ghost" loading={pending === `review:${item.id}`} onClick={() => runAction(`review:${item.id}`, `${item.name} 的权限已审核。`, () => api.setPluginPermissions(item.id, { granted_permissions: requested, reviewed_by: "local-user", note: "本地用户明确授权" }))}>审核并授权</Button>}{reviewed && !active && <Button loading={pending === `enable:${item.id}`} onClick={() => runAction(`enable:${item.id}`, `${item.name} 的清单已激活。`, () => api.enablePlugin(item.id))}>激活清单</Button>}{active && <Button variant="ghost" loading={pending === `disable:${item.id}`} onClick={() => runAction(`disable:${item.id}`, `${item.name} 已停用。`, () => api.disablePlugin(item.id))}>停用</Button>}</article>; })}</div>}
    </section>
  </Panel>;
}
