// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {StoryboardShotBatchTools} from './StoryboardShotBatchTools';
import {newDocument,newScene,newShot,type CreativeInput} from './types';
afterEach(cleanup);
const fixture=():CreativeInput=>({...newDocument('STORYBOARD'),title:'Batch',source_independent:true,scenes:[{...newScene(1),id:'scene'},{...newScene(2),id:'other'}],shots:[{...newShot(1,'scene'),id:'one'},{...newShot(2,'scene'),id:'two'},{...newShot(3,'other'),id:'three'}]});
const props=()=>({draft:fixture(),sceneId:'scene',version:1,dirty:true,canEdit:true,busy:false,onChange:vi.fn()});
const button=(name:string)=>screen.getByRole('button',{name});
function open(){fireEvent.click(screen.getByText('批量设置所选镜头语言'));}
const input=()=>screen.getByLabelText('批量镜头新值');
const apply=()=>button('确认批量应用到分镜草稿（尚未保存）');
const undo=()=>button('撤销本次镜头语言批量编辑');
function retained(element:HTMLElement,key='onClick'){return (element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!][key];}
function stage(){fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.change(input(),{target:{value:'WIDE'}});fireEvent.click(button('预览所选镜头语言'));}
it('previews every old/new value and applies once only after confirmation',()=>{const p=props();render(<StoryboardShotBatchTools {...p}/>);open();stage();expect(p.onChange).not.toHaveBeenCalled();expect(screen.getByText('镜头 1 · one：MEDIUM → WIDE')).toBeTruthy();expect(screen.queryByLabelText('批量选择镜头 3 · three')).toBeNull();const action=retained(apply());act(()=>{action();action();});expect(p.onChange).toHaveBeenCalledTimes(1);expect(p.onChange.mock.calls[0][0].shots.map((row:any)=>row.shot_size)).toEqual(['WIDE','MEDIUM','MEDIUM']);});
it.each(['selection ABA','value ABA','field ABA','draft ABA','scene ABA','busy ABA','permission ABA','version ABA','save ABA','unmount'])('retires an old confirmation after %s',mode=>{
 const p=props(),view=render(<StoryboardShotBatchTools {...p}/>);open();stage();const action=retained(apply());
 if(mode==='selection ABA'){fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));}
 if(mode==='value ABA'){fireEvent.change(input(),{target:{value:'CLOSE'}});fireEvent.change(input(),{target:{value:'WIDE'}});}
 if(mode==='field ABA'){fireEvent.change(screen.getByLabelText('批量镜头字段'),{target:{value:'camera_angle'}});fireEvent.change(screen.getByLabelText('批量镜头字段'),{target:{value:'shot_size'}});}
 if(mode==='unmount')view.unmount();
 if(!['selection ABA','value ABA','field ABA','unmount'].includes(mode)){
   view.rerender(<StoryboardShotBatchTools {...p} draft={mode==='draft ABA'?fixture():p.draft} sceneId={mode==='scene ABA'?'other':p.sceneId} busy={mode==='busy ABA'} canEdit={mode!=='permission ABA'} version={mode==='version ABA'?2:p.version} dirty={mode!=='save ABA'}/>);view.rerender(<StoryboardShotBatchTools {...p}/>);
 }
 act(action);expect(p.onChange).not.toHaveBeenCalled();
});
it('does not reuse stale field DOM values or unfinished IME composition',()=>{const p=props();render(<StoryboardShotBatchTools {...p}/>);open();stage();const action=retained(apply());(input() as HTMLInputElement).value='Unreported';act(action);expect(p.onChange).not.toHaveBeenCalled();fireEvent.change(input(),{target:{value:'WIDE'}});fireEvent.compositionStart(input());fireEvent.click(button('预览所选镜头语言'));expect(screen.queryByRole('button',{name:'确认批量应用到分镜草稿（尚未保存）'})).toBeNull();fireEvent.compositionEnd(input(),{data:'WIDE'});fireEvent.click(button('预览所选镜头语言'));fireEvent.click(apply());expect(p.onChange).toHaveBeenCalledTimes(1);});
it('remounts the IME input when the source owner changes and rejects the old end callback',()=>{const p=props(),view=render(<StoryboardShotBatchTools {...p}/>);open();const old=input();fireEvent.compositionStart(old);const end=retained(old,'onCompositionEnd');view.rerender(<StoryboardShotBatchTools {...p} draft={fixture()}/>);expect(input()).not.toBe(old);act(()=>end({currentTarget:{value:'old source'}}));expect((input() as HTMLInputElement).value).toBe('');expect(p.onChange).not.toHaveBeenCalled();});
it.each(['edit','busy','permission','save','version','scene'])('retires undo after intervening %s',mode=>{const p=props(),view=render(<StoryboardShotBatchTools {...p}/>);open();stage();fireEvent.click(apply());const next=p.onChange.mock.calls[0][0];view.rerender(<StoryboardShotBatchTools {...p} draft={next}/>);const action=retained(undo());view.rerender(<StoryboardShotBatchTools {...p} draft={mode==='edit'?structuredClone(next):next} busy={mode==='busy'} canEdit={mode!=='permission'} dirty={mode!=='save'} version={mode==='version'?2:p.version} sceneId={mode==='scene'?'other':p.sceneId}/>);view.rerender(<StoryboardShotBatchTools {...p} draft={next}/>);act(action);expect(p.onChange).toHaveBeenCalledTimes(1);expect((undo() as HTMLButtonElement).disabled).toBe(true);});
it('reports no-op selections and disables unavailable authoring',()=>{const p=props(),view=render(<StoryboardShotBatchTools {...p}/>);open();fireEvent.click(button('全选当前场景镜头'));fireEvent.change(input(),{target:{value:'MEDIUM'}});fireEvent.click(button('预览所选镜头语言'));expect(screen.getByText(/所选镜头的该字段没有变化/)).toBeTruthy();expect(p.onChange).not.toHaveBeenCalled();view.rerender(<StoryboardShotBatchTools {...p} canEdit={false}/>);expect((input() as HTMLInputElement).disabled).toBe(true);});
