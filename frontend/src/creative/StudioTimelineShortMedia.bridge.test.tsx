// @vitest-environment jsdom
/** The File test supplies current real owner receipts; ordinary frontend runs use
 * an explicitly historical synthetic fixture. Both exercise the mounted handoff. */
import { readFileSync, writeFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StudioTimelineAssetHandoff, appendTimelineAsset } from './StudioTimelineAssetHandoff';
import type { StudioAsset } from './studioClient';
import type { ProductionJob } from './studioProductionClient';
import type { StudioTimelineDraft } from './studioTimelineTypes';
import capture from './fixtures/phase6.capture.editing-pipeline.json';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('hands the exact reviewed short media Asset into the original timeline draft for native File rendering', async () => {
  vi.stubGlobal('crypto', webcrypto);
  const path = process.env.STUDIO_SHORT_MEDIA_HANDOFF_CASE;
  const input = path ? JSON.parse(readFileSync(path, 'utf8')) : { asset: capture.audio_formal,
    receipt: capture.audio_receipts.approved, draft: { title: capture.created.title, timeline: capture.created.timeline } };
  const asset = input.asset as StudioAsset, draft = structuredClone(input.draft) as StudioTimelineDraft;
  draft.timeline.tracks.push({ id: 'short-media', kind: asset.kind === 'audio' ? 'AUDIO' : 'VIDEO', order: draft.timeline.tracks.length,
    gain_db: 0, muted: false, clips: [], ...(draft.timeline.schema_version === 2 ? { role: asset.kind === 'audio' ? 'DIALOGUE' as const : 'OVERLAY' as const } : {}) });
  const readAsset = vi.fn(async () => structuredClone(asset));
  const readJob = vi.fn(async () => structuredClone(input.receipt) as ProductionJob);
  const props = { request: { id: 'current-file-handoff', reference: { asset_id: asset.id, version: asset.version, digest: asset.sha256 }, readAsset },
    draft, canEdit: true, isCurrent: () => true, getRevision: () => 'current', readJob,
    onApply: (trackId: string, fresh: StudioAsset, range?: { in_ms: number; out_ms: number }) => {
      (appendTimelineAsset as (draft: StudioTimelineDraft, track: string, asset: StudioAsset, range?: unknown) => void)(draft, trackId, fresh, range); return true;
    } };
  render(<StudioTimelineAssetHandoff {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '核对交接素材版本' }));
  fireEvent.change(await screen.findByLabelText('交接目标轨道'), { target: { value: 'short-media' } });
  if (input.manual_range) {
    fireEvent.change(screen.getByLabelText('交接来源起点（毫秒）'), { target: { value: String(input.manual_range.in_ms) } });
    fireEvent.change(screen.getByLabelText('交接来源终点（毫秒）'), { target: { value: String(input.manual_range.out_ms) } });
  }
  fireEvent.click(screen.getByRole('button', { name: '明确加入原时间线草稿' }));
  await screen.findByText(/已把核对的原素材版本加入/);
  const clip = draft.timeline.tracks.at(-1)!.clips[0];
  expect(clip.source_snapshot).toMatchObject({ id: asset.id, version: asset.version, digest: asset.sha256, asset_kind: asset.kind });
  expect(readAsset).toHaveBeenCalledTimes(2);
  if (path) writeFileSync(input.output, JSON.stringify(draft));
});
