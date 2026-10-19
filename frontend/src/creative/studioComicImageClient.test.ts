import { beforeEach, expect, it, vi } from 'vitest';
import { studioComicImageClient } from './studioComicImageClient';
import type { ComicRecord } from '../experimental/comicLayoutsClient';
import type { ProductionJob } from './studioProductionClient';
const transport = vi.hoisted(() => ({ json: vi.fn() }));
vi.mock('./studioClient', () => ({ studioTransport: () => transport }));
const hash = 'a'.repeat(64);
const page = { id: 'page', version: 3, status: 'DRAFT', stale: false, document: { title: 'original', panels: [{ id: 'panel', image_brief: '  saved brief  ', artwork_mode: 'IMAGE', asset_id: null, expected_asset_version: null, appearance_references: [], bubbles: [{ text: 'preserved' }] }, { id: 'other', asset_id: 'original', expected_asset_version: 4 }] } } as unknown as ComicRecord;
const source = { id: 'page', kind: 'COMIC_PANEL', version: 3, digest: hash, reference_only: true, comic_panel: { panel_id: 'panel', panel_digest: hash, brief_digest: hash, actor: 'author', scope_key: hash, incarnation: 'file:12345678-1234-1234-1234-123456789012' } };
const options = { request_id: 'request', provider_id: 'local', model_id: 'model', parameters: { width: 512, height: 512, seed: 1 } };
const command = { ...options, operation_id: 'm5.image.t2i', prompt: '  saved brief  ', source_snapshots: [source], allow_cloud: false, license_note: '' };
const response = { contract: 'studio-comic-image-request/1', source_snapshot: source, command, product_acceptance: 'LOCAL_REQUIRED', automatic_dispatch: false, model_called: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
const api = () => studioComicImageClient('project', { sessionToken: 'fixture' });
beforeEach(() => transport.json.mockReset());
it('prepares only the exact saved panel and normalizes nullable source metadata', async () => {
  transport.json.mockResolvedValue({ ...response, source_snapshot: { ...source, asset_kind: null }, command: { ...command, parameters: { steps: null, negative_prompt: null, size: null, quality: null, duration_seconds: null, frame_rate: null, voice_id: null, speech_rate: null, in_ms: null, out_ms: null, ...options.parameters }, source_snapshots: [{ ...source, asset_kind: null }] } });
  expect((await api().request(page, 'panel', options)).source_snapshot).toEqual(source);
  expect(transport.json).toHaveBeenCalledWith('/api/projects/project/studio/production/comic-pages/page/panels/panel/image-request', 'POST', { expected_version: 3, ...options });
});
it.each(['panel', 'brief', 'provider', 'cloud', 'unknown'])('rejects substituted %s preparation receipt', async kind => {
  const bad = structuredClone(response);
  if (kind === 'panel') bad.source_snapshot.comic_panel.panel_id = 'other';
  if (kind === 'brief') bad.command.prompt = 'other';
  if (kind === 'provider') bad.command.provider_id = 'other';
  if (kind === 'cloud') bad.command.allow_cloud = true;
  if (kind === 'unknown') Object.assign(bad, { dispatch: true });
  transport.json.mockResolvedValue(bad); await expect(api().request(page, 'panel', options)).rejects.toBeTruthy();
});
it('requires original approved Image provenance and writes exact optimistic versions, preserving the rest of the document', async () => {
  transport.json.mockResolvedValueOnce(response); const request = await api().request(page, 'panel', options);
  const job = { owner: 'image', id: 'job', operation_id: 'm5.image.t2i', request_id: 'request', version: 5, request_digest: hash, status: 'APPROVED', command: request.command, sources: request.command.source_snapshots, provider: { local: true }, output_candidate: { id: 'asset', kind: 'image', digest: hash, version: 1 }, approved_asset_version: 2 } as ProductionJob;
  const adopted = { ...page, version: 4, document: { ...page.document!, panels: page.document!.panels.map(p => p.id === 'panel' ? { ...p, asset_id: 'asset', expected_asset_version: 2 } : p) } };
  transport.json.mockResolvedValueOnce(adopted); expect(await api().adopt(page, 'panel', request, job)).toEqual(adopted);
  expect(transport.json).toHaveBeenLastCalledWith('/api/projects/project/studio/production/comic-pages/page/panels/panel/adopt-image', 'POST', { expected_version: 3, job_id: 'job', expected_job_version: 5, expected_request_digest: hash, expected_asset_version: 2, expected_output_digest: hash });
  transport.json.mockClear(); await expect(api().adopt(page, 'panel', request, { ...job, status: 'AWAITING_REVIEW' })).rejects.toBeTruthy(); expect(transport.json).not.toHaveBeenCalled();
  transport.json.mockResolvedValue({ ...adopted, document: { ...adopted.document, title: 'changed unrelated content' } }); await expect(api().adopt(page, 'panel', request, job)).rejects.toBeTruthy();
});
it('rejects appearance references before transport rather than silently dropping them', async () => {
  const p = structuredClone(page); p.document!.panels[0].appearance_references = [{ character_id: 'c', asset_id: 'a', expected_asset_version: 1, note: '' }];
  await expect(api().request(p, 'panel', options)).rejects.toBeTruthy(); expect(transport.json).not.toHaveBeenCalled();
});
it.each([undefined, 'VERIFIED', null])('requires the exact backend LOCAL_REQUIRED acceptance flag (%s)', async product_acceptance => {
  transport.json.mockResolvedValue({ ...response, product_acceptance });
  await expect(api().request(page, 'panel', options)).rejects.toBeTruthy();
});
