import {CreativeShotNavigator} from './CreativeShotNavigator';
// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {CreativeSceneNavigator} from './CreativeSceneNavigator';
import {CreativeCanvas} from './CreativeCanvas';
import {newDocument,newScene,newShot,type CreativeInput} from './types';
const draft:CreativeInput={...newDocument('DIRECTOR'),title:'Navigator',source_independent:true,scenes:[{...newScene(1),id:'one',heading:'庭院',location:'神社',action:'等待'},{...newScene(2),id:'two',heading:'山门',time:'黄昏',characters:['旅人'],action:'转身离开'}],director_notes:[{id:'note',number:1,scene_id:'two',note:'逆光剪影',blocking:'靠近鸟居',shot_size:'WIDE',camera_angle:'EYE_LEVEL',camera_motion:'STATIC',duration_seconds:5,emotion:'calm',pacing:'slow',performance:''}]};
afterEach(cleanup);
it('lets a read-only viewer navigate scenes while all document editing fields stay disabled',()=>{
 const onScene=vi.fn(),onChange=vi.fn(),onSave=vi.fn();render(<CreativeCanvas draft={draft} canEdit={false} busy={false} dirty={false} version={1} selectedSceneId="one" onScene={onScene} onShot={vi.fn()} onChange={onChange} onSave={onSave} onNew={vi.fn()}/>);
 const navigator=screen.getByRole('region',{name:'场景导航与筛选'});expect(navigator.closest('fieldset')).toBeNull();expect((screen.getByLabelText('场景标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
 fireEvent.click(within(navigator).getByRole('button',{name:/山门/}));expect(onScene).toHaveBeenCalledWith('two');expect(onChange).not.toHaveBeenCalled();expect(onSave).not.toHaveBeenCalled();
});
it('filters local scene and Director text without modifying data or changing selection',()=>{
 const before=structuredClone(draft),onSelect=vi.fn();render(<CreativeSceneNavigator draft={draft} selectedId="one" busy={false} onSelect={onSelect}/>);
 fireEvent.change(screen.getByLabelText('搜索当前文档场景'),{target:{value:'黄昏 逆光'}});expect(screen.getByRole('button',{name:/山门/})).toBeTruthy();expect(screen.queryByRole('button',{name:/庭院/})).toBeNull();expect(screen.getByText('当前选中场景未匹配，正文仍保留在下方。')).toBeTruthy();expect(onSelect).not.toHaveBeenCalled();expect(draft).toEqual(before);
 fireEvent.click(screen.getByText('清除场景筛选'));expect(screen.getByRole('button',{name:/庭院/})).toBeTruthy();expect(onSelect).not.toHaveBeenCalled();
});
it('blocks busy, replaced-document and unmounted retained navigation callbacks',()=>{
 const onSelect=vi.fn(),props={draft,selectedId:'one',busy:false,onSelect};const view=render(<CreativeSceneNavigator {...props}/>);const button=screen.getByRole('button',{name:/山门/}),callback=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;
 view.rerender(<CreativeSceneNavigator {...props} busy/>);act(()=>callback());view.rerender(<CreativeSceneNavigator {...props} draft={structuredClone(draft)}/>);act(()=>callback());view.unmount();act(()=>callback());expect(onSelect).not.toHaveBeenCalled();
});
it('keeps read-only shot navigation separate from the disabled authoring controls',()=>{
 const value={...draft,mode:'STORYBOARD' as const,director_notes:[],shots:[{...newShot(1,'one'),id:'shot-one'},{...newShot(2,'two'),id:'shot-two',frame_prompt:'旅人背影',lens:'50mm'}]},onScene=vi.fn(),onShot=vi.fn(),onChange=vi.fn();
 render(<CreativeCanvas draft={value} canEdit={false} busy={false} dirty={false} version={1} selectedSceneId="one" selectedShotId="shot-one" onScene={onScene} onShot={onShot} onChange={onChange} onSave={vi.fn()} onNew={vi.fn()}/>);
 const nav=screen.getByRole('region',{name:'镜头导航与筛选'});expect(nav.closest('fieldset')).toBeNull();fireEvent.change(screen.getByLabelText('搜索当前文档镜头'),{target:{value:'50mm 旅人'}});fireEvent.click(within(nav).getByRole('button',{name:/定位镜头 2/}));expect(onShot).toHaveBeenCalledWith('shot-two');expect(onScene).toHaveBeenCalledWith('two');expect(onChange).not.toHaveBeenCalled();
});
it('rejects retained shot navigation after document replacement or unmount',()=>{
 const value={...draft,shots:[{...newShot(1,'one'),id:'shot-one'}]},onSelect=vi.fn();const view=render(<CreativeShotNavigator draft={value} busy={false} onSelect={onSelect}/>);const button=screen.getByRole('button',{name:/定位镜头 1/}),callback=(button as any)[Object.keys(button).find(k=>k.startsWith('__reactProps$'))!].onClick;
 view.rerender(<CreativeShotNavigator draft={structuredClone(value)} busy={false} onSelect={onSelect}/>);act(()=>callback());view.unmount();act(()=>callback());expect(onSelect).not.toHaveBeenCalled();
});
it('does not carry scene or shot query text into a replaced document',()=>{
 const view=render(<CreativeSceneNavigator draft={draft} busy={false} onSelect={vi.fn()}/>);fireEvent.change(screen.getByLabelText('搜索当前文档场景'),{target:{value:'private-query'}});view.rerender(<CreativeSceneNavigator draft={structuredClone(draft)} busy={false} onSelect={vi.fn()}/>);expect((screen.getByLabelText('搜索当前文档场景') as HTMLInputElement).value).toBe('');view.unmount();
 const value={...draft,shots:[{...newShot(1,'one'),id:'shot-one'}]},shotView=render(<CreativeShotNavigator draft={value} busy={false} onSelect={vi.fn()}/>);fireEvent.change(screen.getByLabelText('搜索当前文档镜头'),{target:{value:'private-shot-query'}});shotView.rerender(<CreativeShotNavigator draft={structuredClone(value)} busy={false} onSelect={vi.fn()}/>);expect((screen.getByLabelText('搜索当前文档镜头') as HTMLInputElement).value).toBe('');
});
