import { Badge, StatusMessage } from '../ui/primitives';
import { MODEL_CENTER_CODES, type ModelCenterCatalogPayload, type ModelCenterModel, type ModelCenterStoragePayload } from './modelCenterTypes';
import { readinessNotice, routingExplanation } from './modelCenterOps';
import type { ModelCenterCredentialState, ModelCenterHardwareFact } from './modelCenterTypes';

export type ModelDetailPanelProps = {
  model: ModelCenterModel;
  catalog: ModelCenterCatalogPayload;
  hardware: ModelCenterHardwareFact;
  admission?: ModelCenterStoragePayload['admission'];
  credentials: readonly ModelCenterCredentialState[];
};

/**
 * 模型详情：声明 vs 已验证、许可与路线状态、磁盘需求、准备状态。**全部只读**。
 * 每一条都同时显示原 owner 的字段名与取值，界面不替 owner 下结论。
 */
export function ModelDetailPanel({ model, catalog, hardware, admission, credentials }: ModelDetailPanelProps) {
  const route = routingExplanation(catalog, model.id, hardware, credentials);
  const readiness = readinessNotice(model, hardware, admission);
  const decl = route?.declared_capabilities ?? model.capabilities;
  const ver = route?.verified_capabilities ?? [];
  const ownerFacts: [string, string][] = [
    ['model.status', model.status ?? '未提供'],
    ['model.verified', model.verified === undefined ? '未提供' : String(model.verified)],
    ['model.historically_validated', model.historically_validated === undefined ? '未提供' : String(model.historically_validated)],
    ['model.license', model.license ?? '未提供'],
    ['model.metadata.license_status', model.metadata?.license_status ?? model.license_status ?? '未提供'],
    ['model.runtime_type', model.runtime_type],
    ['model.model_format', model.model_format],
    ['model.source', model.source ?? '未提供'],
    ['hardware_profile', model.hardware_profile ? `${model.hardware_profile.gpu_name} · ${model.hardware_profile.profile_kind}` : '原 owner 未提供档位'],
    ['route.runtime_id', route?.runtime_id ?? '无法唯一关联运行时'],
  ];
  return (
    <section className="ui-panel model-center__detail-panel" aria-label="模型详情">
      <header><h2>模型详情 · {model.display_name}</h2></header>
      <div className="model-center__detail" role="region" aria-label="声明与已验证能力">
        <section aria-label="声明能力">
          <h3>声明（model.capabilities）</h3>
          <p>{decl.length ? decl.join('、') : '未声明任何能力'}</p>
        </section>
        <section aria-label="已验证能力">
          <h3>已验证（原 owner 校验 + 运行时观测）</h3>
          <p>{ver.length ? ver.join('、') : '没有观测证据：声明不会被当成已验证'}</p>
        </section>
      </div>
      <dl className="model-center__facts">
        {ownerFacts.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}
      </dl>
      <section aria-label="路线状态">
        <h3>能否被选中</h3>
        {route?.verdict === 'SELECTABLE'
          ? <StatusMessage tone="success">当前事实允许该模型被路由。仍不代表执行授权：{route.execution_authority}，且本界面 model_called = false。</StatusMessage>
          : null}
        {route?.verdict === 'UNKNOWN'
          ? <StatusMessage tone="warning">结论未知：下方逐条列出缺哪一项原 owner 事实。未知不会被当作可选。</StatusMessage>
          : null}
        {route?.verdict === 'NOT_SELECTABLE'
          ? <StatusMessage tone="warning">{MODEL_CENTER_CODES.routeBlocked.message}</StatusMessage>
          : null}
        {route?.blockers.length
          ? <ul className="model-center__blockers" aria-label="阻塞该模型的事实">{route.blockers.map(item => (
            <li key={`${item.code}:${item.owner_fact}`}><Badge tone="warning">{item.code}</Badge><span className="model-center__owner-fact">{item.owner_fact}</span><span>{item.detail}</span></li>
          ))}</ul>
          : null}
        {route?.availability
          ? <dl className="model-center__facts" aria-label="原 owner 准入事实">
            {Object.entries(route.availability).map(([fact, value]) => (
              <div key={fact}><dt>{fact}</dt><dd>{value ? 'true' : 'false'}</dd></div>
            ))}
          </dl>
          : null}
      </section>
      <section aria-label="磁盘与准备状态">
        <h3>磁盘与准备状态</h3>
        <p className="model-center__readiness">
          <Badge tone={readiness.state === 'READY' ? 'success' : readiness.state === 'FAILED' ? 'error' : 'neutral'}>{readiness.label}</Badge>
          <span>{readiness.detail}</span>
        </p>
        <dl className="model-center__facts">
          <div><dt>档位所需字节</dt><dd>{readiness.required_bytes === null ? '原 owner 未提供' : String(readiness.required_bytes)}</dd></div>
          <div><dt>准入可用字节</dt><dd>{readiness.available_bytes === null ? '未知（不可与 0 互换）' : String(readiness.available_bytes)}</dd></div>
          <div><dt>本界面可启动下载</dt><dd>否（原 owner 没有下载端点）</dd></div>
        </dl>
      </section>
    </section>
  );
}
