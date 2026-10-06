import {AlertCircle,CheckCircle2,LoaderCircle,PencilLine} from 'lucide-react';
import {Button} from './primitives';
import type {DraftDurability} from '../drafts';

export type SaveState='saved'|'dirty'|'saving'|'failed'|'conflict';
export type SaveEvent=
  |{type:'hydrate';hasDraft:boolean;hasConflict:boolean}
  |{type:'edit'}
  |{type:'save-started'}
  |{type:'save-succeeded';hasNewerChanges:boolean}
  |{type:'save-failed';conflict?:boolean};

export function reduceSaveState(state:SaveState,event:SaveEvent):SaveState {
  if(event.type==='hydrate')return event.hasConflict?'conflict':event.hasDraft?'dirty':'saved';
  if(event.type==='edit')return 'dirty';
  if(event.type==='save-started')return 'saving';
  if(event.type==='save-succeeded')return event.hasNewerChanges?'dirty':'saved';
  if(event.type==='save-failed')return event.conflict?'conflict':'failed';
  return state;
}

export function saveStateLabel(state:SaveState):string {
  if(state==='saved')return '已保存';
  if(state==='dirty')return '有未保存修改';
  if(state==='saving')return '保存中…';
  if(state==='conflict')return '保存冲突，请先处理';
  return '保存失败，请重试';
}

export function recoveryStateLabel(state:SaveState,durability:DraftDurability,composing=false,offline=false):string {
  if(composing)return '正在输入…';
  if(state==='saved')return '后端已保存';
  if(state==='saving')return '正在提交，等待后端确认…';
  if(state==='conflict')return '保存冲突，请先处理';
  if(offline)return durability==='durable'?'离线草稿已写入当前浏览器，后端未确认':'离线草稿仅在页面内存，尚未落盘';
  if(state==='failed')return '后端未确认保存，请重试';
  return durability==='durable'?'草稿已写入本机，待提交':'草稿仅在内存，尚未落盘';
}

export function SaveControls({state,ready,onSave,composing=false,recovery}:{state:SaveState;ready:boolean;onSave:()=>void;composing?:boolean;recovery?:{durability:DraftDurability;offline?:boolean;onExport:()=>void;onConflict?:()=>void}}) {
  const label=ready?(recovery?recoveryStateLabel(state,recovery.durability,composing,recovery.offline):saveStateLabel(state)):'正在打开章节…',Icon=!ready?LoaderCircle:state==='saved'?CheckCircle2:state==='dirty'?PencilLine:state==='saving'?LoaderCircle:AlertCircle;
  const blocked=!ready||composing||state==='saving'||state==='conflict';
  return <div className="save-controls"><span className={`save-status save-status--${ready?state:'loading'}`} role="status" aria-live={ready&&(state==='failed'||state==='conflict')?'polite':'off'}><Icon aria-hidden="true"/>{label}</span><Button type="button" disabled={blocked} onClick={onSave}>保存</Button>{ready&&recovery&&state==='conflict'&&recovery.onConflict&&<Button type="button" onClick={recovery.onConflict}>查看冲突</Button>}{ready&&recovery&&state!=='saved'&&<Button type="button" onClick={recovery.onExport}>导出当前草稿</Button>}</div>;
}
