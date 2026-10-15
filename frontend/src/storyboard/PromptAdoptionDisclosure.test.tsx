// @vitest-environment jsdom
/**
 * R3-I — the mounted, collapsed-by-default adoption provenance disclosure.
 *
 * The point of the collapsed default is that the Storyboard workspace's existing read pattern and
 * its exact request counts are unchanged while the panel is closed. The transport mock here
 * deliberately ROUTES by URL so an adoption request can never be satisfied by a generic document
 * mock, and every case asserts on the request log rather than only on rendered text.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PromptAdoptionDisclosure } from './PromptAdoptionDisclosure';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

afterEach(() => { cleanup(); });

const ADOPTION_URL = '/api/projects/p1/studio/documents/doc-1/prompt-adoption';

function adoptionBody(rows: Record<string, unknown>[], documentId = 'doc-1') {
  return {
    contract: 'prompt-adoption/1', document_id: documentId, version: 2, digest: 'd'.repeat(64),
    adoptions: rows,
  };
}

const row = (over: Record<string, unknown> = {}) => ({
  request_id: 'req-1', shot_id: 'shot-1', family_id: 'fam-1', asset_id: 'asset-1',
  revision: 1, digest: 'a'.repeat(64), adopted_by: 'writer-1', adopted_at: 't',
  result_version: 2, still_applied: true, newer_revision_available: false,
  source_readable: true, source_state: 'KNOWN', source_redacted: false,
  ...over,
});

/** Routes by URL, and records every request so counts are assertable. */
function routedTransport(handler: (url: string, method: string) => unknown) {
  const log: { url: string; method: string }[] = [];
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET'): Promise<T> {
      log.push({ url, method });
      return handler(url, method) as T;
    },
  };
  return { transport, log };
}

describe('mounted adoption disclosure', () => {
  it('fetches NOTHING until the user expands it', () => {
    const { transport, log } = routedTransport(() => adoptionBody([row()]));
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                     transport={transport} enabled />);
    expect(log).toEqual([]);
    expect(screen.getByRole('button', { name: '查看 Prompt 采用来源' })).toBeTruthy();
  });

  it('expanding issues exactly one GET to the adoption projection route', async () => {
    const { transport, log } = routedTransport(url => {
      if (url === ADOPTION_URL) return adoptionBody([row()]);
      throw new Error(`unexpected request: ${url}`);
    });
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                     transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-1/)).toBeTruthy());
    expect(log).toEqual([{ url: ADOPTION_URL, method: 'GET' }]);
    // Read-only: no POST anywhere.
    expect(log.every(entry => entry.method === 'GET')).toBe(true);
  });

  it('shows an empty state when the shot has no adoption', async () => {
    const { transport } = routedTransport(() => adoptionBody([]));
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                     transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() =>
      expect(screen.getByText('此镜头尚未采用任何 Prompt 修订。')).toBeTruthy());
  });

  it('switching shot collapses the panel and never shows the previous shot source', async () => {
    const { transport } = routedTransport(url =>
      url === ADOPTION_URL ? adoptionBody([row(), row({ shot_id: 'shot-2', asset_id: 'asset-2',
        request_id: 'req-2' })]) : null);
    const { rerender } = render(
      <PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                               transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-1/)).toBeTruthy());

    rerender(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-2"
                                       transport={transport} enabled />);
    // The identity change collapses the disclosure, so the old source is gone immediately.
    await waitFor(() => expect(screen.queryByText(/asset-1/)).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-2/)).toBeTruthy());
    expect(screen.queryByText(/asset-1/)).toBeNull();
  });

  it('a document switch also collapses and re-reads', async () => {
    const { transport, log } = routedTransport(url =>
      url.includes('doc-2') ? adoptionBody([row({ asset_id: 'asset-doc2' })], 'doc-2')
        : adoptionBody([row({ asset_id: 'asset-doc1' })]));
    const { rerender } = render(
      <PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                               transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-doc1/)).toBeTruthy());

    rerender(<PromptAdoptionDisclosure projectId="p1" documentId="doc-2" shotId="shot-1"
                                       transport={transport} enabled />);
    await waitFor(() => expect(screen.queryByText(/asset-doc1/)).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-doc2/)).toBeTruthy());
    expect(log.every(entry => entry.method === 'GET')).toBe(true);
  });

  it('disabling the gate collapses and does not request anything further', async () => {
    const { transport, log } = routedTransport(() => adoptionBody([row()]));
    const { rerender } = render(
      <PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                               transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/asset-1/)).toBeTruthy());
    const before = log.length;

    rerender(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                       transport={transport} enabled={false} />);
    await waitFor(() => expect(screen.queryByText(/asset-1/)).toBeNull());
    // The button is disabled, so a revoked session cannot re-open the private provenance.
    const button = screen.getByRole('button', { name: '查看 Prompt 采用来源' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(log.length).toBe(before);
    expect(screen.queryByText(/asset-1/)).toBeNull();
  });

  it('with no shot selected nothing is requested and the control is disabled', () => {
    const { transport, log } = routedTransport(() => adoptionBody([row()]));
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId={null}
                                     transport={transport} enabled />);
    const button = screen.getByRole('button', { name: '查看 Prompt 采用来源' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(log).toEqual([]);
  });

  it('an UNKNOWN source is never presented as readable nor as having no newer version', async () => {
    const { transport } = routedTransport(() => adoptionBody([
      row({ source_state: 'UNKNOWN', source_readable: true, newer_revision_available: false,
            still_applied: true }),
    ]));
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                     transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByText(/无法确认来源状态/)).toBeTruthy());
    expect(screen.queryByText('可展示')).toBeNull();
    // `newer_revision_available: false` from an unconfirmed source must NOT read as "no newer".
    expect(screen.getByText('无法确认是否存在更新版本')).toBeTruthy();
    expect(screen.queryByText('无更新版本')).toBeNull();
  });

  it('a malformed adoptions field is refused rather than shown as empty', async () => {
    const { transport } = routedTransport(() => ({
      contract: 'prompt-adoption/1', document_id: 'doc-1', version: 2, digest: 'd'.repeat(64),
    }));
    render(<PromptAdoptionDisclosure projectId="p1" documentId="doc-1" shotId="shot-1"
                                     transport={transport} enabled />);
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.queryByText('此镜头尚未采用任何 Prompt 修订。')).toBeNull();
  });
});
