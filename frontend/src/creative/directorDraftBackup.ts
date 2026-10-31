import {documentInput,type CreativeDocument,type CreativeInput} from './types';
import type {PlanningSnapshot} from './studioProductionGraphContract';
/** Human-readable recovery copy only. Never a server save or execution receipt. */
export function directorDraftBackup(draft:CreativeInput,base:CreativeDocument|undefined,pin:PlanningSnapshot|undefined,uncertain:boolean):Blob{
 if(draft.mode!=='DIRECTOR')throw new Error('只能备份当前导演作者草稿。');
 const reference=base?{id:base.id,version:base.version,...(pin&&pin.id===base.id&&pin.version===base.version?{digest:pin.digest}:{})}:null;
 const payload={contract:'studio-director-author-draft-backup/1',boundary:'LOCAL_AUTHOR_RECOVERY_COPY',server_save_confirmed:false,execution_authority:false,
  save_outcome:uncertain?'UNKNOWN_OR_CONFLICT':'LOCAL_UNSAVED',base_reference:reference,draft:documentInput(draft)};
 const text=JSON.stringify(payload,null,2)+'\n',blob=new Blob([text],{type:'application/json'});
 if(blob.size>2*1024*1024)throw new Error('本地导演备份超过 2 MiB，未下载；原草稿保持不变。');
 return blob;
}
