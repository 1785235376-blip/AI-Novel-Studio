import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from './studioClient';
import { checkedTimelineRow, type StudioTimelineRow } from './studioTimelineTypes';

export const COMIC_HANDOFF = 'studio-comic-timeline-handoff/1';
export const HANDOFF_LOSSES = ['WHOLE_PAGES_FLATTENED_TO_STATIC_PNG', 'NO_PANEL_MOTION_OR_AUDIO',
  'TIMELINE_DRAFT_ONLY_NO_VIDEO_RENDER_OR_APPROVAL', 'ORIGINAL_COMIC_PAGES_UNCHANGED'] as const;
export type HandoffSelection = { id: string; version: number; review_digest: string; duration_ms: number };
export type HandoffRequest = { title: string; pages: HandoffSelection[]; width: number; height: number; fps: number };
export type HandoffPage = { source: Omit<HandoffSelection, 'duration_ms'> & { document_digest: string };
  duration_ms: number; width: number; height: number; bytes: number; png_sha256: string; render_fingerprint: string };
export type HandoffReport = { contract: typeof COMIC_HANDOFF; scope_key: string; incarnation: string; actor: string;
  request: HandoffRequest; request_digest: string; pages: HandoffPage[]; duration_ms: number; losses: string[];
  automatic_dispatch: false; model_called: false; video_rendered: false; approval_inherited: false; preview_digest: string };
export type HandoffConfirm = { request_id: string; request: HandoffRequest; reviewed_preview_digest: string; acknowledge_losses: true };
export type HandoffReceipt = { id: string; request_id: string; version: number; status: 'PLANNED' | 'DRAFT_CREATED' | 'CANCELLED';
  steps: { asset_id: string; asset_version: 1 | null; state: 'PENDING' | 'READY'; observed_state: string }[];
  preview: HandoffReport; timeline_snapshot: { id: string; version: 1; digest: string } | null;
  timeline?: StudioTimelineRow; timeline_state?: 'CREATION_SNAPSHOT' | 'MODIFIED_AFTER_CREATION';
  automatic_dispatch: false; model_called: false; video_rendered: false; approval_inherited: false; source_current_checked: false };
const id = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/, requestId = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;
const hex = /^[a-f0-9]{64}$/, incarnation = /^(file|postgres):[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
function invalid(): never { throw new ApiError({ status: 200, code: 'COMIC_HANDOFF_RESPONSE_INVALID', message: '整页交接数据未通过核对。请保留原请求 ID，重新读回状态。' }); }
function object(v: unknown): Record<string, unknown> { if (!v || typeof v !== 'object' || Array.isArray(v)) invalid(); return v as Record<string, unknown>; }
function fields(v: unknown, required: string[], optional: string[] = []): Record<string, unknown> {
  const row = object(v);
  if (required.some(k => !(k in row)) || Object.keys(row).some(k => !required.includes(k) && !optional.includes(k))) invalid();
  return row;
}
function integer(v: unknown, min = 1, max = Number.MAX_SAFE_INTEGER): number { if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < min || v > max) invalid(); return v; }
function text(v: unknown, pattern: RegExp): string { if (typeof v !== 'string' || !pattern.test(v)) invalid(); return v; }
export const handoffCanonical = (v: unknown): string => JSON.stringify(v, (_key, value) => value && typeof value === 'object' && !Array.isArray(value)
  ? Object.fromEntries(Object.keys(value).sort().map(k => [k, value[k]])) : value);
export async function handoffHash(value: string | Uint8Array): Promise<string> {
  const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : new Uint8Array(value);
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
}
export function checkedHandoffRequest(value: unknown): HandoffRequest {
  const row = fields(value, ['title', 'pages', 'width', 'height', 'fps']);
  if (typeof row.title !== 'string' || !row.title.trim() || row.title.length > 200 || /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(row.title)
    || !Array.isArray(row.pages) || row.pages.length < 1 || row.pages.length > 4) invalid();
  const pages = row.pages.map(v => {
    const p = fields(v, ['id', 'version', 'review_digest', 'duration_ms']);
    return { id: text(p.id, id), version: integer(p.version), review_digest: text(p.review_digest, hex), duration_ms: integer(p.duration_ms, 1, 600000) };
  });
  const width = integer(row.width, 16, 1920), height = integer(row.height, 16, 1080);
  if (width % 2 || height % 2 || new Set(pages.map(p => p.id)).size !== pages.length || pages.reduce((n, p) => n + p.duration_ms, 0) > 600000) invalid();
  return { title: row.title.trim(), pages, width, height, fps: integer(row.fps, 1, 60) };
}
export function checkedHandoffConfirm(value: unknown): HandoffConfirm {
  const row = fields(value, ['request_id', 'request', 'reviewed_preview_digest', 'acknowledge_losses']);
  if (row.acknowledge_losses !== true) invalid();
  return { request_id: text(row.request_id, requestId), request: checkedHandoffRequest(row.request), reviewed_preview_digest: text(row.reviewed_preview_digest, hex), acknowledge_losses: true };
}
function falseFlags(row: Record<string, unknown>) {
  if (['automatic_dispatch', 'model_called', 'video_rendered', 'approval_inherited'].some(k => row[k] !== false)) invalid();
}
export async function checkedHandoffReport(value: unknown, owner: { scopeKey: string; actor?: string }, expected?: HandoffRequest): Promise<HandoffReport> {
  const row = fields(value, ['contract', 'scope_key', 'incarnation', 'actor', 'request', 'request_digest', 'pages', 'duration_ms', 'losses',
    'automatic_dispatch', 'model_called', 'video_rendered', 'approval_inherited', 'preview_digest']);
  falseFlags(row);
  if (row.contract !== COMIC_HANDOFF || row.scope_key !== owner.scopeKey || typeof row.actor !== 'string' || !row.actor || row.actor.length > 240
    || owner.actor !== undefined && row.actor !== owner.actor || handoffCanonical(row.losses) !== handoffCanonical(HANDOFF_LOSSES)) invalid();
  text(row.incarnation, incarnation);
  const request = checkedHandoffRequest(row.request);
  if (handoffCanonical(request) !== handoffCanonical(row.request) || expected && handoffCanonical(request) !== handoffCanonical(expected)
    || await handoffHash(handoffCanonical(request)) !== text(row.request_digest, hex)
    || !Array.isArray(row.pages) || row.pages.length !== request.pages.length) invalid();
  const pages = row.pages.map((v, index) => {
    const page = fields(v, ['source', 'duration_ms', 'width', 'height', 'png_sha256', 'bytes', 'render_fingerprint']);
    const source = fields(page.source, ['id', 'version', 'review_digest', 'document_digest']);
    const selected = request.pages[index];
    if (source.id !== selected.id || source.version !== selected.version || source.review_digest !== selected.review_digest || page.duration_ms !== selected.duration_ms) invalid();
    text(source.document_digest, hex);
    const width = integer(page.width, 64, 1600), height = integer(page.height, 64, 12000);
    if (width * height > 16000000) invalid();
    integer(page.bytes, 1, 25 * 1024 * 1024); text(page.png_sha256, hex); text(page.render_fingerprint, hex);
    return page as unknown as HandoffPage;
  });
  if (row.duration_ms !== request.pages.reduce((n, p) => n + p.duration_ms, 0)) invalid();
  const { preview_digest, ...proof } = row;
  if (await handoffHash(handoffCanonical(proof)) !== text(preview_digest, hex)) invalid();
  return { ...row, request, pages } as HandoffReport;
}
export async function checkedHandoffReceipt(value: unknown, owner: { scopeKey: string; actor?: string; projectId: string; branch: string | null }, expectedId: string, expected?: HandoffConfirm): Promise<HandoffReceipt> {
  const row = fields(value, ['id', 'request_id', 'version', 'status', 'steps', 'preview', 'timeline_snapshot', 'automatic_dispatch', 'model_called',
    'video_rendered', 'approval_inherited', 'source_current_checked'], ['timeline', 'timeline_state']);
  falseFlags(row); text(row.id, id);
  if (text(row.request_id, requestId) !== expectedId || row.source_current_checked !== false || !['PLANNED', 'DRAFT_CREATED', 'CANCELLED'].includes(String(row.status))) invalid();
  const preview = await checkedHandoffReport(row.preview, owner, expected?.request);
  if (expected && (expected.request_id !== expectedId || preview.preview_digest !== expected.reviewed_preview_digest)) invalid();
  if (!Array.isArray(row.steps) || row.steps.length !== preview.pages.length) invalid();
  let pending = false, ready = 0;
  const steps = row.steps.map(v => {
    const step = fields(v, ['asset_id', 'asset_version', 'state', 'observed_state']); text(step.asset_id, id);
    if (step.state === 'READY') {
      if (pending || step.asset_version !== 1 || step.observed_state !== 'READY') invalid(); ready++;
    } else if (step.state === 'PENDING') {
      pending = true;
      if (step.asset_version !== null || !['AWAITING_EXPLICIT_RESUME', 'COMMITTED_AWAITING_EXPLICIT_RESUME', 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'].includes(String(step.observed_state))) invalid();
    } else invalid();
    return step as unknown as HandoffReceipt['steps'][number];
  });
  if (new Set(steps.map(s => s.asset_id)).size !== steps.length || row.version !== 1 + ready + (row.status === 'PLANNED' ? 0 : 1)) invalid();
  let timeline: StudioTimelineRow | undefined;
  if (row.status === 'DRAFT_CREATED') {
    const pin = fields(row.timeline_snapshot, ['id', 'version', 'digest']); text(pin.id, id); text(pin.digest, hex);
    const raw = object(row.timeline), origin = fields(raw.comic_handoff_origin, ['contract', 'receipt_id', 'request_id', 'preview_digest', 'creation_snapshot']);
    if (pending || pin.version !== 1 || raw.novel_id !== owner.projectId || raw.branch_id !== owner.branch
      || origin.contract !== COMIC_HANDOFF || origin.receipt_id !== row.id || origin.request_id !== row.request_id || origin.preview_digest !== preview.preview_digest
      || handoffCanonical(origin.creation_snapshot) !== handoffCanonical(pin)) invalid();
    timeline = checkedTimelineRow(raw, pin.id as string);
    const creation = timeline.version === 1 && timeline.timeline_digest === pin.digest;
    if (row.timeline_state !== (creation ? 'CREATION_SNAPSHOT' : 'MODIFIED_AFTER_CREATION')) invalid();
    if (creation) {
      const t = timeline.timeline;
      if (t.schema_version !== 2 || t.duration_ms !== preview.duration_ms || t.width !== preview.request.width || t.height !== preview.request.height
        || t.fps !== preview.request.fps || t.tracks.length !== 1 || t.tracks[0].kind !== 'VIDEO' || t.tracks[0].clips.length !== steps.length || t.captions.length) invalid();
      let start = 0;
      t.tracks[0].clips.forEach((clip, index) => {
        const pin = preview.pages[index];
        if (clip.source_snapshot.id !== steps[index].asset_id || clip.source_snapshot.version !== 1 || clip.source_snapshot.digest !== pin.png_sha256
          || clip.source_snapshot.kind !== 'ASSET' || clip.source_snapshot.asset_kind !== 'image' || clip.start_ms !== start || clip.in_ms !== 0
          || clip.out_ms !== pin.duration_ms || clip.speed_num !== 1 || clip.speed_den !== 1 || clip.include_audio !== false) invalid();
        start += pin.duration_ms;
      });
    }
  } else if (row.timeline_snapshot !== null || 'timeline' in row || 'timeline_state' in row) invalid();
  return { ...row, steps, preview, ...(timeline ? { timeline } : {}) } as HandoffReceipt;
}

/** Original transport/owners only. No credential or active global scope is stored. */
export function studioComicHandoffClient(projectId: string, context: CollaborationContext) {
  const scope = context.scope ? { mode: 'collaboration', novel_id: projectId, workspace_id: context.scope.workspaceId,
    storyline_id: context.scope.storylineId, branch_id: context.scope.branchId } : { mode: 'local', novel_id: projectId };
  if (context.scope && context.scope.projectId !== projectId) invalid();
  const actor = context.scope ? context.actor?.id : 'local-author', branch = context.scope?.branchId ?? null;
  const ownerKey = handoffCanonical([projectId, scope, actor ?? null]);
  const owner = async () => ({ projectId, branch, actor, scopeKey: await handoffHash(handoffCanonical([projectId, scope])) });
  const transport = studioTransport(context), base = `/api/projects/${encodeURIComponent(projectId)}/studio/production/comic-handoffs`;
  async function json(path: string, method: 'GET' | 'POST', body?: unknown): Promise<unknown> {
    const { blob } = await transport.blobResponse(base + path, method, body, undefined, undefined, { maxBytes: 12 * 1024 * 1024 });
    if (blob.type.split(';')[0] !== 'application/json') invalid();
    try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(await blob.arrayBuffer())); } catch { return invalid(); }
  }
  async function receipt(path: string, method: 'GET' | 'POST', value: unknown, rid: string, expected?: HandoffConfirm) {
    text(rid, requestId); return checkedHandoffReceipt(await json(path, method, value), await owner(), rid, expected);
  }
  return {
    ownerKey,
    async preview(value: HandoffRequest) {
      const request = checkedHandoffRequest(value), raw = fields(await json('/preview', 'POST', request), ['preview', 'pages']);
      const report = await checkedHandoffReport(raw.preview, await owner(), request);
      if (!Array.isArray(raw.pages) || raw.pages.length !== report.pages.length || report.pages.reduce((n, p) => n + p.bytes, 0) > 8 * 1024 * 1024) invalid();
      const images: Blob[] = [];
      for (let index = 0; index < raw.pages.length; index++) {
        const part = fields(raw.pages[index], ['index', 'png_base64']), pin = report.pages[index];
        if (part.index !== index || typeof part.png_base64 !== 'string' || part.png_base64.length !== 4 * Math.ceil(pin.bytes / 3)
          || !/^[A-Za-z0-9+/]*={0,2}$/.test(part.png_base64)) invalid();
        const binary = atob(part.png_base64);
        if (btoa(binary) !== part.png_base64) invalid();
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0)), view = new DataView(bytes.buffer);
        if (bytes.length !== pin.bytes || bytes.length < 33 || handoffCanonical([...bytes.slice(0, 8)]) !== '[137,80,78,71,13,10,26,10]'
          || view.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== 'IHDR' || view.getUint32(16) !== pin.width || view.getUint32(20) !== pin.height
          || await handoffHash(bytes) !== pin.png_sha256) invalid();
        images.push(new Blob([bytes], { type: 'image/png' }));
      }
      return { report, images };
    },
    confirm(value: HandoffConfirm) { const body = checkedHandoffConfirm(value); return receipt('', 'POST', body, body.request_id, body); },
    status(rid: string, expected?: HandoffConfirm) { return receipt('/' + encodeURIComponent(text(rid, requestId)), 'GET', undefined, rid, expected); },
    async resume(value: HandoffConfirm, version: number) {
      const body = checkedHandoffConfirm(value), expected = integer(version, 1, 8);
      const result = await receipt('/' + body.request_id + '/resume', 'POST', { expected_version: expected }, body.request_id, body);
      if (result.status !== 'DRAFT_CREATED' || result.version <= expected) invalid();
      return result;
    },
    async cancel(value: HandoffConfirm, version: number) {
      const body = checkedHandoffConfirm(value), expected = integer(version, 1, 8);
      const result = await receipt('/' + body.request_id + '/cancel', 'POST', { expected_version: expected }, body.request_id, body);
      if (result.status !== 'CANCELLED' || result.version !== expected + 1) invalid();
      return result;
    },
  };
}
export type StudioComicHandoffClient = ReturnType<typeof studioComicHandoffClient>;
