import { useEffect, useState } from "react";
import { KeyRound, Plug, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Badge, Button, EmptyState } from "../ui/primitives";
import { KIND_LABEL, formatResourceKinds, publisherLabel } from "./PluginManagerPanel";
import "./PluginInspector.css";

export type PluginResourceSummary = {
  plugin_id?: string;
  resource_id: string;
  kind: string;
  name?: string;
  description?: string;
  schema_version?: string;
  sha256?: string;
  validated?: boolean;
  summary?: { sha256_short?: string; name?: string; kind?: string; description?: string };
};

export type PluginInspection = {
  id: string;
  name: string;
  version?: string;
  pluginVersion?: string;
  status?: string;
  description?: string;
  capabilities?: string[];
  requestedPermissions?: string[];
  grantedPermissions?: string[];
  executionSupported?: boolean;
  sandbox?: string;
  isolation?: string;
  manifestVersion?: string;
  hostApiVersion?: string;
  executionMode?: string;
  publisher?: string;
  resourceCount?: number;
  resourceKinds?: string[];
  catalogValidated?: boolean;
  catalogValidationStatus?: string;
  catalogErrorCode?: string;
};

function shaShort(resource: PluginResourceSummary): string {
  return resource.summary?.sha256_short || (resource.sha256 ? resource.sha256.slice(0, 12) : "");
}

export function PluginInspector({ inspection }: { inspection?: PluginInspection }) {
  const [resources, setResources] = useState<PluginResourceSummary[]>([]);
  const [catalog, setCatalog] = useState<{ validated?: boolean; validation_status?: string; error_code?: string; status?: string; resource_count?: number; resource_kinds?: string[] }>();
  const [resourceError, setResourceError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);

  const active = inspection?.status === "MANIFEST_ACTIVE";

  useEffect(() => {
    let cancelled = false;
    setResources([]);
    setCatalog(undefined);
    setResourceError(undefined);
    if (!inspection?.id || !active) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api.pluginResources(inspection.id).then((payload) => {
      if (cancelled) return;
      setCatalog(payload);
      setResources(payload.validated ? (payload.items || []) : (payload.validation_status === "PARTIAL" ? payload.items || [] : []));
      if (payload.validation_status === "DRIFT" || payload.error_code === "PLUGIN_MANIFEST_DRIFT") {
        setResourceError("清单与已审核身份不一致，未展示声明式资源。");
      } else if (payload.validation_status === "DUPLICATE" || payload.error_code === "PLUGIN_ID_DUPLICATE") {
        setResourceError("插件 ID 重复，未展示声明式资源。");
      } else if (payload.validated !== true && payload.validation_status !== "PARTIAL") {
        setResourceError(payload.items?.length ? undefined : "没有已通过现场校验的声明式资源。");
      }
      setLoading(false);
    }).catch(() => {
      if (cancelled) return;
      setResources([]);
      setCatalog({ validated: false, validation_status: "FAILED" });
      setResourceError("声明式资源摘要读取失败。未展示未验证内容。");
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [inspection?.id, active, retry]);

  if (!inspection) {
    return (
      <section className="plugin-inspector" aria-label="插件检查面板">
        <div className="workspace-inspector__eyebrow">Inspector</div>
        <EmptyState title="未选择插件" detail="从插件治理列表选择一个 manifest 以查看能力与权限。"/>
      </section>
    );
  }

  const kinds = catalog?.resource_kinds?.length ? catalog.resource_kinds : (resources.map((item) => item.kind).filter(Boolean));
  const count = catalog?.resource_count ?? resources.length;
  const pluginVersion = inspection.pluginVersion || inspection.version;
  const validationLabel = catalog?.validated === true && catalog.validation_status === "VALIDATED"
    ? "已验证"
    : catalog?.validation_status === "PARTIAL" ? "部分资源有效"
      : catalog?.validation_status === "DRIFT" ? "Manifest 漂移"
        : catalog?.validation_status === "DUPLICATE" ? "重复 ID"
          : catalog?.validation_status === "REVIEW_REQUIRED" ? "待重新审核"
            : active ? "未通过现场校验" : "清单未激活";

  return (
    <section className="plugin-inspector" aria-label="插件检查面板">
      <div className="workspace-inspector__eyebrow">Plugin Inspector</div>
      <header>
        <Plug aria-hidden="true"/>
        <div>
          <strong>{inspection.name}</strong>
          <span>{inspection.id}{pluginVersion ? ` · v${pluginVersion}` : ""}</span>
        </div>
        <Badge tone={active ? "success" : "warning"}>{active ? "清单已激活" : inspection.status || "待审核"}</Badge>
      </header>
      <div className="plugin-inspector__boundary">
        <ShieldCheck aria-hidden="true" size={16}/>
        <span>代码执行：当前禁止 · 沙箱：{inspection.sandbox || "未读取"} · 隔离：{inspection.isolation || "DENY_ALL"}</span>
      </div>
      <dl className="plugin-inspector__facts">
        <div><dt>清单版本</dt><dd>{inspection.manifestVersion || "1.0"}</dd></div>
        <div><dt>Host API</dt><dd>{inspection.hostApiVersion || "1"}</dd></div>
        <div><dt>执行模式</dt><dd>{inspection.executionMode || "declarative"}</dd></div>
        <div><dt>发布者</dt><dd>{publisherLabel(inspection.publisher)}</dd></div>
        <div><dt>能力</dt><dd>{inspection.capabilities?.join("、") || "无"}</dd></div>
        <div><dt>请求权限</dt><dd>{inspection.requestedPermissions?.join("、") || "无"}</dd></div>
        <div><dt>已授予</dt><dd>{inspection.grantedPermissions?.join("、") || "无"}</dd></div>
        <div><dt>隔离策略</dt><dd>{inspection.isolation || "DENY_ALL"}</dd></div>
        <div><dt>声明式资源</dt><dd>{count} 个{count ? ` · ${formatResourceKinds(kinds)}` : ""} · {validationLabel}</dd></div>
        <div><dt>插件代码可执行</dt><dd>否</dd></div>
      </dl>
      {inspection.description ? <p className="plugin-inspector__description">{inspection.description}</p> : null}
      <section className="plugin-inspector__resources" aria-labelledby="plugin-resource-title">
        <header>
          <h3 id="plugin-resource-title">声明式资源摘要</h3>
          {active && resourceError ? <Button variant="ghost" onClick={() => setRetry((value) => value + 1)}>重试读取</Button> : null}
        </header>
        {!active ? (
          <p className="novel-help">清单未激活，声明式资源不可展示。</p>
        ) : loading ? (
          <p className="novel-help">正在重新校验声明式资源…</p>
        ) : resourceError ? (
          <p className="plugin-inspector__error" role="alert">{resourceError}</p>
        ) : !resources.length ? (
          <p className="novel-help">没有已通过现场校验的声明式资源。</p>
        ) : (
          <ul>
            {resources.map((resource) => {
              const digest = shaShort(resource);
              return (
                <li key={resource.resource_id}>
                  <KeyRound aria-hidden="true" size={12}/>
                  <div>
                    <strong>{resource.summary?.name || resource.name || resource.resource_id}</strong>
                    <span>{KIND_LABEL[resource.kind] || resource.kind}{resource.schema_version ? ` · schema ${resource.schema_version}` : ""}{digest ? ` · SHA-256 ${digest}` : ""}{resource.validated ? " · 已校验" : ""}</span>
                    {resource.summary?.description || resource.description ? <span>{resource.summary?.description || resource.description}</span> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <p className="novel-help">密钥、插件代码、绝对路径和运行时响应不会在此面板展示。发布者字段不是签名。代码执行：当前禁止。</p>
    </section>
  );
}
