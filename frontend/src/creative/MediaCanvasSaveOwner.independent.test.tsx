// @vitest-environment jsdom
// Independent Save-owner QA with the real Studio HTTP client and synthetic
// valid CanvasView protocol records. This does not verify formal File origins,
// inference, media bytes, server review or browser rendering.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import type {ComponentProps} from 'react';
import {MediaCanvasViewPanel} from './MediaCanvasViewPanel';
import {studioClient} from './studioClient';
import {mediaCanvasDraftKey} from './mediaCanvasLocalDraft';
import type {StudioGraphDraftOwner} from './studioGraphLocalDraft';
import type {CanvasDefinition, CanvasViewRecord} from './studioCanvasViewClient';

const project = 'save-owner-project', canvasId = 'save-owner-view', baseDigest = 'a'.repeat(64);
const context = {sessionToken: 'fixture-save-captured-token'};
const owner: StudioGraphDraftOwner = {projectId: project, incarnation: 'file:save_owner_original', actorId: 'save-owner-author',
  actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: ''};
const pin = {asset_id: 'fixture-protocol-asset', version: 7, digest: 'f'.repeat(64), kind: 'image' as const};
const definition = (): CanvasDefinition => ({schema_version: 1, title: 'Original stored canvas',
  cards: [{id: 'Card_Original', position: {x: 23, y: 47}, asset: {...pin}}], viewport: {x: 8, y: 16, zoom: 1}});
function record(value = definition(), version = 3): CanvasViewRecord {
  return {project_id: project, scope: {mode: 'local', novel_id: project}, id: canvasId, version,
    definition: structuredClone(value), definition_digest: version === 3 ? baseDigest : 'c'.repeat(64),
    created_at: '2026-10-24T15:00:00Z', updated_at: '2026-10-24T15:01:00Z',
    reference_states: value.cards.map(card => ({card_id: card.id, state: 'CURRENT_METADATA', filename: 'protocol-reference.png'})),
    execution_authority: false, binary_content_verified: false, capacity: {history_used: version - 1, record_bytes: 2048}};
}
const json = (body: unknown, code = 200) => new Response(JSON.stringify(body), {status: code, headers: {'Content-Type': 'application/json'}});
const basePath = `/api/projects/${project}/studio/canvas-views`, viewPath = `${basePath}/${canvasId}`;
type Props = ComponentProps<typeof MediaCanvasViewPanel>;
function setup(options: {draftOwner?: StudioGraphDraftOwner | null; put?: (body: Record<string, unknown>) => Promise<Response>} = {}) {
  const state = {saved: record()};
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if (url === basePath && (!init.method || init.method === 'GET')) {
      const row = state.saved;
      return json({items: [{id: row.id, version: row.version, title: row.definition.title, card_count: row.definition.cards.length,
        definition_digest: row.definition_digest, created_at: row.created_at, updated_at: row.updated_at}], execution_authority: false});
    }
    if (url === viewPath && (!init.method || init.method === 'GET')) return json(state.saved);
    if (url === viewPath && init.method === 'PUT') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      if (options.put) return options.put(body);
      state.saved = record(body.definition as CanvasDefinition, state.saved.version + 1); return json(state.saved);
    }
    throw new Error(`Save-owner fixture forbids other operations: ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const props: Props = {active: true, denied: false, identity: 'save-owner-scope', client: studioClient(project, context), canMutate: true,
    busy: false, externalDirty: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn(),
    ...(options.draftOwner === null ? {} : {draftOwner: options.draftOwner ?? owner})};
  return {state, fetcher, props};
}
const puts = (fetcher: ReturnType<typeof vi.fn>) => fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT');
async function openSaved(title = 'Original stored canvas', version = 3) {
  fireEvent.click(screen.getByRole('button', {name: '读取已存画布'}));
  fireEvent.click(await screen.findByRole('button', {name: `${title} · v${version} · 1 张`}));
  await screen.findByDisplayValue(title);
}
function editTitle(value = 'Explicit unsaved title') {fireEvent.change(screen.getByLabelText('画布标题'), {target: {value}});}
function retainedSave() {
  const element = screen.getByRole('button', {name: '保存媒体画布'});
  const key = Object.keys(element).find(name => name.startsWith('__reactProps$'));
  const callback = key && (element as unknown as Record<string, {onClick?: () => void}>)[key]?.onClick;
  if (typeof callback !== 'function') throw new Error('Expected the actual captured Save callback');
  // A DOM click after rerender would invoke the new callback, so retain the old
  // production closure explicitly, matching the repository's owner tests.
  return callback;
}
beforeEach(() => {localStorage.clear(); vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);});
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals();});

describe('independent media-canvas Save owner boundary', () => {
  it('distinguishes read, unsaved and saved states, sends the exact strong Save fence and cold-reopens the exact card pin', async () => {
    const {state, fetcher, props} = setup(); let mounted = render(<MediaCanvasViewPanel {...props}/>); await openSaved();
    expect(screen.getByText('已读取持久化版本')).toBeTruthy(); expect(screen.queryByText('已保存媒体画布')).toBeNull();
    editTitle(); expect(screen.getByText('尚未保存')).toBeTruthy(); expect(puts(fetcher)).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'})); await screen.findByText('已保存媒体画布');
    expect(puts(fetcher)).toHaveLength(1);
    expect(JSON.parse(String(puts(fetcher)[0][1]!.body))).toEqual({expected_version: 3,
      expected_incarnation: owner.incarnation, expected_definition_digest: baseDigest,
      definition: {...definition(), title: 'Explicit unsaved title'}});
    expect(new Headers(puts(fetcher)[0][1]!.headers).get('X-Session-Token')).toBe(context.sessionToken);
    await waitFor(() => expect(localStorage.getItem(mediaCanvasDraftKey(owner))).toBeNull());
    mounted.unmount();
    const cold = studioClient(project, context), get = vi.spyOn(cold.graphs.canvasViews!, 'get');
    mounted = render(<MediaCanvasViewPanel {...props} client={cold}/>); await openSaved('Explicit unsaved title', 4);
    expect((await get.mock.results[0].value).definition.cards[0]).toEqual(definition().cards[0]);
    expect(state.saved.definition.cards[0].asset).toEqual(pin); expect(puts(fetcher)).toHaveLength(1);
    expect(screen.queryByText('已保存媒体画布')).toBeNull();
  });

  it('keeps the existing no-draftOwner caller on the original version-only Save contract', async () => {
    const {fetcher, props} = setup({draftOwner: null}); render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle();
    fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'})); await screen.findByText('已保存媒体画布');
    expect(JSON.parse(String(puts(fetcher)[0][1]!.body))).toEqual({expected_version: 3, definition: {...definition(), title: 'Explicit unsaved title'}});
  });

  it('preserves UNKNOWN input and retires a previously captured Save callback instead of blindly resending', async () => {
    const {fetcher, props} = setup({put: async () => {throw new TypeError('Fixture unknown Save outcome');}});
    render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); const oldSave = retainedSave(); act(oldSave);
    await screen.findByText(/保存结果尚未确认/);
    expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Explicit unsaved title');
    expect(screen.queryByText('已保存媒体画布')).toBeNull(); act(oldSave); await act(async () => {});
    expect(puts(fetcher)).toHaveLength(1);
  });

  it.each(['incarnation', 'project', 'client'])('retires the old Save callback across %s A/B/A', async changed => {
    const {fetcher, props} = setup(); const mounted = render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); const oldSave = retainedSave();
    const changedProps: Props = changed === 'client' ? {...props, client: studioClient(project, {sessionToken: 'fixture-other-captured-client'})}
      : {...props, draftOwner: {...owner, ...(changed === 'project' ? {projectId: 'other-save-project'} : {incarnation: 'file:replacement'})}};
    mounted.rerender(<MediaCanvasViewPanel {...changedProps}/>); mounted.rerender(<MediaCanvasViewPanel {...props}/>); act(oldSave);
    await act(async () => {}); expect(puts(fetcher)).toHaveLength(0); expect(screen.queryByText('已保存媒体画布')).toBeNull();
  });

  it('does not adopt an old successful response after its draft owner went A/B/A', async () => {
    let finish!: (value: Response) => void, body!: Record<string, unknown>;
    const {fetcher, props} = setup({put: value => {body = value; return new Promise(resolve => {finish = resolve;});}});
    const mounted = render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'}));
    await waitFor(() => expect(puts(fetcher)).toHaveLength(1));
    mounted.rerender(<MediaCanvasViewPanel {...props} draftOwner={{...owner, incarnation: 'file:replacement'}}/>);
    mounted.rerender(<MediaCanvasViewPanel {...props}/>);
    await act(async () => {finish(json(record(body.definition as CanvasDefinition, 4)));});
    expect(screen.queryByText('已保存媒体画布')).toBeNull(); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Explicit unsaved title');
    expect(screen.getByText(/保存结果尚未确认/)).toBeTruthy();
  });

  it.each([['stale version', 409], ['stale asset pin', 409], ['revoked write permission', 403]] as const)('preserves the dirty input after %s is refused', async (reason, code) => {
    const {fetcher, props} = setup({put: async () => json({code: 'FIXTURE_SAVE_REFUSED', message: `Fixture ${reason}`}, code)});
    render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'}));
    await screen.findByText(/保存结果尚未确认/);
    expect(puts(fetcher)).toHaveLength(1); expect(screen.queryByText('已保存媒体画布')).toBeNull();
    expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Explicit unsaved title');
    expect((screen.getByRole('button', {name: '保存媒体画布'}) as HTMLButtonElement).disabled).toBe(true);
  });

  it('does not downgrade an explicitly invalid draft owner into the legacy no-owner Save path', async () => {
    const {fetcher, props} = setup({draftOwner: {...owner, incarnation: 'not-a-project-incarnation'}});
    render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'}));
    await screen.findByText(/原画布的项目代次、范围或定义摘要尚未核对/);
    expect(puts(fetcher)).toHaveLength(0); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Explicit unsaved title');
    expect(screen.queryByText('已保存媒体画布')).toBeNull();
  });

  it('rechecks owner and write permission when a deferred mutate wrapper finally invokes the original task', async () => {
    const {fetcher, props} = setup(); let release!: () => Promise<void>;
    props.mutate = <T,>(task: () => Promise<T>) => new Promise<T>((resolve, reject) => {
      release = async () => {try {resolve(await task());} catch (reason) {reject(reason);}};
    });
    const mounted = render(<MediaCanvasViewPanel {...props}/>); await openSaved(); editTitle(); fireEvent.click(screen.getByRole('button', {name: '保存媒体画布'}));
    expect(release).toBeTypeOf('function'); mounted.rerender(<MediaCanvasViewPanel {...props} canMutate={false}/>);
    await act(async () => {await release();});
    expect(puts(fetcher)).toHaveLength(0); expect(screen.queryByText('已保存媒体画布')).toBeNull();
    expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Explicit unsaved title');
  });
});
