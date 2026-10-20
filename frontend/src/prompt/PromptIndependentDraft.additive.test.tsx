// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { PromptWorkspace } from './PromptWorkspace';
import { independentPromptContent, PromptIndependentDraft } from './PromptIndependentDraft';
import { promptEntry } from './promptContract';
import { newDraft, type Draft } from './promptDraft';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

const fixture = (name: string) => JSON.parse(readFileSync(resolve(process.cwd(), 'src/prompt/__fixtures__', name), 'utf8'));
const detail = () => promptEntry(fixture('detail.json'));
function loaded(): Draft {
  const d = detail();
  return { ...newDraft(d.familyId), familyId: d.familyId, baseAssetId: d.headAssetId, baseRevision: d.revision,
    content: { ...newDraft('x').content, text: d.body.value!, negativePrompt: 'negative', parameters: '{"steps":2}',
      modelReference: 'example', seed: '7', characterIds: ['character'], sceneIds: ['scene'], shotIds: ['shot'],
      referenceAssetIds: ['asset'], changeNote: 'old note', changeReason: 'old reason' } };
}
beforeEach(() => localStorage.clear());
afterEach(cleanup);
it('copies only visible content fields, without shared binding arrays or original identity', () => {
  const source = loaded(); const before = JSON.stringify(source);
  const copy = independentPromptContent(source, detail())!;
  expect(copy).toMatchObject({ text: source.content.text, negativePrompt: 'negative', parameters: '{"steps":2}',
    seed: '7', modelReference: 'example', characterIds: [], sceneIds: [], shotIds: [], referenceAssetIds: [],
    changeNote: '', changeReason: '' });
  copy.characterIds.push('new'); expect(JSON.stringify(source)).toBe(before);
  expect(Object.keys(copy)).toEqual(Object.keys(newDraft('new').content));
});
it.each(['DIRTY','SUBMITTING','UNKNOWN','CONFLICT','REJECTED'] as const)('refuses %s instead of discarding work', state => {
  expect(independentPromptContent({ ...loaded(), state }, detail())).toBeNull();
});
it('refuses masks, partial reads, stale baselines and unresolved request identities', () => {
  const d = detail();
  for (const damaged of [{ ...d, redacted: true }, { ...d, readComplete: false }, { ...d, historyComplete: false },
    { ...d, body: { ...d.body, truncated: true } }, { ...d, body: { ...d.body, digest: 'invalid' } },
    { ...d, body: { ...d.body, decodable: false } }, { ...d, revision: d.revision + 1 }]) {
    expect(independentPromptContent(loaded(), damaged)).toBeNull();
  }
  expect(independentPromptContent({ ...loaded(), requestId: 'pending' }, d)).toBeNull();
});
it('consumes one explicit click and refuses disabled access', () => {
  const onCopy = vi.fn(); const transport = { json: vi.fn() } as StudioGraphTransport;
  const draft = loaded(); const entry = detail();
  const view = render(<PromptIndependentDraft draft={draft} detail={entry} scopeKey="a" transport={transport} disabled={false} onCopy={onCopy} />);
  const button = screen.getByRole('button'); fireEvent.click(button); fireEvent.click(button);
  expect(onCopy).toHaveBeenCalledTimes(1);
  view.rerender(<PromptIndependentDraft draft={draft} detail={entry} scopeKey="b" transport={transport} disabled onCopy={onCopy} />);
  fireEvent.click(button); expect(onCopy).toHaveBeenCalledTimes(1);
});
it('actual workspace creates a separate dirty draft without POST; explicit save uses original create route', async () => {
  const calls: {url: string; method: string; body: unknown}[] = [];
  const transport: StudioGraphTransport = { async json<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
    calls.push({ url, method, body });
    if (method === 'POST') return { family_id: 'copy-family', asset_id: 'copy-asset', revision: 1, asset_version: 1,
      text_digest: 'd'.repeat(64), idempotent_replay: false, previous_asset_id: null, payload_digest: 'a'.repeat(64) } as T;
    if (url.endsWith('/prompts')) return fixture('library.json') as T;
    return fixture('detail.json') as T;
  } };
  render(<PromptWorkspace projectId="copy-project" actor="author-copy" transport={transport} mode="PROFESSIONAL" writable denied={false} />);
  fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
  await waitFor(() => expect((screen.getByRole('button', { name: '复制已载入版本为新草稿' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '复制已载入版本为新草稿' }));
  expect((screen.getByLabelText('正文') as HTMLTextAreaElement).value).toBe(detail().body.value);
  expect(calls.filter(c => c.method === 'POST')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: '保存为新 Prompt' }));
  await waitFor(() => expect(calls.filter(c => c.method === 'POST')).toHaveLength(1));
  const call = calls.find(c => c.method === 'POST')!;
  expect(call.url.endsWith('/prompts')).toBe(true);
  expect(call.body).toMatchObject({ origin: 'MANUAL', redacted: false, character_ids: [], scene_ids: [], shot_ids: [], reference_asset_ids: [], change_note: '', change_reason: '' });
  expect(call.body).not.toHaveProperty('expected_revision');
});
it('retires old callbacks and loaded detail across scope A to B to A, and after unmount', () => {
  const onCopy = vi.fn(); const transport = { json: vi.fn() } as StudioGraphTransport;
  const draft = loaded(); const entry = detail();
  const renderProps = (scopeKey: string, nextDetail = entry) => <PromptIndependentDraft draft={draft} detail={nextDetail} scopeKey={scopeKey} transport={transport} disabled={false} onCopy={onCopy} />;
  const view = render(renderProps('a'));
  const button = screen.getByRole('button');
  // Deliberately retain React's old callback to exercise queued/stale host delivery.
  const key = Object.keys(button).find(k => k.startsWith('__reactProps$'))!;
  const retained = (button as unknown as Record<string, {onClick: () => void}>)[key].onClick;
  view.rerender(renderProps('b'));
  retained(); fireEvent.click(screen.getByRole('button')); expect(onCopy).not.toHaveBeenCalled();
  view.rerender(renderProps('a'));
  retained(); fireEvent.click(screen.getByRole('button')); expect(onCopy).not.toHaveBeenCalled();
  view.rerender(renderProps('a', detail()));
  const freshButton = screen.getByRole('button');
  const freshKey = Object.keys(freshButton).find(k => k.startsWith('__reactProps$'))!;
  const freshHandler = (freshButton as unknown as Record<string, {onClick: () => void}>)[freshKey].onClick;
  view.unmount(); freshHandler(); expect(onCopy).not.toHaveBeenCalled();
});
