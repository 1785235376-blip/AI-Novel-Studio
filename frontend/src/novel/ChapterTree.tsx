import {useEffect, useId, useRef, useState} from 'react';
import {GripVertical, MoreHorizontal, Pencil, Trash2} from 'lucide-react';
import {Badge, Button, EmptyState, IconButton, Panel} from '../ui/primitives';
import './novel.css';
import {useT,useTz} from '../i18n'; // [HERMIA-FE-20261025 I18N P2] rail「更多」chapter tree visible strings

export type ChapterTreeItem={id:string;title:string;number?:number;status?:string;wordCount?:number;version?:number};
export type ChapterTreeProps={chapters:ChapterTreeItem[];selectedId?:string;loading?:boolean;error?:string|null;creating?:boolean;reordering?:boolean;onSelect:(id:string)=>void;onCreate:(title:string)=>Promise<void>|void;onRename?:(id:string,title:string)=>Promise<void>|void;onReorder?:(sourceId:string,targetId:string)=>Promise<void>|void;onArchive?:(chapter:ChapterTreeItem)=>Promise<void>|void;onRestore?:(chapter:ChapterTreeItem)=>Promise<void>|void;onDelete?:(chapter:ChapterTreeItem)=>Promise<void>|void;archived?:ChapterTreeItem[];message?:string};

export function CreateChapterDialog({open,pending=false,onSubmit,onClose}:{open:boolean;pending?:boolean;onSubmit:(title:string)=>Promise<void>|void;onClose:()=>void}){
 const input=useRef<HTMLInputElement>(null),dialog=useRef<HTMLElement>(null),[title,setTitle]=useState(''),id=useId();
 const [submitting,setSubmitting]=useState(false),inFlight=useRef(false),composing=useRef(false);
 const close=useRef(onClose),busy=useRef(pending);close.current=onClose;busy.current=pending||submitting;
 useEffect(()=>{
  if(!open)return;
  const previous=document.activeElement;
  setTitle('');composing.current=false;input.current?.focus();
  const onKey=(event:KeyboardEvent)=>{
   // Escape/Enter from an active IME candidate window belong to the IME.
   if(event.isComposing||event.keyCode===229||composing.current)return;
   if(event.key==='Escape'){
    event.preventDefault();event.stopPropagation();
    if(!busy.current&&!inFlight.current)close.current();
   }
   if(event.key==='Tab'){
    const controls=Array.from(dialog.current?.querySelectorAll<HTMLElement>('input:not(:disabled),button:not(:disabled),[tabindex="0"]')||[]);
    const first=controls[0],last=controls[controls.length-1];
    if(!first){event.preventDefault();dialog.current?.focus();return;}
    if(!dialog.current?.contains(document.activeElement)){event.preventDefault();first.focus();}
    else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
   }
  };
  document.addEventListener('keydown',onKey);
  return()=>{document.removeEventListener('keydown',onKey);if(previous instanceof HTMLElement&&previous.isConnected)previous.focus();};
 },[open]);
 const t=useT();
 if(!open)return null;
 const disabled=pending||submitting;
 return <div className="novel-dialog-backdrop" role="presentation"><section ref={dialog} tabIndex={-1} className="novel-dialog" role="dialog" aria-modal="true" aria-labelledby={id}>
  <h2 id={id}>{t('ct.new')}</h2><form onCompositionStart={()=>{composing.current=true}} onCompositionEnd={()=>{composing.current=false}} onSubmit={async e=>{
   e.preventDefault();if(disabled||inFlight.current||composing.current||!title.trim())return;
   inFlight.current=true;setSubmitting(true);
   try{await onSubmit(title.trim());}finally{inFlight.current=false;setSubmitting(false);}
  }}><label>{t('ct.chTitle')}<input ref={input} value={title} disabled={disabled} onChange={e=>setTitle(e.target.value)}/></label><div className="novel-actions"><Button type="button" onClick={onClose} disabled={disabled}>{t('ct.cancel')}</Button><Button variant="primary" type="submit" disabled={disabled}>{t('ct.create')}</Button></div></form>
 </section></div>;
}

export function ChapterTree({chapters,selectedId,loading=false,error,creating=false,reordering=false,onSelect,onCreate,onRename,onReorder,onArchive,onRestore,onDelete,archived=[],message}:ChapterTreeProps){
 const [createOpen,setCreateOpen]=useState(false),[renameId,setRenameId]=useState<string>(),[rename,setRename]=useState(''),[archiveTarget,setArchiveTarget]=useState<ChapterTreeItem>(),[deleteTarget,setDeleteTarget]=useState<ChapterTreeItem>(),[dragId,setDragId]=useState<string>();
 useEffect(()=>{if(!archiveTarget)return;const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();setArchiveTarget(undefined)}};document.addEventListener('keydown',onKey);return()=>document.removeEventListener('keydown',onKey)},[archiveTarget]);
 const t=useT(),tz=useTz(); // [HERMIA-FE-20261025 VERA-FIX P2] 状态徽章走字典
 const beginRename=(c:ChapterTreeItem)=>{setRenameId(c.id);setRename(c.title)};
 const commitRename=async()=>{if(renameId&&rename.trim()){await onRename?.(renameId,rename.trim());setRenameId(undefined)}};
 return <Panel className="novel-chapter-tree" title={t('ct.title')} actions={loading||error?undefined:<Button onClick={()=>setCreateOpen(true)}>{t('ct.new')}</Button>} /* [HERMIA-FE-20261025 VERA-FIX P0-3] 读取中/失败不给新建入口 */>
  {(message||reordering)&&<p role="status">{reordering?t('ct.reordering'):message}</p>}
  {loading?<p role="status">{t('ct.loading')}</p>:error?<div className="novel-error" role="alert">{t('ct.loadErr',{err:error})}</div>:chapters.length===0?<EmptyState title={t('ct.emptyTitle')} detail={t('ct.emptyDetail')}/>:<nav aria-label={t('ct.list')}><ol>{chapters.map(c=><li key={c.id} draggable={!!onReorder&&!reordering} onDragStart={event=>{setDragId(c.id);event.dataTransfer.effectAllowed='move'}} onDragEnd={()=>setDragId(undefined)} onDragOver={event=>{if(dragId&&dragId!==c.id){event.preventDefault();event.dataTransfer.dropEffect='move'}}} onDrop={event=>{event.preventDefault();const source=dragId;setDragId(undefined);if(source&&source!==c.id)void onReorder?.(source,c.id)}}><div className={`${c.id===selectedId?'novel-tree-row is-selected':'novel-tree-row'}${dragId===c.id?' is-dragging':''}`}>
   {renameId===c.id?<form className="novel-tree-rename" onSubmit={e=>{e.preventDefault();void commitRename()}}><input aria-label={t('ct.chTitle')} autoFocus value={rename} onChange={e=>setRename(e.target.value)}/><Button type="submit">{t('ct.save')}</Button><Button type="button" onClick={()=>setRenameId(undefined)}>{t('ct.cancel')}</Button></form>:<>{onReorder&&<span className="novel-tree-drag" title={t('ct.drag')}><GripVertical aria-hidden="true"/></span>}<button className="novel-tree-select" aria-current={c.id===selectedId?'page':undefined} onClick={()=>onSelect(c.id)}><span className="novel-tree-title" title={c.title}>{c.number!==undefined?`${c.number}. `:''}{c.title}</span>{c.status&&<Badge>{tz(c.status)}</Badge>}</button><span className="novel-tree-actions">{onRename&&<IconButton label={t('ct.rename',{title:c.title})} title={t('ct.rename',{title:c.title})} onClick={()=>beginRename(c)}><Pencil aria-hidden="true"/></IconButton>}{onArchive&&<IconButton label={t('ct.more',{title:c.title})} title={t('ct.more',{title:c.title})} onClick={()=>setArchiveTarget(c)}><MoreHorizontal aria-hidden="true"/></IconButton>}</span></>}
  </div></li>)}</ol></nav>}
  {onRestore&&<section aria-labelledby="archived-heading" className="novel-archive-entry"><h3 id="archived-heading">{t('ct.archived')}</h3>{archived.length===0?<p>{t('ct.noArchived')}</p>:<ul>{archived.map(c=><li key={c.id}><span className="novel-archive-title" title={c.title}>{c.number!==undefined?`${c.number}. `:''}{c.title}</span><Button variant="ghost" onClick={()=>onRestore(c)}>{t('ct.restore')}</Button>{onDelete&&<IconButton label={t('ct.delete',{title:c.title})} onClick={()=>setDeleteTarget(c)}><Trash2 aria-hidden="true"/></IconButton>}</li>)}</ul>}</section>}
  <CreateChapterDialog open={createOpen} pending={creating} onClose={()=>setCreateOpen(false)} onSubmit={async v=>{await onCreate(v);setCreateOpen(false)}}/>
  {archiveTarget&&<div className="novel-dialog-backdrop" role="presentation"><section className="novel-dialog" role="dialog" aria-modal="true" aria-labelledby="archive-heading"><h2 id="archive-heading">将“{archiveTarget.title}”移出正文目录？</h2><p>章节正文、版本历史和相关资料都会保留，之后可以从“已移出章节”中恢复。</p><div className="novel-actions"><Button onClick={()=>setArchiveTarget(undefined)}>取消</Button><Button variant="primary" onClick={async()=>{await onArchive?.(archiveTarget);setArchiveTarget(undefined)}}>移出正文目录</Button></div></section></div>}
  {deleteTarget&&<div className="novel-dialog-backdrop" role="presentation"><section className="novel-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-chapter-heading"><h2 id="delete-chapter-heading">永久删除“{deleteTarget.title}”？</h2><p>正文、版本历史和章节关联将被永久删除，此操作无法撤销。</p><div className="novel-actions"><Button onClick={()=>setDeleteTarget(undefined)}>取消</Button><Button variant="danger" onClick={async()=>{await onDelete?.(deleteTarget);setDeleteTarget(undefined)}}>永久删除章节</Button></div></section></div>}
 </Panel>;
}
