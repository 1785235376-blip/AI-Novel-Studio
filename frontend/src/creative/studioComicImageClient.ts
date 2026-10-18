import { ApiError, type CollaborationContext } from '../api';
import type { ComicRecord } from '../experimental/comicLayoutsClient';
import { studioTransport } from './studioClient';
import { checkedComicImageCommand, checkedComicImageSource, sameComicImageCommand } from './studioComicImageContract';
import type { ProductionJob, RecordedMediaCommand } from './studioProductionClient';

export type ComicImageOptions = { request_id: string; provider_id: string; model_id: string; parameters: Record<string, string | number> };
export type ComicImageRequest = { contract: 'studio-comic-image-request/1'; source_snapshot: ReturnType<typeof checkedComicImageSource>; command: RecordedMediaCommand;
  automatic_dispatch: false; model_called: false; output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '漫画图片回执与当前格框不一致。请重新读取原页面和任务核对，不要重复发送。' }); }
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const canonical = (v: unknown): string => JSON.stringify(v, (_key, value) => object(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, value[key]])) : value);
export function comicImageJobMatches(request: ComicImageRequest, job: ProductionJob): boolean {
  return job.owner === 'image' && job.operation_id === 'm5.image.t2i' && job.request_id === request.command.request_id
    && sameComicImageCommand(request.command, job.command) && canonical(job.sources) === canonical(request.command.source_snapshots)
    && job.provider?.local === true;
}
export function studioComicImageClient(projectId: string, context: CollaborationContext) {
  const transport = studioTransport(context);
  const path = (page: ComicRecord, panelId: string) => {
    if (context.scope && context.scope.projectId !== projectId) invalid();
    const panel = page.document?.panels.find(row => row.id === panelId);
    if (!panel || page.stale || panel.artwork_mode === 'BLANK' || !panel.image_brief?.trim() || panel.appearance_references?.length) invalid();
    return `/api/projects/${encodeURIComponent(projectId)}/studio/production/comic-pages/${encodeURIComponent(page.id)}/panels/${encodeURIComponent(panelId)}`;
  };
  return {
    async request(page: ComicRecord, panelId: string, options: ComicImageOptions): Promise<ComicImageRequest> {
      const value = await transport.json<unknown>(path(page, panelId) + '/image-request', 'POST', { expected_version: page.version, ...options });
      if (!object(value) || Object.keys(value).some(key => !['contract', 'source_snapshot', 'command', 'automatic_dispatch', 'model_called', 'output_policy'].includes(key))
        || value.contract !== 'studio-comic-image-request/1' || value.automatic_dispatch !== false || value.model_called !== false || value.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW') invalid();
      const source = checkedComicImageSource(value.source_snapshot), command = checkedComicImageCommand(value.command);
      if (source.id !== page.id || source.version !== page.version || source.comic_panel.panel_id !== panelId
        || canonical(source) !== canonical(command.source_snapshots[0]) || command.request_id !== options.request_id
        || command.provider_id !== options.provider_id || command.model_id !== options.model_id
        || command.prompt !== page.document!.panels.find(panel => panel.id === panelId)!.image_brief
        || canonical(options.parameters) !== canonical(command.parameters)) invalid();
      return { ...value, source_snapshot: source, command } as ComicImageRequest;
    },
    async adopt(page: ComicRecord, panelId: string, request: ComicImageRequest, job: ProductionJob): Promise<ComicRecord> {
      if (!comicImageJobMatches(request, job) || job.status !== 'APPROVED' || !job.output_candidate || job.output_candidate.kind !== 'image'
        || !job.approved_asset_version || request.source_snapshot.id !== page.id || request.source_snapshot.version !== page.version || request.source_snapshot.comic_panel.panel_id !== panelId) invalid();
      const value = await transport.json<ComicRecord>(path(page, panelId) + '/adopt-image', 'POST', { expected_version: page.version, job_id: job.id,
        expected_job_version: job.version, expected_request_digest: job.request_digest,
        expected_asset_version: job.approved_asset_version, expected_output_digest: job.output_candidate.digest });
      const expected = { ...page.document!, panels: page.document!.panels.map(panel => panel.id === panelId
        ? { ...panel, asset_id: job.output_candidate!.id, expected_asset_version: job.approved_asset_version } : panel) };
      if (!value || value.id !== page.id || value.version !== page.version + 1 || value.status !== 'DRAFT' || value.stale !== false || canonical(value.document) !== canonical(expected)) invalid();
      return value;
    },
  };
}
export type StudioComicImageClient = ReturnType<typeof studioComicImageClient>;
