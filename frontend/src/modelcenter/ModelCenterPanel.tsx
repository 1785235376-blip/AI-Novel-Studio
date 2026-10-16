/**
 * UX-07 组合根：`ModelCenterPanel`。
 *
 * 这是新的挂载入口（`frontend/src/modelcenter/`），它**不**注册任何模型、不下载、
 * 不清理、不搬迁，也不写任何后端状态。Lead 负责把它挂到工作区；本目录不与
 * `frontend/src/ui/**`（含既有 `ModelCenter.tsx` 受保护表面）或 UX-08 的
 * `frontend/src/guide/` 发生任何文件级交叠。
 */

import { useMemo } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import { CapabilityMatrix } from './CapabilityMatrix';
import { ModelDetailPanel } from './ModelDetailPanel';
import { ProviderKeyState } from './ProviderKeyState';
import { StoragePanel, StorageSourceNotice } from './StoragePanel';
import { capabilityMatrix, orphanCandidates, storageReport } from './modelCenterOps';
import type { ModelCenterSourceStatus } from './modelCenterClient';
import { MODEL_CENTER_CODES, type ModelCenterPanelProps, type ModelCenterSurfaceState } from './modelCenterTypes';
import { useModelCenter } from './useModelCenter';
import './modelCenter.css';

function StatusBanner({ state, code, message, hasModels }: {
  state: ModelCenterSurfaceState; code?: string; message?: string; hasModels: boolean;
}) {
  if (state === 'DENIED') {
    return (
      <StatusMessage tone="error">
        模型中心读取被拒绝（DENIED）：这不是"没有可用模型"。{message ?? MODEL_CENTER_CODES.readDenied.message}{code ? `（${code}）` : ''}
      </StatusMessage>
    );
  }
  if (state === 'FAILED') {
    return (
      <StatusMessage tone="error">
        模型中心读取失败（FAILED）。{message ?? MODEL_CENTER_CODES.readFailed.message}{code ? `（${code}）` : ''}
      </StatusMessage>
    );
  }
  if (state === 'EMPTY' && !hasModels) {
    return <EmptyState title="注册表为空" detail="原 owner 成功返回，但模型注册表里没有任何模型。空注册表与读取失败是两回事，这里不会把它说成“没有可用模型”。" />;
  }
  if (state === 'LOADING') return <StatusMessage>正在读取模型注册表、运行时状态与存储事实…</StatusMessage>;
  return null;
}

function sourceCode(status: ModelCenterSourceStatus): string | undefined {
  return 'code' in status ? status.code : undefined;
}

export function ModelCenterPanel(props: ModelCenterPanelProps) {
  const controller = useModelCenter({
    projectId: props.projectId, transport: props.transport, scope: props.scope,
    identity: props.identity, active: props.active, denied: props.denied, busy: props.busy,
    isCurrent: props.isCurrent, read: props.read, mutate: props.mutate,
    catalog: props.catalog, storage: props.storage, hardware: props.hardware,
    onUnavailable: props.onUnavailable,
  });
  const matrix = useMemo(() => controller.catalog ? capabilityMatrix(controller.catalog) : undefined, [controller.catalog]);
  const report = useMemo(() => controller.storage ? storageReport(controller.storage) : undefined, [controller.storage]);
  const orphans = useMemo(() => orphanCandidates(undefined, controller.storage), [controller.storage]);
  const selected = controller.catalog?.models.find(model => model.id === controller.selected) ?? controller.catalog?.models[0];
  const catalogStatus = controller.sources.catalog;
  const storageStatus = controller.sources.storage;

  return (
    <section className="ui-panel model-center-panel" aria-label="模型中心与存储"
      data-surface-state={controller.state} data-catalog-state={catalogStatus.state} data-storage-state={storageStatus.state}>
      <header>
        <h2>模型中心与存储</h2>
        <Button disabled={!controller.canRead} onClick={() => void controller.reload()}>重新读取模型注册表</Button>
      </header>
      <p className="model-center__hint">
        本面板是只读消费者：不注册模型、不下载、不准备、不修复、不清理、不迁移、不删除、不调度，
        也不读取或保存任何密钥值。每一条结论都标注来自哪个原 owner 事实；原 owner 没有提供的事实，
        界面显示为"未知"而不是补一个看起来更好的值。
      </p>
      {props.denied && <StatusMessage tone="error">当前会话无权查看模型中心（DENIED）。</StatusMessage>}
      <StatusBanner state={controller.state} code={controller.problem?.code} message={controller.problem?.message}
        hasModels={(controller.catalog?.models.length ?? 0) > 0} />

      {controller.catalog ? (
        <>
          {catalogStatus.state !== 'READY' && <StorageSourceNotice state={catalogStatus.state} code={sourceCode(catalogStatus)} />}
          {matrix ? <CapabilityMatrix matrix={matrix} selected={selected?.id} onSelect={controller.select} /> : null}
        </>
      ) : null}

      {selected && controller.catalog ? (
        <ModelDetailPanel model={selected} catalog={controller.catalog} hardware={controller.hardware}
          admission={controller.storage?.admission} credentials={controller.credentials} />
      ) : null}

      <StoragePanel report={report ?? storageReport(undefined)} orphans={orphans} loaded={!!report}
        sourceState={storageStatus.state} sourceCode={sourceCode(storageStatus)}
        canReRead={controller.canRead} onReRead={() => void controller.reload()} />

      <ProviderKeyState credentials={controller.credentials} />

      <div className="model-center__actions">
        <Button disabled variant="ghost">下载模型（不可用：原 owner 没有下载端点）</Button>
        <Button disabled variant="ghost">准备 / 修复模型（不可用：原 owner 没有对应端点）</Button>
        <Button disabled variant="ghost">清理磁盘（不可用：physical_cleanup_available = false）</Button>
        <Button disabled variant="ghost">删除孤儿文件（不可用：孤儿报告是只读的）</Button>
      </div>
    </section>
  );
}

export default ModelCenterPanel;
