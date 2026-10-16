// @vitest-environment jsdom
// Component evidence only; actual File/PostgreSQL browser acceptance has its own live spec.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import type { CreativeDocument } from '../creative/types';
import { PromptAdoptionWritePanel } from './PromptAdoptionWritePanel';
import { StoryboardWorkspacePanel } from './StoryboardWorkspacePanel';
import { storyboardReceipt } from './storyboardWorkspaceFixtures.testFixture';
import type { PromptAdoptionRequest } from './promptAdoptionWriteClient';

afterEach(cleanup);
const fixture = (name: string) => JSON.parse(readFileSync(resolve(process.cwd(), 'src/prompt/__fixtures__', name), 'utf8'));
const target = { documentId: 'doc-1', shotId: 'shot-1', version: 2, digest: 'd'.repeat(64) };
const gate = async <T,>(work: () => Promise<T>) => work();
function harness(options: { enabled?: unknown; approved?: boolean; projectionVersion?: number;
  sourceBody?: Record<string, unknown>; post?: (request: PromptAdoptionRequest, attempt: number) => Promise<void>;
  bodyWait?: Promise<void>; readbackWrong?: boolean; replayNewer?: boolean } = {}) {
  const detail = fixture('detail.json'), body = { ...fixture('revision-2-body.json'), ...options.sourceBody };
  let approved = options.approved ?? true, written = false, attempts = 0;
  const calls: { url: string; method: string; body: unknown; key?: string }[] = [];
  let stored: PromptAdoptionRequest | undefined;
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET', value?: unknown, _signal?: AbortSignal, key?: string): Promise<T> {
      calls.push({ url, method, body: value, key });
      const entry = { ...detail, approved, review_status: approved ? 'APPROVED' : 'DRAFT' };
      if (method === 'GET' && url.endsWith('/prompt-adoption')) return {
        contract: 'prompt-adoption/1', document_id: 'doc-1',
        version: written ? (options.replayNewer ? 4 : 3) : options.projectionVersion ?? 2,
        digest: written ? 'e'.repeat(64) : target.digest, write_enabled: options.enabled ?? true,
        adoptions: written ? [{ ...stored, digest: stored!.expected_digest, result_version: 3,
          source_state: 'KNOWN', source_readable: true, source_redacted: false,
          still_applied: !options.replayNewer }] : [],
      } as T;
      if (method === 'GET' && url.endsWith('/prompts')) {
        return { ...fixture('library.json'), entries: [entry] } as T;
      }
      if (method === 'GET' && url.endsWith('/body')) { await options.bodyWait; return body as T; }
      if (method === 'GET' && url.includes('/prompts/')) return entry as T;
      if (method === 'POST' && url.includes('/approve?')) { approved = true; return {} as T; }
      if (method === 'POST' && url.endsWith('/prompt-adoption')) {
        stored = value as PromptAdoptionRequest; attempts++; written = true;
        await options.post?.(stored, attempts);
        return { committed: true, replayed: attempts > 1, document_id: 'doc-1', shot_id: 'shot-1',
          version: options.replayNewer ? 4 : 3, digest: 'e'.repeat(64), adoption: {
            contract: 'prompt-adoption/1', ...stored, document_id: 'doc-1', field: 'frame_prompt',
            digest: stored.expected_digest, digest_of: 'ORIGINAL_BYTES', target_version: 2,
            target_digest: target.digest, result_version: 3, source_binding_contract: 'prompt-adoption-bindings/1',
            source_bindings_verified: true,
          } } as T;
      }
      throw new Error(`unexpected ${method} ${url}`);
    },
  };
  const readDocument = vi.fn(async () => ({ id: 'doc-1', mode: 'STORYBOARD', version: options.replayNewer ? 4 : 3,
    shots: [{ id: 'shot-1', frame_prompt: options.readbackWrong ? 'other' : body.value }] } as CreativeDocument));
  const onCommitted = vi.fn(async () => {}), mutate = vi.fn(gate), read = vi.fn(gate);
  const props = { projectId: 'p1', identity: 'actor-a|branch-a', target, transport,
    enabled: true, writable: true, busy: false, isCurrent: () => true,
    read: read as typeof gate, mutate: mutate as typeof gate, readDocument, onCommitted };
  return { props, calls, detail, body, onCommitted, mutate, readDocument };
}
async function inspect() { fireEvent.click(screen.getByRole('button', { name: '核对 Prompt 采用条件' })); }
const bodyText = (h: ReturnType<typeof harness>) => (_text: string, element: Element | null) =>
  element?.tagName === 'PRE' && element.textContent === h.body.value;
async function selectSource(h: ReturnType<typeof harness>) {
  await inspect();
  const select = await screen.findByLabelText('Prompt 来源家族');
  await waitFor(() => expect(select.querySelectorAll('option')).toHaveLength(2));
  fireEvent.change(select, { target: { value: h.detail.family_id } });
  fireEvent.click(screen.getByRole('button', { name: '读取所选 Prompt 修订' }));
  await screen.findByText(bodyText(h));
}
const confirm = () => fireEvent.click(screen.getByRole('checkbox'));
const adopt = () => fireEvent.click(screen.getByRole('button', { name: '采用到当前镜头' }));

describe('Prompt adoption conditional write panel', () => {
  it.each([false, 'absent'])('makes no automatic request and keeps a closed/absent gate read-only: %s', async enabled => {
    const h = harness({ enabled });
    if (enabled === 'absent') {
      const original = h.props.transport.json;
      h.props.transport.json = async <T,>(...args: Parameters<StudioGraphTransport['json']>) => {
        const raw = await original<Record<string, unknown>>(...args); delete raw.write_enabled; return raw as T;
      };
    }
    render(<PromptAdoptionWritePanel {...h.props} />);
    expect(h.calls).toHaveLength(0); await inspect();
    await screen.findByText('当前环境未开放 Prompt 采用写入。');
    expect(h.calls).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '采用到当前镜头' })).toBeNull();
    expect(h.mutate).not.toHaveBeenCalled();
  });
  it('an enabled server does not grant a read-only host write controls', async () => {
    const h = harness(); render(<PromptAdoptionWritePanel {...h.props} writable={false} />);
    await inspect(); await screen.findByText('当前工作区仅可读取，无法审批或采用 Prompt。');
    expect(h.calls).toHaveLength(1); expect(screen.queryByRole('checkbox')).toBeNull();
    expect(h.mutate).not.toHaveBeenCalled();
  });
  it('refuses a stale target snapshot before reading any source', async () => {
    const h = harness({ projectionVersion: 7 }); render(<PromptAdoptionWritePanel {...h.props} />);
    await inspect(); await screen.findByText(/分镜版本已变化/);
    expect(h.calls).toHaveLength(1); expect(screen.queryByLabelText('Prompt 来源家族')).toBeNull();
  });
  it('refuses a foreign revision body instead of previewing or adopting it', async () => {
    const h = harness({ sourceBody: { asset_id: 'other' } }); render(<PromptAdoptionWritePanel {...h.props} />);
    await inspect(); const select = await screen.findByLabelText('Prompt 来源家族');
    await waitFor(() => expect(select.querySelectorAll('option')).toHaveLength(2));
    fireEvent.change(select, { target: { value: h.detail.family_id } });
    fireEvent.click(screen.getByRole('button', { name: '读取所选 Prompt 修订' }));
    await screen.findByText(/无法核实所选修订/); expect(screen.queryByText(bodyText(h))).toBeNull();
    expect(h.mutate).not.toHaveBeenCalled();
  });
  it('requires explicit approval, then re-reads metadata and original body', async () => {
    const h = harness({ approved: false }); render(<PromptAdoptionWritePanel {...h.props} />); await selectSource(h);
    expect((screen.getByRole('button', { name: '采用到当前镜头' }) as HTMLButtonElement).disabled).toBe(true);
    expect(h.mutate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '批准所选 Prompt 修订' }));
    await screen.findByText('已回读并确认所选 Prompt 修订获批。');
    const approval = h.calls.findIndex(row => row.url.includes('/approve?'));
    expect(h.calls.slice(approval + 1).map(row => row.method)).toEqual(['GET', 'GET']);
    expect(h.calls[approval].url).toContain(`/${h.detail.head_asset_id}/approve?expected_version=${h.detail.asset_version}`);
    expect(h.calls.filter(row => row.method === 'POST')).toHaveLength(1);
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
  });
  it('double clicks commit once, sends pins only, and waits for original readback plus host reload', async () => {
    let release!: () => void;
    const held = new Promise<void>(resolve => { release = resolve; });
    const h = harness({ post: async () => held });
    render(<PromptAdoptionWritePanel {...h.props} />); await selectSource(h); confirm(); adopt(); adopt();
    await waitFor(() => expect(h.calls.filter(row => row.method === 'POST')).toHaveLength(1));
    expect(h.onCommitted).not.toHaveBeenCalled(); release();
    await screen.findByText('已回读确认：Prompt 已采用到当前镜头，来源修订保持固定。');
    const post = h.calls.find(row => row.method === 'POST')!;
    expect(Object.keys(post.body as object).sort()).toEqual(['asset_id', 'expected_digest', 'expected_digest_target',
      'expected_version', 'family_id', 'request_id', 'revision', 'shot_id']);
    expect(post.body).toMatchObject({ asset_id: h.body.asset_id, expected_digest: h.body.digest,
      expected_version: 2, expected_digest_target: target.digest });
    expect(post.key).toBe((post.body as PromptAdoptionRequest).request_id);
    expect(h.readDocument).toHaveBeenCalledWith('doc-1'); expect(h.onCommitted).toHaveBeenCalledTimes(1);
    expect(h.onCommitted).toHaveBeenCalledWith(expect.objectContaining({ id: 'doc-1', version: 3,
      shots: [{ id: 'shot-1', frame_prompt: h.body.value }] }), 2);
    expect(h.mutate).toHaveBeenCalledTimes(1);
  });
  it('unknown outcomes retry the identical frozen request without rebase', async () => {
    const h = harness({ post: async (_request, attempt) => { if (attempt === 1) throw new TypeError('network lost'); } });
    render(<PromptAdoptionWritePanel {...h.props} />); await selectSource(h); confirm(); adopt();
    await screen.findByText(/采用结果未知/);
    expect((screen.getByLabelText('Prompt 来源家族') as HTMLSelectElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '重试原采用请求' }));
    await screen.findByText('已回读确认：Prompt 已采用到当前镜头，来源修订保持固定。');
    const posts = h.calls.filter(row => row.method === 'POST'); expect(posts).toHaveLength(2);
    expect(posts[0]).toEqual(posts[1]);
  });
  it('a committed response with different current shot text never claims a successful current adoption', async () => {
    const h = harness({ readbackWrong: true }); render(<PromptAdoptionWritePanel {...h.props} />);
    await selectSource(h); confirm(); adopt(); await screen.findByText(/服务端已确认提交，但当前镜头与来源回读尚未完成/);
    expect(h.onCommitted).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '重新核对采用结果' }));
    await waitFor(() => expect(h.readDocument).toHaveBeenCalledTimes(2));
    expect(h.calls.filter(row => row.method === 'POST')).toHaveLength(1);
  });
  it('a newer host version rejects the readback without success or a second POST on recheck', async () => {
    const h = harness();
    const onCommitted = vi.fn(async () => { throw new Error('newer clean host version'); });
    render(<PromptAdoptionWritePanel {...h.props} onCommitted={onCommitted} />);
    await selectSource(h); confirm(); adopt();
    await screen.findByText(/服务端已确认提交，但当前镜头与来源回读尚未完成/);
    expect(onCommitted).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('已回读确认：Prompt 已采用到当前镜头，来源修订保持固定。')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重新核对采用结果' }));
    await waitFor(() => expect(onCommitted).toHaveBeenCalledTimes(2));
    expect(h.calls.filter(row => row.method === 'POST')).toHaveLength(1);
    expect(h.readDocument).toHaveBeenCalledTimes(2);
  });
  it('synchronously clears preview and consent when the target version changes', async () => {
    const h = harness(); const view = render(<PromptAdoptionWritePanel {...h.props} />);
    await selectSource(h); confirm();
    view.rerender(<PromptAdoptionWritePanel {...h.props} target={{ ...target, version: 3, digest: 'e'.repeat(64) }} />);
    expect(screen.queryByText(bodyText(h))).toBeNull(); expect(screen.queryByRole('checkbox')).toBeNull();
    expect(h.calls.filter(row => row.method === 'POST')).toHaveLength(0);
  });
  it('an old actor/branch body response cannot populate the new session', async () => {
    let release!: () => void; const wait = new Promise<void>(resolve => { release = resolve; });
    const h = harness({ bodyWait: wait }); const view = render(<PromptAdoptionWritePanel {...h.props} />);
    await inspect(); const select = await screen.findByLabelText('Prompt 来源家族');
    await waitFor(() => expect(select.querySelectorAll('option')).toHaveLength(2));
    fireEvent.change(select, { target: { value: h.detail.family_id } });
    fireEvent.click(screen.getByRole('button', { name: '读取所选 Prompt 修订' }));
    await waitFor(() => expect(h.calls.some(row => row.url.endsWith('/body'))).toBe(true));
    view.rerender(<PromptAdoptionWritePanel {...h.props} identity="actor-b|branch-b" />);
    release(); await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByText(bodyText(h))).toBeNull(); expect(screen.queryByRole('checkbox')).toBeNull();
  });
  it('permission refusal hides source and never asserts that no write occurred', async () => {
    const h = harness({ post: async () => { throw new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: 'private' }); } });
    const onUnavailable = vi.fn(); render(<PromptAdoptionWritePanel {...h.props} onUnavailable={onUnavailable} />);
    await selectSource(h); confirm(); adopt(); await screen.findByText(/采用结果需由原记录核对/);
    expect(screen.queryByText(bodyText(h))).toBeNull(); expect(onUnavailable).toHaveBeenCalledTimes(1);
    expect(h.onCommitted).not.toHaveBeenCalled(); expect(screen.queryByText('private')).toBeNull();
  });
  it('the mounted Storyboard owner reloads and closes old provenance after verified commit', async () => {
    const h = harness(); const original = h.props.transport.json;
    let reads = 0;
    h.props.transport.json = async <T,>(...args: Parameters<StudioGraphTransport['json']>): Promise<T> => {
      const [url] = args;
      if (url.endsWith('/storyboard')) {
        reads++;
        const receipt = storyboardReceipt();
        receipt.document_snapshot = { id: 'doc-1', version: reads > 1 ? 3 : 2,
          digest: reads > 1 ? 'e'.repeat(64) : target.digest };
        receipt.director_sources = [];
        receipt.shots = [receipt.shots[0]];
        receipt.shots[0].shot_id = 'shot-1'; receipt.shots[0].shot.id = 'shot-1';
        receipt.shots[0].shot.continuity = null;
        if (reads > 1) receipt.shots[0].shot.frame_prompt = h.body.value;
        return receipt as T;
      }
      if (url === '/api/novels/p1/experimental/creative/documents/doc-1') return await h.props.readDocument() as T;
      return original<T>(...args);
    };
    render(<StoryboardWorkspacePanel projectId="p1" identity="p1|doc-1" transport={h.props.transport}
      active denied={false} busy={false} writable isCurrent={() => true} read={gate} mutate={gate} />);
    await waitFor(() => expect(reads).toBe(1));
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await screen.findByText('此镜头尚未采用任何 Prompt 修订。');
    await selectSource(h); confirm(); adopt();
    await screen.findByText('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。');
    expect(reads).toBe(2);
    expect(screen.queryByText('此镜头尚未采用任何 Prompt 修订。')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '查看 Prompt 采用来源' }));
    await screen.findByText('仍然生效');
    expect(screen.getByText(`${h.body.asset_id} · r${h.body.revision}`)).toBeTruthy();
  });
});
