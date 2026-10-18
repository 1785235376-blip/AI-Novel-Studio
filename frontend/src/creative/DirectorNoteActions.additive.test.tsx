// @vitest-environment jsdom
import {useState} from 'react';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {editDirectorNote} from './directorNoteEditing';
import {DirectorNoteActions} from './DirectorNoteActions';
import {CreativeCanvas} from './CreativeCanvas';
import {newDocument,newScene,type DirectorSceneNote} from './types';
afterEach(cleanup);
function fixture(){const a={...newScene(1),id:'scene-a'},b={...newScene(2),id:'scene-b'};const note=(id:string,number:number,scene_id:string):DirectorSceneNote=>({id,number,scene_id,note:id,blocking:'keep',shot_size:'WIDE',camera_angle:'EYE_LEVEL',camera_motion:'STATIC',duration_seconds:5,emotion:'quiet',pacing:'slow',performance:'wait',performances:[{character:'A',action:'stand',expression:'calm',state:'waiting'}]});return {...newDocument('DIRECTOR'),title:'Director',source_independent:true,scenes:[a,b],director_notes:[note('first',1,a.id),note('other-scene',2,b.id),note('last',3,a.id)]};}
it('reorders within the selected scene without rewriting other scene or note evidence',()=>{const draft=fixture(),before=structuredClone(draft),next=editDirectorNote(draft,'last','earlier');expect(next.director_notes.map(r=>[r.id,r.number])).toEqual([['last',1],['other-scene',2],['first',3]]);expect(next.director_notes[1]).toEqual(before.director_notes[1]);expect(draft).toEqual(before);expect(editDirectorNote(draft,'first','earlier')).toBe(draft);});
it('duplicates detached author detail under a new stable ID, with bounded unique numbering',()=>{const draft=fixture(),next=editDirectorNote(draft,'first','duplicate',()=> 'new-note');expect(next.director_notes.map(r=>[r.id,r.number])).toEqual([['first',1],['new-note',2],['other-scene',3],['last',4]]);next.director_notes[1].performances![0].action='changed';expect(draft.director_notes[0].performances![0].action).toBe('stand');expect(()=>editDirectorNote(draft,'first','duplicate',()=> 'first')).toThrow();const full={...draft,director_notes:Array.from({length:200},(_,i)=>({...draft.director_notes[0],id:`n${i}`,number:i+1}))};expect(()=>editDirectorNote(full,'n0','duplicate')).toThrow(/200/);});
it('uses original canvas onChange and explicit save without auto-saving',()=>{const save=vi.fn();function Harness(){const [draft,setDraft]=useState(fixture());return <CreativeCanvas draft={draft} dirty canEdit busy={false} selectedSceneId="scene-a" onScene={()=>{}} onShot={()=>{}} onChange={setDraft} onSave={()=>save(draft)} onNew={()=>{}}/>;}render(<Harness/>);fireEvent.click(screen.getByText('后移导演调度 1'));expect(save).not.toHaveBeenCalled();fireEvent.click(screen.getByText('复制导演调度 1'));expect(save).not.toHaveBeenCalled();fireEvent.click(screen.getByText('保存草稿'));expect(save).toHaveBeenCalledTimes(1);expect(save.mock.calls[0][0].director_notes).toHaveLength(4);});
it('removes only the selected top-level note without renumbering or mutating any surviving author content',()=>{
 const draft=fixture(),before=structuredClone(draft),next=editDirectorNote(draft,'first','remove');
 expect(next.director_notes).toEqual([before.director_notes[1],before.director_notes[2]]);
 expect(next.scenes).toBe(draft.scenes);expect(draft).toEqual(before);
 const bound={...draft,shots:[{director_note_ids:['first']}] as any};expect(()=>editDirectorNote(bound,'first','remove')).toThrow(/引用/);expect(bound.director_notes).toHaveLength(3);
 expect(()=>editDirectorNote(draft,'unknown','remove')).toThrow();
});
it('requires a draft-bound explicit removal confirmation and leaves persistence to the original Save action',()=>{
 const save=vi.fn();function Harness(){const [draft,setDraft]=useState(fixture());return <CreativeCanvas draft={draft} dirty canEdit busy={false} selectedSceneId="scene-a" onScene={()=>{}} onShot={()=>{}} onChange={setDraft} onSave={()=>save(draft)} onNew={()=>{}}/>;}
 render(<Harness/>);
 const remove=()=>screen.getByRole('button',{name:'从当前草稿移除调度 1',hidden:true}) as HTMLButtonElement;
 expect(remove().disabled).toBe(true);fireEvent.click(screen.getByLabelText('确认移除导演调度 1'));expect(remove().disabled).toBe(false);
 fireEvent.click(screen.getByText('复制导演调度 1'));expect(remove().disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('确认移除导演调度 1'));fireEvent.click(remove());
 expect(screen.queryByText('移除导演调度 1')).toBeNull();expect(save).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('保存草稿'));expect(save.mock.calls[0][0].director_notes.map((r:any)=>r.id)).not.toContain('first');expect(save.mock.calls[0][0].director_notes).toHaveLength(3);
});
function retained<T>(element:HTMLElement,name:string):T{const key=Object.keys(element).find(key=>key.startsWith('__reactProps$'))!;return (element as unknown as Record<string,Record<string,T>>)[key][name];}
it.each(['uncheck','draft change','permission ABA','unmount'])('does not reuse removal consent after %s',mode=>{
 const draft=fixture(),onChange=vi.fn(),props={draft,noteId:'first',disabled:false,onChange};const view=render(<DirectorNoteActions {...props}/>);
 fireEvent.click(screen.getByLabelText('确认移除导演调度 1'));
 const remove=retained<()=>void>(screen.getByRole('button',{name:'从当前草稿移除调度 1',hidden:true}),'onClick');
 if(mode==='uncheck'){
  const uncheck=retained<(event:any)=>void>(screen.getByLabelText('确认移除导演调度 1'),'onChange');act(()=>{uncheck({target:{checked:false}});remove();});
 }else{if(mode==='draft change')view.rerender(<DirectorNoteActions {...props} draft={{...draft,title:'Changed'}}/>);
 else if(mode==='permission ABA'){view.rerender(<DirectorNoteActions {...props} disabled/>);view.rerender(<DirectorNoteActions {...props}/>);}else view.unmount();act(remove);}
 expect(onChange).not.toHaveBeenCalled();
});
