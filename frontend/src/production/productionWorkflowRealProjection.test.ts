/**
 * Cross-boundary contract check: the STRICT frontend decoder must accept a real
 * backend payload.
 *
 * The fixture is not hand-written. It is the exact JSON emitted by
 * `scripts/emit_phase7_workflow_fixture.py` from a real File-backed run of the
 * landed `ProductionWorkflowService` (activated neutral studio + saved intent v2
 * + one real imported image), so a field rename or an added/removed key on
 * either side fails this test instead of failing in a browser.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '../api';
import { productionWorkflowProjection } from './productionWorkflowContract';
import fixture from './fixtures/productionWorkflowProjection.real.json';

const PROJECT = 'phase7-fixture-project';

/** The strict decoder signals failure with a machine code; assert the code, not the message. */
function rejectionCode(run: () => unknown): string | undefined {
  try {
    run();
    return undefined;
  } catch (error) {
    return error instanceof ApiError ? error.problem.code : undefined;
  }
}

describe('production workflow contract against a real backend projection', () => {
  const decoded = productionWorkflowProjection(fixture, PROJECT, { mode: 'local', novel_id: PROJECT });

  it('accepts the real payload and preserves the frozen identities', () => {
    expect(decoded.schema_version).toBe(1);
    expect(decoded.contract).toBe('studio-production-workflow/1');
    expect(decoded.project_id).toBe(PROJECT);
    expect(decoded.advisory_only).toBe(true);
    expect(decoded.execution_authority).toBe(false);
  });

  it('carries the seven modules in the frozen integration order', () => {
    expect(decoded.modules.map(row => row.id)).toEqual(
      ['director', 'storyboard', 'image', 'video', 'audio', 'timeline', 'asset']);
    expect(decoded.modules.every(row => row.owner.length > 0)).toBe(true);
  });

  it('projects the saved intent actually written through the owner', () => {
    expect(decoded.creative_intent.version).toBe(2);
    expect(decoded.creative_intent.preset).toBe('EDITING');
    const selected = decoded.creative_intent.values.filter(row => row.selected).map(row => row.intent_id);
    expect(selected).toEqual(['ai_short_film', 'custom']);
    expect(decoded.creative_intent.values.find(row => row.intent_id === 'custom')?.custom).toBe(true);
    expect(decoded.creative_intent.values).toHaveLength(11);
  });

  it('projects the real imported asset into exactly the image and library modules', () => {
    const byId = Object.fromEntries(decoded.modules.map(row => [row.id, row]));
    expect(byId.image.asset_count).toBe(1);
    expect(byId.image.status).toBe('IN_PRODUCTION');
    expect(byId.asset.asset_count).toBe(1);
    expect(byId.video.asset_count).toBe(0);
    expect(byId.audio.asset_count).toBe(0);
    expect(decoded.asset_overview.total).toBe(1);
    expect(decoded.asset_overview.by_kind.image).toBe(1);
  });

  it('reports the neutral studio start state from the owner activation receipt', () => {
    expect(decoded.project_start.state).toBe('STARTED');
    expect(decoded.project_start.entry_kind).toBe('NEUTRAL_STUDIO');
    expect(decoded.project_start.start_action.path).toBe('/api/experimental/projects');
  });

  it('refuses the real payload for any other project identity', () => {
    expect(rejectionCode(() => productionWorkflowProjection(fixture, 'another-project',
      { mode: 'local', novel_id: 'another-project' }))).toBe('PRODUCTION_WORKFLOW_SCOPE_MISMATCH');
  });

  it('refuses a real payload with one unknown key added anywhere', () => {
    const tampered = { ...(fixture as Record<string, unknown>), unexpected_key: true };
    expect(rejectionCode(() => productionWorkflowProjection(tampered, PROJECT,
      { mode: 'local', novel_id: PROJECT }))).toBe('PRODUCTION_WORKFLOW_RESPONSE_INVALID');
  });
});
