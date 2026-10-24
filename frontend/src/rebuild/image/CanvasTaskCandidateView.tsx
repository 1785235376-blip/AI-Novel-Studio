import {useEffect, useRef, useState} from 'react';
import {api, getCollaborationContext, getCollaborationEpoch, subscribeCollaborationContext, type CollaborationContext, type ScopedReadOptions} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {Button, StatusMessage} from '../../ui/primitives';
import {canvasTaskBindingKey, captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskAdoption, type CanvasTaskBinding} from './canvasTaskBinding';
import {checkedCanvasTaskCandidate, sameCanvasTaskCandidate, type CanvasTaskCandidate} from './canvasTaskCandidate';
import {abortableCanvasCandidateRead, canvasCandidateBlobSha256, canvasCandidateCryptoAvailable, canvasCandidateMediaType,
  canvasCandidateObservationSha256, checkedCanvasCandidateAsset, sameCanvasCandidateAsset, type CanvasCandidateAsset} from './canvasCandidateReview';
import '../../novel/ImageTaskInspector.css';

type Props = {candidate: CanvasTaskCandidate; binding: CanvasTaskBinding; nodePrompt?: string; isCurrent: () => boolean; onUnavailable: (message: string) => void};
type Preview = {uri: string; request: number; fence: object; sha256?: string; size?: number; mediaType?: string};
type Review = {preview: Preview; asset: CanvasCandidateAsset; jobObservationSha256: string; fence: object};
const READ_TIMEOUT_MS = 15_000;
const MAX_IMAGE_BYTES = 36 * 1024 * 1024;
const stale = () => new Error('Candidate source or authority changed');

/** Original Job and Asset remain authoritative. Adoption is only a browser navigation hint. */
export function CanvasTaskCandidateView({candidate, binding, nodePrompt, isCurrent, onUnavailable}: Props) {
  const [preview, setPreview] = useState<Preview>();
  const [loaded, setLoaded] = useState<Preview>();
  const [review, setReview] = useState<Review>();
  const [confirmed, setConfirmed] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const mounted = useRef(false), running = useRef(false), sequence = useRef(0);
  const objectUrl = useRef<string>(), download = useRef<AbortController>();
  const previewRef = useRef<Preview>(), loadedRef = useRef<Preview>(), reviewRef = useRef<Review>(), confirmedRef = useRef(false);
  const initialEpoch = useRef({client: getCollaborationEpoch(), host: useLocalHostSession.getState().epoch});
  const fence = useRef({candidate, binding, nodePrompt, token: {}});
  if (fence.current.candidate !== candidate || fence.current.binding !== binding || fence.current.nodePrompt !== nodePrompt) {
    fence.current = {candidate, binding, nodePrompt, token: {}};
  }
  const token = fence.current.token;
  const live = useRef({candidate, isCurrent}); live.current = {candidate, isCurrent};
  const ownerKey = canvasTaskBindingKey(binding.owner, binding.nodeId);
  const sameOwner = () => {
    const owner = captureCanvasTaskOwner(candidate.novelId);
    return !!owner && canvasTaskBindingKey(owner, binding.nodeId) === ownerKey
      && JSON.stringify(readCanvasTaskBinding(owner, binding.nodeId)) === JSON.stringify(binding);
  };
  const current = () => mounted.current && fence.current.token === token && live.current.candidate === candidate
    && initialEpoch.current.client === getCollaborationEpoch() && initialEpoch.current.host === useLocalHostSession.getState().epoch
    && isCurrent() && live.current.isCurrent() && sameOwner();
  function clearReview() {
    confirmedRef.current = false; reviewRef.current = undefined;
    setConfirmed(false); setReview(undefined); setSaved(false);
  }
  function releasePreview() {
    if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = undefined; }
    previewRef.current = undefined; loadedRef.current = undefined;
    setPreview(undefined); setLoaded(undefined); clearReview();
  }
  function hide() {
    sequence.current += 1; download.current?.abort(); download.current = undefined;
    running.current = false; setBusy(false); releasePreview(); setError('');
  }
  useEffect(() => {
    mounted.current = true;
    const retire = () => {
      if (!mounted.current) return;
      hide();
      setError('原身份或权限范围已改变，请从原节点重新读取；旧预览与确认不会恢复。');
    };
    const stopClient = subscribeCollaborationContext(retire);
    const stopHost = useLocalHostSession.subscribe(state => { if (state.epoch !== initialEpoch.current.host) retire(); });
    return () => {
      mounted.current = false; sequence.current += 1; download.current?.abort(); stopClient(); stopHost();
      if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = undefined; }
    };
  }, []);
  useEffect(() => { hide(); }, [candidate, binding, nodePrompt]);

  function captureContext(): CollaborationContext {
    const context = getCollaborationContext();
    return {...context, scope: context.scope && {...context.scope}, actor: context.actor && {...context.actor},
      localHostToken: context.localHostToken ?? useLocalHostSession.getState().token};
  }
  function transaction() {
    const request = sequence.current;
    const controller = new AbortController(); download.current = controller;
    const timeout = setTimeout(() => controller.abort(), READ_TIMEOUT_MS);
    const options: ScopedReadOptions = {redirect: 'error', credentials: 'omit', cache: 'no-store',
      referrerPolicy: 'no-referrer', signal: controller.signal};
    const valid = () => current() && request === sequence.current && !controller.signal.aborted;
    const checked = <T,>(read: Promise<T>) => abortableCanvasCandidateRead(read, controller.signal).then(value => {
      if (!valid()) throw stale();
      return value;
    });
    const finish = () => {
      clearTimeout(timeout);
      if (download.current === controller) download.current = undefined;
      if (mounted.current && fence.current.token === token && request === sequence.current) {
        running.current = false; setBusy(false);
      }
    };
    return {request, controller, options, checked, valid, finish};
  }
  function matchesCandidate(result: {items: unknown[]}) {
    const matches = (Array.isArray(result.items) ? result.items : []).filter(row => row && typeof row === 'object' && 'id' in row && row.id === candidate.jobId);
    return sameCanvasTaskCandidate(candidate, matches.length === 1 ? checkedCanvasTaskCandidate(binding, matches[0]) : undefined);
  }
  async function assertWrite(context: CollaborationContext, tx: ReturnType<typeof transaction>) {
    if (!tx.valid() || !sameOwner()) throw stale();
    if (binding.owner.mode === 'collaboration') {
      if (!context.scope) throw stale();
      const permissions = await tx.checked(api.permissions(context.scope, context, tx.options));
      if (permissions.actor_id !== binding.owner.actorId || permissions.domain !== 'NOVEL' || permissions.capabilities?.['domain.write'] !== true) throw stale();
    } else {
      const host = useLocalHostSession.getState();
      if (!host.token || host.token !== context.localHostToken || host.actorId !== binding.owner.actorId
        || host.epoch !== initialEpoch.current.host) throw stale();
    }
    if (!tx.valid() || !sameOwner()) throw stale();
  }
  async function metadata(context: CollaborationContext, tx: ReturnType<typeof transaction>) {
    if (!candidate.assetId) throw stale();
    const result = await tx.checked(api.assetMetadata(candidate.assetId, candidate.novelId, context, tx.options));
    const asset = checkedCanvasCandidateAsset(binding, candidate, result);
    if (!asset) throw stale();
    return asset;
  }
  async function freshJob(context: CollaborationContext, tx: ReturnType<typeof transaction>) {
    if (!matchesCandidate(await tx.checked(api.imageJobs(candidate.novelId, context, tx.options)))) throw stale();
  }
  const reviewedNow = (value: Review | undefined): value is Review => !!value && value.fence === token && value === reviewRef.current
    && previewRef.current === value.preview && loadedRef.current === value.preview && value.preview.request === sequence.current
    && value.preview.fence === token && current();

  async function inspect() {
    if (!current() || running.current || !candidate.previewKind) return;
    sequence.current += 1;
    running.current = true; setBusy(true); setError(''); releasePreview();
    const context = captureContext(), tx = transaction();
    try {
      await freshJob(context, tx);
      if (candidate.previewKind === 'asset' && candidate.assetId) {
        const blob = await tx.checked(api.assetDownload(candidate.assetId, candidate.novelId, context, {...tx.options, maxBytes: MAX_IMAGE_BYTES}));
        const mediaType = canvasCandidateMediaType(blob.type);
        if (!blob.size || blob.size > MAX_IMAGE_BYTES || !mediaType) {
          onUnavailable('原资产未提供本入口支持的图片内容。请核对原任务与资产，不会改用结果链接。');
          return;
        }
        let sha256: string | undefined;
        if (canvasCandidateCryptoAvailable()) {
          try { sha256 = await tx.checked(canvasCandidateBlobSha256(blob)); }
          catch { if (!tx.valid()) throw stale(); }
        }
        await freshJob(context, tx);
        const uri = URL.createObjectURL(blob); objectUrl.current = uri;
        const next = {uri, request: tx.request, fence: token, sha256, size: blob.size, mediaType};
        previewRef.current = next; setPreview(next);
      } else if (candidate.previewKind === 'inline' && candidate.previewUri) {
        const next = {uri: candidate.previewUri, request: tx.request, fence: token};
        previewRef.current = next; setPreview(next);
      }
    } catch {
      if (current() && tx.request === sequence.current) onUnavailable('原候选读取失败或权限已变化。请刷新原任务状态后核对，不会自动重试。');
    } finally { tx.finish(); }
  }
  async function prepareReview() {
    const image = previewRef.current;
    if (!current() || running.current || !image || image !== loadedRef.current || image.request !== sequence.current
      || image.fence !== token || !image.sha256 || !canvasCandidateCryptoAvailable()
      || candidate.approvalStatus !== 'APPROVED' || candidate.previewKind !== 'asset') return;
    running.current = true; setBusy(true); setError(''); clearReview();
    const context = captureContext(), tx = transaction();
    try {
      await freshJob(context, tx);
      const asset = await metadata(context, tx);
      if (asset.assetSha256 !== image.sha256 || asset.size !== image.size || asset.mediaType !== image.mediaType) throw stale();
      await assertWrite(context, tx);
      const confirmedAsset = await metadata(context, tx);
      if (!sameCanvasCandidateAsset(asset, confirmedAsset)) throw stale();
      await freshJob(context, tx);
      const jobObservationSha256 = await tx.checked(canvasCandidateObservationSha256(candidate));
      if (!tx.valid() || previewRef.current !== image || loadedRef.current !== image) throw stale();
      const next = {preview: image, asset, jobObservationSha256, fence: token};
      reviewRef.current = next; setReview(next);
    } catch {
      if (current() && tx.request === sequence.current) {
        clearReview(); setError('原任务、资产内容或写权限无法核实，未准备采用。请刷新后重新预览；不会自动重试。');
      }
    } finally { tx.finish(); }
  }
  async function adopt() {
    const checked = reviewRef.current;
    if (!reviewedNow(checked) || !confirmedRef.current || running.current) return;
    confirmedRef.current = false; setConfirmed(false); running.current = true; setBusy(true); setError('');
    const context = captureContext(), tx = transaction();
    try {
      await freshJob(context, tx);
      const asset = await metadata(context, tx);
      if (!sameCanvasCandidateAsset(asset, checked.asset)) throw stale();
      const blob = await tx.checked(api.assetDownload(asset.assetId, candidate.novelId, context, {...tx.options, maxBytes: MAX_IMAGE_BYTES}));
      if (blob.size !== asset.size || canvasCandidateMediaType(blob.type) !== asset.mediaType) throw stale();
      const sha256 = await tx.checked(canvasCandidateBlobSha256(blob));
      if (sha256 !== asset.assetSha256 || sha256 !== checked.preview.sha256) throw stale();
      if (!sameCanvasCandidateAsset(asset, await metadata(context, tx))) throw stale();
      await freshJob(context, tx);
      await assertWrite(context, tx);
      const mayWrite = () => tx.valid() && reviewedNow(checked);
      if (!mayWrite()) throw stale();
      const persisted = writeCanvasTaskAdoption(binding, {assetId: asset.assetId, assetVersion: asset.assetVersion,
        assetSha256: sha256, jobObservationSha256: checked.jobObservationSha256}, mayWrite);
      if (!persisted) {
        if (mounted.current && fence.current.token === token) {
          clearReview(); setError('未确认保存本机关联。请重新读取原节点和任务核对；不会自动重试，也不宣称存储已回滚。');
        }
        return;
      }
      if (mounted.current && fence.current.token === token) { setSaved(true); reviewRef.current = undefined; setReview(undefined); }
    } catch {
      if (current() && tx.request === sequence.current) {
        clearReview(); setError('原任务、资产内容或写权限已变化，未确认采用。请刷新后重新预览；不会自动重试。');
      }
    } finally { tx.finish(); }
  }

  const visiblePreview = preview?.fence === token && current() ? preview : undefined;
  const visibleReview = reviewedNow(review) ? review : undefined;
  const canPrepare = !!visiblePreview && loaded === visiblePreview && !!visiblePreview.sha256 && canvasCandidateCryptoAvailable()
    && candidate.approvalStatus === 'APPROVED' && candidate.previewKind === 'asset';
  return <section aria-label="原任务候选结果">
    <h4>原任务读取快照</h4>
    <p className="novel-help">候选只读，未自动采用。以下来自原任务记录；请求摘要不是图片文件校验，尝试次数和更新时间不是服务端正式版本。</p>
    {nodePrompt !== undefined && nodePrompt.trim() !== candidate.prompt.trim() && <StatusMessage tone="warning">当前节点提示词已不同；以下仍是历史原任务候选，不会覆盖当前草稿。</StatusMessage>}
    <dl className="image-task-inspector__facts">
      <div><dt>来源节点</dt><dd>{candidate.nodeId}</dd></div>
      <div><dt>原任务</dt><dd>{candidate.jobId}</dd></div>
      <div><dt>项目</dt><dd>{candidate.novelId}</dd></div>
      <div><dt>图片服务</dt><dd>{candidate.providerId}</dd></div>
      <div><dt>模型</dt><dd>{candidate.modelId}</dd></div>
      <div><dt>执行尝试</dt><dd>{candidate.attempt}</dd></div>
      <div><dt>任务更新时间</dt><dd>{candidate.updatedAt}</dd></div>
      <div><dt>请求摘要</dt><dd>{candidate.requestSha256}</dd></div>
      <div><dt>审核记录</dt><dd>{candidate.approvalStatus === 'APPROVED' ? '服务端标记已接受入库' : '尚未接受入库'}</dd></div>
      {candidate.assetId && <div><dt>记录资产 ID</dt><dd>{candidate.assetId}</dd></div>}
    </dl>
    <label>原任务提示词<textarea aria-label="原任务提示词" value={candidate.prompt} readOnly rows={3}/></label>
    {!candidate.previewKind && <StatusMessage>原任务尚未提供入库资产或内联图片；当前接口未提供未入库网络候选的内容读取，这里只显示来源信息。</StatusMessage>}
    <Button disabled={!candidate.previewKind || busy} loading={busy} onClick={() => void inspect()}>预览原任务候选结果</Button>
    {(visiblePreview || busy) && <Button variant="ghost" onClick={hide}>隐藏候选预览</Button>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {visiblePreview && <div className="image-task-inspector__preview"><img key={visiblePreview.request} src={visiblePreview.uri} alt="原节点任务候选结果" referrerPolicy="no-referrer"
      onLoad={event => {
        if (current() && previewRef.current === visiblePreview && sequence.current === visiblePreview.request
          && event.currentTarget.naturalWidth > 0 && event.currentTarget.naturalHeight > 0) {
          loadedRef.current = visiblePreview; setLoaded(visiblePreview); clearReview();
        }
      }} onError={() => {
        if (current() && previewRef.current === visiblePreview && sequence.current === visiblePreview.request) {
          hide(); setError('候选预览加载失败。来源记录保留，未执行或采用任何结果。');
        }
      }}/></div>}
    {candidate.approvalStatus === 'APPROVED' && candidate.previewKind === 'asset' && <>
      <Button disabled={!canPrepare || busy} loading={busy} onClick={() => void prepareReview()}>准备人工核对</Button>
      {visiblePreview && !visiblePreview.sha256 && <StatusMessage>当前环境无法核对图片内容 SHA-256，只能只读预览，不能准备或采用到原节点。</StatusMessage>}
      {visibleReview && <section aria-label="本次原节点采用确认">
        <p>已重新核对原资产 v{visibleReview.asset.assetVersion} 和当前读到的图片内容 SHA-256。仅保存此浏览器的原节点导航关联，不改变服务端审核记录。</p>
        <label><input type="checkbox" aria-label="已查看上述图片，并确认仅采用到此浏览器的原节点" checked={confirmed} disabled={busy}
          onChange={event => {
            if (!running.current && reviewedNow(visibleReview)) { confirmedRef.current = event.currentTarget.checked; setConfirmed(event.currentTarget.checked); }
          }}/>已查看上述图片，并确认仅采用到此浏览器的原节点</label>
        <Button disabled={!confirmed || busy} loading={busy} onClick={() => void adopt()}>采用到此浏览器原节点</Button>
      </section>}
    </>}
    {saved && <StatusMessage tone="success">已保存此浏览器原节点的资产导航关联；原 Job 和 Asset 仍由服务端管理，没有执行或更改服务端审核。</StatusMessage>}
    <p className="novel-help">{candidate.previewKind === 'asset' ? '已入库结果通过原资产接口读取，并在显示前再次核对原任务快照。' : '内联图片在重新核对原任务快照后显示；网络结果地址不会直接用于预览。'}只读预览不代表生成质量、图片内容审核或持续权限核验。采用仅限明确核对后的已入库原资产，不会调用执行、接受入库或服务端审核接口。</p>
  </section>;
}
