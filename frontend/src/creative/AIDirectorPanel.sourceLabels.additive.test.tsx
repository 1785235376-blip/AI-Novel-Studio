// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient } from './client';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('preserves the original screenplay option label while identifying storyboard sources', async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ items: [] }) })); vi.stubGlobal('fetch', fetchMock);
  const screenplay: CreativeDocument = { ...newDocument('SCREENPLAY'), id: 'screenplay', title: '原剧本', version: 2, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, scenes: [{ ...newScene(1), id: 'scene' }] };
  const storyboard: CreativeDocument = { ...screenplay, id: 'storyboard', title: '原分镜', mode: 'STORYBOARD', shots: [{ ...newShot(1, 'scene'), id: 'shot' }] };
  render(<AIDirectorPanel client={creativeClient('project', { sessionToken: 'captured' })} documents={[screenplay, storyboard]} canMutate={false} onDocument={vi.fn()} onDenied={vi.fn()} />);
  expect(screen.getByRole('option', { name: '原剧本 · v2' })).toBeTruthy();
  expect(screen.getByRole('option', { name: '原分镜 · 分镜 · v2' })).toBeTruthy();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
});
