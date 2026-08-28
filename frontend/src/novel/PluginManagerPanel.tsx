import { useEffect, useMemo, useState } from "react";
import { CircleOff, Plug, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Badge, Button, EmptyState, Panel, StatusMessage } from "../ui/primitives";
import "./PluginManagerPanel.css";
import type { PluginInspection } from "./PluginInspector";

export type PluginManifestSummary = {
  id: string;
  name: string;
  version: string;
  description?: string;
  capabilities?: string[];
  requested_permissions?: string[];
  manifest_version?: string;
  host_api_version?: string;
  execution_mode?: string;
  publisher?: string;
  resources?: Array<{ kind?: string }>;
};

export type DiscoveredPlugin = {
  plugin_dir?: string;
  path?: string;
  error?: string;
  error_code?: string;
  manifest?: PluginManifestSummary;
  resource_count?: number;
  resource_kinds?: string[];
  publisher_trust?: string;
};

export type RegisteredPlugin = {
  id: string;
  name: string;
  version?: string;
  status?: string;
  description?: string;
  capabilities?: string[];
  requested_permissions?: string[];
  granted_permissions?: string[];
  manifest_version?: string;
  host_api_version?: string;
  execution_mode?: string;
  publisher?: string;
  resources?: Array<{ kind?: string }>;
};

export const KIND_LABEL: Record<string, string> = {
  writing_presets: "写作预设",
  workflow_templates: "工作流模板",
  export_profiles: "导出配置",
};

const UNSAFE_PATH = /(?:^[A-Za-z]:[\\/])|(?:^[\\/])|(?:\\\\)|(?:\.\.)|(?:[\\:])/;

export function safePluginDirId(value?: string): string {
  if (!value) return "";
  if (UNSAFE_PATH.test(value)) return "";
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(value)) return "";
  return value;
}

export function safePluginError(item: DiscoveredPlugin): string {
  const text = item.error || "";
  if (/traceback|file "|exception:|[A-Za-z]:[\\/]|stack/i.test(text)) {
    return "插件清单无效，未通过合同校验。";
  }
  if (text) return text;
  if (item.error_code) return "插件清单无效，未通过合同校验。";
  return "";
}

export function publisherLabel(publisher?: string): string {
  const name = String(publisher || "").trim();
  return name ? `${name}（未验证发布者）` : "未声明（未验证发布者）";
}

export function resourceKindsOf(item: { resource_kinds?: string[]; resources?: Array<{ kind?: string }>; manifest?: PluginManifestSummary }): string[] {
  if (item.resource_kinds?.length) return item.resource_kinds;
  const resources = item.resources || item.manifest?.resources || [];
  return Array.from(new Set(resources.map((resource) => resource.kind).filter((kind): kind is string => Boolean(kind))));
}

export function resourceCountOf(item: { resource_count?: number; resources?: Array<unknown>; manifest?: PluginManifestSummary }): number {
  if (typeof item.resource_count === "number") return item.resource_count;
  return (item.resources || item.manifest?.resources || []).length;
}

export function formatResourceKinds(kinds: string[]): string {
  if (!kinds.length) return "无声明式资源";
  return kinds.map((kind) => KIND_LABEL[kind] || "声明式资源").join("、");
}

const statusLabel = (status?: string) =>
  status === "MANIFEST_ACTIVE" ? "清单已激活"
    : status === "DISABLED" ? "已停用"
      : status === "PERMISSIONS_REVIEWED" ? "权限已审核"
        : "待审核";

function isReviewed(item: RegisteredPlugin): boolean {
  const requested = item.requested_permissions || [];
  const granted = item.granted_permissions || [];
  return requested.length === granted.length && requested.every((permission) => granted.includes(permission));
}

export function PluginManagerPanel({ onInspect }: { onInspect?: (inspection?: PluginInspection) => void } = {}) {
  const [items, setItems] = useState<DiscoveredPlugin[]>([]);
  const [registered, setRegistered] = useState<RegisteredPlugin[]>([]);
  const [health, setHealth] = useState<any>();
  const [runtime, setRuntime] = useState<any>();
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState("");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string }>();

  const refresh = async () => {
    setLoading(true);
    setMessage(undefined);
    try {
      const [found, current, status, runtimeStatus] = await Promise.all([
        api.discoverPlugins(),
        api.plugins(),
        api.multimodalHealth(),
        api.pluginRuntimeStatus(),
      ]);
      setItems(found.items || []);
      setRegistered(current.items || []);
      setHealth(status);
      setRuntime(runtimeStatus);
    } catch {
      setMessage({ tone: "error", text: "插件状态读取失败，请检查本地服务后重新扫描。" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const visibleItems = useMemo(() => {
    const value = query.trim().toLocaleLowerCase();
    if (!value) return items;
    return items.filter((item) => {
      const fields = [item.manifest?.name, item.manifest?.id, safePluginDirId(item.plugin_dir || item.path)];
      return fields.filter(Boolean).some((field) => String(field).toLocaleLowerCase().includes(value));
    });
  }, [items, query]);

  const runAction = async (key: string, success: string, action: () => Promise<unknown>) => {
    setPending(key);
    setMessage(undefined);
    try {
      await action();
      await refresh();
      setMessage({ tone: "success", text: success });
    } catch {
      setMessage({ tone: "error", text: "操作未完成。权限、插件版本或本地服务状态可能已变化，请刷新后重试。" });
    } finally {
      setPending("");
    }
  };

  const activeCount = registered.filter((item) => item.status === "MANIFEST_ACTIVE").length;

  const inspect = (item: RegisteredPlugin) => onInspect?.({
    id: item.id,
    name: item.name,
    version: item.version,
    status: item.status,
    description: item.description,
    capabilities: item.capabilities,
    requestedPermissions: item.requested_permissions,
    grantedPermissions: item.granted_permissions,
    executionSupported: false,
    sandbox: runtime?.sandbox,
    isolation: runtime?.isolation || "DENY_ALL",
    manifestVersion: item.manifest_version || "1.0",
    hostApiVersion: item.host_api_version || "1",
    executionMode: item.execution_mode || "declarative",
    publisher: item.publisher,
    resourceCount: resourceCountOf(item),
    resourceKinds: resourceKindsOf(item),
  });

  return (
    <Panel title="插件治理" className="plugin-manager" actions={
      <Button variant="ghost" loading={loading} onClick={refresh}>
        <RefreshCw aria-hidden="true" size={15}/>{loading ? "扫描中" : "重新扫描"}
      </Button>
    }>
      <div className="plugin-manager__summary" aria-label="插件状态摘要">
        <div><span>本地发现</span><strong>{items.length}</strong></div>
        <div><span>已注册</span><strong>{registered.length}</strong></div>
        <div><span>清单激活</span><strong>{activeCount}</strong></div>
        <div><span>代码执行</span><strong>禁止</strong></div>
      </div>
      <section className="plugin-manager__runtime" aria-labelledby="plugin-runtime-title">
        <div>
          <h3 id="plugin-runtime-title">运行边界</h3>
          <p>插件默认拒绝权限。当前激活仅表示清单可用，不代表插件代码能够执行。</p>
        </div>
        <dl>
          <div><dt>沙箱</dt><dd>{runtime?.sandbox || "未读取"}</dd></div>
          <div><dt>隔离策略</dt><dd>{runtime?.isolation || "DENY_ALL"}</dd></div>
          <div><dt>图片 Provider</dt><dd>{health ? health.image_providers?.length || 0 : "未读取"}</dd></div>
          <div><dt>视频配置</dt><dd>{health ? health.video_provider_configs || 0 : "未读取"}</dd></div>
        </dl>
      </section>
      {message && <StatusMessage tone={message.tone}>{message.text}</StatusMessage>}
      <section className="plugin-manager__section" aria-labelledby="discovered-title">
        <header>
          <div>
            <h3 id="discovered-title">本地发现</h3>
            <p>扫描本地插件目录并验证 manifest，注册不会自动授权。</p>
          </div>
          <label className="plugin-manager__search">
            <Search aria-hidden="true" size={15}/>
            <span className="sr-only">筛选本地插件</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="筛选名称或 ID"/>
          </label>
        </header>
        {!visibleItems.length && !loading ? (
          <EmptyState title={query ? "没有匹配的插件" : "未发现本地插件"} detail={query ? "调整筛选条件后重试。" : "将有效插件放入本地插件目录，然后重新扫描。"}/>
        ) : (
          <div className="plugin-manager__rows">
            {visibleItems.map((item, index) => {
              const manifest = item.manifest;
              const isRegistered = manifest && registered.some((plugin) => plugin.id === manifest.id);
              const dirId = safePluginDirId(item.plugin_dir || item.path);
              const errorText = safePluginError(item);
              const kinds = resourceKindsOf(item);
              const count = resourceCountOf(item);
              return (
                <article className="plugin-manager__row" key={`${dirId || "plugin"}-${index}`}>
                  <div className="plugin-manager__identity">
                    <Plug aria-hidden="true" size={17}/>
                    <div>
                      <strong>{manifest?.name || "无效插件"}</strong>
                      <span>{dirId || (manifest?.id ? manifest.id : "本地插件")}</span>
                    </div>
                  </div>
                  {errorText ? (
                    <p className="plugin-manager__error" role="alert">{errorText}</p>
                  ) : (
                    <>
                      <div className="plugin-manager__meta">
                        <span>v{manifest?.version}</span>
                        <span>清单 {manifest?.manifest_version || "1.0"} · Host API {manifest?.host_api_version || "1"}</span>
                        <span>execution_mode={manifest?.execution_mode || "declarative"}</span>
                        <span>{publisherLabel(manifest?.publisher)}</span>
                        <span>{count} 个声明式资源{count ? `（${formatResourceKinds(kinds)}）` : ""}</span>
                        <span>{manifest?.capabilities?.length || 0} 项能力</span>
                        <span>{manifest?.requested_permissions?.length || 0} 项权限请求</span>
                      </div>
                      <Button
                        variant="ghost"
                        disabled={Boolean(isRegistered)}
                        loading={pending === `register:${manifest?.id}`}
                        onClick={() => manifest && runAction(`register:${manifest.id}`, `${manifest.name} 已注册，权限仍保持默认拒绝。`, () => api.registerPlugin(manifest))}
                      >
                        {isRegistered ? "已注册" : "注册"}
                      </Button>
                    </>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
      <section className="plugin-manager__section" aria-labelledby="registered-title">
        <header>
          <div>
            <h3 id="registered-title">已注册插件</h3>
            <p>审核权限后才能激活清单；运行时执行策略仍独立生效。</p>
          </div>
        </header>
        {!registered.length ? (
          <EmptyState title="暂无已注册插件" detail="从本地发现列表选择一个有效插件进行注册。"/>
        ) : (
          <div className="plugin-manager__rows">
            {registered.map((item) => {
              const requested = item.requested_permissions || [];
              const reviewed = isReviewed(item);
              const active = item.status === "MANIFEST_ACTIVE";
              const kinds = resourceKindsOf(item);
              const count = resourceCountOf(item);
              return (
                <article className="plugin-manager__row plugin-manager__row--registered" key={item.id}>
                  <button type="button" className="plugin-manager__identity plugin-manager__identity--select" onClick={() => inspect(item)} aria-label={`检查插件 ${item.name}`}>
                    {reviewed ? <ShieldCheck aria-hidden="true" size={17}/> : <CircleOff aria-hidden="true" size={17}/>}
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.id}{item.version ? ` · v${item.version}` : ""}</span>
                    </div>
                  </button>
                  <Badge tone={active ? "success" : reviewed ? "info" : "warning"}>{statusLabel(item.status)}</Badge>
                  <div className="plugin-manager__lifecycle" aria-label="插件生命周期">
                    <span className="is-on">已发现</span>
                    <span className="is-on">已注册</span>
                    <span className={reviewed ? "is-on" : ""}>权限已审核</span>
                    <span className={active ? "is-on" : ""}>Manifest 已激活</span>
                    <span className={active ? "is-on" : ""}>声明式资源已验证</span>
                    <span>插件代码可执行：否</span>
                  </div>
                  <div className="plugin-manager__permissions">
                    <span>请求权限</span>
                    <strong>{requested.join("、") || "无"}</strong>
                    <span>{publisherLabel(item.publisher)}</span>
                    <span>execution_mode={item.execution_mode || "declarative"} · {count} 个资源{count ? `（${formatResourceKinds(kinds)}）` : ""}</span>
                  </div>
                  {!reviewed && (
                    <Button variant="ghost" loading={pending === `review:${item.id}`} onClick={() => runAction(`review:${item.id}`, `${item.name} 的权限已审核。`, () => api.setPluginPermissions(item.id, { granted_permissions: requested, reviewed_by: "local-user", note: "本地用户明确授权" }))}>
                      审核并授权
                    </Button>
                  )}
                  {reviewed && !active && (
                    <Button loading={pending === `enable:${item.id}`} onClick={() => runAction(`enable:${item.id}`, `${item.name} 的清单已激活。`, () => api.enablePlugin(item.id))}>
                      激活清单
                    </Button>
                  )}
                  {active && (
                    <Button variant="ghost" loading={pending === `disable:${item.id}`} onClick={() => runAction(`disable:${item.id}`, `${item.name} 已停用。`, () => api.disablePlugin(item.id))}>
                      停用
                    </Button>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </Panel>
  );
}
