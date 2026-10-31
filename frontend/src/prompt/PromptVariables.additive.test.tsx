// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { fillPromptVariables, promptVariableNames } from './promptVariables';
import { PromptVariablesPanel } from './PromptVariablesPanel';
import { PromptEditorPanel } from './PromptEditorPanel';
import { newDraft } from './promptDraft';
afterEach(cleanup);
it('fills repeated Unicode names literally without trimming, recursion or expression evaluation',()=>{
 const text='  {{角色}}\r\n{{角色}} {{place}} {{x.y}} \\{{literal}}  ';
 expect(promptVariableNames(text)).toEqual(['角色','place']);
 expect(fillPromptVariables(text,{'角色':'小机器人🙂',place:'$& {{角色}}'}).text).toBe('  小机器人🙂\r\n小机器人🙂 $& {{角色}} {{x.y}} \\{{literal}}  ');
});
it('requires own property values and allows prototype-shaped names only as literal authored keys',()=>{
 expect(()=>fillPromptVariables('{{constructor}}',{})).toThrow();expect(()=>fillPromptVariables('{{__proto__}}',{})).toThrow();
 expect(fillPromptVariables('{{__proto__}}',JSON.parse('{"__proto__":"literal"}')).text).toBe('literal');
});
it('bounds variables, values and expanded UTF-8 bytes without truncation',()=>{
 expect(()=>promptVariableNames(Array.from({length:33},(_,i)=>`{{v${i}}}`).join(''))).toThrow();
 expect(()=>fillPromptVariables('{{x}}',{x:''})).toThrow();expect(()=>fillPromptVariables('{{x}}',{x:'x'.repeat(8193)})).toThrow();
 expect(()=>fillPromptVariables('{{x}}'.repeat(9),{x:'文'.repeat(8192)})).toThrow();expect(fillPromptVariables('{{x}}',{x:' '})).toMatchObject({text:' ',bytes:1});
});
const button=(name:string)=>screen.getByRole('button',{name,hidden:true});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
function preview(){fireEvent.change(screen.getByLabelText('变量 角色'),{target:{value:'小机器人'}});fireEvent.click(button('预览变量填写结果'));fireEvent.click(screen.getByLabelText('已核对完整正文，替换当前本地草稿'));}
it('requires explicit preview/confirmation and consumes local apply once',()=>{
 const props={text:' {{角色}} ',owner:{},scope:'A',disabled:false,onApply:vi.fn()};render(<PromptVariablesPanel {...props}/>);preview();expect(props.onApply).not.toHaveBeenCalled();
 const apply=handler(button('将变量结果填入正文草稿'));act(()=>{apply();apply();});expect(props.onApply).toHaveBeenCalledTimes(1);expect(props.onApply).toHaveBeenCalledWith(' 小机器人 ');
});
it('invalidates retained apply after revocation and composition',()=>{
 const props={text:'{{角色}}',owner:{},scope:'A',disabled:false,onApply:vi.fn()};render(<PromptVariablesPanel {...props}/>);preview();const apply=handler(button('将变量结果填入正文草稿'));
 fireEvent.click(screen.getByLabelText('已核对完整正文，替换当前本地草稿'));act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();
 fireEvent.click(screen.getByLabelText('已核对完整正文，替换当前本地草稿'));fireEvent.compositionStart(screen.getByLabelText('变量 角色'));act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();
});
it('retires source-owner changes and clears private variable input on scope switch',()=>{
 const props={text:'{{角色}}',owner:{},scope:'A',disabled:false,onApply:vi.fn()};const view=render(<PromptVariablesPanel {...props}/>);preview();const apply=handler(button('将变量结果填入正文草稿'));
 view.rerender(<PromptVariablesPanel {...props} scope='B'/>);act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();expect((screen.getByLabelText('变量 角色') as HTMLTextAreaElement).value).toBe('');
});
it('mounts in original prompt editor and changes only text without saving a revision',()=>{
 const draft=newDraft('family');draft.content.text=' {{角色}} ';draft.content.negativePrompt='Keep negative';
 const props={draft,copyScopeKey:'project',detail:null,mode:'PROFESSIONAL' as const,locked:false,busy:false,canSave:true,conflictCode:null,saveError:null,fieldError:null,onEdit:vi.fn(),onSave:vi.fn(),onRetry:vi.fn(),onRebase:vi.fn(),onDiscard:vi.fn()};
 render(<PromptEditorPanel {...props}/>);preview();fireEvent.click(button('将变量结果填入正文草稿'));
 expect(props.onEdit).toHaveBeenCalledTimes(1);expect(props.onEdit).toHaveBeenCalledWith({text:' 小机器人 '});expect(props.onSave).not.toHaveBeenCalled();expect(draft.content.negativePrompt).toBe('Keep negative');
});
