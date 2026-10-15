// @vitest-environment jsdom
/**
 * R3-I — read-only Prompt adoption panel.
 *
 * Focused on the properties that actually break in production: stale async responses after a
 * shot/document/project switch, an unconfirmable source never looking readable or applied, and
 * a permission failure clearing private provenance rather than leaving it on screen.
 */
import { StrictMode } from 'react';

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PromptAdoptionPanel } from './PromptAdoptionPanel';
import { createPromptAdoptionClient, decodeAdoptionProjection } from './promptAdoptionClient';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const projection = (over: Record<string, unknown> = {}, row: Record<string, unknown> = {}) => ({
  contract: 'prompt-adoption/1',
  document_id: 'doc-1',
  version: 2,
  digest: 'd'.repeat(64),
  adoptions: [{
    request_id: 'req-1', shot_id: 'shot-1', family_id: 'fam-1', asset_id: 'asset-1',
    revision: 1, digest: 'a'.repeat(64), adopted_by: 'writer-1',
    adopted_at: '2026-10-16T00:00:00Z', result_version: 2,
    still_applied: true, newer_revision_available: false, source_readable: true,
    source_state: 'KNOWN', source_redacted: false,
    ...row,
  }],
  ...over,
});

function transportOf(handler: (url: string) => unknown): StudioGraphTransport {
  return { async json<T>(url: string): Promise<T> { return handler(url) as T; } };
}

describe('read-only adoption panel', () => {
  it('renders the pinned source and its state for the selected shot', async () => {
    const transport = transportOf(() => projection());
    render(<PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-1"
                                transport={transport} />);
    await waitFor(() => expect(screen.getByText(/asset-1 · r1/)).toBeTruthy());
    expect(screen.getByText('fam-1')).toBeTruthy();
    expect(screen.getByText('仍然生效')).toBeTruthy();
    expect(screen.getByText('可展示')).toBeTruthy();
    expect(screen.getByText('无更新版本')).toBeTruthy();
    // Read-only: no adoption affordance is offered while the production switch is closed.
    expect(screen.queryByRole('button', { name: /采用/ })).toBeNull();
  });

  it('shows an empty state when the shot has no adoption', async () => {
    const transport = transportOf(() => projection({ adoptions: [] }));
    render(<PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-1"
                                transport={transport} />);
    await waitFor(() => expect(screen.getByText('此镜头尚未采用任何 Prompt 修订。')).toBeTruthy());
  });

  it('an unconfirmable source never reads as applied or readable', () => {
    const decoded = decodeAdoptionProjection(projection({}, {
      still_applied: undefined, source_readable: undefined, source_state: undefined,
      newer_revision_available: undefined,
    }));
    expect(decoded.adoptions[0].stillApplied).toBe(false);
    expect(decoded.adoptions[0].sourceReadable).toBe(false);
    expect(decoded.adoptions[0].sourceState).toBe('UNKNOWN');
  });

  it('a stale response cannot overwrite a newer selection', async () => {
    // A mutable holder: assigning through a plain `let` narrows to never under strict TS.
    const gate: { release?: () => void } = {};
    const first = new Promise<void>(resolve => { gate.release = resolve; });
    let call = 0;
    const transport: StudioGraphTransport = {
      async json<T>(url: string): Promise<T> {
        call += 1;
        if (call === 1) {
          await first;
          return projection({}, { shot_id: 'shot-1', asset_id: 'OLD-asset' }) as T;
        }
        return projection({}, { shot_id: 'shot-2', asset_id: 'NEW-asset' }) as T;
      },
    };
    const { rerender } = render(
      <StrictMode>
        <PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-1" transport={transport} />
      </StrictMode>);
    // Switch the selection before the first read resolves.
    rerender(
      <StrictMode>
        <PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-2" transport={transport} />
      </StrictMode>);
    await waitFor(() => expect(screen.getByText(/NEW-asset/)).toBeTruthy());
    gate.release?.();
    await new Promise(resolve => setTimeout(resolve, 30));
    expect(screen.queryByText(/OLD-asset/)).toBeNull();
    expect(screen.getByText(/NEW-asset/)).toBeTruthy();
  });

  it('a permission failure clears previously shown provenance', async () => {
    let call = 0;
    const transport: StudioGraphTransport = {
      async json<T>(): Promise<T> {
        call += 1;
        if (call === 1) return projection() as T;
        throw new Error('PROJECT_SCOPE_FORBIDDEN');
      },
    };
    const { rerender } = render(
      <PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-1" transport={transport} />);
    await waitFor(() => expect(screen.getByText(/asset-1/)).toBeTruthy());
    rerender(
      <PromptAdoptionPanel projectId="p1" documentId="doc-1" shotId="shot-3" transport={transport} />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.queryByText(/asset-1/)).toBeNull();
  });

  it('the client is read-only and targets the official projection route', async () => {
    const seen: string[] = [];
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method?: string): Promise<T> {
        seen.push(`${method ?? 'GET'} ${url}`);
        return projection() as T;
      },
    };
    const client = createPromptAdoptionClient('proj 1', transport);
    const found = await client.forShot('doc/1', 'shot-1');
    expect(found?.assetId).toBe('asset-1');
    expect(seen).toEqual(['GET /api/projects/proj%201/studio/documents/doc%2F1/prompt-adoption']);
  });

  it('rejects a foreign contract instead of guessing', () => {
    expect(() => decodeAdoptionProjection(projection({ contract: 'something-else/9' })))
      .toThrow(/契约/);
  });
});
