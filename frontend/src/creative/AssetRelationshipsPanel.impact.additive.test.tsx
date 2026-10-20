// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import type { StudioAsset, StudioReference, StudioReferenceKind, StudioRelationshipGraph } from './studioClient';

const digest = 'a'.repeat(64);
const source = (): StudioAsset => ({ id: 'source', novel_id: 'project', branch_id: null, filename: 'source.png', kind: 'image', media_type: 'image/png', size: 3, sha256: digest, version: 4, created_at: '', updated_at: '', relationships: [] });
const reference = (kind: StudioReferenceKind = 'ASSET', patch: Partial<StudioReference> = {}): StudioReference => ({ kind, id: 'target', version: 2, digest, label: '可访问目标', deleted: false, ...patch });

function setup(options: { asset?: StudioAsset; canMutate?: boolean; canReview?: boolean; blocked?: boolean; current?: () => boolean } = {}) {
  const client = { references: vi.fn(async (kind: StudioReferenceKind) => ({ items: [reference(kind)], read_only: true as const, content_copied: false as const })), relationships: vi.fn<() => Promise<StudioRelationshipGraph>>(), addRelationship: vi.fn(async () => source()), removeRelationship: vi.fn(async () => source()) };
  const onDirtyChange = vi.fn(), mutate = vi.fn(async (operation: () => Promise<StudioAsset>) => operation());
  const props = { asset: options.asset || source(), client, canMutate: options.canMutate ?? true, canReview: options.canReview ?? false, blocked: options.blocked ?? false, busy: false, isCurrent: options.current || (() => true), read: async <T,>(operation: () => Promise<T>) => operation(), mutate, onDirtyChange };
  const result = render(<AssetRelationshipsPanel {...props} />);
  return { ...result, props, client, onDirtyChange, mutate };
}
async function open() { fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); await screen.findByRole('option', { name: '可访问目标 · v2' }); }

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('optional descriptive asset relationships', () => {
  it('shows only recorded direct incoming relationships and explicitly limits impact coverage', async () => {
    const { client } = setup();
    client.relationships.mockResolvedValue({ graph_kind: 'ASSET_RELATIONSHIPS', nodes: [
      { id: 'other', kind: 'ASSET', asset_kind: 'image', label: '使用此图的素材', version: 3, digest },
    ], edges: [{ id: 'incoming', from: 'other', owner: 'ASSET_LINEAGE', type: 'DERIVED_FROM', state: 'CURRENT', target: reference('ASSET', { id: 'source' }) }], executable: false, knowledge_graph: false, automatic_regeneration: false });
    await open(); fireEvent.click(screen.getByRole('button', { name: '读取项目关联概览' }));
    const impact = await screen.findByRole('region', { name: '当前资产引用影响' });
    expect(impact.textContent).toContain('使用此图的素材'); expect(screen.getByText(/不是完整影响清单/)).toBeTruthy();
    expect(client.addRelationship).not.toHaveBeenCalled(); expect(client.removeRelationship).not.toHaveBeenCalled();
  });

});
