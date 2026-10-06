import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MessageCircleQuestion } from 'lucide-react';
import { ApiError, type CollaborationContext } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { HandoffTarget, TutorGuidance, VerifierResult } from '../../../contracts/local-interop/v1/protocol';
import {
  diagnosticFields, interopClient, interopErrorMessage, metadataFields, newInteropRequestId,
  type ContentKind, type ContextPreview, type ContextSource, type DiagnosticField, type DiagnosticPreview,
  type EventSharingPreview, type HostRoute, type InteropSession, type InteropStatus, type MetadataField,
} from './client';
import './localTutor.css';

export type EditorSelection = { from: number; to: number; text: string; text_start?: number; text_end?: number };
export type LocalTutorProps = {
  context: CollaborationContext; projectId: string; module: string; surface: string;
  chapterId?: string; chapterVersion?: number; taskId?: string;
  selection?: EditorSelection; sourceReady: boolean;
  onNavigate: (route: HostRoute, signal: AbortSignal) => void | Promise<void>;
};
type View = 'ask' | 'settings' | 'diagnostics';
const capabilityNames: Record<string, string> = {
  'project.context.read': '读取明确选择的项目资料', 'project.selection.share': '每次请求选中文本',
  'project.metadata.read': '读取软件与项目状态', 'task.status.read': '读取任务状态',
  'task.error.read': '读取错误代码', 'diagnostics.read': '诊断共享',
  'model.registry.read': '读取模型元数据', 'model.runtime.status.read': '读取运行时状态',
  'tutor.guidance.request': '请求指导', 'tutor.guidance.receive': '接收指导',
  'verifier.request': '请求验证', 'verifier.result.receive': '接收验证结果',
  'case.candidate.create': '本机案例候选', 'handoff.open_feature': '点击打开功能',
  'handoff.open_project': '点击打开项目', 'handoff.open_task': '点击打开任务',
};
const metadataNames: Record<MetadataField, string> = { task: '当前任务状态', error: '错误代码', model: '当前模型元数据', runtime: '当前模型运行状态' };
const diagnosticNames: Record<DiagnosticField, string> = { software_id: '软件 ID', software_version: '软件版本', feature: '当前功能', error_code: '错误代码', task_state: '任务状态', runtime: '运行时元数据', model: '模型元数据', capability_state: '能力状态' };

export function localTutorIdentity(props: LocalTutorProps) {
  const scope = props.context.scope;
  return JSON.stringify([props.context.sessionToken, props.context.actor?.id, props.context.actor?.workspaceId, scope?.workspaceId, scope?.projectId,
    scope?.storylineId, scope?.branchId, props.projectId, props.chapterId, props.module, props.surface, props.taskId]);
}

/** One consumer of the existing shell slots, no parallel shell or startup discovery. */
export function useLocalTutorIntegration(props: LocalTutorProps) {
  const [opened, setOpened] = useState<{ identity: string; view: View }>();
  const identity = localTutorIdentity(props);
  useLayoutEffect(() => { setOpened(undefined); }, [identity]);
  const show = (view: View) => setOpened({ identity, view });
  return {
    entry: <Button variant="ghost" className="local-tutor-entry" onClick={() => show('ask')}><MessageCircleQuestion aria-hidden="true" />问助手</Button>,
    settings: <Panel title="AI Tutor Integration"><p>本机优先 · 默认关闭 · 正文逐次确认共享</p><Button onClick={() => show('settings')}>本机 Tutor 集成设置</Button></Panel>,
    dialog: opened?.identity === identity ? <LocalTutorDialog key={identity} {...props} initialView={opened.view} onClose={() => setOpened(undefined)} /> : null,
  };
}

export function LocalTutorDialog(props: LocalTutorProps & { initialView?: View; onClose: () => void }) {
  const identity = localTutorIdentity(props);
  const client = useMemo(() => interopClient(props.context), [identity]);
  const [view, setView] = useState<View>(props.initialView ?? 'ask');
  const [status, setStatus] = useState<InteropStatus>();
  const [session, setSession] = useState<InteropSession>();
  const [endpoint, setEndpoint] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [fields, setFields] = useState<MetadataField[]>([...metadataFields]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticField[]>([...diagnosticFields]);
  const [content, setContent] = useState<ContentKind>('NONE');
  const [eventOptIn, setEventOptIn] = useState(false);
  const [eventFields, setEventFields] = useState<MetadataField[]>([...metadataFields]);
  const [eventPreview, setEventPreview] = useState<EventSharingPreview>();
  const [eventSharing, setEventSharing] = useState<'off' | 'active' | 'unknown'>('off');
  const [sharedEventFields, setSharedEventFields] = useState<MetadataField[]>([]);
  const eventSharingState = useRef<'off' | 'active' | 'unknown'>('off');
  const eventRevision = useRef(0);
  function markEventSharing(value: 'off' | 'active' | 'unknown', fields: MetadataField[] = []) {
    eventSharingState.current = value; setEventSharing(value); setSharedEventFields(fields);
  }
  const [sources, setSources] = useState<ContextSource[]>([]);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [preview, setPreview] = useState<ContextPreview>();
  const [diagnostic, setDiagnostic] = useState<DiagnosticPreview>();
  const [guidance, setGuidance] = useState<TutorGuidance>();
  const [verification, setVerification] = useState<VerifierResult>();
  const currentSession = useRef<InteropSession>();
  const revokingSession = useRef<{ session: InteropSession; pending?: Promise<boolean> }>();
  const masterOffPending = useRef(false);
  const alive = useRef(true);
  const epoch = useRef(0);
  const pending = useRef<{ id: string; controller: AbortController; epoch: number; eventConsent: boolean }>();
  const dialog = useRef<HTMLElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const closeAction = useRef(props.onClose);
  closeAction.current = props.onClose;

  const clearReview = () => { setEventPreview(undefined); setPreview(undefined); setDiagnostic(undefined); setGuidance(undefined); setVerification(undefined); setNotice(''); };
  function cancelPending(showNotice = true) {
    const operation = pending.current;
    epoch.current += 1; pending.current = undefined;
    if (operation) {
      operation.controller.abort();
      void client.cancel(operation.id, currentSession.current?.session_id).catch(() => undefined);
      if (operation.eventConsent) pauseSharingAfterCancellation();
    }
    if (alive.current) { setBusy(''); if (showNotice) { clearReview(); setNotice('本次请求已取消，旧响应不会用于新请求。'); } }
  }
  function confirmRevocation() {
    currentSession.current = undefined; revokingSession.current = undefined; masterOffPending.current = false;
    eventRevision.current += 1;
    if (alive.current) { setSession(undefined); markEventSharing('off'); setEventOptIn(false); clearReview(); }
  }
  function disconnect(showNotice = true): Promise<boolean> {
    cancelPending(false);
    const record = revokingSession.current ?? (currentSession.current ? { session: currentSession.current, pending: undefined as Promise<boolean> | undefined } : undefined);
    currentSession.current = undefined; eventRevision.current += 1;
    if (!record) return Promise.resolve(!masterOffPending.current);
    revokingSession.current = record;
    if (alive.current) { setSession(undefined); markEventSharing('unknown'); setEventOptIn(false); clearReview(); }
    if (record.pending) return record.pending;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 30_000);
    record.pending = client.disconnect(record.session.session_id, controller.signal).then(receipt => {
      if (receipt.session_id !== record.session.session_id || receipt.status !== 'DISCONNECTED')
        throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' });
      if (revokingSession.current === record) {
        revokingSession.current = undefined;
        if (alive.current && !masterOffPending.current) {
          markEventSharing('off');
          if (showNotice) setNotice('已确认连接撤销；再次共享需要重新连接和确认。');
        }
      }
      return true;
    }).catch(() => {
      if (alive.current && revokingSession.current === record) {
        markEventSharing('unknown'); setError('连接撤销尚未确认，持续共享可能仍在运行。请重试断开或关闭集成。');
      }
      return false;
    }).finally(() => { clearTimeout(timer); if (revokingSession.current === record) record.pending = undefined; });
    return record.pending;
  }
  function dismissUnconfirmed() {
    alive.current = false; cancelPending(false); closeAction.current();
  }
  async function close() {
    const acknowledged = await disconnect(false);
    if (!alive.current) return;
    if (acknowledged && !masterOffPending.current) { alive.current = false; closeAction.current(); }
    else setNotice('撤销结果未确认。仅关闭面板不代表持续共享已经停止。');
  }
  async function run(label: string, action: (id: string, signal: AbortSignal, current: () => boolean) => Promise<void>, eventConsent = false) {
    if (pending.current || !alive.current) return;
    const operation = { id: newInteropRequestId(), controller: new AbortController(), epoch: ++epoch.current, eventConsent };
    pending.current = operation; setBusy(label); setError(''); setNotice('');
    const current = () => alive.current && epoch.current === operation.epoch && !operation.controller.signal.aborted;
    const timer = setTimeout(() => {
      if (!current()) return;
      cancelPending(false); clearReview(); setError(interopErrorMessage(new ApiError({ status: 408, code: 'TIMEOUT', message: '' })));
    }, 30_000);
    try { await action(operation.id, operation.controller.signal, current); }
    catch (failure) {
      if (current()) {
        clearReview(); setError(interopErrorMessage(failure));
        if (operation.eventConsent) pauseSharingAfterCancellation();
        if (failure instanceof ApiError && ['SESSION_REVOKED', 'PERMISSION_DENIED', 'SESSION_REQUIRED'].includes(failure.problem.code)) disconnect(false);
      }
    } finally {
      clearTimeout(timer);
      if (pending.current === operation) { pending.current = undefined; if (alive.current) setBusy(''); }
    }
  }
  function requireReceipt(value: { request_id: string; session_id: string }, requestId: string, sessionId: string) {
    if (value.request_id !== requestId || value.session_id !== sessionId)
      throw new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' });
  }
  function refreshStatus() {
    void run('读取集成状态', async (_id, signal, current) => {
      const value = await client.status(signal);
      if (!current()) return;
      setStatus(value);
      if (!value.enabled || !value.feature_enabled || value.acceptance_mode) confirmRevocation();
    });
  }
  useEffect(() => {
    alive.current = true; if (props.context.sessionToken) refreshStatus();
    return () => { alive.current = false; disconnect(false); };
  }, [client]);
  useLayoutEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  // A fresh version, changed selection or unsaved editor invalidates approval.
  const sourceIdentity = JSON.stringify([props.chapterVersion, props.sourceReady, props.selection?.text_start, props.selection?.text_end, props.selection?.text]);
  const sourceObserved = useRef(sourceIdentity);
  useEffect(() => {
    if (sourceObserved.current === sourceIdentity) return;
    sourceObserved.current = sourceIdentity;
    cancelPending(false); clearReview(); setContent('NONE'); setSourceIds([]);
    if (eventPreview || eventSharingState.current !== 'off') pauseSharingAfterCancellation();
  }, [sourceIdentity]);

  function pauseSharingAfterCancellation() {
    const origin = currentSession.current;
    if (!origin) return;
    const revision = ++eventRevision.current, requestId = newInteropRequestId();
    if (alive.current) { markEventSharing('unknown'); setEventOptIn(false); setEventPreview(undefined); }
    void client.eventUnsubscribe(origin.session_id, requestId).then(value => {
      requireReceipt(value, requestId, origin.session_id);
      if (value.subscription_active !== false || value.metadata_fields.length !== 0) throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' });
      if (alive.current && eventRevision.current === revision && currentSession.current?.session_id === origin.session_id) markEventSharing('off');
    }).catch(() => {
      if (alive.current && eventRevision.current === revision && currentSession.current?.session_id === origin.session_id)
        setError('持续共享停止结果尚未确认，请再次停止共享或关闭集成。');
    });
  }
  const stopEventSharing = () => {
    cancelPending(false); clearReview(); setEventOptIn(false);
    const origin = currentSession.current;
    if (!origin) return;
    eventRevision.current += 1; markEventSharing('unknown');
    void run('停止持续状态共享', async (requestId, signal, current) => {
      const value = await client.eventUnsubscribe(origin.session_id, requestId, signal);
      if (!current()) return;
      requireReceipt(value, requestId, origin.session_id);
      if (value.subscription_active !== false || value.metadata_fields.length !== 0) throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' });
      markEventSharing('off'); setNotice('持续状态共享已停止；不会自动恢复。已发送的信息无法撤回。');
    });
  };
  const previewEventSharing = () => {
    if (!session || !eventOptIn || eventSharing !== 'off') return;
    clearReview();
    void run('预览持续状态共享', async (requestId, signal, current) => {
      const value = await client.eventPreview(session.session_id, eventFields, requestId, signal);
      if (!current()) return;
      requireReceipt(value, requestId, session.session_id);
      if (value.subscription_active !== false || value.metadata_fields.some(field => !eventFields.includes(field)) || value.capsule.content?.level !== 'NONE' || previewExpired(value.expires_at))
        throw new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' });
      eventRevision.current += 1; markEventSharing('off'); setEventPreview(value);
    });
  };
  const subscribeEvents = () => {
    if (!session || !eventPreview || !eventOptIn || eventSharing !== 'off') return;
    if (previewExpired(eventPreview.expires_at)) { clearReview(); setError(interopErrorMessage(new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' }))); return; }
    const reviewed = eventPreview;
    setEventPreview(undefined); markEventSharing('unknown');
    void run('确认持续状态共享', async (requestId, signal, current) => {
      const value = await client.eventSubscribe(session.session_id, reviewed.preview_id, requestId, signal);
      if (!current()) return;
      requireReceipt(value, requestId, session.session_id);
      if (value.subscription_active !== true || JSON.stringify([...value.metadata_fields].sort()) !== JSON.stringify([...reviewed.metadata_fields].sort()))
        throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' });
      eventRevision.current += 1; markEventSharing('active', value.metadata_fields); setEventOptIn(false);
    }, true);
  };
  const has = (capability: string) => session?.capabilities.includes(capability) === true;
  const canConnect = !!status?.enabled && status.feature_enabled && !status.acceptance_mode
    && !!props.context.sessionToken && !!props.context.scope && !revokingSession.current && !masterOffPending.current;
  const selectionReady = props.sourceReady && !!props.selection?.text && Number.isInteger(props.selection.text_start) && Number.isInteger(props.selection.text_end);
  const canPreview = !!session && has('tutor.guidance.request') && (!content || content === 'NONE' || props.sourceReady)
    && (content !== 'SELECTION' || selectionReady) && (content !== 'SPECIFIC_CONTEXT' || sourceIds.length > 0);
  const previewExpired = (expires: string) => !Number.isFinite(Date.parse(expires)) || Date.parse(expires) <= Date.now();
  const changeContent = (value: ContentKind) => { cancelPending(false); clearReview(); setContent(content === value ? 'NONE' : value); };
  const switchView = (next: View) => { if (eventPreview) stopEventSharing(); else { cancelPending(false); clearReview(); } setView(next); };
  const connect = () => void run('连接本机 Tutor', async (request_id, signal, current) => {
    const scope = props.context.scope!;
    const value = await client.connect({ request_id, endpoint, project_id: props.projectId,
      scope: { workspace_id: scope.workspaceId, project_id: scope.projectId, storyline_id: scope.storylineId, branch_id: scope.branchId },
      module: props.module, surface: props.surface, chapter_id: props.chapterId, task_id: props.taskId }, signal);
    if (!current()) { void client.disconnect(value.session_id).catch(() => undefined); return; }
    requireReceipt(value, request_id, value.session_id);
    if (value.subscription_active !== false || !Array.isArray(value.metadata_fields) || value.metadata_fields.length !== 0
      || value.product.product_role !== 'AI_TUTOR' || !value.product.protocol_versions?.includes('1.0')
      || value.capabilities.some(capability => ['model.execute', 'project.write'].includes(capability))) {
      void client.disconnect(value.session_id).catch(() => undefined);
      throw new ApiError({ status: 400, code: 'INVALID_MESSAGE', message: '' });
    }
    currentSession.current = value; setSession(value); clearReview();
    eventRevision.current += 1; markEventSharing('off'); setEventOptIn(false); setEventFields([...metadataFields]);
  });
  const changeEnabled = (enabled: boolean) => {
    if (!enabled) { masterOffPending.current = true; markEventSharing('unknown'); void disconnect(false); }
    void run(enabled ? '启用本机集成' : '关闭本机集成', async (request_id, signal, current) => {
      await client.settings(enabled, request_id, signal);
      const value = await client.status(signal);
      if (current()) {
        if (!enabled && value.enabled) throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' });
        setStatus(value); if (!value.enabled) confirmRevocation();
      }
    });
  };
  const buildPreview = () => {
    if (!session || !canPreview) return;
    if (eventPreview) pauseSharingAfterCancellation();
    clearReview();
    void run('生成共享预览', async (request_id, signal, current) => {
      const value = await client.preview({ request_id, session_id: session.session_id, content_kind: content,
        metadata_fields: fields, chapter_id: props.chapterId,
        ...(content !== 'NONE' ? { expected_chapter_version: props.chapterVersion } : {}),
        ...(content === 'SELECTION' ? { selection_start: props.selection!.text_start, selection_end: props.selection!.text_end } : {}),
        ...(content === 'SPECIFIC_CONTEXT' ? { context_ids: sourceIds } : {}),
      }, signal);
      if (!current()) return;
      requireReceipt(value, request_id, session.session_id);
      if (previewExpired(value.expires_at)) throw new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' });
      setPreview(value);
    });
  };
  const share = (kind: 'context' | 'diagnostic') => {
    const receipt = kind === 'context' ? preview : diagnostic;
    if (!session || !receipt) return;
    if (previewExpired(receipt.expires_at)) { clearReview(); setError(interopErrorMessage(new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' }))); return; }
    setPreview(undefined); setDiagnostic(undefined); // Consume this approval before awaiting.
    void run('等待 Tutor 指导', async (request_id, signal, current) => {
      const value = await (kind === 'context' ? client.ask : client.diagnosticShare)(session.session_id, receipt.preview_id, request_id, signal);
      if (!current()) return;
      requireReceipt(value, request_id, session.session_id);
      if (value.guidance.session_id !== session.protocol_session_id || value.guidance.request_id !== request_id)
        throw new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' });
      setGuidance(value.guidance);
    });
  };
  const handoff = (target: HandoffTarget) => {
    if (!session) return;
    void run('核对导航目标', async (request_id, signal, current) => {
      const value = await client.handoff(session.session_id, target, request_id, signal);
      if (!current()) return;
      requireReceipt(value, request_id, session.session_id);
      await props.onNavigate(value.route, signal);
      if (current()) close();
    });
  };
  const loadSources = () => {
    if (!session) return;
    void run('读取可选资料元数据', async (_id, signal, current) => {
      const value = await client.sources(session.session_id, signal);
      if (!current()) return;
      if (value.session_id !== session.session_id) throw new ApiError({ status: 409, code: 'CONTEXT_STALE', message: '' });
      setSources(value.items);
    });
  };

  const body = <div className="backdrop local-tutor-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
    <section ref={dialog} className="local-tutor-dialog" role="dialog" aria-modal="true" aria-labelledby="local-tutor-title"
      onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
        if (event.key !== 'Tab') return;
        const nodes = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]')];
        if (!nodes.length) return;
        const index = nodes.indexOf(document.activeElement as HTMLElement);
        event.preventDefault(); nodes[(index + (event.shiftKey ? -1 : 1) + nodes.length) % nodes.length]?.focus();
      }}>
      <header className="local-tutor-header"><div><h2 id="local-tutor-title">问助手 · Local Tutor</h2><p>本机优先 · 预览后确认 · 只读指导</p></div><Button ref={closeButton} onClick={close} aria-label="关闭本机 Tutor">关闭</Button></header>
      <nav className="local-tutor-tabs" aria-label="Tutor 功能">
        <Button aria-pressed={view === 'ask'} onClick={() => switchView('ask')}>问助手</Button>
        <Button aria-pressed={view === 'diagnostics'} onClick={() => switchView('diagnostics')}>共享诊断</Button>
        <Button aria-pressed={view === 'settings'} onClick={() => switchView('settings')}>集成设置</Button>
      </nav>
      <div className="local-tutor-scroll">
        {error && <StatusMessage tone="error">{error}</StatusMessage>}
        {notice && <StatusMessage>{notice}</StatusMessage>}
        {eventSharing === 'unknown' && !session && <StatusMessage tone="warning"><strong>撤销状态 UNKNOWN</strong><p>尚未确认主机已停止持续共享。关闭面板不会关闭 Studio 主机。</p>{revokingSession.current && <Button onClick={() => void disconnect()}>重试断开连接</Button>}{masterOffPending.current && <Button disabled={!!busy} onClick={() => changeEnabled(false)}>重试关闭集成</Button>}<Button onClick={dismissUnconfirmed}>仅关闭面板（撤销未确认）</Button></StatusMessage>}
        <div className="local-tutor-boundary"><Badge tone={session?.mode === 'MOCK_ONLY' ? 'warning' : 'neutral'}>{session?.mode ?? 'LOCAL_REQUIRED'}</Badge><span>真实 Tutor Desktop 接入与 Windows Named Pipe：LOCAL_REQUIRED。参考服务连接不代表桌面联调完成。</span></div>
        {(!props.context.sessionToken || !props.context.scope) && <StatusMessage>需已授权的工作区会话；当前文件模式仍可正常写作。</StatusMessage>}
        {!status && !busy && props.context.sessionToken && <Button onClick={refreshStatus}>重试读取集成状态</Button>}
        {status && <>
          <Panel title="AI Tutor Integration" actions={<Badge tone={session ? 'success' : 'neutral'}>{eventSharing === 'unknown' && !session ? '撤销待确认' : session ? '已握手' : status.enabled ? '等待连接' : '关闭'}</Badge>}>
            <label className="local-tutor-choice"><input type="checkbox" checked={status.enabled && !status.acceptance_mode} disabled={!!busy && !status.enabled || !status.feature_enabled || status.acceptance_mode} onChange={event => changeEnabled(event.target.checked)} />Enable Local Tutor Integration</label>
            {status.acceptance_mode ? <p>V1 Acceptance Mode 强制关闭此实验功能。</p> : !status.feature_enabled ? <p>实验开关 local_tutor_interop_v1 当前关闭；需要主机明确启用后才能连接。</p> : !status.enabled ? <p>默认关闭。启用不会自动发现、启动或连接其他软件。</p> : null}
            <dl className="local-tutor-facts"><div><dt>Detected Tutor</dt><dd>{session?.product.display_name ?? '未连接'}</dd></div><div><dt>Protocol</dt><dd>{session ? 'PoemSeed Local Interop 1.0' : '待握手：1.0'}</dd></div><div><dt>当前范围</dt><dd>{props.module} / {props.surface}</dd></div></dl>
            {!session ? <div className="local-tutor-connect"><label>开发用本机 Tutor 地址<input aria-label="开发用本机 Tutor 地址" placeholder="http://127.0.0.1:端口" value={endpoint} disabled={!!busy} onChange={event => setEndpoint(event.target.value)} /></label><Button disabled={!canConnect || !endpoint || !!busy} onClick={connect}>连接本机 Tutor</Button><small>仅 loopback HTTP 参考运行时。不会扫描网络、自动启动应用或共享正文。</small></div> : <Button disabled={!!busy} onClick={() => disconnect()}>断开连接</Button>}
          </Panel>
          {session && <Panel title="持续状态共享 · 本次会话" aria-label="持续状态共享" actions={<Badge tone={eventSharing === 'active' ? 'info' : eventSharing === 'unknown' ? 'warning' : 'neutral'}>{eventSharing === 'active' ? '已授权持续共享' : eventSharing === 'unknown' ? '状态待确认' : '持续共享关闭'}</Badge>}>
            <p>仅连接和单次问助手不会授权后续状态共享。持续共享仅包含本次会话的元数据，正文始终为 NONE。</p>
            <p>范围：{props.module} / {props.surface}；仅当前项目、分支和章节。关闭、切换范围或重连后须重新确认。</p>
            {eventSharing === 'unknown' && <p>共享状态尚未确认；可停止持续共享或关闭集成。</p>}
            {eventSharing === 'active' && <p aria-label="正在共享的状态类别">已授权类别：软件、页面与范围 ID{sharedEventFields.map(field => ` · ${metadataNames[field]}`).join('')}</p>}
            {eventSharing !== 'off' ? <Button onClick={stopEventSharing}>停止持续状态共享</Button> : <>
              <label className="local-tutor-choice"><input type="checkbox" checked={eventOptIn} disabled={!!busy} onChange={event => { if (!event.target.checked && eventPreview) stopEventSharing(); else { setEventOptIn(event.target.checked); setEventPreview(undefined); } }} />准备持续共享状态（需另行预览和确认）</label>
              {eventOptIn && <>
                <p>软件身份、协议、当前页面和范围 ID 为必需元数据。选择允许后续更新的类别：</p>
                {metadataFields.map(field => <label className="local-tutor-choice" key={field}><input type="checkbox" checked={eventFields.includes(field)} disabled={!!busy} onChange={() => { if (eventPreview) stopEventSharing(); else setEventPreview(undefined); setEventFields(values => values.includes(field) ? values.filter(value => value !== field) : [...values, field]); }} />持续共享：{metadataNames[field]}</label>)}
                <Button disabled={!!busy} onClick={previewEventSharing}>预览持续状态共享</Button>
              </>}
            </>}
            <p>停止后不会自动恢复；已经发送的信息无法撤回。</p>
            {eventPreview && <div><h3>待确认的持续共享范围</h3><p>允许后续更新：软件、页面与范围 ID{eventPreview.metadata_fields.map(field => ` · ${metadataNames[field]}`).join('')}</p><pre className="local-tutor-preview" aria-label="持续状态共享预览" tabIndex={0}>{JSON.stringify({ metadata_fields: eventPreview.metadata_fields, capsule: eventPreview.capsule, expires_at: eventPreview.expires_at }, null, 2)}</pre><Button disabled={!!busy} onClick={stopEventSharing}>取消持续共享预览</Button><Button variant="primary" disabled={!!busy} onClick={subscribeEvents}>确认开启本次会话持续共享</Button></div>}
          </Panel>}
          {view === 'settings' && <Panel title={session ? '当前协商权限' : '可用协议能力（尚未授予 Tutor）'}>
            <ul>{(session?.capabilities ?? status.capabilities).map(capability => <li key={capability}>{capabilityNames[capability] ?? capability} <small>{capability}</small></li>)}</ul>
            <p>选中文本、当前章节和其他资料每次均需重新勾选、预览和确认。</p>
            <p>Disabled：Model Execution · Project Write · 自动修改设置</p>
            <p>关闭集成会断开连接并停止后续事件；保留 Studio 项目与 Tutor 历史。</p>
          </Panel>}
          {view === 'ask' && <Panel title="将共享的内容">
            {eventSharing === 'active' && <p>持续共享正在按上方已授权类别运行；本次额外内容仍需单独确认。</p>}
            <label className="local-tutor-choice"><input type="checkbox" checked disabled />当前软件与版本（协议必需）</label>
            <label className="local-tutor-choice"><input type="checkbox" checked disabled />当前页面与范围 ID（协议必需）</label>
            {metadataFields.map(field => <label className="local-tutor-choice" key={field}><input type="checkbox" checked={fields.includes(field)} disabled={!!busy} onChange={() => { clearReview(); setFields(values => values.includes(field) ? values.filter(value => value !== field) : [...values, field]); }} />{metadataNames[field]}</label>)}
            <div className="local-tutor-content-choices">
              <label className="local-tutor-choice"><input type="checkbox" checked={content === 'SELECTION'} disabled={!!busy || !selectionReady || !has('project.selection.share')} onChange={() => changeContent('SELECTION')} />选中文本</label>
              <label className="local-tutor-choice"><input type="checkbox" checked={content === 'CHAPTER'} disabled={!!busy || !props.sourceReady || !props.chapterId || !has('project.context.read')} onChange={() => changeContent('CHAPTER')} />当前章节</label>
              <label className="local-tutor-choice"><input type="checkbox" checked={content === 'SPECIFIC_CONTEXT'} disabled={!!busy || !props.sourceReady || !has('project.context.read')} onChange={() => changeContent('SPECIFIC_CONTEXT')} />其他资料（明确选择章节）</label>
            </div>
            {!props.sourceReady && <p>正文尚未保存或未打开；可共享元数据，正文需要先保存并核对版本。</p>}
            {!selectionReady && props.sourceReady && <p>请先在当前编辑器选中文本，再打开问助手。</p>}
            {content === 'SELECTION' && <><p>已选 {Array.from(props.selection?.text ?? '').length} 字符 · 来源版本 {props.chapterVersion}</p><pre className="local-tutor-preview" aria-label="当前编辑器选区">{props.selection?.text}</pre></>}
            {content === 'SPECIFIC_CONTEXT' && <div><Button disabled={!!busy} onClick={loadSources}>列出可选章节元数据</Button><p>最多选择 4 个章节，总内容有上限；不会自动选择整个项目。</p>{sources.map(source => <label key={source.id} className="local-tutor-choice"><input type="checkbox" checked={sourceIds.includes(source.id)} disabled={!!busy || sourceIds.length >= 4 && !sourceIds.includes(source.id)} onChange={() => { clearReview(); setSourceIds(ids => ids.includes(source.id) ? ids.filter(id => id !== source.id) : [...ids, source.id]); }} />{source.label} · v{source.version}</label>)}</div>}
            <p>默认 content = NONE。此步骤只在 Studio 主机生成预览；确认后才发送到已连接的 Tutor。</p>
            <Button disabled={!canPreview || !!busy} onClick={buildPreview}>生成共享预览</Button>
          </Panel>}
          {view === 'diagnostics' && <Panel title="诊断字段预览选择">
            <p>生成诊断预览前会先停止持续共享，之后不会自动恢复；已发送的信息无法撤回。</p>
            <p>仅限已清理、有限量的本机诊断；不包含正文、原始 Prompt、密钥、完整路径、截图或日志转储。</p>
            {diagnosticFields.map(field => <label key={field} className="local-tutor-choice"><input type="checkbox" checked={diagnostics.includes(field)} disabled={!!busy} onChange={() => { clearReview(); setDiagnostics(values => values.includes(field) ? values.filter(value => value !== field) : [...values, field]); }} />{diagnosticNames[field]}</label>)}
            <Button disabled={!!busy || !session || !has('diagnostics.read') || !has('tutor.guidance.request')} onClick={() => { if (!session) return; clearReview(); setEventOptIn(false); eventRevision.current += 1; markEventSharing('unknown'); void run('生成诊断预览', async (request_id, signal, current) => { const value = await client.diagnosticPreview(session.session_id, diagnostics, request_id, signal); if (!current()) return; requireReceipt(value, request_id, session.session_id); if (value.event_subscription_paused !== true) throw new ApiError({ status: 409, code: 'INVALID_MESSAGE', message: '' }); markEventSharing('off'); setNotice('已停止持续状态共享，再生成最小化诊断预览；不会自动恢复。已发送的信息无法撤回。'); setDiagnostic(value); }, true); }}>生成诊断预览</Button>
          </Panel>}
        </>}
        {preview && <Review title="待确认的 Context Capsule" expires={preview.expires_at} value={preview.capsule} busy={!!busy} onCancel={() => { clearReview(); setNotice('已取消共享。'); }} onConfirm={() => share('context')} />}
        {diagnostic && <Review title="待确认的 Diagnostic Capsule" expires={diagnostic.expires_at} value={{ diagnostic: diagnostic.diagnostic, context: diagnostic.capsule }} busy={!!busy} onCancel={() => { clearReview(); setNotice('已取消共享。'); }} onConfirm={() => share('diagnostic')} />}
        {guidance && <Panel title="Tutor Guidance · 只读建议">
          <StatusMessage>建议不会写入正文、修改设置、运行模型或自动导航。Tutor Advice ≠ Canon。</StatusMessage>
          <h3>{guidance.summary}</h3><p className="local-tutor-text">{guidance.diagnosis}</p>
          <ol>{(guidance.steps ?? []).map(step => <li key={step.step_id}><p className="local-tutor-text">{step.instruction}</p>{step.handoff && <Button disabled={!!busy} onClick={() => handoff(step.handoff!)}>核对并打开目标</Button>}</li>)}</ol>
          {!!guidance.warnings?.length && <div><h3>注意事项</h3><ul>{(guidance.warnings ?? []).map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
          {!!guidance.references?.length && <div><h3>参考来源（定位信息，不自动读取）</h3><ul>{(guidance.references ?? []).map((reference, index) => <li key={index}>{reference.label} · {reference.source_id} · <span className="local-tutor-text">{reference.locator}</span></li>)}</ul></div>}
          {guidance.recommended_model && <div><h3>模型建议 · 不自动执行</h3><pre className="local-tutor-preview">{JSON.stringify(guidance.recommended_model, null, 2)}</pre></div>}
          {guidance.verification_condition && <div><h3>验证条件</h3><pre className="local-tutor-preview">{JSON.stringify(guidance.verification_condition, null, 2)}</pre><Button disabled={!!busy || !session || !has('verifier.request')} onClick={() => { if (!session) return; void run('核对真实 Studio 状态', async (request_id, signal, current) => { const value = await client.verify(session.session_id, guidance.guidance_id, request_id, signal); if (!current()) return; requireReceipt(value, request_id, session.session_id); requireReceipt(value.result, request_id, session.protocol_session_id); setVerification(value.result); }); }}>使用当前 Studio 证据验证</Button></div>}
          {verification && <div role="status"><Badge tone={verification.status === 'VERIFIED' ? 'success' : verification.status === 'FAILED' ? 'error' : 'warning'}>{verification.status}</Badge><p>{verification.reason}</p><p>依据主机状态和证据，不采用模型自报成功。</p><pre className="local-tutor-preview" aria-label="验证证据">{JSON.stringify(verification.evidence, null, 2)}</pre></div>}
        </Panel>}
      </div>
      <footer className="local-tutor-footer"><span role="status">{busy || (eventSharing === 'unknown' ? '撤销状态 UNKNOWN' : session ? '已连接 · LOCAL_ONLY' : '面板未连接')}</span>{busy && <Button onClick={() => cancelPending()}>取消当前请求</Button>}<Button onClick={close}>关闭并断开</Button></footer>
    </section>
  </div>;
  return createPortal(body, document.body);
}

function Review({ title, value, expires, busy, onCancel, onConfirm }: { title: string; value: unknown; expires: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <Panel title={title}><p>请核对完整内容。有效期至 {expires}；来源或权限变化后须重新预览。</p><pre className="local-tutor-preview" aria-label={title} tabIndex={0}>{JSON.stringify(value, null, 2)}</pre><div className="local-tutor-actions"><Button disabled={busy} onClick={onCancel}>取消共享</Button><Button variant="primary" disabled={busy} onClick={onConfirm}>确认并发送给 Tutor</Button></div></Panel>;
}
