import {useEffect, useRef, useState, useSyncExternalStore} from 'react';
import {api, getCollaborationContext, getCollaborationEpoch, subscribeCollaborationContext} from '../../api';
import {ImageQueuePanel} from '../../novel/ImageQueuePanel';
import {Button, Panel, StatusMessage} from '../../ui/primitives';
import {CloudPromptConsent, useScopedRequestConsent} from '../../useScopedRequestConsent';
import {useStudio} from '../../store';
import {useLocalHostSession} from '../../localHostSession';
import {rbError} from '../rebuildApi';
import {writeCanvasTaskBinding} from './canvasTaskBinding';
import {useCanvasTaskBinding} from './useCanvasTaskBinding';

type Props = {novelId: string; nodeId: string; prompt: string; onClose: () => void; isSourceCurrent?: () => boolean};
type Provider = {
  provider_id: string; display_name?: string; default_model?: string;
  configured: boolean; registered: boolean; reachable?: boolean; local?: boolean;
};
const configured = (provider: Provider) => provider.configured === true && provider.registered === true && provider.reachable !== false;
const clientIdentity = () => {
  const context = getCollaborationContext();
  return JSON.stringify([context.sessionToken, context.localHostToken, context.actor?.id, context.actor?.workspaceId,
    context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
};
const identity = (state: ReturnType<typeof useStudio.getState>) => JSON.stringify([
  state.sessionToken, state.actor?.id, state.actor?.workspaceId, state.scope?.workspaceId,
  state.scope?.projectId, state.scope?.storylineId, state.scope?.branchId, state.novelId,
]);

/** A draft node supplies text only. Persistent jobs and their IDs belong to the existing image queue. */
export function CanvasImageQueue(props: Props) {
  const {scopeKey} = useScopedRequestConsent([]);
  const hostEpoch = useLocalHostSession(state => state.epoch);
  const clientEpoch = useSyncExternalStore(subscribeCollaborationContext, getCollaborationEpoch, getCollaborationEpoch);
  const [scopeEpoch, setScopeEpoch] = useState(0);
  useEffect(() => {
    let observed = identity(useStudio.getState());
    return useStudio.subscribe(state => {
      const next = identity(state);
      if (next !== observed) {
        observed = next;
        // Retire both provider reads and the queue owner even for a batched A/B/A change.
        setScopeEpoch(epoch => epoch + 1);
      }
    });
  }, []);
  return <CanvasImageQueueSession key={JSON.stringify([scopeKey, scopeEpoch, hostEpoch, clientEpoch, props.novelId, props.nodeId, props.prompt])} {...props} />;
}

function CanvasImageQueueSession({novelId, nodeId, prompt, onClose, isSourceCurrent}: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerId, setProviderId] = useState('');
  const [modelId, setModelId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bindingError, setBindingError] = useState('');
  const {owner: bindingOwner, binding} = useCanvasTaskBinding(novelId, nodeId);
  const inputRevision = useRef(0);
  const revision = inputRevision.current;
  const hostEpoch = useLocalHostSession(state => state.epoch);
  const consent = useScopedRequestConsent([novelId, nodeId, prompt, providerId, modelId]);
  useEffect(() => {
    let current = true;
    const capturedScope = consent.captureScope();
    const client = clientIdentity();
    const clientEpoch = getCollaborationEpoch();
    const scopeCurrent = () => capturedScope() && useLocalHostSession.getState().epoch === hostEpoch && clientIdentity() === client && getCollaborationEpoch() === clientEpoch;
    api.assetProviders().then(result => {
      if (current && scopeCurrent()) setProviders((Array.isArray(result.items) ? result.items : []).filter(
        item => !!item && typeof item.provider_id === 'string' && !!item.provider_id.trim(),
      ));
    }).catch(reason => { if (current && scopeCurrent()) setError(rbError(reason)); })
      .finally(() => { if (current && scopeCurrent()) setLoading(false); });
    return () => { current = false; };
  }, []);
  const provider = providers.find(item => item.provider_id === providerId);
  const local = provider?.local === true;
  const canCreate = !!novelId && !!prompt.trim() && !!provider && configured(provider) && !!modelId.trim() && (local || consent.allowed);
  const capturedScope = consent.captureScope();
  const canCreateNow = () => {
    if (isSourceCurrent && !isSourceCurrent()) { setBindingError('原图片节点已退役或已移除；请关闭面板并从当前原节点重新打开，不会继续入队。'); return false; }
    return canCreate && capturedScope() && inputRevision.current === revision && useLocalHostSession.getState().epoch === hostEpoch;
  };
  const draft = {novel_id: novelId, provider_id: providerId, model_id: modelId.trim(), prompt: prompt.trim(), allow_cloud_prompt: !local && consent.allowed};
  const rememberCreatedTask = (receipt: unknown) => {
    if (isSourceCurrent && !isSourceCurrent()) return;
    const row = receipt && typeof receipt === 'object' ? receipt as Record<string, unknown> : undefined;
    if (!row || typeof row.id !== 'string' || row.novel_id !== novelId || row.provider_id !== draft.provider_id
      || row.model_id !== draft.model_id || row.prompt !== draft.prompt
      || bindingOwner?.mode === 'collaboration' && row.branch_id !== bindingOwner.branchId) {
      setBindingError('任务回执缺少可核实的原项目与任务 ID，未保存节点关联；请核对原队列，不会自动重试。');
      return;
    }
    if (!bindingOwner || !writeCanvasTaskBinding(bindingOwner, nodeId, row.id)) {
      setBindingError(`任务已入队（${row.id}），但本机关联未保存。请保留原任务 ID 并核对身份、节点及浏览器存储；不会自动重试。`);
    } else setBindingError('');
  };
  return <Panel title="所选节点的图片任务" actions={<Button type="button" variant="ghost" onClick={onClose}>关闭节点任务参数</Button>}>
    <p>来源节点：{nodeId}。仅使用本次确认的提示词；画布结构仍是本机草稿，不会保存为服务端执行图。</p>
    <label>本次节点提示词<textarea aria-label="本次节点提示词" value={prompt} readOnly rows={3}/></label>
    <p className="novel-help">先选择服务与模型，再明确保存到队列。执行、取消和接受结果均由原任务入口单独确认；服务配置不代表推理已经验证。</p>
    {loading && <StatusMessage>正在读取图片服务配置…</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {!bindingOwner && <StatusMessage>尚未验证可持久关联的身份；显式入队后仍需保留原任务 ID，本面板不会声称已恢复节点关联。</StatusMessage>}
    {bindingError && <StatusMessage tone="warning">{bindingError}</StatusMessage>}
    {binding && <p className="novel-help">此节点原入队任务：{binding.taskId}。这是历史任务关联，不代表当前提示词已经入队。</p>}
    {!loading && !error && !providers.some(configured) && <StatusMessage tone="warning">缺少已配置的图片服务，暂不能创建新任务。已有任务仍以服务端记录为准。</StatusMessage>}
    <label>图片服务<select aria-label="画布任务图片服务" value={providerId} disabled={loading || !!error} onChange={event => {
      inputRevision.current += 1;
      const id = event.target.value;
      setProviderId(id);
      setModelId(providers.find(item => item.provider_id === id)?.default_model || '');
    }}>
      <option value="">请选择图片服务</option>
      {providers.map(item => <option key={item.provider_id} value={item.provider_id} disabled={!configured(item)}>{item.display_name || item.provider_id}{configured(item) ? '' : '（未就绪）'}</option>)}
    </select></label>
    <label>模型<input aria-label="画布任务模型" value={modelId} disabled={!provider || !configured(provider)} onChange={event => { inputRevision.current += 1; setModelId(event.target.value); }}/></label>
    {provider && !local && <CloudPromptConsent target={`${provider.display_name || providerId} / ${modelId || '未选择模型'}`} checked={consent.allowed} onChange={allowed => { inputRevision.current += 1; consent.setAllowed(allowed); }}/>}
    <ImageQueuePanel novelId={novelId} draft={draft} local={local} creationDisabled={!canCreate} canCreateNow={canCreateNow} executionSourceRevision={revision} isExecutionSourceCurrent={()=>capturedScope()&&inputRevision.current===revision&&(!isSourceCurrent||isSourceCurrent())} requestedTaskId={binding?.taskId} onTaskCreated={rememberCreatedTask}/>
  </Panel>;
}
