import {AlertCircle,CheckCircle2,LoaderCircle,PencilLine} from 'lucide-react';
import {Button} from './primitives';

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

export function SaveControls({state,ready,onSave}:{state:SaveState;ready:boolean;onSave:()=>void}) {
  const label=ready?saveStateLabel(state):'正在打开章节…',Icon=!ready?LoaderCircle:state==='saved'?CheckCircle2:state==='dirty'?PencilLine:state==='saving'?LoaderCircle:AlertCircle;
  const blocked=!ready||state==='saving'||state==='conflict';
  return <div className="save-controls"><span className={`save-status save-status--${ready?state:'loading'}`} role="status" aria-live={ready&&(state==='failed'||state==='conflict')?'polite':'off'}><Icon aria-hidden="true"/>{label}</span><Button type="button" disabled={blocked} onClick={onSave}>保存</Button></div>;
}
