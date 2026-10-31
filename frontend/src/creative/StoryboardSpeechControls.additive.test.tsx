// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { StoryboardProductionPanel } from './StoryboardProductionPanel';
import { useStoryboardProductionController, type StoryboardProductionProps } from './useStoryboardProductionController';
import type { CreativeClient } from './client';
import type { StudioClient } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import { speechBoard, speechDocument, speechProvider, speechRequest, speechJob } from './storyboardSpeech.testFixtures';
import type { StoryboardAudioRequest } from './studioStoryboardSpeechContract';
const deferred = <T,>() => { let resolve!: (value: T) => void; return { promise: new Promise<T>(yes => { resolve = yes; }), resolve: (value: T) => resolve(value) }; };
function mount(approved = true) {
  const board = { ...speechBoard(), approved }, creative = { storyboardGet: vi.fn().mockResolvedValue(board), storyboardAudioRequest: vi.fn().mockResolvedValue(speechRequest()), storyboardImageRequest: vi.fn(), storyboardBindImage: vi.fn(), storyboardTimelineCreate: vi.fn(), storyboardTimelineDraft: vi.fn() };
  const studio = { assets: vi.fn().mockResolvedValue({ items: [] }) }, production = { providers: vi.fn().mockResolvedValue([speechProvider]), preview: vi.fn(), create: vi.fn(), execute: vi.fn(), review: vi.fn(), list: vi.fn() };
  const props: StoryboardProductionProps = { document: speechDocument(), client: creative as unknown as CreativeClient, studio: studio as unknown as StudioClient, production: production as unknown as StudioProductionClient,
    active: true, editable: true, busy: false, isBusy: () => false, isCurrent: () => true, perform: work => work(), onDocument: vi.fn(), onDenied: vi.fn(), onDirtyChange: vi.fn() };
  const view = render(<StoryboardProductionPanel {...props} />); return { ...view, props, board, creative, production, studio };
}
const prepareName = '准备版本绑定语音请求';
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function ready() {
  fireEvent.click(button('明确读取已保存创作回执')); await screen.findByLabelText('对白条目');
  fireEvent.click(button('明确读取已有图片与模型配置')); await screen.findByRole('option', { name: 'local-speech · speech-fixture' });
}
function choose() { change('对白条目', '1'); change('已有语音模型', mediaProviderKey(speechProvider)); change('对白语音标识', 'narrator'); change('对白语速（0.5–2）', '1.2'); }
beforeEach(() => { vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Unexpected network'))); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('Speech preparation in the existing Storyboard Inspector', () => {
  it('makes no request on mount and requires every choice explicitly', async () => {
    const state = mount(); expect(state.creative.storyboardGet).not.toHaveBeenCalled(); expect(state.production.providers).not.toHaveBeenCalled(); await ready();
    expect(button(prepareName).disabled).toBe(true); change('对白条目', '1'); expect((screen.getByLabelText('已保存对白原文') as HTMLTextAreaElement).value).toBe('Second authored line.');
    change('已有语音模型', mediaProviderKey(speechProvider)); change('对白语音标识', 'narrator'); expect(button(prepareName).disabled).toBe(true);
    change('对白语速（0.5–2）', '0.4'); expect(button(prepareName).disabled).toBe(true); change('对白语速（0.5–2）', '1.2'); expect(button(prepareName).disabled).toBe(false);
    expect(state.creative.storyboardAudioRequest).not.toHaveBeenCalled();
  });
  it('hands off only a prepared command to the original media panel, without creating or executing a task', async () => {
    const state = mount(); await ready(); choose(); fireEvent.click(button(prepareName)); await screen.findByText('原分镜语音请求');
    expect(state.creative.storyboardAudioRequest).toHaveBeenCalledWith(state.board, state.board.shots[0], 1, 'local-speech', 'speech-fixture', expect.any(String), 'narrator', 1.2);
    for (const call of [state.production.preview, state.production.create, state.production.execute, state.production.review, state.creative.storyboardTimelineCreate, state.creative.storyboardTimelineDraft, state.props.onDocument]) expect(call).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('对白语音标识')).toBeNull(); fireEvent.click(button('关闭当前请求视图，保留原任务')); await screen.findByLabelText('对白语音标识');
    expect(state.creative.storyboardAudioRequest).toHaveBeenCalledTimes(1);
  });
  it('refuses saved tasks with the same request ID but changed speech provenance', async () => {
    const state = mount(); await ready(); choose(); fireEvent.click(button(prepareName)); await screen.findByText('原分镜语音请求');
    const changed = speechJob(); changed.command!.storyboard_speech!.dialogue_index = 0; state.production.list.mockResolvedValue([changed]); fireEvent.click(button('读取任务列表'));
    await screen.findByText('原语音任务与当前分镜对白请求不一致，请读取原回执核对。'); expect(screen.queryByLabelText('已保存任务')).toBeNull(); expect(state.production.execute).not.toHaveBeenCalled();
  });
  it('blocks preparation until the saved Storyboard has explicit approval', async () => {
    const state = mount(false); await ready(); choose(); expect(button(prepareName).disabled).toBe(true); fireEvent.click(button(prepareName)); expect(state.creative.storyboardAudioRequest).not.toHaveBeenCalled();
  });
  it('clears all speech choices on shot selection and does not use sound text as dialogue', async () => {
    const state = mount(); await ready(); choose(); fireEvent.click(button(`SHOT ${state.board.shots[1].shot.number} · v${state.board.shots[1].shot_version}`));
    expect((screen.getByLabelText('对白条目') as HTMLSelectElement).value).toBe(''); expect((screen.getByLabelText('已有语音模型') as HTMLSelectElement).value).toBe('');
    expect((screen.getByLabelText('对白语音标识') as HTMLInputElement).value).toBe(''); expect((screen.getByLabelText('对白语速（0.5–2）') as HTMLInputElement).value).toBe(''); expect(button(prepareName).disabled).toBe(true);
  });
  it('serializes repeated clicks and ignores a late preparation after document version changes', async () => {
    const state = mount(), pending = deferred<StoryboardAudioRequest>(); state.creative.storyboardAudioRequest.mockReturnValue(pending.promise); await ready(); choose();
    fireEvent.click(button(prepareName)); fireEvent.click(button(prepareName)); expect(state.creative.storyboardAudioRequest).toHaveBeenCalledTimes(1);
    state.rerender(<StoryboardProductionPanel {...state.props} document={{ ...state.props.document, version: state.props.document.version + 1 }} />);
    await act(async () => pending.resolve(speechRequest())); expect(screen.queryByText('原分镜语音请求')).toBeNull(); expect(state.production.create).not.toHaveBeenCalled();
  });
  it.each(['permission', 'identity', 'inactive'])('ignores late preparation after %s is revoked', async scope => {
    const state = mount(), pending = deferred<StoryboardAudioRequest>(); state.creative.storyboardAudioRequest.mockReturnValue(pending.promise); await ready(); choose(); fireEvent.click(button(prepareName));
    const props = { ...state.props, ...(scope === 'permission' ? { editable: false } : scope === 'inactive' ? { active: false } : { isCurrent: () => false }) };
    state.rerender(<StoryboardProductionPanel {...props} />); await act(async () => pending.resolve(speechRequest())); expect(screen.queryByText('原分镜语音请求')).toBeNull();
  });
  it.each(['permission', 'identity', 'inactive', 'client', 'production'])('does not resurrect pending preparation after %s A→B→A', async scope => {
    const state = mount(), pending = deferred<StoryboardAudioRequest>(); state.creative.storyboardAudioRequest.mockReturnValue(pending.promise); await ready(); choose(); fireEvent.click(button(prepareName));
    const changed = { ...state.props, ...(scope === 'permission' ? { editable: false } : scope === 'inactive' ? { active: false } : scope === 'client' ? { client: { ...state.props.client } } : scope === 'production' ? { production: { ...state.props.production } } : { isCurrent: () => false }) };
    state.rerender(<StoryboardProductionPanel {...changed} />); state.rerender(<StoryboardProductionPanel {...state.props} />);
    await act(async () => pending.resolve(speechRequest())); expect(screen.queryByText('原分镜语音请求')).toBeNull(); expect(state.production.create).not.toHaveBeenCalled();
  });
  it('clears speech choices when re-reading a receipt changes the selected shot', async () => {
    const state = mount(); await ready(); choose(); fireEvent.click(button('明确读取已保存创作回执')); await waitFor(() => expect((screen.getByLabelText('对白条目') as HTMLSelectElement).value).toBe(''));
    expect((screen.getByLabelText('已有语音模型') as HTMLSelectElement).value).toBe(''); expect((screen.getByLabelText('对白语音标识') as HTMLInputElement).value).toBe(''); expect(button(prepareName).disabled).toBe(true);
  });
  it('rejects retained prepare and selection callbacks after authority or choices change', async () => {
    const state = mount(); state.unmount(); const hook = renderHook(props => useStoryboardProductionController(props), { initialProps: state.props });
    act(() => hook.result.current.read()); await waitFor(() => expect(hook.result.current.receipt).toBeTruthy()); act(() => hook.result.current.loadResources()); await waitFor(() => expect(hook.result.current.providers).toHaveLength(1));
    act(() => hook.result.current.chooseDialogue('1')); act(() => hook.result.current.chooseSpeechProvider(mediaProviderKey(speechProvider))); act(() => hook.result.current.changeSpeechVoice('narrator')); act(() => hook.result.current.changeSpeechRate('1.2'));
    const stalePrepare = hook.result.current.prepareSpeech, staleDialogue = hook.result.current.chooseDialogue;
    act(() => hook.result.current.chooseDialogue('0')); act(() => stalePrepare()); expect(state.creative.storyboardAudioRequest).not.toHaveBeenCalled();
    hook.rerender({ ...state.props, editable: false }); hook.rerender(state.props); act(() => staleDialogue('1')); expect(hook.result.current.dialogueIndex).toBe('0');
  });
  it('invalidates a stale source without automatic retries', async () => {
    const state = mount(); state.creative.storyboardAudioRequest.mockRejectedValue(new ApiError({ status: 409, code: 'CREATIVE_STORYBOARD_AUDIO_SOURCE_CHANGED', message: 'source changed' })); await ready(); choose(); fireEvent.click(button(prepareName));
    await screen.findByText('source changed'); expect(screen.queryByLabelText('对白条目')).toBeNull(); expect(state.creative.storyboardAudioRequest).toHaveBeenCalledTimes(1); expect(state.production.create).not.toHaveBeenCalled();
  });
  it('leaves explicit preparation retry available after a read-only network failure', async () => {
    const state = mount(); state.creative.storyboardAudioRequest.mockRejectedValueOnce(new Error('offline')); await ready(); choose(); fireEvent.click(button(prepareName));
    await waitFor(() => expect(button(prepareName).disabled).toBe(false)); expect(state.creative.storyboardAudioRequest).toHaveBeenCalledTimes(1); expect(screen.queryByText('原分镜语音请求')).toBeNull();
    fireEvent.click(button(prepareName)); await screen.findByText('原分镜语音请求'); expect(state.creative.storyboardAudioRequest).toHaveBeenCalledTimes(2);
  });
});
