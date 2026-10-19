// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { AssetBrowserPanel } from './AssetBrowserPanel';
import { AssetDetailPanel } from './AssetDetailPanel';
import { assetBrowserAsset, assetBrowserList } from './assetBrowserContract';
import { assetRow, FIXTURE_PROJECT, provenance } from './assetBrowserFixtures';
import { assetBrowserRows } from './assetBrowserOps';
import { ASSET_BROWSER_ERROR_CODES } from './assetBrowserTypes';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const metadata = (producer: unknown) => assetRow({ filename: 'source.txt', kind: 'file', media_type: 'text/plain',
  provenance: provenance({ origin: 'GENERATED_RESULT', producer }) });
const decode = (producer: unknown) => assetBrowserAsset(metadata(producer), FIXTURE_PROJECT);

it('shows provider and model only from the existing on-demand owner detail, with no extra read or mutation', async () => {
  const calls: string[] = [], mutate = vi.fn(), network = vi.fn();
  vi.stubGlobal('fetch', network);
  const asset = metadata({ declared_by: 'actor-not-for-display', provider_id: 'recorded-provider', model_id: 'recorded-model' });
  render(<AssetBrowserPanel projectId={FIXTURE_PROJECT} identity="producer" active denied={false} busy={false}
    isCurrent={() => true} read={work => work()} mutate={mutate} transport={{ json: async <T,>(url: string) => {
      calls.push(url);
      return (url.endsWith('/studio/assets') ? { items: [asset] } : asset) as T;
    } }}/>) ;
  fireEvent.click(await screen.findByRole('button', { name: '选择素材 source.txt' }));
  const source = await screen.findByRole('region', { name: '来源与许可' });
  await waitFor(() => expect(within(source).getByText('recorded-provider')).toBeTruthy());
  expect(within(source).getByText('recorded-model')).toBeTruthy();
  expect(source.textContent).not.toContain('actor-not-for-display');
  expect(calls).toEqual([`/api/projects/${FIXTURE_PROJECT}/studio/assets`, `/api/projects/${FIXTURE_PROJECT}/studio/assets/asset-a`]);
  expect(mutate).not.toHaveBeenCalled(); expect(network).not.toHaveBeenCalled();
});

it('keeps omitted, null and empty producer fields unverified without guessing from generation metadata', () => {
  for (const producer of [undefined, null, {}, { provider_id: null, model_id: null }, { provider_id: '', model_id: ' ' }]) {
    const detail = assetBrowserAsset({ ...metadata(producer), provenance: provenance({ producer,
      generation: { model_id: 'not-a-producer-model' } }) }, FIXTURE_PROJECT);
    const row = assetBrowserRows([detail], Date.now())[0];
    const view = render(<AssetDetailPanel row={row} detail={detail} detailState="READY" referencesUnverified busy={false}
      onReadDetail={vi.fn()} onLoadReferences={vi.fn()} onCompare={vi.fn()} onSendTo={vi.fn()} onDeleteIntent={vi.fn()}/>);
    const source = screen.getByRole('region', { name: '来源与许可' });
    for (const label of ['提供方记录', '模型记录']) {
      expect(within(source).getByText(label).nextElementSibling?.textContent).toBe('未核实');
    }
    expect(source.textContent).not.toContain('not-a-producer-model');
    view.unmount();
  }
});

it('retains only provider/model fields and rejects malformed or unbounded producer disclosures', () => {
  expect(decode({ declared_by: 'private-actor', provider_id: 'provider', model_id: 'model' }).provenance?.producer)
    .toEqual({ provider_id: 'provider', model_id: 'model' });
  for (const producer of [[], 'invalid', { provider_id: 7 }, { model_id: 'bad\nmodel' },
    { provider_id: 'x'.repeat(241) }, { provider_id: 'provider', credential: 'PRIVATE_SENTINEL' }]) {
    try { decode(producer); throw new Error('Expected invalid producer rejection'); }
    catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).problem.code).toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
      expect((error as ApiError).message).not.toContain('PRIVATE_SENTINEL');
    }
  }
  expect(() => assetBrowserList({ items: [metadata({ provider_id: 7 })] }, FIXTURE_PROJECT))
    .toThrow(expect.objectContaining({ problem: expect.objectContaining({ code: ASSET_BROWSER_ERROR_CODES.listInvalid }) }));
});

it('replaces the displayed record when the selected detail changes, preserving unknowns', () => {
  const detail = decode({ provider_id: 'old-provider', model_id: 'old-model' });
  const props = { row: assetBrowserRows([detail], Date.now())[0], detailState: 'READY' as const,
    referencesUnverified: true, busy: false, onReadDetail: vi.fn(), onLoadReferences: vi.fn(),
    onCompare: vi.fn(), onSendTo: vi.fn(), onDeleteIntent: vi.fn() };
  const view = render(<AssetDetailPanel {...props} detail={detail}/>);
  expect(screen.getByText('old-provider')).toBeTruthy();
  view.rerender(<AssetDetailPanel {...props} detail={decode(null)}/>);
  expect(screen.queryByText('old-provider')).toBeNull(); expect(screen.queryByText('old-model')).toBeNull();
  expect(screen.getByText('模型记录').nextElementSibling?.textContent).toBe('未核实');
});
