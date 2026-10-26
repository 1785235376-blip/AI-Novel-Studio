/**
 * Stage 4 (DCI t188u): SEPARATE counterexample file (not LiveContract).
 * Covers: unknown-field reject (no silent filter), provenance cannot be dropped,
 * auth/authority not loosened, BACKEND_BLOCKED image-node-result 403 is failure,
 * old jobs without field stay compatible at the parser boundary.
 * Does not claim product PASS; does not fix backend CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN.
 */
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import {
  canvasImageNodeInCommand,
  checkedCanvasImageNodeBinding,
  checkedCanvasImageNodeOrigin,
} from './canvasImageNode';
import { createStudioGraphClient } from './studioGraphClient';
import live from '../../../tests/fixtures/studio_dci_live_image_node.json';

const L = live.api as unknown as Record<string, { status: number; body: any }>;
const goodBinding = () => structuredClone(L['get.final'].body.command.canvas_image_node);

function goodOrigin() {
  return {
    contract: 'studio-canvas-image-node-result/1',
    target: goodBinding(),
    job_id: 'job-1',
    job_version: 1,
    job_request_digest: 'a'.repeat(64),
    asset: { asset_id: 'asset-1', version: 1, digest: 'b'.repeat(64), kind: 'image' },
  };
}

describe('Stage4 counterexamples (separate from LiveContract)', () => {
  it('unknown binding field is rejected — not silently filtered', () => {
    const withExtra = { ...goodBinding(), unexpected: 'x' };
    // A silent-filter implementation would strip `unexpected` and return; exact() must throw.
    expect(() => checkedCanvasImageNodeBinding(withExtra)).toThrow();
    expect(() => checkedCanvasImageNodeBinding(goodBinding())).not.toThrow();
  });

  it('unknown origin field is rejected — provenance surface stays closed', () => {
    expect(() => checkedCanvasImageNodeOrigin({ ...goodOrigin(), leaked: true })).toThrow();
    expect(() => checkedCanvasImageNodeOrigin(goodOrigin())).not.toThrow();
  });

  it('dropping a provenance key on origin is rejected (no soft-ok without job_request_digest)', () => {
    const missing = goodOrigin() as Record<string, unknown>;
    delete missing.job_request_digest;
    expect(() => checkedCanvasImageNodeOrigin(missing)).toThrow();
  });

  it('mixed media fields with canvas_image_node are rejected (no silent strip)', () => {
    const cmd = structuredClone(L['get.final'].body.command);
    cmd.canvas_return = { kind: 'image' };
    expect(() => canvasImageNodeInCommand(cmd)).toThrow();
  });

  it('old jobs without canvas_image_node stay compatible at parser boundary', () => {
    const cmd = structuredClone(L['get.final'].body.command);
    delete cmd.canvas_image_node;
    expect(canvasImageNodeInCommand(cmd)).toBeUndefined();
  });

  it('does not loosen execution_authority on canvas-view responses', async () => {
    const definition = {
      schema_version: 1,
      title: 'Media',
      cards: [{ id: 'Card', position: { x: 0, y: 0 }, asset: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' } }],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const row = {
      project_id: 'project',
      scope: { mode: 'local', novel_id: 'project' },
      id: 'view',
      version: 1,
      definition: structuredClone(definition),
      definition_digest: 'b'.repeat(64),
      created_at: '2026-10-18',
      updated_at: '2026-10-18',
      reference_states: [{ card_id: 'Card', state: 'CURRENT_METADATA', filename: 'test.png' }],
      execution_authority: true, // counterexample: loosened authority must be rejected
      binary_content_verified: false,
      capacity: { history_used: 1, record_bytes: 1000 },
    };
    const json = vi.fn().mockResolvedValue(row);
    const client = createStudioGraphClient('project', {}, { json }).canvasViews;
    await expect(client.get('view')).rejects.toThrow();
  });

  it('image-node-result 403 BACKEND_BLOCKED is failure, not soft success', async () => {
    const definition = {
      schema_version: 1,
      title: 'Media',
      cards: [] as unknown[],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const empty = {
      project_id: 'project',
      scope: { mode: 'local', novel_id: 'project' },
      id: 'view',
      version: 1,
      definition: structuredClone(definition),
      definition_digest: 'b'.repeat(64),
      created_at: '2026-10-18',
      updated_at: '2026-10-18',
      reference_states: [] as unknown[],
      execution_authority: false,
      binary_content_verified: false,
      capacity: { history_used: 0, record_bytes: 100 },
    };
    const blocked = new ApiError({
      status: 403,
      code: 'CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN',
      message: '当前会话无权访问此内容。请重新核对身份和分支。',
    });
    const json = vi.fn()
      .mockResolvedValueOnce(empty)
      .mockRejectedValueOnce(blocked);
    const client = createStudioGraphClient('project', {}, { json }).canvasViews!;
    const source = await client.get('view');
    const incarnation = 'file:12345678-1234-1234-1234-123456789abc';
    const job = { id: 'formal-job', version: 5, request_digest: 'd'.repeat(64) };
    const pin = { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' as const };
    await expect(client.imageNodeResult(source, incarnation, job, pin)).rejects.toMatchObject({
      problem: { status: 403, code: 'CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN' },
    });
    // Must have attempted the POST — not short-circuited into a fake adopt.
    expect(json).toHaveBeenCalledTimes(2);
    expect(json.mock.calls[1][0]).toContain('/image-node-result');
    expect(json.mock.calls[1][1]).toBe('POST');
  });
});
