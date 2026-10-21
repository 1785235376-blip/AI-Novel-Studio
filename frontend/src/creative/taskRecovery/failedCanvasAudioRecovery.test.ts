import { describe, expect, it } from 'vitest';
import { deriveFailedCanvasAudioCommand as derive } from './failedCanvasAudioRecovery';
import { recoveryFixture } from './recovery.testFixtures';


describe('explicit failed canvas audio draft derivation', () => {
  it('preserves complete envelope and immutable pins with a fresh closed origin, without mutating originals', () => {
    const f = recoveryFixture(), before = JSON.stringify(f);
    const result = derive(f.job, f.task, 'new-request');
    expect(result).toEqual({ ...f.command, request_id: 'new-request', derived_from: { owner: 'audio', job_id: f.job.id,
      job_version: 4, request_id: f.job.request_id, request_digest: f.job.request_digest, receipt_digest: f.job.receipt_digest } });
    expect(JSON.stringify(f)).toBe(before);
    result.parameters.gain_db = 0; result.canvas_return!.source.version++;
    expect(f.job.command!.parameters.gain_db).toBe(-6); expect(f.task.returnBinding!.source.version).toBe(2);
  });
  it.each<Record<string, number>>([{}, { gain_db: 0, fade_in_ms: 0, fade_out_ms: 0 }])('retains old omission or explicit zero without defaults: %j', extras => {
    const f = recoveryFixture(); f.job.command!.parameters = { in_ms: 0, out_ms: 1000, ...extras };
    f.job.execution_recipe.parameters = { ...f.job.command!.parameters }; f.job.receipt_digest = null;
    const result = derive(f.job, f.task, 'new');
    expect(result.parameters).toEqual(f.job.command!.parameters); expect(result.derived_from.receipt_digest).toBeNull();
  });
  it('strips only known recorded null placeholders and source reference markers', () => {
    const f = recoveryFixture();
    Object.assign(f.job.command!.parameters, { width: null, height: null, steps: null, seed: null, cfg: null, negative_prompt: null,
      size: null, quality: null, duration_seconds: null, frame_rate: null, voice_id: null, speech_rate: null });
    f.job.command!.source_snapshots[0].reference_only = true; f.job.sources[0].reference_only = true;
    const result = derive(f.job, f.task, 'new'); expect(result.parameters).toEqual(f.command.parameters);
    expect(result.source_snapshots).toEqual([f.source]); expect(Object.hasOwn(result.source_snapshots[0], 'reference_only')).toBe(false);
  });
  it.each(['UNKNOWN', 'RUNNING', 'QUEUED', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'AWAITING_REVIEW', 'SUCCEEDED', 'APPROVED', 'CANCELLED'] as const)(
    'refuses %s without proposing replay', status => { const f = recoveryFixture(); f.job.status = status; expect(() => derive(f.job, f.task, 'new')).toThrow(); });
  it.each(['', 'original-request', 'a/b', 'a b', '-id', 'a'.repeat(101)])('refuses invalid or reused new request: %s', request => {
    const f = recoveryFixture(); expect(() => derive(f.job, f.task, request)).toThrow();
  });
  it.each(['owner', 'operation', 'provider', 'model', 'cloud', 'prompt', 'command request', 'missing command', 'missing binding',
    'job id', 'job version', 'request digest', 'receipt digest', 'remote may continue', 'reconciliation', 'candidate', 'automatic replay',
    'command secret', 'source secret', 'source marker', 'recipe secret', 'unknown null', 'control null', 'known real value',
    'incomplete range', 'overlapping fades', 'nonfinite gain', 'source pin', 'job sources', 'task pin', 'recipe parameters',
    'recipe format', 'recipe fallback', 'recipe adapter', 'project', 'branch', 'scope', 'incarnation', 'canvas version', 'card', 'retired'])(
    'rejects unsafe or changed origin: %s', change => {
      const f = recoveryFixture(), c = f.job.command!, b = f.task.returnBinding!;
      if (change === 'owner') f.job.owner = 'video';
      if (change === 'operation') f.job.operation_id = 'm8.audio.music';
      if (change === 'provider') f.job.provider = { provider_id: 'remote', model_id: 'm', local: true, route_digest: 'f'.repeat(64) };
      if (change === 'model') c.model_id = 'other';
      if (change === 'cloud') c.allow_cloud = true;
      if (change === 'prompt') c.prompt = 'do more';
      if (change === 'command request') c.request_id = 'different';
      if (change === 'missing command') f.job.command = null;
      if (change === 'missing binding') delete f.task.returnBinding;
      if (change === 'job id') f.job.id = 'bad/id';
      if (change === 'job version') f.job.version = 0;
      if (change === 'request digest') f.job.request_digest = 'bad';
      if (change === 'receipt digest') f.job.receipt_digest = 'bad';
      if (change === 'remote may continue') f.job.remote_compute_may_continue = true;
      if (change === 'reconciliation') f.job.needs_reconciliation = true;
      if (change === 'candidate') f.job.output_candidate = { id: 'candidate', version: 1, digest: 'f'.repeat(64), kind: 'audio' };
      if (change === 'automatic replay') Object.assign(f.job, { automatic_replay: true });
      if (change === 'command secret') Object.assign(c, { credential: 'must-not-copy' });
      if (change === 'source secret') Object.assign(c.source_snapshots[0], { token: 'must-not-copy' });
      if (change === 'source marker') Object.assign(c.source_snapshots[0], { reference_only: false });
      if (change === 'recipe secret') Object.assign(f.job.execution_recipe, { custom: true });
      if (change === 'unknown null') Object.assign(c.parameters, { future_parameter: null });
      if (change === 'control null') Object.assign(c.parameters, { gain_db: null });
      if (change === 'known real value') c.parameters.seed = 0;
      if (change === 'incomplete range') delete c.parameters.out_ms;
      if (change === 'overlapping fades') c.parameters.fade_out_ms = 1000;
      if (change === 'nonfinite gain') c.parameters.gain_db = NaN;
      if (change === 'source pin') c.source_snapshots[0].version++;
      if (change === 'job sources') f.job.sources[0].digest = 'f'.repeat(64);
      if (change === 'task pin') f.task.source.version++;
      if (change === 'recipe parameters') f.job.execution_recipe.parameters = { in_ms: 0, out_ms: 1000 };
      if (change === 'recipe format') f.job.execution_recipe.output_profile = 'FLAC';
      if (change === 'recipe fallback') Object.assign(f.job.execution_recipe, { automatic_fallback: true });
      if (change === 'recipe adapter') f.job.execution_recipe.adapter = 'PROVIDER';
      if (change === 'project') f.job.novel_id = 'other';
      if (change === 'branch') f.job.branch_id = 'other';
      if (change === 'scope') b.scope = { mode: 'collaboration', novel_id: 'project', workspace_id: 'w', storyline_id: 's', branch_id: 'b' };
      if (change === 'incarnation') b.incarnation = 'file:11234567-89ab-4cde-8fab-0123456789ab';
      if (change === 'canvas version') b.canvas_version++;
      if (change === 'card') b.card_id = 'replacement';
      if (change === 'retired') f.task.isCurrent = () => false;
      expect(() => derive(f.job, f.task, 'new')).toThrow();
    });
  it('accepts a matching collaboration scope while preserving its exact return binding', () => {
    const f = recoveryFixture(); f.job.branch_id = 'branch';
    f.task.returnBinding!.scope = { mode: 'collaboration', novel_id: 'project', workspace_id: 'workspace', storyline_id: 'story', branch_id: 'branch' };
    f.job.command!.canvas_return = structuredClone(f.task.returnBinding);
    expect(derive(f.job, f.task, 'new').canvas_return).toEqual(f.task.returnBinding);
  });
  it('rechecks an origin retired during validation', () => {
    const f = recoveryFixture(); let checks = 0; f.task.isCurrent = () => ++checks === 1;
    expect(() => derive(f.job, f.task, 'new')).toThrow();
  });
});


it('derives a new link from an already derived FAILED receipt, preserving the original template pin', () => {
  const f = recoveryFixture();
  const previous = { owner: 'audio', job_id: 'earlier-failed-job', job_version: 3, request_id: 'earlier-request',
    request_digest: 'f'.repeat(64), receipt_digest: null };
  const template = { contract: 'studio-canvas-audio-template/1', graph_id: 'original-graph', graph_version: 2,
    definition_digest: '1'.repeat(64), execution_digest: '2'.repeat(64), node_id: 'trim-node', parameters: { in_ms: 0, out_ms: 1000 } };
  Object.assign(f.job.command!, { derived_from: structuredClone(previous), template_ref: structuredClone(template) });
  const before = JSON.stringify(f.job), result = derive(f.job, f.task, 'another-new-request');
  expect(result.derived_from.job_id).toBe(f.job.id); expect(result.derived_from.request_id).toBe(f.job.request_id);
  expect(result.template_ref).toEqual(template); expect(result.template_ref).not.toBe(template);
  result.template_ref!.parameters.in_ms = 10; expect(JSON.stringify(f.job)).toBe(before);
});
it.each(['null', 'owner', 'id', 'version', 'request', 'request digest', 'receipt', 'extension', 'self job', 'self request'])(
  'rejects malformed prior recorded derivation: %s', change => {
    const f = recoveryFixture(); const previous: Record<string, unknown> = { owner: 'audio', job_id: 'previous-job', job_version: 2,
      request_id: 'previous-request', request_digest: 'f'.repeat(64), receipt_digest: null };
    if (change === 'owner') previous.owner = 'video';
    if (change === 'id') previous.job_id = 'bad/id';
    if (change === 'version') previous.job_version = 0;
    if (change === 'request') previous.request_id = '';
    if (change === 'request digest') previous.request_digest = 'bad';
    if (change === 'receipt') delete previous.receipt_digest;
    if (change === 'extension') previous.credential = 'no-copy';
    if (change === 'self job') previous.job_id = f.job.id;
    if (change === 'self request') previous.request_id = f.job.request_id;
    Object.assign(f.job.command!, { derived_from: change === 'null' ? null : previous });
    expect(() => derive(f.job, f.task, 'new')).toThrow();
  });
it.each(['null', 'contract', 'id', 'version', 'digest', 'node', 'parameters', 'parameter extension', 'extension'])(
  'rejects malformed recorded template provenance: %s', change => {
    const f = recoveryFixture(); const template: Record<string, unknown> = { contract: 'studio-canvas-audio-template/1', graph_id: 'graph',
      graph_version: 2, definition_digest: '1'.repeat(64), execution_digest: '2'.repeat(64), node_id: 'trim', parameters: { in_ms: 0, out_ms: 1000 } };
    if (change === 'contract') template.contract = 'future';
    if (change === 'id') template.graph_id = 'bad/id';
    if (change === 'version') template.graph_version = 0;
    if (change === 'digest') template.execution_digest = 'bad';
    if (change === 'node') template.node_id = '';
    if (change === 'parameters') template.parameters = { in_ms: 0, out_ms: 0 };
    if (change === 'parameter extension') template.parameters = { in_ms: 0, out_ms: 1000, gain_db: 0 };
    if (change === 'extension') template.credential = 'no-copy';
    Object.assign(f.job.command!, { template_ref: change === 'null' ? null : template });
    expect(() => derive(f.job, f.task, 'new')).toThrow();
  });
