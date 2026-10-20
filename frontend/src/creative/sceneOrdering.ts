import type {CreativeInput} from './types';
/** Reorder existing author scenes without retargeting notes, shots or source evidence. */
export function moveAuthorScene(draft:CreativeInput,id:string,direction:'earlier'|'later'):CreativeInput{
 if(!['SCREENPLAY','DIRECTOR'].includes(draft.mode)||!['earlier','later'].includes(direction)||draft.scenes.length>200)throw new Error('当前文档不支持此场景排序。');
 const rows=[...draft.scenes].sort((a,b)=>a.sequence-b.sequence);
 if(new Set(rows.map(row=>row.id)).size!==rows.length||new Set(rows.map(row=>row.sequence)).size!==rows.length||rows.some(row=>!row.id||!Number.isSafeInteger(row.sequence)||row.sequence<1||row.sequence>10000))throw new Error('请先核对场景身份和顺序。');
 const index=rows.findIndex(row=>row.id===id);if(index<0)throw new Error('当前场景不存在。');
 const other=index+(direction==='earlier'?-1:1);if(other<0||other>=rows.length)return draft;
 const selected=rows[index],neighbor=rows[other];rows[index]={...neighbor,sequence:selected.sequence};rows[other]={...selected,sequence:neighbor.sequence};
 return {...draft,scenes:rows};
}
