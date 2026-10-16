import { useCallback, useMemo, useState } from 'react';
import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { createDeliveryClient } from './deliveryClient';
import { deliveryEntitlements, deliveryItems, deliveryReceiptPage } from './deliveryContract';
import { handoverManifest } from './deliveryOps';
import {
  DELIVERY_CODES, DELIVERY_ITEM_KIND_LABELS, DELIVERY_NOTICES, DELIVERY_RECEIPT_STATE_LABELS,
  type DeliveryEntitlements, type DeliveryItem, type DeliveryItemKind, type DeliveryReceiptPage,
  type DeliveryRecovery, type DeliveryRequest, type DeliverySurfaceState,
} from './deliveryTypes';
import { useDelivery } from './useDelivery';
import { ItemExportPanel } from './ItemExportPanel';
import { HandoverManifestPanel } from './HandoverManifestPanel';
import { ReceiptRecoveryPanel } from './ReceiptRecoveryPanel';
import './deliveryCenter.css';

/**
 * UX-09 统一导出与工程交接 —— 组合根与挂载入口（props **冻结**）。
 *
 * 这个面板是**消费者**：它不创建导出任务、不派发、不取消、不重试，也不新增第二套
 * 交接协议。它做三件事：
 *
 * 1. 读取原导出 owner 的公开回执（`GET /api/exports`、`GET /api/exports/{id}`，
 *    经注入的 `StudioGraphTransport`）；
 * 2. 判定**单个对象**能否独立导出，并在格式不被支持时给出明确拒绝；
 * 3. 清点工程交接包（只含被显式勾选且身份有权导出的对象），并把丢失的回执
 *    复原成"重新读取原请求"，绝不再次派发。
 *
 * 挂载方式（与 `TaskCenterPanel` 同一形状，组合根只做一行接入）：
 * `frontend/src/ui/moduleRegistry.tsx` 由 Lead 负责接线，本目录**不改动**任何受保护表面。
 *
 * ```tsx
 * <DeliveryCenterPanel projectId={novelId} transport={studioTransport(context)} scope={context.scope}
 *   identity={cacheKey} active={deliveryView} denied={denied || identityRetired} busy={busy}
 *   isCurrent={current} read={guarded} mutate={graphMutation}
 *   items={decodedItems} receipts={decodedReceipts} entitlements={decodedEntitlements}
 *   onUnavailable={deny} />
 * ```
 */

/** 冻结的挂载 props（逐条来自本工作包的任务书）。 */
export type DeliveryCenterPanelProps = {
  projectId: string;
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
  identity: string;
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(w: () => Promise<T>) => Promise<T>;
  mutate: <T>(w: () => Promise<T>) => Promise<T>;
  items?: unknown;
  receipts?: unknown;
  entitlements?: unknown;
  onUnavailable?: () => void;
};

/** 授权缺失时的唯一保守取值：没有权利，就没有任何可导出项。 */
function deniedEntitlements(projectId: string, identity: string): DeliveryEntitlements {
  return {
    project_id: projectId, identity, can_export: false, item_kinds: [], formats: [],
    max_item_bytes: 0, max_package_bytes: 0, max_items: 0,
  };
}

function decode<T>(work: () => T): { value: T | null; problem: string | null } {
  try { return { value: work(), problem: null }; } catch (reason) {
    return { value: null, problem: reason instanceof ApiError ? reason.problem.message : '本目录读取到的授权数据不可用。' };
  }
}

export function DeliveryCenterPanel(props: DeliveryCenterPanelProps) {
  const { projectId, transport, scope, identity, denied } = props;
  const client = useMemo(() => createDeliveryClient(projectId, transport, scope),
    // 传输对象每次渲染都可能是新实例：客户端按捕获到的分支身份重建。
    [projectId, transport, scope?.workspaceId, scope?.projectId, scope?.storylineId, scope?.branchId]);
  const controller = useDelivery({
    identity, active: props.active, denied, busy: props.busy, isCurrent: props.isCurrent,
    read: props.read, client, onUnavailable: props.onUnavailable,
  });

  // 授权与对象只在父层明确给出时解码；缺失一律按"没有权利/没有对象"处理，绝不猜测。
  const entitlementMissing = props.entitlements === undefined || props.entitlements === null;
  const decoded = useMemo(
    () => (entitlementMissing ? { value: null, problem: null } : decode(() => deliveryEntitlements(props.entitlements, projectId))),
    [entitlementMissing, props.entitlements, projectId],
  );
  const entitlements = decoded.value ?? deniedEntitlements(projectId, identity);
  const items = useMemo<DeliveryItem[]>(() => {
    if (props.items === undefined || props.items === null) return [];
    try { return deliveryItems(props.items); } catch { return []; }
  }, [props.items]);
  const receipts = useMemo<DeliveryReceiptPage | undefined>(() => {
    if (props.receipts === undefined || props.receipts === null) return undefined;
    try { return deliveryReceiptPage(props.receipts, projectId); } catch { return undefined; }
  }, [props.receipts, projectId]);

  const [selected, setSelected] = useState<string[]>([]);
  const [kind, setKind] = useState<DeliveryItemKind | ''>('');
  const [notice, setNotice] = useState('');
  const [lastRequest, setLastRequest] = useState<DeliveryRequest | null>(null);
  const [lastRecovery, setLastRecovery] = useState<DeliveryRecovery | null>(null);

  const toggle = useCallback((id: string) => {
    if (!props.isCurrent()) return;
    setSelected(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]);
  }, [props]);
  const selection = useMemo(() => items.filter(item => selected.includes(item.id)), [items, selected]);
  const manifest = useMemo(() => handoverManifest(selection, entitlements), [selection, entitlements]);

  /**
   * 派发**只能**由原导出 owner 执行。这里只登记"请求已经离开本机"，
   * 并立刻给出恢复计划（原请求参数 + 只读的重新读取路径）；本目录没有派发方法。
   */
  const rememberDispatch = useCallback((request: DeliveryRequest) => {
    controller.trackAttempt(request, projectId);
    setLastRequest(request);
    setLastRecovery(controller.recoveryFor({ project_id: projectId, request, receipt: null }));
    setNotice(DELIVERY_NOTICES.opOnly);
  }, [controller, projectId]);

  const receiptPage = receipts ?? controller.page;
  const emptyPageHasMore = receiptPage?.items.length === 0 && receiptPage.next_offset !== null;
  const stateLabel: Record<DeliverySurfaceState, string> = {
    IDLE: '未读取', LOADING: '正在读取', READY: '已读取', EMPTY: emptyPageHasMore ? '当前页为空' : '没有记录', DENIED: '无权限', FAILED: '读取失败',
  };
  const tone = controller.state === 'DENIED' ? 'error' : controller.state === 'FAILED' ? 'warning'
    : controller.state === 'EMPTY' ? 'neutral' : 'info';

  return <Panel title="统一导出与工程交接" className="delivery-center" aria-label="统一导出与工程交接"
    actions={<>
      <Badge tone={tone}>{stateLabel[controller.state]}</Badge>
      <Button loading={controller.state === 'LOADING'} disabled={!controller.canRead}
        onClick={() => void controller.reload()}>重新读取导出回执</Button>
    </>}>
    <p className="delivery-center__help">
      格式、限额、任务状态与恢复次数全部照原导出服务显示：这里不创建导出任务、不派发、不取消、不重试。
      单个对象可以独立导出，不依赖项目其余部分是否完成；工程交接包只包含被显式勾选且当前身份有权导出的对象。
    </p>

    {entitlementMissing && <StatusMessage tone="warning">尚未读取到当前身份的导出授权；在拿到授权之前，这里不显示任何可导出项。</StatusMessage>}
    {decoded.problem && <StatusMessage tone="error">{decoded.problem}</StatusMessage>}
    {controller.problem && <StatusMessage tone="error">{controller.problem.message}（{controller.problem.code}）</StatusMessage>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
    {controller.notice && <StatusMessage>{controller.notice}</StatusMessage>}

    {controller.state === 'DENIED' && <div className="delivery-center__denied" role="alert">
      <strong>没有读取导出回执的权限</strong>
      <p>{DELIVERY_NOTICES.emptyIsNotDenied}（被拒绝的读取不会显示成“没有记录”。）</p>
    </div>}
    {controller.state === 'FAILED' && <StatusMessage tone="warning">导出回执读取失败；这里不会用空列表代替真实状态。</StatusMessage>}
    {controller.state === 'EMPTY' && <EmptyState title={emptyPageHasMore ? '当前页没有导出回执' : '还没有导出回执'}
      detail={emptyPageHasMore ? '当前页没有返回回执，但原服务仍提供后续页标记。请到原导出中心继续翻页。'
        : '原导出服务在该项目下还没有记录；这不等于项目没有可导出内容。'} />}

    <ItemExportPanel
      items={items}
      entitlements={entitlements}
      kind={kind}
      onKindChange={setKind}
      selection={selected}
      onToggle={toggle}
      onRememberDispatch={rememberDispatch}
    />

    <HandoverManifestPanel manifest={manifest} selectionCount={selection.length} />

    <ReceiptRecoveryPanel
      state={controller.state}
      page={receiptPage}
      attempts={controller.attempts}
      lastRequest={lastRequest}
      lastRecovery={lastRecovery}
      onRecover={async (key, jobId) => { setNotice(DELIVERY_NOTICES.readOnlyRecovery); await controller.recover(key, jobId); }}
    />

    <p className="delivery-center__help">
      {DELIVERY_NOTICES.receiptNotSuccess}{DELIVERY_NOTICES.executionIsNotDelivery}
    </p>
    <p className="delivery-center__help delivery-center__codes">
      稳定机器码：<code>{DELIVERY_CODES.responseInvalid}</code> · <code>{DELIVERY_CODES.scopeMismatch}</code> · <code>{DELIVERY_CODES.formatUnknown}</code> · <code>{DELIVERY_CODES.itemForeignProject}</code> · <code>{DELIVERY_CODES.receiptUnknown}</code>
    </p>
    <p className="delivery-center__help">
      可用对象种类：{Object.values(DELIVERY_ITEM_KIND_LABELS).join('、')}；回执三态：{Object.values(DELIVERY_RECEIPT_STATE_LABELS).join('、')}。
    </p>
  </Panel>;
}
