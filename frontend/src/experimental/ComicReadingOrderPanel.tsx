import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { ComicDocument } from './comicLayoutsClient';
import { previewComicReadingOrder } from './comicReadingOrder';
type Props={document:ComicDocument;scope:object;disabled:boolean;getRevision:()=>number;onApply:(document:ComicDocument)=>boolean};
export function ComicReadingOrderPanel(props:Props){
 type Preview={value:ReturnType<typeof previewComicReadingOrder>;token:object;revision:number};
 const [preview,setPreview]=useState<Preview>(),[error,setError]=useState(''),[confirmed,setConfirmed]=useState(false);
 const alive=useRef(true),proof=useRef(preview),consent=useRef<Preview>();proof.current=preview;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const values=[props.document,props.scope,props.disabled,props.getRevision()];const owner=useRef({values,token:{}});if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};const token=owner.current.token;
 const live=useRef(props);live.current=props;const current=()=>alive.current&&!live.current.disabled&&owner.current.token===token;
 const visible=preview&&preview.token===token&&preview.revision===props.getRevision()?preview:undefined;
 function clear(){proof.current=undefined;consent.current=undefined;setPreview(undefined);setConfirmed(false);setError('');}
 return <details aria-label="漫画阅读顺序整理"><summary>按原坐标规则整理编号</summary><p>采用原服务的从上到下、同一纵坐标从左到右规则，只改阅读编号。格框、气泡、图片和原镜头绑定都不移动。不能据此判断叙事顺序，也不会解决重叠或批准排版。</p>
  <Button disabled={props.disabled} onClick={()=>{if(!current())return;clear();try{const next={value:previewComicReadingOrder(props.document),token,revision:props.getRevision()};proof.current=next;setPreview(next);}catch(reason){setError(reason instanceof Error?reason.message:'编号预览失败。');}}}>预览按坐标整理编号</Button>
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  {visible&&<section aria-label="漫画编号变更预览"><p>{visible.value.changes.length} 个格框的编号将变化，草稿尚未修改。</p><ul>{visible.value.changes.map(row=><li key={row.id}>{row.id}：{Number.isFinite(row.before)?row.before:'无效'} → {row.after}</li>)}</ul>
   <label><input type="checkbox" checked={confirmed} disabled={props.disabled||!visible.value.changes.length} onChange={event=>{if(current()){consent.current=event.target.checked?visible:undefined;setConfirmed(event.target.checked);}}}/>已核对编号，只修改阅读顺序</label>
   <Button disabled={props.disabled||!confirmed||!visible.value.changes.length} onClick={()=>{if(!current()||proof.current!==visible||consent.current!==visible||visible.revision!==live.current.getRevision())return;clear();if(!props.onApply(visible.value.document))setError('当前来源或输入已变化，未应用，请重新预览。');}}>应用阅读编号到本地草稿</Button>
  </section>}
 </details>;
}
