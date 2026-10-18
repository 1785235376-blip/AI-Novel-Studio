import {useEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {editDirectorNote,type DirectorNoteAction} from './directorNoteEditing';
import type {CreativeInput} from './types';
type Props={draft:CreativeInput;noteId:string;disabled:boolean;onChange:(value:CreativeInput)=>void};
export function DirectorNoteActions(props:Props){
 const live=useRef(props);live.current=props;const alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const lifetime=useRef({draft:props.draft,disabled:props.disabled,noteId:props.noteId,token:{}});
 if(lifetime.current.draft!==props.draft||lifetime.current.disabled!==props.disabled||lifetime.current.noteId!==props.noteId)lifetime.current={draft:props.draft,disabled:props.disabled,noteId:props.noteId,token:{}};
 const token=lifetime.current.token,[error,setError]=useState<{token:object;text:string}>();
 const note=props.draft.director_notes.find(row=>row.id===props.noteId);if(!note)return null;
 const same=props.draft.director_notes.filter(row=>row.scene_id===note.scene_id).sort((a,b)=>a.number-b.number),index=same.findIndex(row=>row.id===note.id);
 function apply(action:DirectorNoteAction){if(!alive.current||live.current.disabled||lifetime.current.token!==token||live.current.noteId!==props.noteId)return;
  try{const next=editDirectorNote(props.draft,props.noteId,action);if(next!==props.draft)live.current.onChange(next);}catch(reason){setError({token,text:reason instanceof Error?reason.message:'导演调度编辑未完成。'});}}
 return <div className="creative-actions"><Button disabled={props.disabled||index<=0} onClick={()=>apply('earlier')}>前移导演调度 {note.number}</Button><Button disabled={props.disabled||index>=same.length-1} onClick={()=>apply('later')}>后移导演调度 {note.number}</Button><Button disabled={props.disabled||props.draft.director_notes.length>=200} onClick={()=>apply('duplicate')}>复制导演调度 {note.number}</Button>{error?.token===token&&<StatusMessage tone="warning">{error.text}</StatusMessage>}</div>;
}
