// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import cases from './voicePronunciation.testFixture.json';
import {parsePronunciationRules,pronunciationPreview} from './voicePronunciation';
import {PronunciationPreview} from './PronunciationPreview';
afterEach(cleanup);
it.each(cases)('matches the original literal contract for $text',row=>{expect(pronunciationPreview(row.text,parsePronunciationRules(row.rules))).toEqual({text:row.expected,characters:Array.from(row.expected).length,truncated:false});});
it.each(['a=1\na=2','a=','missing','a=<say>','a=tab\tvalue',`${'a'.repeat(161)}=b`,Array.from({length:101},(_,i)=>`${i}=a`).join('\n')])('rejects invalid rules without silently ignoring them',value=>{expect(()=>parsePronunciationRules(value)).toThrow();});
it('counts full simultaneous expansion while retaining only a Unicode-safe bounded preview',()=>{const result=pronunciationPreview('🙂'.repeat(20000),parsePronunciationRules('🙂='+'字'.repeat(240)));expect(result).toEqual({text:'字'.repeat(4000),characters:4800000,truncated:true});expect(()=>pronunciationPreview('a'.repeat(20001),[])).toThrow();});
it('renders read-only local preview and replaces it with an honest error for invalid rules',()=>{const view=render(<PronunciationPreview text="重庆" rules="重庆=chong qing"/>);expect((screen.getByLabelText('发音替换后的朗读文本预览') as HTMLTextAreaElement).value).toBe('chong qing');expect((screen.getByLabelText('发音替换后的朗读文本预览') as HTMLTextAreaElement).readOnly).toBe(true);view.rerender(<PronunciationPreview text="重庆" rules="重庆="/>);expect(screen.queryByLabelText('发音替换后的朗读文本预览')).toBeNull();expect(screen.getByText(/不接受标记或控制字符/)).toBeTruthy();});
