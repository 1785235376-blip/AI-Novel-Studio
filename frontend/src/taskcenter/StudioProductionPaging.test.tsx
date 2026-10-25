// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLocalHostSession } from '../localHostSession';
import { cutoutJob, cutoutProject } from '../creative/studioCpuCutout.testFixtures';
import videoFixture from '../creative/fixtures/phase4.file-api-job-candidate.json';
import { studioProductionClient } from '../creative/studioProductionClient';
import { StudioProductionTasksPanel, type StudioProductionTasksProps } from './StudioProductionTasks';
import type { StudioProductionTask } from './studioProductionTask';

/** [HERMIA-FE-CONTRACTS G-AUD-1] 合同夹具，仅证明前端接缝。 */
const projectId = cutoutProject, base = `/api/projects/${projectId}/studio/production`;
const image = (id?: string) => ({ ...cutoutJob('AWAITING_REVIEW', 3), ...(id ? { id } : {}) }) as StudioProductionTask;
const video = () => ({ ...structuredClone(videoFixture), novel_id: projectId, id: 'video-job' }) as unknown as StudioProductionTask;
const response = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(value) });
let fetcher: ReturnType<typeof vi.fn>;
const client = () => studioProductionClient(projectId, { sessionToken: '', localHostToken: '' });
beforeEach(() => { useLocalHostSession.setState({ token: '', actorId: '' }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const props = (): StudioProductionTasksProps => ({ projectId, branchId: null, identity: 's', client: client(), active: true, denied: false,
  busy: false, isCurrent: () => true, read: (w: () => Promise<unknown>) => w(), onOpen: vi.fn(), onUnavailable: vi.fn() } as StudioProductionTasksProps);

describe('production listPage client', () => {
  it('sends only provided filters and parses the paged envelope', async () => {
    fetcher = vi.fn(async () => response({ items: [image()], total: 3, limit: 1, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED' }));
    vi.stubGlobal('fetch', fetcher);
    const page = await client().listPage({ owner: 'image', operation_id: 'm5.image.cutout', limit: 1, offset: 0 });
    expect(fetcher.mock.calls[0][0]).toBe(`${base}/jobs?owner=image&operation_id=m5.image.cutout&limit=1&offset=0`);
    expect(page.paging).toEqual({ total: 3, limit: 1, offset: 0, has_more: true });
    expect(page.items).toHaveLength(1);
  });
  it('falls back to the old unpaged envelope and rejects bad filters locally', async () => {
    fetcher = vi.fn(async () => response({ items: [image()], product_acceptance: 'LOCAL_REQUIRED' }));
    vi.stubGlobal('fetch', fetcher);
    expect((await client().listPage({ owner: 'image', limit: 50, offset: 0 })).paging).toBeNull();
    await expect(client().listPage({ owner: 'IMAGE' as never })).rejects.toThrow();
    await expect(client().listPage({ operation_id: 'm9.unknown' as never })).rejects.toThrow();
    await expect(client().listPage({ limit: 0 })).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe('production listPage contract guards [Vera fix1]', () => {
  const env = (o: Record<string, unknown>) => response({ items: [image()], total: 3, limit: 1, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED', ...o });
  it('[M7] rejects has_more that contradicts offset + limit < total', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => env({ has_more: false })));
    await expect(client().listPage({ owner: 'image', limit: 1, offset: 0 })).rejects.toThrow();
    vi.stubGlobal('fetch', vi.fn(async () => env({ total: 1, has_more: true })));
    await expect(client().listPage({ owner: 'image', limit: 1, offset: 0 })).rejects.toThrow();
  });
  it('[M8] rejects a partial paging envelope instead of treating it as unpaged', async () => {
    for (const drop of ['total', 'limit', 'offset', 'has_more']) {
      const value: Record<string, unknown> = { items: [image()], total: 3, limit: 1, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED' };
      delete value[drop];
      vi.stubGlobal('fetch', vi.fn(async () => response(value)));
      await expect(client().listPage({ owner: 'image', limit: 1, offset: 0 }), drop).rejects.toThrow();
    }
  });
  it('[P3] offset beyond total is a valid empty page; a non-empty one is not', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ items: [], total: 1, limit: 50, offset: 50, has_more: false, product_acceptance: 'LOCAL_REQUIRED' })));
    expect(await client().listPage({ owner: 'image', limit: 50, offset: 50 })).toEqual({ items: [], paging: { total: 1, limit: 50, offset: 50, has_more: false } });
    vi.stubGlobal('fetch', vi.fn(async () => response({ items: [image()], total: 1, limit: 50, offset: 50, has_more: false, product_acceptance: 'LOCAL_REQUIRED' })));
    await expect(client().listPage({ owner: 'image', limit: 50, offset: 50 })).rejects.toThrow();
  });
});

const many = (n: number, from = 0) => Array.from({ length: n }, (_, i) => image(`img-${from + i}`));
describe('production panel filters', () => {
  it('keeps the unpaged default read, then filters + loads more only on explicit choice', async () => {
    fetcher = vi.fn(async (url: string) => {
      if (url === `${base}/jobs`) return response({ items: [image(), video()] });
      if (url === `${base}/jobs?owner=image&limit=50&offset=0`) return response({ items: many(50), total: 51, limit: 50, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED' });
      if (url === `${base}/jobs?owner=image&limit=50&offset=50`) return response({ items: many(1, 50), total: 51, limit: 50, offset: 50, has_more: false, product_acceptance: 'LOCAL_REQUIRED' });
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<StudioProductionTasksPanel {...props()} />);
    await screen.findByRole('article', { name: 'Studio video video-job' });
    expect(fetcher.mock.calls[0][0]).toBe(`${base}/jobs`);
    fireEvent.change(screen.getByLabelText('任务类型'), { target: { value: 'image' } });
    await screen.findByText(/已加载 50 条/);
    expect(document.body.textContent).not.toMatch(/共 \d+ 条/);
    fireEvent.click(screen.getByRole('button', { name: '加载更多制作任务' }));
    await waitFor(() => expect(screen.getByText(/已加载 51 条/)).toBeTruthy());
    expect(screen.queryByRole('button', { name: '加载更多制作任务' })).toBeNull();
    expect(screen.queryByRole('article', { name: 'Studio video video-job' })).toBeNull();
  });
  it('[P3] list shrinking between load-mores is not an error and keeps the shown rows', async () => {
    fetcher = vi.fn(async (url: string) => {
      if (url === `${base}/jobs`) return response({ items: [image()] });
      if (url === `${base}/jobs?owner=image&limit=50&offset=0`) return response({ items: many(50), total: 51, limit: 50, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED' });
      if (url === `${base}/jobs?owner=image&limit=50&offset=50`) return response({ items: [], total: 49, limit: 50, offset: 50, has_more: false, product_acceptance: 'LOCAL_REQUIRED' });
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<StudioProductionTasksPanel {...props()} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('任务类型'), { target: { value: 'image' } });
    await screen.findByText(/已加载 50 条/);
    fireEvent.click(screen.getByRole('button', { name: '加载更多制作任务' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: '加载更多制作任务' })).toBeNull());
    expect(screen.getByText(/已加载 50 条/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/读取失败|回执不完整/);
    expect(screen.getAllByRole('article').length).toBe(50);
  });
});
