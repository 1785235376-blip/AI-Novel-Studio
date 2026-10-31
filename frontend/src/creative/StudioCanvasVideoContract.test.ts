import { afterEach, describe, expect, it, vi } from 'vitest';
import native from './canvasVideoTrimTask.testFixtures';
import audio from './canvasAudioTrimTask.testFixtures';
import { studioProductionClient, type MediaCommand, type ProductionJob } from './studioProductionClient';
import { checkedCanvasVideoTaskCommand, type CanvasVideoTaskCommand } from './canvasVideoTrimTask';
import { canvasReturnInCommand, canvasReturnInJob, checkedCanvasReturnBinding } from './studioCanvasReturnBinding';

// Source-generated software receipts only; candidate bytes are not playable video.
// Real FFmpeg decoding is tested separately in Python. No model run is claimed.
const project = native.canvas.project_id;
const base = `/api/projects/${project}/studio/production`;
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const command = (): CanvasVideoTaskCommand => checkedCanvasVideoTaskCommand(structuredClone(native.command));
const job = (key: 'queued' | 'executed' | 'approved'): ProductionJob => structuredClone(native[key]) as unknown as ProductionJob;
const client = () => studioProductionClient(project, { sessionToken: 'synthetic-test-session' });
const body = (init: RequestInit) => JSON.parse(String(init.body));
type Edit = (value: any) => void;
const changed = <T,>(value: T, edit: Edit): T => { const next = structuredClone(value); edit(next); return next; };
const candidateBytes = () => Uint8Array.from(atob(native.candidate_base64), character => character.charCodeAt(0));

afterEach(() => vi.unstubAllGlobals());

it('decodes synthetic preview/queue/execute/get/list/review/candidate through the original SDK owners', async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({ url, init });
    if (url === `${base}/canvas-video/preview`) return json(native.preview);
    if (url === `${base}/canvas-video/queue`) return json(native.queued);
    if (url === `${base}/canvas-video/jobs/${native.queued.id}/execute`) return json(native.executed);
    if (url === `${base}/jobs/timeline/${native.queued.id}/review`) return json(native.approved);
    if (url === `${base}/jobs/timeline/${native.queued.id}/candidate`) return new Response(candidateBytes(), {
      headers: { 'Content-Type': 'video/mp4' },
    });
    if (url === `${base}/jobs/timeline/${native.queued.id}`) return json(native.executed);
    if (url === `${base}/jobs`) return json({ items: [native.executed] });
    throw new Error(`Unexpected SDK route: ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const sdk = client(), input = command();
  const preview = await sdk.canvasVideoPreview(input);
  expect(preview.command).toEqual(input);
  expect(preview.execution_available).toBe(true);
  expect(preview.automatic_dispatch).toBe(false);
  const queued = await sdk.canvasVideoQueue(input, preview.preview_digest);
  expect(calls.map(call => call.url)).toEqual([`${base}/canvas-video/preview`, `${base}/canvas-video/queue`]);
  const executed = await sdk.canvasVideoExecute(queued);
  const loaded = await sdk.get('timeline', executed.id);
  const listed = await sdk.list();
  const approved = await sdk.review(loaded);
  const candidate = await sdk.candidate(executed);

  expect(executed.status).toBe('SUCCEEDED');
  expect(loaded.canvas_video).toEqual(input);
  expect(listed).toEqual([loaded]);
  expect(loaded.command).toBeNull();
  expect(loaded.provider).toBeNull();
  expect(approved.status).toBe('APPROVED');
  expect(approved.approved_asset_version).toBe(native.formal_asset.version);
  expect(canvasReturnInJob(approved)).toEqual(input.canvas_return);
  expect(executed.media_measurement).toMatchObject({ duration_ms: 600, width: 640, height: 360, fps: 25,
    video_codec: 'h264', container: 'mp4', profile_validation: 'NATIVE_FFPROBE_EXACT',
    render_profile: 'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4',
    export_profile: { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: 400, audio_bitrate_kbps: 96, crf: 23 } });
  expect(native.real_cpu_ffmpeg).toBe(false);
  expect(native.model_called).toBe(false);
  expect(native.output.decoded_frames).toBe(15);
  expect(candidate.type).toBe('video/mp4');
  expect(new Uint8Array(await candidate.arrayBuffer())).toEqual(candidateBytes());
  expect(candidate.size).toBe(native.output.byte_count);

  expect(calls.map(call => [call.url, call.init.method])).toEqual([
    [`${base}/canvas-video/preview`, 'POST'], [`${base}/canvas-video/queue`, 'POST'],
    [`${base}/canvas-video/jobs/${queued.id}/execute`, 'POST'], [`${base}/jobs/timeline/${queued.id}`, 'GET'],
    [`${base}/jobs`, 'GET'], [`${base}/jobs/timeline/${queued.id}/review`, 'POST'],
    [`${base}/jobs/timeline/${queued.id}/candidate`, 'GET'],
  ]);
  expect(body(calls[0].init)).toEqual(input);
  expect(body(calls[1].init)).toEqual({ command: input, reviewed_preview_digest: preview.preview_digest });
  expect(new Headers(calls[1].init.headers).get('Idempotency-Key')).toBe(input.request_id);
  expect(body(calls[2].init)).toEqual({ expected_version: queued.version, expected_request_digest: queued.request_digest });
  expect(body(calls[5].init)).toEqual({ expected_version: loaded.version, expected_request_digest: loaded.request_digest,
    reviewed_output_digest: loaded.output_candidate!.digest });
});

it('decodes source-generated queued GET/list and approved GET receipts without dispatch or adoption', async () => {
  let reads = 0;
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    expect(init.method).toBe('GET');
    if (url === `${base}/jobs`) return json(native.list_queued);
    expect(url).toBe(`${base}/jobs/timeline/${native.queued.id}`);
    return json(reads++ === 0 ? native.get_queued : native.get);
  });
  vi.stubGlobal('fetch', fetcher);
  const sdk = client();
  expect(await sdk.get('timeline', native.queued.id)).toEqual(native.get_queued);
  expect(await sdk.list()).toEqual(native.list_queued.items);
  expect(await sdk.get('timeline', native.queued.id)).toEqual(native.get);
  expect(fetcher).toHaveBeenCalledTimes(3);
});

describe('fresh dedicated request admission', () => {
  const invalidInputs: [string, Edit][] = [
    ['unsupported parameter', value => { value.parameters.gain_db = 0; }],
    ['non-frame-aligned range', value => { value.parameters.in_ms = 1001; }],
    ['provider', value => { value.provider_id = 'unavailable-provider'; }],
    ['model', value => { value.model_id = 'unavailable-model'; }],
    ['cloud permission', value => { value.allow_cloud = true; }],
    ['prompt', value => { value.prompt = 'not a generation task'; }],
    ['projection-only source', value => { value.source_snapshots[0].reference_only = true; }],
    ['mismatched source pin', value => { value.source_snapshots[0].version += 1; }],
    ['extra timeline field', value => { value.timeline_snapshot.unrecognised = null; }],
    ['extra return-binding field', value => { value.canvas_return.unrecognised = null; }],
  ];
  it.each(invalidInputs)('rejects %s before preview or queue transport', async (_name, edit) => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    const input = changed(command(), edit), sdk = client();
    await expect(sdk.canvasVideoPreview(input)).rejects.toBeDefined();
    await expect(sdk.canvasVideoQueue(input, native.preview.preview_digest)).rejects.toBeDefined();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['project', 'branch', 'client context'] as const)('rejects wrong %s before transport', async mode => {
    const input = command();
    if (mode === 'project') {
      input.canvas_return.project_id = 'other-project'; input.canvas_return.scope.novel_id = 'other-project';
    }
    if (mode === 'branch') input.canvas_return.scope = { mode: 'collaboration', novel_id: project,
      workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'other-branch' };
    const sdk = mode === 'client context' ? studioProductionClient(project, { sessionToken: 'synthetic-test-session',
      scope: { projectId: 'other-project', workspaceId: 'workspace', storylineId: 'storyline', branchId: 'branch' } }) : client();
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    await expect(sdk.canvasVideoPreview(input)).rejects.toBeDefined();
    await expect(sdk.canvasVideoQueue(input, native.preview.preview_digest)).rejects.toBeDefined();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('rejects an absent reviewed preview digest before queue transport', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    await expect(client().canvasVideoQueue(command(), '')).rejects.toBeDefined();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['UNKNOWN', 'RUNNING', 'SUCCEEDED', 'APPROVED'] as const)('does not send %s through dedicated execute', async status => {
    const input = job(status === 'APPROVED' ? 'approved' : status === 'SUCCEEDED' ? 'executed' : 'queued');
    input.status = status;
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    await expect(client().canvasVideoExecute(input)).rejects.toBeDefined();
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe('expected preview and action identity', () => {
  const swappedCommands: [string, Edit][] = [
    ['target card', value => { value.canvas_return.card_id = 'other-card'; }],
    ['canvas digest', value => { value.canvas_return.canvas_digest = 'a'.repeat(64); }],
    ['incarnation', value => { value.canvas_return.incarnation = 'file:00000000-0000-0000-0000-000000000001'; }],
    ['source pin', value => { value.source_snapshots[0].digest = 'a'.repeat(64); value.canvas_return.source.digest = 'a'.repeat(64); }],
    ['timeline snapshot', value => { value.timeline_snapshot.version += 1; }],
    ['request identity', value => { value.request_id = 'other-request'; }],
  ];
  it.each(swappedCommands)('rejects self-consistent but swapped %s in preview/queue/execute/review', async (_name, edit) => {
    const alteredPreview: any = structuredClone(native.preview); edit(alteredPreview.command);
    if (_name === 'source pin') alteredPreview.execution_recipe.timeline.tracks[0].clips[0].source_snapshot.digest = 'a'.repeat(64);
    const alteredJob = (key: 'queued' | 'executed' | 'approved') => changed(native[key], value => {
      edit(value.canvas_video);
      value.sources = structuredClone(value.canvas_video.source_snapshots);
      value.timeline_snapshot = structuredClone(value.canvas_video.timeline_snapshot);
      value.request_id = value.canvas_video.request_id;
      if (_name === 'source pin') value.execution_recipe.timeline.tracks[0].clips[0].source_snapshot.digest = 'a'.repeat(64);
    });
    vi.stubGlobal('fetch', vi.fn(async (url: string) => json(url.endsWith('/preview') ? alteredPreview
      : url.endsWith('/queue') ? alteredJob('queued') : url.endsWith('/review') ? alteredJob('approved') : alteredJob('executed'))));
    const sdk = client();
    await expect(sdk.canvasVideoPreview(command())).rejects.toBeDefined();
    await expect(sdk.canvasVideoQueue(command(), native.preview.preview_digest)).rejects.toBeDefined();
    await expect(sdk.canvasVideoExecute(job('queued'))).rejects.toBeDefined();
    await expect(sdk.review(job('executed'))).rejects.toBeDefined();
  });
  it.each(['request_digest', 'recipe_digest'] as const)('rejects changed %s in execution/review receipts', async field => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => json(changed(url.endsWith('/review') ? native.approved : native.executed, value => {
      if (field === 'recipe_digest') value.execution_recipe.recipe_digest = 'a'.repeat(64);
      else value.request_digest = 'a'.repeat(64);
    }))));
    await expect(client().canvasVideoExecute(job('queued'))).rejects.toBeDefined();
    await expect(client().review(job('executed'))).rejects.toBeDefined();
  });
  it('rejects a non-advancing execution version', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ...native.executed, version: native.queued.version })));
    await expect(client().canvasVideoExecute(job('queued'))).rejects.toBeDefined();
  });
  it('preserves execution-unavailable preview without dispatching', async () => {
    const fetcher = vi.fn(async () => json({ ...native.preview, execution_available: false })); vi.stubGlobal('fetch', fetcher);
    expect((await client().canvasVideoPreview(command())).execution_available).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe('strict stored video capsule and native recipe projection', () => {
  const corruptions: [string, Edit][] = [
    ['cross-project receipt', value => { value.novel_id = 'other-project'; }],
    ['cross-branch receipt', value => { value.branch_id = 'other-branch'; }],
    ['source disagreement', value => { value.sources[0].version += 1; }],
    ['snapshot disagreement', value => { value.timeline_snapshot.version += 1; }],
    ['rendered audio inclusion', value => { value.execution_recipe.timeline.tracks[0].clips[0].include_audio = true; }],
    ['rendered range', value => { value.execution_recipe.timeline.tracks[0].clips[0].in_ms = 1040; }],
    ['unsupported export', value => { value.execution_recipe.output_profile = 'REVIEW_MP4'; }],
    ['changed H264 export controls', value => { value.execution_recipe.export_profile.video_bitrate_kbps = 401; }],
    ['unknown adapter', value => { value.execution_recipe.adapter = 'UNKNOWN'; }],
    ['legacy command substitution', value => { value.command = value.canvas_video; }],
    ['provider execution state', value => { value.status = 'REMOTE_RUNNING'; }],
    ['automatic replay', value => { value.automatic_replay = true; }],
    ['missing capsule', value => { value.canvas_video = null; }],
    ['wrong measured duration', value => { value.media_measurement.duration_ms = 640; }],
    ['old MPEG4 candidate', value => { value.media_measurement.video_codec = 'mpeg4'; }],
    ['missing native measurement', value => { value.media_measurement = null; }],
    ['candidate media kind', value => { value.output_candidate.kind = 'audio'; }],
  ];
  it.each(corruptions)('rejects %s through original get and list', async (_name, edit) => {
    const receipt = changed(native.executed, edit);
    vi.stubGlobal('fetch', vi.fn(async (url: string) => json(url === `${base}/jobs` ? { items: [receipt] } : receipt)));
    await expect(client().get('timeline', native.executed.id)).rejects.toBeDefined();
    await expect(client().list()).rejects.toBeDefined();
  });
  it.each(['scope', 'timeline', 'dispatch'] as const)('rejects preview %s corruption', async field => {
    const receipt = changed(native.preview, value => {
      if (field === 'scope') value.branch_id = 'other-branch';
      if (field === 'timeline') value.execution_recipe.timeline.width = 1280;
      if (field === 'dispatch') value.automatic_dispatch = true;
    });
    vi.stubGlobal('fetch', vi.fn(async () => json(receipt)));
    await expect(client().canvasVideoPreview(command())).rejects.toBeDefined();
  });
  it('reads UNKNOWN once and refuses dedicated replay', async () => {
    const receipt = { ...native.queued, status: 'UNKNOWN', needs_reconciliation: true };
    const fetcher = vi.fn(async () => json(receipt)); vi.stubGlobal('fetch', fetcher);
    const sdk = client(), loaded = await sdk.get('timeline', native.queued.id);
    expect(loaded.status).toBe('UNKNOWN'); expect(loaded.automatic_replay).toBe(false);
    await expect(sdk.canvasVideoExecute(loaded)).rejects.toBeDefined();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

it('retains an old timeline without guessing a canvas capsule and keeps generic execute on its original endpoint', async () => {
  const legacy: any = structuredClone(native.queued); delete legacy.canvas_video;
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url);
    if (url.endsWith('/execute')) return json({ code: 'STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY' }, 409);
    return json(legacy);
  }));
  const sdk = client(), loaded = await sdk.get('timeline', native.queued.id);
  expect(loaded.canvas_video).toBeUndefined(); expect(canvasReturnInJob(loaded)).toBeUndefined();
  await expect(sdk.canvasVideoExecute(loaded)).rejects.toBeDefined();
  expect(calls).toHaveLength(1);
  await expect(sdk.execute(loaded)).rejects.toMatchObject({ problem: { status: 409, code: 'STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY' } });
  expect(calls).toEqual([`${base}/jobs/timeline/${loaded.id}`, `${base}/jobs/timeline/${loaded.id}/execute`]);
});

it.each(['m5.image.i2i', 'm8.audio.trim'] as const)('does not admit a video binding through legacy %s parsing or transport', async operation_id => {
  const binding = command().canvas_return;
  expect(() => checkedCanvasReturnBinding(binding)).toThrow();
  const legacy = { ...command(), operation_id, ...(operation_id === 'm5.image.i2i' ? { image_source: binding.source } : {}) } as unknown as MediaCommand;
  expect(() => canvasReturnInCommand(legacy)).toThrow();
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  await expect(client().preview(legacy)).rejects.toBeDefined();
  await expect(client().create(legacy, native.preview.preview_digest)).rejects.toBeDefined();
  expect(fetcher).not.toHaveBeenCalled();
});

it('retains the original image/audio return parser and native audio Job read', async () => {
  const image = changed(command().canvas_return, value => { value.source.asset_kind = 'image'; });
  expect(checkedCanvasReturnBinding(image).source.asset_kind).toBe('image');
  expect(canvasReturnInCommand({ operation_id: 'm5.image.i2i', allow_cloud: false, canvas_return: image,
    source_snapshots: [image.source], image_source: image.source })).toEqual(image);
  expect(canvasReturnInCommand(audio.command)).toEqual(audio.command.canvas_return);
  vi.stubGlobal('fetch', vi.fn(async () => json(audio.approved)));
  const loaded = await studioProductionClient(audio.canvas.project_id, { sessionToken: 'synthetic-test-session' }).get('audio', audio.approved.id);
  expect(loaded.status).toBe('APPROVED'); expect(loaded.canvas_video).toBeUndefined();
  expect(canvasReturnInJob(loaded)?.source.asset_kind).toBe('audio');
});
