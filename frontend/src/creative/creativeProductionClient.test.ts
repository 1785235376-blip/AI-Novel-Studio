import { afterEach, describe, expect, it, vi } from 'vitest';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, type CreativeDocument, type VisualTarget } from './types';
afterEach(() => vi.unstubAllGlobals());
const source: CreativeDocument = { ...newDocument('DIRECTOR'), id: 'synthetic-director', title: 'Synthetic Director', source_independent: true, version: 7, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'synthetic', source_evidence: {} };
const target: VisualTarget = { style: 'quiet', atmosphere: 'calm', reference_works: ['synthetic reference'], color: 'neutral', rhythm: 'slow' };
describe('Original creative endpoints retain explicit production choices', () => {
  it('omits new derive policy by default and sends Director Notes policy only explicitly', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => source }); vi.stubGlobal('fetch', fetcher); const client = creativeClient('synthetic-project', { sessionToken: 'synthetic-unit-session' });
    await client.derive(source, 'STORYBOARD'); await client.derive(source, 'STORYBOARD', 'DIRECTOR_NOTES');
    expect(JSON.parse(String(fetcher.mock.calls[0][1].body))).toEqual({ expected_version: 7, mode: 'STORYBOARD' });
    expect(JSON.parse(String(fetcher.mock.calls[1][1].body))).toEqual({ expected_version: 7, mode: 'STORYBOARD', shot_policy: 'DIRECTOR_NOTES' });
  });
  it('passes authored visual goal and distinguishes preserved goal from explicit clear', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }); vi.stubGlobal('fetch', fetcher); const client = creativeClient('synthetic-project', { sessionToken: 'synthetic-unit-session' });
    await client.propose(source); await client.propose(source, target);
    const proposal = { id: 'synthetic-proposal', version: 2, output_digest: 'a'.repeat(64) } as DirectorProposal;
    await client.review(proposal, 'Reviewed goal', []); await client.review(proposal, 'Reviewed goal', [], null);
    expect(JSON.parse(String(fetcher.mock.calls[0][1].body)).visual_target).toBeUndefined(); expect(JSON.parse(String(fetcher.mock.calls[1][1].body)).visual_target).toEqual(target);
    expect(JSON.parse(String(fetcher.mock.calls[2][1].body)).visual_target).toBeUndefined(); expect(JSON.parse(String(fetcher.mock.calls[3][1].body)).visual_target).toBeNull();
  });
});
