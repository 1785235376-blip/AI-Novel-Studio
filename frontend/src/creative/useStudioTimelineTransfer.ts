import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, timelineBinding, timelineSourcesCurrent, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';
import { checkedTimelineTransferInput, timelineExchangeReferences, type TimelineTransferDirection, type TimelineTransferFormat,
  type TimelineTransferInput, type TimelineTransferPreview } from './studioTimelineTransferTypes';

type Mapping = { reference: string; assetId: string };
type TransferAttempt = { requestId: string; source: StudioTimelineRow; preview: TimelineTransferPreview; input: TimelineTransferInput; acknowledged: boolean };
type Options = { props: StudioTimelineEditorProps; source?: StudioTimelineRow; canOperate: boolean; isReady: () => boolean;
  onAdopt: (row: StudioTimelineRow) => void; onAuthorityLost: () => void; onGateChange: (locked: boolean) => void };

/** Private transfer draft and original-owner receipts; no renderer or timeline owner. */
export function useStudioTimelineTransfer(options: Options) {
  const [direction, setDirection] = useState<TimelineTransferDirection>('EXPORT'), [format, setFormat] = useState<TimelineTransferFormat>('OTIO');
  const [content, setContent] = useState(''), [mappings, setMappings] = useState<Mapping[]>([]);
  const [preview, setPreview] = useState<TimelineTransferPreview>(), [acknowledged, setAcknowledged] = useState(false), [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState<'FILE' | 'PREVIEW' | 'IMPORT' | 'ATTACHMENT' | 'CHECK'>(), [unknown, setUnknown] = useState<TransferAttempt>();
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [attachment, setAttachment] = useState<{ url: string; filename: string; digest: string; bytes: number }>();
  const latest = useRef(options); latest.current = options;
  const form = useRef({ direction, format, content, mappings, preview, acknowledged, confirmed });
  form.current = { direction, format, content, mappings, preview, acknowledged, confirmed };
  const owner = useRef(options.props.client), epoch = useRef(0), alive = useRef(true), busy = useRef(false), attempt = useRef<TransferAttempt>();
  const reading = useRef<AbortController>(), url = useRef<string>();
  const available = !!options.props.client.timelineTransferPreview && !!options.props.client.timelineTransferImport && !!options.props.client.timelineTransferAttachment;
  const current = () => alive.current && owner.current === latest.current.props.client && latest.current.props.isCurrent();
  const owns = owner.current === options.props.client && options.props.isCurrent();
  const locked = busy.current || !!unknown;
  const dirty = owns && (content !== '' || mappings.length > 0 || !!preview || confirmed || acknowledged || !!unknown || !!pending || !!attachment);

  function clearAttachment() { if (url.current) URL.revokeObjectURL(url.current); url.current = undefined; setAttachment(undefined); }
  function clearPreview() { form.current.preview = undefined; form.current.acknowledged = false; form.current.confirmed = false;
    setPreview(undefined); setAcknowledged(false); setConfirmed(false); clearAttachment(); }
  function reset() {
    epoch.current++; reading.current?.abort(); reading.current = undefined; busy.current = false; attempt.current = undefined;
    latest.current.onGateChange(false); clearPreview();
    form.current = { direction: 'EXPORT', format: 'OTIO', content: '', mappings: [], preview: undefined, acknowledged: false, confirmed: false };
    setDirection('EXPORT'); setFormat('OTIO'); setContent(''); setMappings([]); setPending(undefined); setUnknown(undefined); setError(''); setNotice('');
  }
  useEffect(() => { alive.current = true; return () => {
    alive.current = false; epoch.current++; reading.current?.abort(); if (url.current) URL.revokeObjectURL(url.current);
    latest.current.onGateChange(false);
  }; }, []);
  useEffect(() => { owner.current = options.props.client; reset(); }, [options.props.client]);
  useEffect(() => { if (!owns) reset(); }, [owns]);
  const sourceBinding = options.source ? timelineBinding(options.source) : '';
  useEffect(() => {
    // A returned import is adopted by the original controller. A pending or
    // unknown send retains its identity until exact original receipt recovery.
    if (!busy.current && !attempt.current) clearPreview();
  }, [sourceBinding]);

  function change(update: Partial<Pick<typeof form.current, 'direction' | 'format' | 'content' | 'mappings'>>) {
    if (!current() || busy.current || attempt.current || !latest.current.canOperate) return;
    clearPreview(); Object.assign(form.current, update);
    if (update.direction !== undefined) setDirection(update.direction);
    if (update.format !== undefined) setFormat(update.format);
    if (update.content !== undefined) setContent(update.content);
    if (update.mappings !== undefined) setMappings(update.mappings);
    setError(''); setNotice('');
  }
  function body(source: StudioTimelineRow): TimelineTransferInput {
    const input = form.current;
    const bindings = input.direction === 'IMPORT' && input.format === 'OTIO' ? input.mappings.map(mapping => {
      const asset = latest.current.props.assets.find(row => row.id === mapping.assetId && !row.deleted_at && ['image', 'video', 'audio'].includes(row.kind));
      if (!asset) throw new Error('每个引用都需要明确选择当前可访问的正式素材。');
      const snapshot: StudioTimelineSource = { id: asset.id, kind: 'ASSET', asset_kind: asset.kind as StudioTimelineSource['asset_kind'], version: asset.version, digest: asset.sha256 };
      return { reference: mapping.reference, source_snapshot: snapshot };
    }) : [];
    return checkedTimelineTransferInput({ expected_version: source.version, reviewed_timeline_digest: source.timeline_digest,
      direction: input.direction, format: input.format, content: input.direction === 'IMPORT' ? input.content : '', media_bindings: bindings });
  }
  function begin(operation: NonNullable<typeof pending>, recovering = false) {
    if (!current() || busy.current || !available || !recovering && (!latest.current.canOperate || !latest.current.isReady() || attempt.current)) return;
    busy.current = true; latest.current.onGateChange(true); const token = ++epoch.current;
    setPending(operation); setError(''); setNotice(''); clearAttachment();
    return { token, client: latest.current.props.client };
  }
  function active(request: { token: number; client: typeof owner.current }) { return current() && epoch.current === request.token && request.client === owner.current; }
  function finish(request: { token: number; client: typeof owner.current }) {
    if (epoch.current !== request.token) return;
    busy.current = false; latest.current.onGateChange(!!attempt.current); if (active(request)) setPending(undefined);
  }
  function failed(reason: unknown, fallback: string) {
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) { reset(); latest.current.onAuthorityLost(); return; }
    setError(apiErrorView(reason, fallback).message);
    if (reason instanceof ApiError && [404, 410, 501].includes(reason.status)) latest.current.props.onUnavailable();
  }
  async function selectFile(file?: File) {
    if (!file || !current() || busy.current || attempt.current || !available || !latest.current.canOperate
      || !latest.current.isReady() || form.current.direction !== 'IMPORT') return;
    const captured = { direction: form.current.direction, format: form.current.format, content: form.current.content,
      source: latest.current.source ? timelineBinding(latest.current.source) : '' };
    const maximum = captured.format === 'OTIO' ? 2 * 1024 * 1024 : 192000;
    if (!file.name.toLowerCase().endsWith(`.${captured.format.toLowerCase()}`)) {
      setError(`请选择与当前 ${captured.format} 格式一致的 .${captured.format.toLowerCase()} 文件。`); return;
    }
    if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > maximum) {
      setError(`文件必须非空，且不超过 ${maximum} 字节。`); return;
    }
    const request = begin('FILE'); if (!request) return;
    clearPreview();
    try {
      const text = await latest.current.props.mutate(async () => {
        // This reads only the File explicitly selected by the user. Neither a
        // path nor the file's reference strings grant media or API authority.
        if (!active(request)) throw new Error('当前会话已经变化，请重新选择文件。');
        const bytes = await file.arrayBuffer();
        if (bytes.byteLength !== file.size || bytes.byteLength > maximum) throw new Error('所选文件的字节数发生变化，请重新选择。');
        try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
        catch { throw new Error('所选文件不是有效 UTF-8 文本，请以 UTF-8 保存后重新选择。'); }
      });
      if (!active(request)) return;
      // The parent can still render our own just-finished mutex as busy, and
      // isReady includes this operation's transfer gate. Recheck independent
      // authority, source and draft fences without treating our gate as stale.
      if (!latest.current.props.canMutate || !latest.current.canOperate && !latest.current.props.busy
        || attempt.current || !latest.current.source || !timelineSourcesCurrent(latest.current.source.timeline, latest.current.props.assets)
        || form.current.direction !== captured.direction
        || form.current.format !== captured.format || form.current.content !== captured.content
        || (latest.current.source ? timelineBinding(latest.current.source) : '') !== captured.source) {
        setNotice('交换设置或保存版本已经变化，未覆盖当前草稿；请重新选择文件。'); return;
      }
      form.current.content = text; form.current.mappings = []; setContent(text); setMappings([]);
      clearPreview(); setNotice('已读取所选文件到本轮交换草稿。请核对内容；OTIO 还需逐项绑定素材，然后明确读取预览。');
    } catch (reason) {
      if (active(request)) {
        if (reason instanceof ApiError) failed(reason, '所选文件读取失败。');
        else setError(reason instanceof Error ? reason.message : '所选文件读取失败，请重新选择。');
      }
    } finally { finish(request); }
  }
  async function previewTransfer() {
    const source = latest.current.source, method = latest.current.props.client.timelineTransferPreview;
    if (!source || !method) return;
    let input: TimelineTransferInput; try { input = body(source); } catch (reason) { setError(reason instanceof Error ? reason.message : '请核对交换输入。'); return; }
    const request = begin('PREVIEW'); if (!request) return;
    clearPreview(); const abort = new AbortController(); reading.current = abort;
    try {
      const value = await latest.current.props.mutate(() => latest.current.props.read(() => method(source, input, abort.signal)));
      if (!active(request)) return;
      if (!timelineSourcesCurrent(value.timeline, latest.current.props.assets)) throw new Error('预览绑定的素材已经变化，请刷新素材并重新预览。');
      form.current.preview = value; setPreview(value); setNotice('已取得原时间线的转换预览；尚未修改保存版本。请核对片段、字幕和全部损失项。');
    } catch (reason) { if (active(request)) failed(reason, '交换预览失败。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  function checkedImport(row: StudioTimelineRow, saved: TransferAttempt) {
    const value = checkedTimelineRow(row, saved.source.id), receipt = value.transfer_receipt;
    if (value.version !== saved.source.version + 1 || value.title !== saved.source.title || value.timeline_digest !== saved.preview.timeline_digest
      || JSON.stringify(value.timeline) !== JSON.stringify(saved.preview.timeline) || !receipt || receipt.operation !== 'TRANSFER_IMPORT'
      || receipt.request_id !== saved.requestId || receipt.input_version !== saved.source.version || receipt.input_digest !== saved.source.timeline_digest
      || receipt.output_digest !== saved.preview.timeline_digest || receipt.preview_digest !== saved.preview.preview_digest
      || receipt.format !== saved.input.format || receipt.transfer_input_digest !== saved.preview.input_digest || receipt.acknowledge_losses !== saved.acknowledged
      || !timelineSourcesCurrent(value.timeline, latest.current.props.assets)) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID',
      message: '此读取未证明原导入请求已完成，继续保留 UNKNOWN；不会再次发送。' });
    return value;
  }
  async function importTransfer() {
    const source = latest.current.source, value = form.current.preview, method = latest.current.props.client.timelineTransferImport;
    if (!source || !value || !method || value.direction !== 'IMPORT' || !form.current.confirmed || value.requires_loss_acknowledgment && !form.current.acknowledged) return;
    let input: TimelineTransferInput; try { input = body(source); } catch (reason) { failed(reason, '导入输入已变化。'); return; }
    const request = begin('IMPORT'); if (!request) return;
    const saved: TransferAttempt = { requestId: crypto.randomUUID(), source: cloneTimeline(source), preview: cloneTimeline(value), input,
      acknowledged: form.current.acknowledged };
    attempt.current = saved; setUnknown(saved); latest.current.onGateChange(true);
    try {
      const row = await latest.current.props.mutate(() => method(source, input, value, saved.requestId, saved.acknowledged));
      if (!active(request)) return;
      const checked = checkedImport(row, saved); attempt.current = undefined; setUnknown(undefined);
      latest.current.onAdopt(checked); clearPreview(); setContent(''); setMappings([]); form.current.content = ''; form.current.mappings = [];
      setNotice('原时间线导入回执已核对并采用新版本，本地撤销与重做已清空。原媒体和导出任务保留。');
    } catch (reason) { if (active(request)) failed(reason, '原导入结果不明，请读取原保存记录核对。'); }
    finally { finish(request); }
  }
  async function checkOriginal() {
    const saved = attempt.current; if (!saved) return;
    const request = begin('CHECK', true); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try {
      const row = await latest.current.props.mutate(() => latest.current.props.read(() => request.client.timelineGet(saved.source.id, abort.signal)));
      if (!active(request)) return;
      const checked = checkedImport(row, saved); attempt.current = undefined; setUnknown(undefined); latest.current.onAdopt(checked);
      clearPreview(); setContent(''); setMappings([]); form.current.content = ''; form.current.mappings = [];
      setNotice('已从原时间线读取到本次请求的精确导入回执并采用新版本，没有再次导入。');
    } catch (reason) { if (active(request)) failed(reason, '原导入回执尚未核对，保留 UNKNOWN。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  async function attachmentTransfer() {
    const source = latest.current.source, value = form.current.preview, method = latest.current.props.client.timelineTransferAttachment;
    if (!source || !value || !method || value.direction !== 'EXPORT' || !form.current.confirmed || value.requires_loss_acknowledgment && !form.current.acknowledged) return;
    let input: TimelineTransferInput; try { input = body(source); } catch (reason) { failed(reason, '附件预览已变化。'); return; }
    const request = begin('ATTACHMENT'); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try {
      const blob = await latest.current.props.mutate(() => latest.current.props.read(() => method(source, input, value, form.current.acknowledged, abort.signal)));
      if (!active(request)) return;
      const generated = URL.createObjectURL(blob); url.current = generated;
      setAttachment({ url: generated, filename: `studio-timeline.${input.format.toLowerCase()}`, digest: value.output_sha256!, bytes: blob.size });
      setNotice('已取得并核对附件字节数与 SHA256，请明确保存文件；此附件不证明外部软件导入已验收。');
    } catch (reason) { if (active(request)) failed(reason, '附件读取失败。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  function discoverReferences() {
    if (!current() || busy.current || attempt.current || !latest.current.canOperate || form.current.direction !== 'IMPORT' || form.current.format !== 'OTIO') return;
    try {
      const refs = timelineExchangeReferences(form.current.content), previous = form.current.mappings;
      change({ mappings: refs.map(reference => ({ reference, assetId: previous.find(row => row.reference === reference)?.assetId ?? '' })) });
      setNotice('仅识别引用文字。请逐项选择当前素材，正式解析及精确映射仍由原服务核对。');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '引用识别失败。'); }
  }
  return { available, owns, direction, format, content: owns ? content : '', mappings: owns ? mappings : [], preview: owns ? preview : undefined,
    acknowledged, confirmed, pending, unknown: owns ? unknown : undefined, error: owns ? error : '', notice: owns ? notice : '',
    attachment: owns ? attachment : undefined, dirty, locked, canOperate: available && options.canOperate && !locked,
    isCurrentPreview: (value: TimelineTransferPreview) => current() && available && !busy.current && !attempt.current
      && latest.current.canOperate && latest.current.isReady() && form.current.preview === value,
    change, selectFile, discoverReferences, previewTransfer, importTransfer, checkOriginal, attachmentTransfer,
    clear: () => { if (current() && !busy.current && !attempt.current) reset(); },
    setAcknowledged: (value: boolean) => { if (current() && !busy.current && !attempt.current && form.current.preview) { form.current.acknowledged = value; setAcknowledged(value); } },
    setConfirmed: (value: boolean) => { if (current() && !busy.current && !attempt.current && form.current.preview) { form.current.confirmed = value; setConfirmed(value); } } };
}
export type StudioTimelineTransferController = ReturnType<typeof useStudioTimelineTransfer>;
