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

describe('production panel filters', () => {
  it('keeps the unpaged default read, then filters + loads more only on explicit choice', async () => {
    fetcher = vi.fn(async (url: string) => {
      if (url === `${base}/jobs`) return response({ items: [image(), video()] });
      if (url === `${base}/jobs?owner=image&limit=50&offset=0`) return response({ items: [image('img-a')], total: 2, limit: 50, offset: 0, has_more: true, product_acceptance: 'LOCAL_REQUIRED' });
      if (url === `${base}/jobs?owner=image&limit=50&offset=1`) return response({ items: [image('img-b')], total: 2, limit: 50, offset: 1, has_more: false, product_acceptance: 'LOCAL_REQUIRED' });
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<StudioProductionTasksPanel {...props()} />);
    await screen.findByRole('article', { name: 'Studio video video-job' });
    expect(fetcher.mock.calls[0][0]).toBe(`${base}/jobs`);
    fireEvent.change(screen.getByLabelText('任务类型'), { target: { value: 'image' } });
    await screen.findByText(/已加载 1 条/);
    expect(document.body.textContent).not.toMatch(/共 \d+ 条/);
    fireEvent.click(screen.getByRole('button', { name: '加载更多制作任务' }));
    await waitFor(() => expect(screen.getByText(/已加载 2 条/)).toBeTruthy());
    expect(screen.queryByRole('button', { name: '加载更多制作任务' })).toBeNull();
    expect(screen.queryByRole('article', { name: 'Studio video video-job' })).toBeNull();
  });
});
