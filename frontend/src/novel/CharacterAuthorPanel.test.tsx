// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AiWritingPanel } from './AiWritingPanel';
import type { TextRuntimeDiagnostics } from '../api';
const base = { novelId: 'n', chapterNumber: 1, models: [{ provider_id: 'ollama', model_id: 'local-test', display_name: 'Configured local', available: true }], selection: { providerId: 'ollama', modelId: 'local-test' }, onSelectionChange: vi.fn(), onGenerate: vi.fn(), onCancel: vi.fn(), onAccept: vi.fn(), onReject: vi.fn(), readiness: { state: 'READY' } as TextRuntimeDiagnostics };
const options = { enabled: true, chapterId: 'n:1', chapterVersion: 3, source: 'SECRET_SELECTED_SOURCE', profile: 'QUALITY' as const, styleProfileId: 'secret-style', plotPlanId: 'secret-plan', context: { sessionToken: '' }, saved: true, characterId: 'hero' };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('excludes source/style/plan before requesting character preview and disables unsupported operations', async () => {
  const exit = vi.fn(), sent: any[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => { const value = JSON.parse(init.body); sent.push(value); return new Response(JSON.stringify({ contract: 'AUTHOR_REQUEST_V1', preview_digest: 'a'.repeat(64), chapter_id: 'n:1', chapter_version: 3, target: 'local', provider_id: 'ollama', model_id: 'local-test', prompt_characters: 12, source_characters: 0, source_strategy: 'CHARACTER_KNOWLEDGE_ONLY', truncation: 'NONE', token_count: null, context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: 'ONLY_KNOWN_FACT', context: {}, parameters: {}, system_instruction: null } }), { status: 200 }); }));
  const generate = vi.fn();
  render(<AiWritingPanel {...base} onGenerate={generate} authorPreview={{ ...options, onExitCharacter: exit }} />);
  expect((screen.getByRole('tab', { name: '改写' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('tab', { name: '润色' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '2' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('附加要求（可选）'), { target: { value: 'Ask the known question' } });
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
  await screen.findByText('请求已预检');
  expect(sent[0]).toMatchObject({ character_id: 'hero', profile: 'LOCAL_ONLY', source: '', selected_text: '', style: '' });
  expect(sent[0]).not.toHaveProperty('plot_plan_id'); expect(sent[0]).not.toHaveProperty('style_profile_id');
  expect(JSON.stringify(sent)).not.toContain('SECRET_SELECTED_SOURCE');
  expect(screen.getByText(/仅人物可知信息，不含正文/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '生成创作下一章草稿' }));
  await waitFor(() => expect(generate).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole('button', { name: '退出人物视角生成' })); expect(exit).toHaveBeenCalledOnce();
});
it('does not carry a previous receipt into another character or a newer source version', async () => {
  const generate = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ preview_digest: 'a'.repeat(64), chapter_version: 3, source_strategy: 'CHARACTER_KNOWLEDGE_ONLY', source_characters: 0, context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: 'KNOWN', context: {}, parameters: {} } }), { status: 200 })));
  const view = render(<AiWritingPanel {...base} onGenerate={generate} authorPreview={options} />);
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' })); await screen.findByText('请求已预检');
  view.rerender(<AiWritingPanel {...base} onGenerate={generate} authorPreview={{ ...options, characterId: 'other', chapterVersion: 4 }} />);
  expect((screen.getByRole('button', { name: '生成创作下一章草稿' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByDisplayValue('KNOWN')).toBeNull(); expect(generate).not.toHaveBeenCalled();
});
it('binds exact scene identity into preview and invalidates it when scene changes', async () => {
  const sent: any[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => { sent.push(JSON.parse(init.body)); return new Response(JSON.stringify({ preview_digest: 'a'.repeat(64), chapter_version: 3, source_strategy: 'CHARACTER_KNOWLEDGE_ONLY', source_characters: 0, context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: 'SCENE_KNOWN', context: {}, parameters: {} } }), { status: 200 }); }));
  const generate = vi.fn(); const view = render(<AiWritingPanel {...base} onGenerate={generate} authorPreview={{ ...options, sceneId: 'scene-one' }} />);
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' })); await screen.findByText('请求已预检');
  expect(sent[0]).toMatchObject({ character_id: 'hero', scene_id: 'scene-one', source: '', profile: 'LOCAL_ONLY' });
  view.rerender(<AiWritingPanel {...base} onGenerate={generate} authorPreview={{ ...options, sceneId: 'scene-two' }} />);
  expect((screen.getByRole('button', { name: '生成创作下一章草稿' }) as HTMLButtonElement).disabled).toBe(true);
  expect(generate).not.toHaveBeenCalled(); expect(screen.queryByDisplayValue('SCENE_KNOWN')).toBeNull();
});
