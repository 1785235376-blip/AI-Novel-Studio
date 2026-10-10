// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SharedUniversePanel } from './SharedUniversePanel';
import { experimentalClient } from './api';
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const catalog = { records: [{ key: 'locations:port', kind: 'locations', title: 'Port', source_digest: 'a'.repeat(64), references: [] }], projects: [{ id: 'sequel', title: 'Sequel' }], truncated: false };
const snapshot = { id: 'snap', version: 1, status: 'IMMUTABLE', snapshot_revision: 1, snapshot_digest: 'b'.repeat(64), universe_key: 'shared', title: 'Frozen world', content_withheld: false, source_changes: [], records: { 'locations:port': { name: 'Port' } } };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('source preview has no writes; separate explicit pin approval keeps exact snapshot and CAS', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return response(catalog);
    if (url.endsWith('/snapshots')) return response({ items: [snapshot] });
    if (url.endsWith('/pin-preview')) return response({ ...JSON.parse(String(init.body)), preview_digest: 'c'.repeat(64), target_title: 'Sequel', snapshot_revision: 1, previous_snapshot_id: null, source_changes: [] });
    return response({ items: [] });
  }); vi.stubGlobal('fetch', fetch); render(<SharedUniversePanel client={experimentalClient('original', { sessionToken: 'host' })} />);
  await screen.findByText('Frozen world · shared'); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('要固定的世界观快照'), { target: { value: 'snap' } }); fireEvent.change(screen.getByLabelText('系列作品'), { target: { value: 'sequel' } });
  fireEvent.click(screen.getByRole('button', { name: '比较作品固定版本' })); const confirm = await screen.findByRole('button', { name: '确认固定此作品世界观版本' }); expect((confirm as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我确认仅为此作品固定这个世界观版本')); fireEvent.click(confirm);
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/pins') && init.method === 'POST')).toBe(true));
  const [, init] = fetch.mock.calls.find(([url, init]) => url.endsWith('/pins') && init.method === 'POST')!;
  expect(JSON.parse(String(init.body))).toEqual({ snapshot_id: 'snap', target_project_id: 'sequel', role: 'SEQUEL', expected_version: 0, preview_digest: 'c'.repeat(64), confirmed: true });
});
it('withholds inaccessible snapshot content and disables snapshot creation without selection', async () => {
  const fetch = vi.fn(async (url: string) => url.endsWith('/catalog') ? response(catalog) : url.endsWith('/incoming') ? response({ items: [], truncated: false }) : response({ items: [{ id: 'snap', version: 1, status: 'IMMUTABLE', snapshot_revision: 1, content_withheld: true }] }));
  vi.stubGlobal('fetch', fetch); render(<SharedUniversePanel client={experimentalClient('original', { sessionToken: '' })} />);
  await screen.findByText(/来源权限或隐私不可用/); expect(screen.queryByText('Frozen world')).toBeNull(); expect((screen.getByRole('button', { name: '预览不可变世界观快照' }) as HTMLButtonElement).disabled).toBe(true);
});
it('refresh revocation hides cached snapshot and work titles while retaining only actionable errors', async () => {
  let denied = false;
  const fetch = vi.fn(async (url: string) => denied ? response({ detail: { code: 'FORBIDDEN' } }, 403) : response(url.endsWith('/catalog') ? catalog : url.endsWith('/snapshots') ? { items: [snapshot] } : { items: [] }));
  vi.stubGlobal('fetch', fetch); render(<SharedUniversePanel client={experimentalClient('original', { sessionToken: 'host' })} />);
  await screen.findByText('Frozen world · shared'); denied = true; fireEvent.click(screen.getByRole('button', { name: '刷新世界观快照与固定版本' }));
  await waitFor(() => expect(screen.queryByText('Frozen world · shared')).toBeNull()); await screen.findAllByText(/FORBIDDEN/);
  expect(screen.queryByRole('option', { name: /Frozen world/ })).toBeNull();
});
