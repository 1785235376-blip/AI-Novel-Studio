import { describe, expect, it, vi } from 'vitest';
import { checkedCanvasVideoTaskJob } from '../canvasVideoTrimTask';
import { canDeriveFailedCanvasVideoDraft, deriveFailedCanvasVideoDraft } from './failedCanvasVideoRecovery';
import { hash, recoveryFixture } from './recovery.testFixtures';

describe('original FAILED CanvasVideo draft preparation', () => {
  it.each([undefined, false, true])('preserves the exact range and include_audio=%s, origin and immutable parent', audio => {
    const { job, task } = recoveryFixture(audio), before = structuredClone(job);
    const result = deriveFailedCanvasVideoDraft(job, task, 'new-explicit-request');
    expect(checkedCanvasVideoTaskJob(job)).toEqual(job);
    expect(result).toEqual({ request_id: 'new-explicit-request',
      derived_from: { owner: 'timeline', job_id: job.id, job_version: job.version, request_id: job.request_id,
        request_digest: job.request_digest, receipt_digest: job.receipt_digest },
      parameters: job.canvas_video.parameters, source_snapshots: job.canvas_video.source_snapshots, canvas_return: job.canvas_video.canvas_return });
    expect(Object.hasOwn(result, 'timeline_snapshot')).toBe(false);
    expect(Object.hasOwn(result.parameters, 'include_audio')).toBe(audio !== undefined);
    result.parameters.in_ms = 0; result.source_snapshots[0].version = 999; result.canvas_return.scope.novel_id = 'changed';
    expect(job).toEqual(before); expect(task.source.version).toBe(2); expect(task.returnBinding!.scope.novel_id).toBe('project');
  });
  it('preserves a null receipt digest without substituting a hash', () => {
    const { job, task } = recoveryFixture(); job.receipt_digest = null;
    expect(deriveFailedCanvasVideoDraft(job, task, 'new').derived_from.receipt_digest).toBeNull();
  });
  it('preserves the complete original collaboration scope and incarnation', () => {
    const { job, task } = recoveryFixture();
    job.branch_id = 'branch'; job.canvas_video.canvas_return.scope = { mode: 'collaboration', novel_id: 'project',
      workspace_id: 'workspace', project_id: 'collab-project', storyline_id: 'storyline', branch_id: 'branch' };
    job.canvas_video.canvas_return.incarnation = 'postgres:00000000-0000-0000-0000-000000000002';
    task.returnBinding = structuredClone(job.canvas_video.canvas_return);
    expect(deriveFailedCanvasVideoDraft(job, task, 'new').canvas_return).toEqual(task.returnBinding);
  });
  it.each(['UNKNOWN', 'RUNNING', 'CANCELLED', 'QUEUED', 'SUCCEEDED', 'APPROVED', 'REVIEWING'] as const)('rejects %s parents', status => {
    const { job, task } = recoveryFixture(); job.status = status;
    expect(() => deriveFailedCanvasVideoDraft(job, task, 'new')).toThrow(); expect(canDeriveFailedCanvasVideoDraft(job, task)).toBe(false);
  });
  it.each(['', 'original-request', 'bad/request', 'a'.repeat(101)])('rejects reused or invalid request identity %s', request => {
    const { job, task } = recoveryFixture(); expect(() => deriveFailedCanvasVideoDraft(job, task, request)).toThrow();
  });
  it.each(['legacy', 'owner', 'command', 'source', 'sources', 'branch', 'request', 'digest', 'receipt', 'version', 'timeline',
    'recipe', 'profile', 'candidate', 'measurement', 'approved', 'reconcile', 'cloud', 'parameter', 'undefined-audio', 'unknown-command'])(
    'rejects a changed or untyped original %s', kind => {
      const { job, task } = recoveryFixture(); const value: any = job;
      if (kind === 'legacy') delete value.canvas_video;
      if (kind === 'owner') value.owner = 'video';
      if (kind === 'command') value.command = {};
      if (kind === 'source') value.canvas_video.source_snapshots[0].version++;
      if (kind === 'sources') value.sources[0].digest = hash('b');
      if (kind === 'branch') value.branch_id = 'other';
      if (kind === 'request') value.request_id = 'other';
      if (kind === 'digest') value.request_digest = 'bad';
      if (kind === 'receipt') value.receipt_digest = 'bad';
      if (kind === 'version') value.version = 0;
      if (kind === 'timeline') value.timeline_snapshot.version++;
      if (kind === 'recipe') value.execution_recipe.adapter = 'REMOTE';
      if (kind === 'profile') value.execution_recipe.export_profile.crf++;
      if (kind === 'candidate') value.output_candidate = { id: 'candidate', kind: 'video', version: 1, digest: hash('f') };
      if (kind === 'measurement') value.media_measurement = {};
      if (kind === 'approved') value.approved_asset_version = 2;
      if (kind === 'reconcile') value.needs_reconciliation = true;
      if (kind === 'cloud') value.canvas_video.allow_cloud = true;
      if (kind === 'parameter') value.canvas_video.parameters.speed = 2;
      if (kind === 'undefined-audio') value.canvas_video.parameters.include_audio = undefined;
      if (kind === 'unknown-command') value.canvas_video.extra = undefined;
      expect(() => deriveFailedCanvasVideoDraft(job, task, 'new')).toThrow();
    });
  it.each(['missing', 'scope', 'incarnation', 'canvas', 'canvas-version', 'canvas-digest', 'card', 'source', 'source-kind', 'source-extension'])(
    'requires exact current task return/source binding: %s', kind => {
      const { job, task } = recoveryFixture(); const value: any = task;
      if (kind === 'missing') delete value.returnBinding;
      if (kind === 'scope') value.returnBinding.scope.project_id = 'other';
      if (kind === 'incarnation') value.returnBinding.incarnation = 'file:00000000-0000-0000-0000-000000000002';
      if (kind === 'canvas') value.returnBinding.canvas_id = 'other';
      if (kind === 'canvas-version') value.returnBinding.canvas_version++;
      if (kind === 'canvas-digest') value.returnBinding.canvas_digest = hash('f');
      if (kind === 'card') value.returnBinding.card_id = 'other';
      if (kind === 'source') value.source.version++;
      if (kind === 'source-kind') value.source.asset_kind = 'audio';
      if (kind === 'source-extension') value.source.reference_only = undefined;
      expect(() => deriveFailedCanvasVideoDraft(job, task, 'new')).toThrow();
    });
  it('rechecks the task getter after validation and never reads a client or dispatches', () => {
    const { job, task } = recoveryFixture(); task.isCurrent = vi.fn().mockReturnValueOnce(true).mockReturnValue(false);
    expect(() => deriveFailedCanvasVideoDraft(job, task, 'new')).toThrow(); expect(task.isCurrent).toHaveBeenCalledTimes(2);
  });
  it.each(['job', 'source', 'binding'])('rejects a getter that mutates the %s while validating', kind => {
    const { job, task } = recoveryFixture();
    task.isCurrent = () => {
      if (kind === 'job') job.version++;
      if (kind === 'source') task.source.version++;
      if (kind === 'binding') task.returnBinding!.canvas_version++;
      return true;
    };
    expect(() => deriveFailedCanvasVideoDraft(job, task, 'new')).toThrow();
  });
});
