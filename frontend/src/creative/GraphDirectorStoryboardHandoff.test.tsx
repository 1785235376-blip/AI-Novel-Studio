// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GraphDirectorStoryboardHandoff } from './GraphDirectorStoryboardHandoff';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
import { ApiError } from '../api';
const pin = { id: 'director', version: 3, digest: 'a'.repeat(64) };
const source: CreativeDocument = { ...newDocument('DIRECTOR'), id: pin.id, version: 3, status: 'DRAFT', title: 'Human authored fixture', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, scenes: [newScene(1)], director_notes: [{ id: 'note', number: 1, scene_id: 'scene', note: 'Pause then turn', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: '', pacing: '', performance: '', blocking: '' }] };
const storyboard: CreativeDocument = { ...source, id: 'storyboard', title: 'Human draft shots', version: 1, mode: 'STORYBOARD', shots: [{ ...newShot(1, 'scene'), id: 'shot', frame_prompt: 'Pause then turn' }], source_documents: { [pin.id]: { version: pin.version, digest: pin.digest } } };
function setup() {
  const client: GraphDirectorSource = { history: vi.fn(), create: vi.fn(), update: vi.fn(), capabilities: vi.fn(), derive: vi.fn().mockResolvedValue(storyboard), list: vi.fn().mockResolvedValue({ items: [source, storyboard] }), export: vi.fn().mockResolvedValue({ document: storyboard, document_digest: 'b'.repeat(64) }) };
  return { client, source, snapshot: pin, active: true, canCreate: true, busy: false, isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onPending: vi.fn() };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const confirm = () => fireEvent.click(screen.getByRole('checkbox'));
afterEach(cleanup);
describe('original director storyboard handoff', () => {
  it('previews the exact source, explicitly derives through the original owner and reopens status without writes', async () => {
    const props = setup(); const view = render(<GraphDirectorStoryboardHandoff {...props} />);
    expect(props.client.list).not.toHaveBeenCalled(); expect(screen.getByText(/交接来源/).textContent).toContain(pin.digest);
    click('交接到原分镜草稿'); expect(props.client.derive).not.toHaveBeenCalled(); confirm(); click('交接到原分镜草稿');
    await screen.findByRole('complementary', { name: '分镜原文档状态回传' });
    expect(props.client.derive).toHaveBeenCalledTimes(1); expect(props.client.derive).toHaveBeenCalledWith(source, 'STORYBOARD', 'DIRECTOR_NOTES');
    expect(props.onPending).toHaveBeenLastCalledWith(false); expect(screen.getByText('Pause then turn')).toBeTruthy();
    view.unmount(); render(<GraphDirectorStoryboardHandoff {...props} />); click('读取关联分镜与状态');
    await screen.findByRole('button', { name: '读取分镜 Human draft shots · v1' }); click('读取分镜 Human draft shots · v1');
    await screen.findByText(new RegExp('b'.repeat(64))); expect(props.client.derive).toHaveBeenCalledTimes(1);
  });
  it('invalidates confirmation on unsaved edits and prevents missing digest, read-only and busy creation', () => {
    const props = setup(); const view = render(<GraphDirectorStoryboardHandoff {...props} />); confirm();
    view.rerender(<GraphDirectorStoryboardHandoff {...props} canCreate={false} />);
    view.rerender(<GraphDirectorStoryboardHandoff {...props} />); expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
    for (const override of [{ snapshot: undefined }, { canCreate: false }, { busy: true }]) {
      view.rerender(<GraphDirectorStoryboardHandoff {...props} {...override} />); click('交接到原分镜草稿');
    }
    expect(props.client.derive).not.toHaveBeenCalled();
  });
  it('keeps UNKNOWN locked even after reading an older existing sibling; no automatic retry', async () => {
    const props = setup(); vi.mocked(props.client.derive).mockRejectedValue(new Error('offline'));
    render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('交接到原分镜草稿');
    await waitFor(() => expect(props.client.derive).toHaveBeenCalledTimes(1)); await screen.findByRole('alert');
    click('读取关联分镜与状态'); await screen.findByRole('button', { name: '读取分镜 Human draft shots · v1' }); click('读取分镜 Human draft shots · v1');
    await screen.findByText(new RegExp('b'.repeat(64))); expect(props.onPending).toHaveBeenLastCalledWith(true);
    expect((screen.getByRole('button', { name: '交接到原分镜草稿' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('rejects mismatched success receipts and ignores late reads across A→B→A', async () => {
    const props = setup(); vi.mocked(props.client.derive).mockResolvedValue({ ...storyboard, source_documents: {} });
    const view = render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('交接到原分镜草稿'); await screen.findByRole('alert');
    expect(props.onPending).toHaveBeenLastCalledWith(true); expect(screen.queryByRole('complementary')).toBeNull();
    let resolve!: (v: { items: CreativeDocument[] }) => void; vi.mocked(props.client.list).mockReturnValue(new Promise(yes => resolve = yes));
    click('读取关联分镜与状态'); view.rerender(<GraphDirectorStoryboardHandoff {...props} active={false} />); view.rerender(<GraphDirectorStoryboardHandoff {...props} />);
    await act(async () => resolve({ items: [storyboard] })); expect(screen.queryByRole('button', { name: /读取分镜 Human/ })).toBeNull();
  });
  it('rejects a receipt that reuses the director identity instead of creating an independent draft', async () => {
    const props = setup(); vi.mocked(props.client.derive).mockResolvedValue({ ...storyboard, id: source.id });
    render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('交接到原分镜草稿');
    await screen.findByRole('alert'); expect(screen.queryByRole('complementary')).toBeNull(); expect(props.onPending).toHaveBeenLastCalledWith(true);
  });
  it('invalidates confirmations and late reads across actual source and client replacements', async () => {
    const props = setup(); let resolve!: (v: { items: CreativeDocument[] }) => void;
    vi.mocked(props.client.list).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('读取关联分镜与状态');
    view.rerender(<GraphDirectorStoryboardHandoff {...props} source={{ ...source, id: 'other' }} snapshot={{ ...pin, id: 'other' }} />);
    view.rerender(<GraphDirectorStoryboardHandoff {...props} />);
    await act(async () => resolve({ items: [storyboard] })); expect(screen.queryByRole('button', { name: /读取分镜 Human/ })).toBeNull();
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
    vi.mocked(props.client.list).mockReturnValue(new Promise(yes => resolve = yes)); click('读取关联分镜与状态');
    view.rerender(<GraphDirectorStoryboardHandoff {...props} client={setup().client} />);
    await act(async () => resolve({ items: [storyboard] })); expect(screen.queryByRole('button', { name: /读取分镜 Human/ })).toBeNull();
  });
  it('reports a different saved source version and clears prior content on denied reads', async () => {
    const props = setup(); vi.mocked(props.client.export).mockResolvedValue({ document: { ...storyboard, source_documents: { director: { version: 2, digest: 'c'.repeat(64) } } }, document_digest: 'b'.repeat(64), format: '', boundary: '' });
    render(<GraphDirectorStoryboardHandoff {...props} />); click('读取关联分镜与状态'); await screen.findByRole('button', { name: '读取分镜 Human draft shots · v1' }); click('读取分镜 Human draft shots · v1');
    await screen.findByText('此分镜绑定另一导演版本；不会自动覆盖或重绑。');
    vi.mocked(props.client.export).mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: '无权读取' })); click('核对分镜原文档版本');
    await screen.findByText('无权读取'); expect(screen.queryByRole('complementary')).toBeNull(); expect(props.client.derive).not.toHaveBeenCalled();
  });
});

const addName = '将此分镜草稿添加到当前画布';
function canvasSetup() {
  const props = setup();
  vi.mocked(props.client.export).mockImplementation(async id => ({ document: id === source.id ? source : storyboard, document_digest: id === source.id ? pin.digest : 'b'.repeat(64), format: '', boundary: '' }));
  return { ...props, canvasHandoff: { scope: {}, verificationScope: {}, available: true, isVerificationCurrent: () => true, insert: vi.fn().mockReturnValue(true) } };
}
async function deriveAndVerify() {
  confirm(); click('交接到原分镜草稿'); await screen.findByRole('complementary');
  expect((screen.getByRole('button', { name: addName }) as HTMLButtonElement).disabled).toBe(true);
  click('核对分镜原文档版本');
  await waitFor(() => expect((screen.getByRole('button', { name: addName }) as HTMLButtonElement).disabled).toBe(false));
}
it('verifies both original owners before an explicit one-shot current-canvas insertion', async () => {
  const props = canvasSetup(); render(<GraphDirectorStoryboardHandoff {...props} />); await deriveAndVerify();
  expect(props.canvasHandoff.insert).not.toHaveBeenCalled();
  expect(props.client.export).toHaveBeenCalledWith(source.id);
  click(addName); click(addName);
  expect(props.canvasHandoff.insert).toHaveBeenCalledTimes(1);
  expect(props.canvasHandoff.insert).toHaveBeenCalledWith({ id: storyboard.id, version: 1, digest: 'b'.repeat(64) }, props.canvasHandoff.scope);
  expect(props.client.update).not.toHaveBeenCalled();
  expect(screen.getByText(/已添加一个未连接/)).toBeTruthy();
});
it.each(['source', 'ancestry', 'digest', 'status', 'version'] as const)('rejects %s drift without any canvas write', async kind => {
  const props = canvasSetup();
  vi.mocked(props.client.export).mockImplementation(async id => ({
    document: id === source.id ? { ...source, version: kind === 'source' ? 4 : 3 } : { ...storyboard,
      ...(kind === 'ancestry' ? { source_documents: {} } : {}), ...(kind === 'status' ? { status: 'APPROVED' as const } : {}), ...(kind === 'version' ? { version: 2 } : {}) },
    document_digest: id === source.id ? pin.digest : kind === 'digest' ? 'bad' : 'b'.repeat(64), format: '', boundary: '' }));
  render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('交接到原分镜草稿'); await screen.findByRole('complementary');
  click('核对分镜原文档版本'); await screen.findByRole('alert'); expect(props.canvasHandoff.insert).not.toHaveBeenCalled();
});
it('pins verification before asynchronous reads and retires canvas ABA results', async () => {
  const props = canvasSetup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
  vi.mocked(props.client.export).mockReturnValue(new Promise(yes => resolve = yes));
  const view = render(<GraphDirectorStoryboardHandoff {...props} />); confirm(); click('交接到原分镜草稿'); await screen.findByRole('complementary');
  click('核对分镜原文档版本');
  view.rerender(<GraphDirectorStoryboardHandoff {...props} canvasHandoff={{ ...props.canvasHandoff, verificationScope: {} }} />);
  view.rerender(<GraphDirectorStoryboardHandoff {...props} />);
  await act(async () => resolve({ document: storyboard, document_digest: 'b'.repeat(64), format: '', boundary: '' }));
  expect(props.canvasHandoff.insert).not.toHaveBeenCalled(); expect(screen.queryByRole('complementary')).toBeNull();
});
it('retires a verified insertion on source ABA and keeps UNKNOWN unable to insert', async () => {
  const props = canvasSetup(); const view = render(<GraphDirectorStoryboardHandoff {...props} />); await deriveAndVerify();
  view.rerender(<GraphDirectorStoryboardHandoff {...props} sourceScope="changed" />); view.rerender(<GraphDirectorStoryboardHandoff {...props} />);
  expect(screen.queryByRole('button', { name: addName })).toBeNull();
  vi.mocked(props.client.derive).mockRejectedValue(new Error('offline')); confirm(); click('交接到原分镜草稿'); await screen.findByRole('alert');
  click('读取关联分镜与状态'); await screen.findByRole('button', { name: '读取分镜 Human draft shots · v1' }); click('读取分镜 Human draft shots · v1');
  await screen.findByRole('complementary'); expect((screen.getByRole('button', { name: addName }) as HTMLButtonElement).disabled).toBe(true);
});

it('a fresh derivation clears the previously verified insertion intent', async () => {
  const props = canvasSetup(); render(<GraphDirectorStoryboardHandoff {...props} />); await deriveAndVerify();
  confirm(); click('交接到原分镜草稿');
  await waitFor(() => expect(props.client.derive).toHaveBeenCalledTimes(2));
  await screen.findByRole('complementary');
  expect((screen.getByRole('button', { name: addName }) as HTMLButtonElement).disabled).toBe(true);
  click(addName); expect(props.canvasHandoff.insert).not.toHaveBeenCalled();
});
