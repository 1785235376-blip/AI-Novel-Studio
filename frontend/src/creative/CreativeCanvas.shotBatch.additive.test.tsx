// @vitest-environment jsdom
import {useState} from 'react';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {CreativeCanvas} from './CreativeCanvas';
import {newDocument,newScene,newShot,type CreativeInput} from './types';
afterEach(cleanup);
it('edits explicitly selected shot language through the original canvas and Save, with bounded undo',()=>{
 const initial:CreativeInput={...newDocument('STORYBOARD'),title:'Selected shot language',source_independent:true,scenes:[{...newScene(1),id:'scene'},{...newScene(2),id:'other'}],shots:[{...newShot(1,'scene'),id:'one',frame_prompt:'Keep prompt',video_generation_hint:'Keep video hint',director_note_ids:['note']},{...newShot(2,'scene'),id:'two',duration_seconds:9},{...newShot(3,'other'),id:'three'}]};
 initial.director_notes=[{id:'note',number:1,scene_id:'scene',note:'Original author source',shot_size:'MEDIUM',camera_angle:'EYE_LEVEL',camera_motion:'STATIC',duration_seconds:5,emotion:'',pacing:'',performance:'',blocking:''}];
 const save=vi.fn();function Mounted(){const [draft,setDraft]=useState(initial);return <><CreativeCanvas draft={draft} dirty canEdit busy={false} selectedSceneId="scene" onScene={()=>{}} onShot={()=>{}} onChange={setDraft} onSave={()=>save(draft)} onNew={()=>{}}/><output aria-label="分镜草稿快照">{JSON.stringify(draft)}</output></>}
 render(<Mounted/>);fireEvent.click(screen.getByText('批量设置所选镜头语言'));
 const plan=()=>{fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.click(screen.getByLabelText('批量选择镜头 2 · two'));fireEvent.change(screen.getByLabelText('批量镜头字段'),{target:{value:'camera_motion'}});fireEvent.change(screen.getByLabelText('批量镜头新值'),{target:{value:'PAN'}});fireEvent.click(screen.getByRole('button',{name:'预览所选镜头语言'}));};
 plan();expect(save).not.toHaveBeenCalled();expect(JSON.parse(screen.getByLabelText('分镜草稿快照').textContent!).shots).toEqual(initial.shots);
 fireEvent.click(screen.getByRole('button',{name:'确认批量应用到分镜草稿（尚未保存）'}));let next=JSON.parse(screen.getByLabelText('分镜草稿快照').textContent!);expect(next.shots.map((row:any)=>row.camera_motion)).toEqual(['PAN','PAN','STATIC']);expect(next.shots[0]).toEqual({...initial.shots[0],camera_motion:'PAN'});expect(next.shots[1]).toEqual({...initial.shots[1],camera_motion:'PAN'});expect(next.shots[2]).toEqual(initial.shots[2]);expect(save).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'撤销本次镜头语言批量编辑'}));expect(JSON.parse(screen.getByLabelText('分镜草稿快照').textContent!)).toEqual(initial);
 plan();fireEvent.click(screen.getByRole('button',{name:'确认批量应用到分镜草稿（尚未保存）'}));fireEvent.click(screen.getByRole('button',{name:'保存草稿'}));expect(save).toHaveBeenCalledTimes(1);expect(save.mock.calls[0][0].shots.map((row:any)=>row.camera_motion)).toEqual(['PAN','PAN','STATIC']);
});
