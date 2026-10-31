// @vitest-environment jsdom
// Preserve the lowercase invalid-format fixture independently of the protected uppercase MP3 case.
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient, type MediaCommand } from './studioProductionClient';
import capture from './fixtures/phase6.capture.editing-pipeline.json';

let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  useLocalHostSession.setState({ token: 'synthetic-flac-format-variant-unit', actorId: '' });
  fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('rejects the lowercase mp3 fixture without network', async () => {
  const input = structuredClone(capture.audio_receipts.command) as MediaCommand;
  input.parameters.output_format = 'mp3';
  await expect(studioProductionClient(capture.audio_receipts.approved.novel_id, { sessionToken: '' }).preview(input)).rejects.toBeTruthy();
  expect(fetcher).not.toHaveBeenCalled();
});
