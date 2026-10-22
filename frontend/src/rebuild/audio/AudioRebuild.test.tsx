// @vitest-environment jsdom
// [HERMIA-FE-20261022 R4] 声音页按原型重做：真实接口、一页一主、无多轨、无内部编号
import {describe, it, expect, vi, afterEach, beforeEach} from 'vitest';
import {render, screen, fireEvent, cleanup, waitFor} from '@testing-library/react';
import {AudioRebuild, audioItemsFrom, bookProgress} from './AudioRebuild';
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
let speech: any[] = []; let providers: any[] = [];
beforeEach(() => { vi.stubGlobal('fetch', vi.fn((url: string) => {
  if (url.includes('speech-generations')) return json({items: speech});
  if (url.includes('audiobook/manifest')) return json({chapters: [{chapter_id: 'n1:1', title: '来信', audio_count: 0, production_status: 'NOT_QUEUED'}]});
  if (url.includes('audio/providers')) return json({items: providers});
  return json({});
})); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); speech = []; providers = []; });
const primaries = () => document.querySelectorAll('.aud-ws .mw-head .nv-btn--primary');
describe('AudioRebuild', () => {
  it('empty library: honest empty copy, 新建配音 is the one page primary, no tracks', async () => {
    render(<AudioRebuild novelId="n1" />);
    await screen.findByText('声音库是空的');
    expect(primaries()).toHaveLength(1);
    expect(primaries()[0].textContent).toBe('新建配音');
    expect(document.querySelector('.aud-ws[data-nle-tracks="0"]')).toBeTruthy();
    expect(screen.getByText('尚未选中内容')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/n1:1|NOT_QUEUED|AudioTaskInspector|NLE/);
  });
  it('selected item: 送到剪辑… becomes primary; TTS disabled with reason when no provider', async () => {
    speech = [{voice: 'alloy', audio_uri: '/a.mp3'}];
    render(<AudioRebuild novelId="n1" />);
    fireEvent.click(await screen.findByRole('option', {name: /配音 1/}));
    expect(primaries()[0].textContent).toBe('送到剪辑…');
    expect((document.querySelector('#ttsGo') as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => expect(document.querySelector('[data-tts-reason]')?.textContent).toContain('需要先在 AI 主控里接好语音服务'));
    expect(screen.getByText(/1 章 · 0 已有音频/)).toBeTruthy();
  });
  it('send to edit requires explicit confirm', async () => {
    const onSend = vi.fn();
    render(<AudioRebuild novelId="n1" onSendToEdit={onSend} />);
    await screen.findByText('声音库是空的');
    fireEvent.click(document.querySelector('#audSendEdit')!);
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(document.querySelector('[data-send-edit-confirm]')!);
    expect(onSend).toHaveBeenCalledOnce();
  });
  it('helpers map real payloads', () => {
    expect(audioItemsFrom([{voice: 'v'}], {chapters: [{chapter_id: 'c', title: 'T', audio_count: 2}]}).map(i => i.kind)).toEqual(['人声', '有声书']);
    expect(bookProgress({chapters: [{audio_count: 1}, {production_status: 'QUEUED'}]})).toEqual({total: 2, done: 1, queued: 1});
  });
});
