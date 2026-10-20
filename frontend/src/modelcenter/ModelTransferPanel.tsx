import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { createModelTransferClient } from './modelTransferClient';
import type { ModelTransferCatalog, ModelTransferCleanupPreview, ModelTransferPreview, ModelTransferSource, ModelTransferState, ModelTransferTask } from './modelTransferContract';
import type { ModelCenterPanelProps } from './modelCenterTypes';

type Props = Pick<ModelCenterPanelProps, 'projectId' | 'transport' | 'scope' | 'identity' | 'active' | 'denied' | 'busy' | 'isCurrent' | 'read' | 'mutate'>;
type View = {
  token: object; catalog?: ModelTransferCatalog; selected: string; preview?: ModelTransferPreview;
  cleanup?: ModelTransferCleanupPreview; pending?: string; error?: string; notice?: string; needsRead?: boolean;
};
const labels: Record<ModelTransferState, string> = {
  TRANSFERRING: '正在传输', PAUSING: '正在请求暂停（尚未停止）', PAUSED: '已暂停',
  CANCELLING: '正在请求取消（尚未停止）', VERIFYING: '正在校验', COMPLETED: '传输并校验完成',
  CANCELLED: '已取消', FAILED: '失败', INTERRUPTED: '已中断', CLEANED: '已清理本任务部分文件',
};
function SourceFacts({ source }: { source: ModelTransferSource }) {
  return <>
    <p>发布者：{source.publisher}；模型：{source.model_id}；固定修订：{source.revision}</p>
    <p>许可证：<a href={source.license_url} target="_blank" rel="noreferrer">{source.license_name}</a> · <a href={source.model_card_url} target="_blank" rel="noreferrer">查看模型说明</a></p>
    <label>审核后的下载来源 URL<textarea readOnly value={source.url} /></label>
    <p>精确文件大小：{source.size_bytes} bytes</p>
    <label>预期 SHA-256<textarea readOnly value={source.sha256} /></label>
  </>;
}
/** Explicit, host-owned transfers only. Rendering, navigation and read never start a transfer. */
export function ModelTransferPanel(props: Props) {
  const scopeKey = JSON.stringify(props.scope);
  const key = JSON.stringify([props.projectId, props.identity, scopeKey, props.active, props.denied]);
  const client = useMemo(() => {
    try {
      if (props.scope && props.scope.projectId !== props.projectId) return undefined;
      return createModelTransferClient(props.projectId, props.transport, props.scope);
    } catch { return undefined; }
  }, [props.projectId, props.transport, scopeKey]);
  const alive = useRef(true), latest = useRef(props), active = useRef<AbortController>();
  latest.current = props;
  const owner = useRef({ key, client, token: {} });
  if (owner.current.key !== key || owner.current.client !== client) {
    active.current?.abort(); active.current = undefined;
    owner.current = { key, client, token: {} };
  }
  const token = owner.current.token;
  const [state, setState] = useState<View>();
  useEffect(() => { alive.current = true; return () => { alive.current = false; active.current?.abort(); }; }, []);
  // The outer mutation wrapper can set busy while a request is running. That
  // prevents another command, but must not retire its own successful receipt.
  const current = () => alive.current && owner.current.token === token && latest.current.active
    && !latest.current.denied && latest.current.isCurrent();
  const visible = state?.token === token ? state : undefined;
  const catalog = visible?.catalog;
  const selected = catalog?.sources.find(source => source.id === visible?.selected);
  const blocked = !client || props.busy || !!visible?.pending || !!visible?.needsRead;
  const ready = !!catalog?.configured && catalog.platform_supported && catalog.sources.length > 0 && catalog.blockers.length === 0;
  const preview = visible?.preview, cleanup = visible?.cleanup;
  function update(change: Partial<View>) {
    if (current()) setState(previous => ({ ...(previous?.token === token ? previous : { token, selected: '' }), ...change, token }));
  }
  async function run<T>(label: string, write: boolean, operation: (signal: AbortSignal) => Promise<T>, accept: (value: T) => void) {
    if (!client || !current() || latest.current.busy || active.current || (write && visible?.needsRead)) return;
    const abort = new AbortController(), captured = latest.current;
    active.current = abort;
    update({ pending: label, error: undefined, notice: undefined });
    try {
      const work = () => {
        // Wrappers may defer execution. Never let a captured command cross an
        // identity/transport/scope change before it reaches the transport.
        if (!current() || abort.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        return operation(abort.signal);
      };
      const result = await (write ? captured.mutate(work) : captured.read(work));
      if (current() && !abort.signal.aborted) accept(result);
    } catch (reason) {
      if (current() && !abort.signal.aborted) {
        const denied = reason instanceof ApiError && [401, 403].includes(reason.status);
        const rejected = reason instanceof ApiError && [400, 401, 403, 404, 409, 422].includes(reason.status);
        update({ preview: undefined, cleanup: undefined, needsRead: true,
          error: write ? rejected ? '传输操作被拒绝或任务版本已变化，未自动重试。请明确重新读取并核对当前状态。'
            : '写入结果未知，未自动重试。请明确重新读取传输状态，核对结果后再操作。'
            : denied ? '传输读取被拒绝（DENIED）；这不代表没有传输任务。'
              : '传输读取失败或回执无效；保留的事实不能视为最新状态。请明确重新读取。' });
      }
    } finally {
      if (active.current === abort) {
        active.current = undefined;
        if (current()) update({ pending: undefined });
      }
    }
  }
  function read() {
    if (!client) return;
    update({ preview: undefined, cleanup: undefined });
    void run('正在读取受控传输状态…', false, signal => client.list(signal), result => {
      update({ catalog: result, selected: result.sources.some(source => source.id === visible?.selected) ? visible!.selected : '',
        needsRead: false, preview: undefined, cleanup: undefined, notice: '已读取当前传输状态；后续变化需再次明确读取。' });
    });
  }
  function prepare() {
    if (!client || !selected || blocked || !ready) return;
    update({ preview: undefined, cleanup: undefined });
    void run('正在检查来源与目标空间…', false, signal => client.preview(selected, signal), result => update({ preview: result }));
  }
  function started(task: ModelTransferTask) {
    update({ catalog: catalog ? { ...catalog, items: [...catalog.items.filter(item => item.id !== task.id), task] } : undefined,
      preview: undefined, cleanup: undefined, needsRead: true,
      notice: '已收到操作回执。请明确重新读取传输状态；暂停或取消请求尚未停止时会显示等待状态。' });
  }
  function action(task: ModelTransferTask, kind: 'pause' | 'resume' | 'cancel') {
    if (!client || blocked || (kind === 'resume' && !ready)) return;
    void run('正在提交传输操作…', true, signal => client[kind](task, signal), started);
  }
  function prepareCleanup(task: ModelTransferTask) {
    if (!client || blocked) return;
    update({ preview: undefined, cleanup: undefined });
    void run('正在检查本任务部分文件…', false, signal => client.cleanupPreview(task, signal), result => update({ cleanup: result }));
  }
  if (!props.active || props.denied || !props.isCurrent()) return null;
  const enoughSpace = !!preview && preview.available_bytes >= preview.required_bytes;
  const previewLive = !!preview && preview.expires_at > Date.now() / 1000;
  return <section aria-label="受控模型文件传输" aria-busy={!!visible?.pending}>
    <h3>受控模型文件传输</h3>
    <p>这里只管理传输服务拥有的任务与部分文件。已有模型注册表不提供下载授权；打开面板不会联网下载、自动恢复或扫描外部模型目录。</p>
    <Button disabled={!client || props.busy || !!visible?.pending} onClick={read}>明确读取传输状态</Button>
    {!client && <StatusMessage tone="warning">当前项目上下文无效，传输读取和操作已停用。</StatusMessage>}
    {!catalog && !visible?.pending && !visible?.error && <StatusMessage>尚未读取受控传输配置。生产默认未配置已审核来源与目标目录；现有已列出的模型不能据此下载。</StatusMessage>}
    {visible?.pending && <StatusMessage>{visible.pending}</StatusMessage>}
    {visible?.error && <StatusMessage tone="error">{visible.error}</StatusMessage>}
    {visible?.notice && <StatusMessage>{visible.notice}</StatusMessage>}
    {catalog && <>
      {!catalog.configured && <StatusMessage tone="warning">下载不可用：尚未配置已审核来源和受控目标目录。</StatusMessage>}
      {!catalog.platform_supported && <StatusMessage tone="warning">当前平台不支持安全受控传输，开始和恢复已停用。</StatusMessage>}
      {catalog.blockers.length > 0 && <ul aria-label="传输阻碍">{catalog.blockers.map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
      {catalog.sources.length === 0 ? <EmptyState title="没有已审核的下载来源" detail="这不代表模型注册表为空，也不会把已有注册模型转换为可下载来源。" />
        : <><label>已审核下载来源<select value={visible!.selected} disabled={blocked || !ready} onChange={event => {
          if (current() && !active.current && !blocked) update({ selected: event.target.value, preview: undefined, cleanup: undefined });
        }}><option value="">明确选择来源</option>{catalog.sources.map(source => <option key={source.id} value={source.id}>{source.display_name}</option>)}</select></label>
          {selected && <SourceFacts source={selected} />}
          <Button disabled={blocked || !ready || !selected} onClick={prepare}>预览下载与目标目录</Button>
        </>}
      {preview && <section aria-label="下载确认预览">
        <h4>开始前核对</h4>
        <p>已审核来源：{preview.source.display_name}。上方来源、发布者、许可证、固定修订、精确字节与 SHA-256 均绑定本次预览。</p>
        <label>确认的目标目录 / 文件<textarea readOnly value={preview.destination} /></label>
        <p>所需：{preview.required_bytes} bytes；可用于传输：{preview.available_bytes} bytes（已扣除保留空间与配额限制）；已保留空间：{preview.reserve_bytes} bytes。</p>
        <p>预览有效期至 {new Date(preview.expires_at * 1000).toISOString()}。确认将访问上方公开来源并写入此受控目标；不会执行或加载模型。</p>
        {!enoughSpace && <StatusMessage tone="warning">目标空间不足，不能开始。</StatusMessage>}
        {!previewLive && <StatusMessage tone="warning">预览已过期，请重新预览。</StatusMessage>}
        <Button variant="primary" disabled={blocked || !ready || !enoughSpace || !previewLive} onClick={() => {
          if (!client || !current() || blocked || !ready) return;
          if (preview.expires_at <= Date.now() / 1000) { update({ preview: undefined, error: '下载预览已过期，请重新预览并确认。' }); return; }
          void run('正在提交已确认的传输…', true, signal => client.start(preview, signal), started);
        }}>确认来源、许可证与目标并开始下载</Button>
      </section>}
      <h4>服务拥有的传输任务</h4>
      <p>进度是最近一次读取或操作回执，不会自动刷新。传输完成只表示文件校验通过，不代表模型可执行、已注册或已启用。</p>
      {catalog.items.length === 0 && <EmptyState title="没有受控传输任务" detail="读取成功；当前服务尚未记录传输任务。" />}
      {catalog.items.map(task => <section key={task.id} aria-label={`传输任务 ${task.display_name}`}>
        <h4>{task.display_name} <Badge>{labels[task.state]}</Badge></h4>
        <p>任务 {task.id}；来源 {task.source_id}；版本 {task.version}。已接收 {task.bytes_received} / {task.total_bytes} bytes。</p>
        {task.error_code && <StatusMessage tone="warning">服务错误码：{task.error_code}</StatusMessage>}
        {task.state === 'TRANSFERRING' && <Button disabled={blocked} onClick={() => action(task, 'pause')}>暂停传输</Button>}
        {task.can_resume && <><p>恢复将继续该任务原先确认的来源和目标目录，服务会重新核对；不会另选来源或目标。</p>
          <Button disabled={blocked || !ready} onClick={() => action(task, 'resume')}>确认原来源与目标并恢复</Button></>}
        {['TRANSFERRING', 'PAUSED', 'INTERRUPTED', 'FAILED'].includes(task.state) && <Button disabled={blocked} onClick={() => action(task, 'cancel')}>取消传输（保留部分文件）</Button>}
        {['PAUSED', 'CANCELLED', 'FAILED', 'INTERRUPTED'].includes(task.state) && <Button disabled={blocked} onClick={() => prepareCleanup(task)}>预览清理本任务部分文件</Button>}
        {cleanup?.task_id === task.id && <section aria-label="部分文件清理确认">
          <p>仅清理本任务拥有的部分文件：{cleanup.bytes} bytes，任务版本 {cleanup.version}。不会删除已完成模型或外部文件；清理后无法从这些部分字节恢复。</p>
          <Button variant="danger" disabled={blocked || cleanup.expires_at <= Date.now() / 1000} onClick={() => {
            if (!client || !current() || blocked) return;
            if (cleanup.expires_at <= Date.now() / 1000) { update({ cleanup: undefined, error: '清理预览已过期，请重新预览并确认。' }); return; }
            void run('正在清理已确认的部分文件…', true, signal => client.cleanup(task, cleanup, signal), started);
          }}>确认清理 {cleanup.bytes} bytes 部分文件</Button>
        </section>}
      </section>)}
    </>}
  </section>;
}
