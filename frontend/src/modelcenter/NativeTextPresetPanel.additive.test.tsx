// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NativeTextPresetPanel, nativeTextHostPreview } from './NativeTextPresetPanel';
const props={transport:{json:vi.fn()},projectId:'project',identity:'owner-a',active:true,denied:false,busy:false,isCurrent:()=>true};
afterEach(cleanup);
it('prepares original model-only variables locally without any fetch or credential field',()=>{
 const fetch=vi.spyOn(globalThis,'fetch').mockRejectedValue(new Error('Must not request'));
 try {
  render(<NativeTextPresetPanel {...props} />);
  expect(screen.queryByLabelText('平台文本模型 ID')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'查看 Claude / Gemini 文本预设'}));
  fireEvent.change(screen.getByLabelText('原生文本 API 平台'),{target:{value:'claude'}});
  fireEvent.change(screen.getByLabelText('平台文本模型 ID'),{target:{value:'account-selected-model'}});
  expect((screen.getByLabelText('原生文本主机配置预览（未应用）') as HTMLTextAreaElement).value).toBe('ANTHROPIC_MODEL=account-selected-model');
  fireEvent.change(screen.getByLabelText('原生文本 API 平台'),{target:{value:'gemini'}});
  expect((screen.getByLabelText('平台文本模型 ID') as HTMLInputElement).value).toBe('');
  fireEvent.change(screen.getByLabelText('平台文本模型 ID'),{target:{value:'models/account-selected-model'}});
  expect((screen.getByLabelText('原生文本主机配置预览（未应用）') as HTMLTextAreaElement).value).toBe('GEMINI_MODEL=models/account-selected-model');
  expect(fetch).not.toHaveBeenCalled(); expect(screen.queryByLabelText(/密钥/)).toBeNull();
 } finally { fetch.mockRestore(); }
});
it('retires prepared hints across owner changes and respects busy/denied state',()=>{
 const view=render(<NativeTextPresetPanel {...props} />);
 fireEvent.click(screen.getByRole('button'));fireEvent.change(screen.getByLabelText('原生文本 API 平台'),{target:{value:'claude'}});
 fireEvent.change(screen.getByLabelText('平台文本模型 ID'),{target:{value:'private-model-name'}});
 view.rerender(<NativeTextPresetPanel {...props} identity="owner-b" />);
 expect(screen.queryByLabelText('平台文本模型 ID')).toBeNull();
 view.rerender(<NativeTextPresetPanel {...props} />);expect(screen.queryByText('private-model-name')).toBeNull();
 view.rerender(<NativeTextPresetPanel {...props} busy />);expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
 view.rerender(<NativeTextPresetPanel {...props} denied />);expect(screen.queryByRole('button')).toBeNull();
});
it.each(['','bad name','model\nOTHER=value','model"quoted','$(run)','../../model','a/../b'])('refuses unsafe or ambiguous host-preview model %j',model=>{
 expect(nativeTextHostPreview('claude',model)).toBeUndefined();
});
it('rejects arbitrary platform keys and missing context',()=>{
 expect(nativeTextHostPreview('__proto__','model')).toBeUndefined();
 render(<NativeTextPresetPanel {...props} projectId="" />);
 expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
});

it('uses the original project-scope validation even for local hints',()=>{
 render(<NativeTextPresetPanel {...props} scope={{workspaceId:'workspace',projectId:'other-project',storylineId:'storyline',branchId:'branch'}} />);
 expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
 expect(props.transport.json).not.toHaveBeenCalled();
});
