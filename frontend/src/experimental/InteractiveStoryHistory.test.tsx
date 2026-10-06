// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { InteractiveStoryHistory } from './InteractiveStoryHistory';
import { interactiveStoryClient, type InteractiveStory } from './interactiveStoryClient';
import { experimentalClient } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('history restoration forwards an exact receipt and never reviews automatically', async () => {
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/history') ? { items: [{ version: 1, status: 'APPROVED', spec: { title: 'Old title' }, preview_digest: 'a'.repeat(64) }] } : { id: 'story', version: 3, status: 'DRAFT' })));
  vi.stubGlobal('fetch', fetch); const perform = vi.fn(async fn => { await fn(); });
  render(<InteractiveStoryHistory api={interactiveStoryClient(experimentalClient('n1', { sessionToken: '' }))} story={{ id: 'story', version: 2, status: 'DRAFT' } as InteractiveStory} blocked={false} perform={perform} />);
  expect(fetch).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' })); fireEvent.click(await screen.findByRole('button', { name: '恢复互动 v1 为待审草稿' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2)); const [, init] = fetch.mock.calls[1] as unknown as [string, RequestInit]; expect(JSON.parse(String(init.body))).toEqual({ expected_version: 2, restore_version: 1, preview_digest: 'a'.repeat(64) });
});
