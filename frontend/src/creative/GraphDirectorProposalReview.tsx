import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import { AIDirectorPanel } from './AIDirectorPanel';
import type { CreativeClient, DirectorProposalClient } from './client';
import type { CreativeDocument } from './types';
import type { DirectorModelClient } from './directorModelClient';
import type { PlanningSnapshot } from './studioProductionGraphContract';

export type GraphDirectorReviewSource = Pick<CreativeClient, 'list'> & Partial<DirectorProposalClient>;
const methods = ['proposals', 'proposal', 'propose', 'review', 'cancelProposal', 'get',
  'modelRoutes', 'previewModel', 'dispatchModel', 'refreshModel'] as const;
export function hasDirectorProposalReview(client: GraphDirectorReviewSource): client is GraphDirectorReviewSource & DirectorProposalClient {
  return methods.every(key => typeof client[key] === 'function');
}
type Props = {
  client: GraphDirectorReviewSource & DirectorProposalClient;
  active: boolean; canMutate: boolean; busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onPendingChange: (value: boolean) => void;
  onDocument: (document: CreativeDocument, expectedSnapshot?: PlanningSnapshot) => void;
  onDenied: () => void;
  onOpenModels?: () => void;
};

/** Mount the original proposal queue and review owner inside the optional canvas
 * console. No parallel proposal store, automatic graph pin or execution path. */
export function GraphDirectorProposalReview(props: Props) {
  const [open, setOpen] = useState(false), [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<CreativeDocument[]>([]), [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const alive = useRef(true), initialClient = useRef(props.client);
  const latest = useRef(props); latest.current = props;
  const life = useRef({ active: props.active, client: props.client, generation: 0 });
  const modelAuthority = useRef({ allowed: props.canMutate, generation: 0 });
  if (modelAuthority.current.allowed !== props.canMutate)
    modelAuthority.current = { allowed: props.canMutate, generation: modelAuthority.current.generation + 1 };
  if (life.current.active !== props.active || life.current.client !== props.client)
    life.current = { active: props.active, client: props.client, generation: life.current.generation + 1 };
  const requests = useRef(0), requestLock = useRef(false);
  const pendingParts = useRef({ loading: false, review: false });
  const report = useCallback((part: 'loading' | 'review', value: boolean) => {
    pendingParts.current[part] = value;
    const next = pendingParts.current.loading || pendingParts.current.review;
    setPending(next); latest.current.onPendingChange(next);
  }, []);
  const reviewPending = useCallback((value: boolean) => report('review', value), [report]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; requests.current++; }; }, []);
  const boundClient = useMemo<DirectorProposalClient>(() => {
    const assertCurrent = (generation: number) => {
      if (!alive.current || !latest.current.active || !latest.current.isCurrent()
          || initialClient.current !== props.client || latest.current.client !== props.client || life.current.generation !== generation)
        throw new ApiError({ status: 403, code: 'STUDIO_GRAPH_SCOPE_MISMATCH', message: '身份或项目已变化，请重新打开导演审核。' });
    };
    const call = async <T,>(write: boolean, work: () => Promise<T>) => {
      const generation = life.current.generation;
      assertCurrent(generation);
      if (write && (!latest.current.canMutate || latest.current.busy))
        throw new Error('请先处理当前导演或画布操作，再提交建议审核。');
      const result = await (write ? latest.current.mutate : latest.current.read)(() => { assertCurrent(generation); return work(); });
      assertCurrent(generation);
      return result;
    };
    const independentDirector = props.client.independentDirector ? () => {
      const generation = life.current.generation;
      const authorityGeneration = modelAuthority.current.generation;
      assertCurrent(generation);
      const original = props.client.independentDirector!();
      const assertModelCurrent = () => {
        assertCurrent(generation);
        if (modelAuthority.current.generation !== authorityGeneration)
          throw new ApiError({ status: 403, code: 'STUDIO_GRAPH_SCOPE_MISMATCH', message: '审核上下文已变化，请重新打开模型审核。' });
      };
      const invoke = async <T,>(write: boolean, work: () => Promise<T>) => {
        // A retained factory result cannot borrow a later active lifetime.
        assertModelCurrent();
        const result = await call(write, () => { assertModelCurrent(); return work(); });
        assertModelCurrent();
        if (write && !latest.current.canMutate)
          throw new ApiError({ status: 403, code: 'STUDIO_GRAPH_SCOPE_MISMATCH', message: '审核权限已变化，请重新核对原任务状态。' });
        return result;
      };
      return {
        readStatus: (...args) => invoke(false, () => original.readStatus(...args)),
        readAdoptedDraft: (...args) => invoke(false, () => original.readAdoptedDraft(...args)),
        readPreview: (...args) => invoke(false, () => original.readPreview(...args)),
        readPending: (...args) => invoke(false, () => original.readPending(...args)),
        reconcileReview: (...args) => invoke(false, () => original.reconcileReview(...args)),
        preview: (...args) => invoke(true, () => original.preview(...args)),
        dispatch: (...args) => invoke(true, () => original.dispatch(...args)),
        prepareReview: (...args) => invoke(true, () => original.prepareReview(...args)),
        review: (...args) => invoke(true, () => original.review(...args)),
        cancel: (...args) => invoke(true, () => original.cancel(...args)),
      } satisfies DirectorModelClient;
    } : undefined;
    return {
      ...(independentDirector ? { independentDirector } : {}),
      proposals: signal => call(false, () => props.client.proposals(signal)),
      proposal: (id, signal) => call(false, () => props.client.proposal(id, signal)),
      get: (id, signal) => call(false, () => props.client.get(id, signal)),
      modelRoutes: signal => call(false, () => props.client.modelRoutes(signal)),
      ...(props.client.modelCapabilities ? { modelCapabilities: (signal?: AbortSignal) => call(false, () => props.client.modelCapabilities!(signal)) } : {}),
      ...(props.client.previewStoryboardModel ? { previewStoryboardModel: (...args: Parameters<NonNullable<DirectorProposalClient['previewStoryboardModel']>>) => call(true, () => props.client.previewStoryboardModel!(...args)) } : {}),
      ...(props.client.dispatchStoryboardModel ? { dispatchStoryboardModel: (...args: Parameters<NonNullable<DirectorProposalClient['dispatchStoryboardModel']>>) => call(true, () => props.client.dispatchStoryboardModel!(...args)) } : {}),
      propose: (...args) => call(true, () => props.client.propose(...args)),
      review: (...args) => call(true, () => props.client.review(...args)),
      cancelProposal: (...args) => call(true, () => props.client.cancelProposal(...args)),
      previewModel: (...args) => call(true, () => props.client.previewModel(...args)),
      dispatchModel: (...args) => call(true, () => props.client.dispatchModel(...args)),
      refreshModel: (...args) => call(true, () => props.client.refreshModel(...args)),
    };
  }, [props.client]);
  const acceptDocument = useCallback((document: CreativeDocument, expectedSnapshot?: PlanningSnapshot) => {
    if (!alive.current || !latest.current.active || !latest.current.isCurrent() || initialClient.current !== latest.current.client) return;
    latest.current.onDocument(document, expectedSnapshot ? { ...expectedSnapshot } : undefined);
  }, []);
  const denied = useCallback(() => {
    if (!alive.current || initialClient.current !== latest.current.client) return;
    setDocuments([]); setOpen(false); latest.current.onDenied();
  }, []);
  async function loadSources() {
    if (requestLock.current || pending || props.busy || !props.active || !props.isCurrent() || initialClient.current !== props.client) return;
    const generation = life.current.generation, ticket = ++requests.current;
    const current = () => alive.current && latest.current.active && latest.current.isCurrent()
      && initialClient.current === latest.current.client && generation === life.current.generation && ticket === requests.current;
    requestLock.current = true; setLoading(true); report('loading', true); setError('');
    try {
      const result = await props.read(() => {
        if (!current()) throw new Error('原来源读取已过期，请重新打开导演审核。');
        return props.client.list();
      });
      if (!current()) return;
      setDocuments(result.items); setOpen(true);
    } catch (reason) {
      if (!current()) return;
      setError(apiErrorView(reason, '剧本或分镜来源读取失败，未创建导演建议。').message);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) denied();
    } finally {
      requestLock.current = false;
      if (alive.current) { setLoading(false); report('loading', false); }
    }
  }
  if (!props.active || !props.isCurrent() || initialClient.current !== props.client) return null;
  return <section aria-label="画布原导演建议审核">
    <h3>原剧本 / 分镜 → 导演建议与人工审核</h3>
    <p>读取原 Creative owner 已保存的剧本或分镜，复用原建议与审核队列。分镜默认使用规则辅助；只有主机明确支持完整分镜上下文并逐次确认，才可调用本地模型。采用后是独立导演草稿；图节点绑定仍需明确选择和保存。</p>
    <Button disabled={props.busy || loading || pending} onClick={() => void loadSources()}>
      {open ? '刷新原剧本来源' : '从已保存剧本打开导演建议审核'}
    </Button>
    {!open && <Button disabled={props.busy || loading || pending} onClick={() => void loadSources()}>从已保存分镜打开导演建议审核</Button>}
    {open && <Button disabled={props.busy || pending} onClick={() => setOpen(false)}>收起导演建议审核</Button>}
    {loading && <StatusMessage>正在读取原剧本来源…</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {open && <AIDirectorPanel client={boundClient} documents={documents} canMutate={props.canMutate && !props.busy && !loading} modelAuthority={props.canMutate}
      onDocument={acceptDocument} onDenied={denied} onPendingChange={reviewPending} onOpenModels={props.onOpenModels} />}
  </section>;
}
