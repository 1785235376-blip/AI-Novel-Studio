import {creativeId,type CreativeInput} from './types';
export type DirectorNoteAction='earlier'|'later'|'duplicate'|'remove';
/** Original author draft only; source scene/evidence and stable existing IDs stay. */
export function editDirectorNote(draft:CreativeInput,id:string,action:DirectorNoteAction,newId:()=>string=creativeId):CreativeInput{
 if(!['earlier','later','duplicate','remove'].includes(action)||draft.mode!=='DIRECTOR'||draft.director_notes.length>200)throw new Error('导演调度草稿不可编辑。');
 const rows=[...draft.director_notes].sort((a,b)=>a.number-b.number),index=rows.findIndex(row=>row.id===id);
 if(index<0||new Set(rows.map(r=>r.id)).size!==rows.length||new Set(rows.map(r=>r.number)).size!==rows.length)throw new Error('导演调度身份或顺序不完整。');
 const selected=rows[index];if(!draft.scenes.some(scene=>scene.id===selected.scene_id))throw new Error('导演调度场景不存在。');
 if(action==='remove'){
  if(draft.shots.some(shot=>shot.director_note_ids?.includes(id)))throw new Error('该调度仍被当前镜头引用，请先在原编辑器核对关联。');
  return {...draft,director_notes:draft.director_notes.filter(row=>row.id!==id)};
 }
 if(action==='duplicate'){
  if(rows.length>=200)throw new Error('导演调度已达到 200 条上限。');
  const nextId=newId();if(!nextId||rows.some(row=>row.id===nextId))throw new Error('新导演调度身份无效。');
  rows.splice(index+1,0,{...structuredClone(selected),id:nextId});
  return {...draft,director_notes:rows.map((row,i)=>({...row,number:i+1}))};
 }
 const same=rows.filter(row=>row.scene_id===selected.scene_id),position=same.findIndex(row=>row.id===id),neighbor=same[position+(action==='earlier'?-1:1)];
 if(!neighbor)return draft;
 const other=rows.findIndex(row=>row.id===neighbor.id);
 rows[index]={...neighbor,number:selected.number};rows[other]={...selected,number:neighbor.number};
 return {...draft,director_notes:rows};
}
