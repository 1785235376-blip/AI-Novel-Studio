import { beforeEach, describe, expect, it, vi } from 'vitest';
import { checkedComicImageCommand, checkedComicImageSource, sameComicImageCommand } from './studioComicImageContract';
import { studioProductionClient, type ProductionJob, type ProductionPreview } from './studioProductionClient';
const transport = vi.hoisted(() => ({ json: vi.fn(), blob: vi.fn() }));
vi.mock('./studioClient', async original => ({ ...await original<typeof import('./studioClient')>(), studioTransport: () => transport }));
const digest = 'a'.repeat(64);
const source = () => ({ id: 'page-1', kind: 'COMIC_PANEL' as const, version: 1, digest, reference_only: true as const,
  comic_panel: { panel_id: 'panel-1', panel_digest: digest, brief_digest: digest, actor: 'author', scope_key: digest, incarnation: 'file:12345678-1234-1234-1234-123456789012' } });
const command = () => checkedComicImageCommand({ operation_id: 'm5.image.t2i', request_id: 'comic-request', provider_id: 'local', model_id: 'fixture', prompt: 'A quiet room.', parameters: { width: 512, height: 512 }, source_snapshots: [source()], allow_cloud: false, license_note: '' });
const job = (): ProductionJob => ({ contract: 'studio-production-job/1', owner: 'image', id: 'job-1', novel_id: 'project', branch_id: null, version: 1,
  operation_id: 'm5.image.t2i', request_id: 'comic-request', status: 'QUEUED', request_digest: digest, receipt_digest: null, output_candidate: null,
  product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null, sources: [source()], command: command(),
  provider: { provider_id: 'local', model_id: 'fixture', local: true, route_digest: digest },
  execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', adapter: 'ORIGINAL_HTTP_PROVIDER', recipe_digest: digest, automatic_fallback: false },
  approved_asset_version: null, created_at: '', updated_at: '' });
const preview = (): ProductionPreview => ({ contract: 'studio-production-preview/1', novel_id: 'project', branch_id: null, request_id: 'comic-request', operation_id: 'm5.image.t2i', preview_digest: digest, request_digest: digest, command: command(), provider: job().provider, sources: [{ snapshot: source(), measured: {} }], execution_recipe: job().execution_recipe, product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' });
const client = () => studioProductionClient('project', { sessionToken: 'inert-fixture' });
beforeEach(() => transport.json.mockReset());
describe('Comic panel provenance is closed and exact', () => {
  it('normalizes nullable projection fields', () => {
    expect(checkedComicImageSource({ ...source(), asset_kind: null })).toEqual(source());
    expect(checkedComicImageCommand({ ...command(), parameters: { width: 512, height: 512, seed: null } }).parameters).toEqual(command().parameters);
  });
  it.each(['panel_id', 'panel_digest', 'brief_digest', 'actor', 'scope_key', 'incarnation'])('rejects changed %s equality', field => {
    const changed = source(); (changed.comic_panel as Record<string, string>)[field] = field.endsWith('digest') || field === 'scope_key' ? 'b'.repeat(64) : field === 'incarnation' ? 'postgres:12345678-1234-1234-1234-123456789012' : 'other';
    expect(sameComicImageCommand(command(), { ...command(), source_snapshots: [changed] })).toBe(false);
  });
  it.each([{ extra: true }, { asset_kind: 'image' }, { reference_only: false }, { version: 0 }, { digest: 'bad' }, { comic_panel: { ...source().comic_panel, extra: true } }])('rejects malformed source %j', change => expect(() => checkedComicImageSource({ ...source(), ...change })).toThrow());
  it.each([{ allow_cloud: true }, { operation_id: 'm5.image.i2i' }, { source_snapshots: [source(), source()] }, { image_source: source() }, { parameters: { voice_id: 'voice' } }])('rejects inappropriate comic command %j', change => expect(() => checkedComicImageCommand({ ...command(), ...change })).toThrow());
  it('leaves ordinary commands alone while rejecting provenance injection/removal', () => {
    const ordinary = { ...command(), source_snapshots: [] };
    expect(sameComicImageCommand(ordinary, ordinary)).toBe(true);
    expect(sameComicImageCommand(ordinary, command())).toBe(false);
    expect(sameComicImageCommand(command(), ordinary)).toBe(false);
  });
});
describe('Original Image lifecycle retains comic provenance', () => {
  it('accepts preview/create/get/list/execute/review without a new job schema', async () => {
    transport.json.mockResolvedValueOnce(preview()); expect((await client().preview(command())).command).toEqual(command());
    transport.json.mockResolvedValueOnce(job()); expect((await client().create(command(), digest)).sources).toEqual([source()]);
    transport.json.mockResolvedValueOnce(job()); expect((await client().get('image', 'job-1')).command).toEqual(command());
    transport.json.mockResolvedValueOnce({ items: [job()] }); expect(await client().list()).toHaveLength(1);
    for (const action of ['execute', 'review'] as const) { transport.json.mockResolvedValueOnce(job()); expect((await client()[action](job())).sources).toEqual([source()]); }
  });
  it.each(['preview', 'create', 'execute', 'review'] as const)('rejects substituted panel source on %s', async action => {
    const changed = action === 'preview' ? preview() : job();
    const replacement = { ...source(), comic_panel: { ...source().comic_panel, panel_id: 'other-panel' } };
    changed.command!.source_snapshots = [replacement];
    if ('owner' in changed) changed.sources = [replacement]; else changed.sources = [{ snapshot: replacement, measured: {} }];
    transport.json.mockResolvedValue(changed);
    const request = action === 'preview' ? client().preview(command()) : action === 'create' ? client().create(command(), digest) : client()[action](job());
    await expect(request).rejects.toBeTruthy();
  });
  it('rejects mismatched job sources, cloud receipts and unknown regular-source fields', async () => {
    const mismatch = job(); (mismatch.sources[0] as ReturnType<typeof source>).comic_panel.brief_digest = 'b'.repeat(64);
    const cloud = job(); cloud.provider!.local = false;
    const unknown = job(); unknown.sources = [{ id: 'asset', kind: 'ASSET', version: 1, digest, asset_kind: 'image', comic_panel: source().comic_panel } as never];
    for (const value of [mismatch, cloud, unknown]) { transport.json.mockResolvedValue(value); await expect(client().get('image', 'job-1')).rejects.toBeTruthy(); }
  });
  it('decodes stored projections with omitted reference defaults and nullable parameter defaults', async () => {
    const wire = job(), projected = { ...source(), asset_kind: null } as Record<string, unknown>;
    delete projected.reference_only; wire.sources = [projected as never];
    (wire.command!.parameters as Record<string, unknown>).scale = null;
    (wire.command!.parameters as Record<string, unknown>).target_peak_dbfs = null;
    transport.json.mockResolvedValue(wire);
    const decoded = await client().get('image', wire.id);
    expect(decoded.sources).toEqual([source()]); expect(decoded.command!.parameters).toEqual(command().parameters);
    const result = preview(); result.sources = [{ snapshot: projected as never, measured: {} }];
    transport.json.mockResolvedValue(result); expect((await client().preview(command())).sources![0].snapshot).toEqual(source());
  });
  it.each(['prompt', 'request_id', 'provider_id', 'license_note', 'parameters'])('rejects changed comic %s across review', async field => {
    const changed = job();
    if (field === 'parameters') changed.command!.parameters = { width: 1024, height: 512 };
    else { (changed.command as unknown as Record<string, unknown>)[field] = 'changed'; if (field === 'request_id') changed.request_id = 'changed'; if (field === 'provider_id') changed.provider!.provider_id = 'changed'; }
    transport.json.mockResolvedValue(changed); await expect(client().review(job())).rejects.toBeTruthy();
  });
  it('refuses malformed comic commands before transport', async () => {
    await expect(client().preview({ ...command(), allow_cloud: true })).rejects.toBeTruthy(); expect(transport.json).not.toHaveBeenCalled();
  });
});
