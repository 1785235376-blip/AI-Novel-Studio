import { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/primitives';
import type { CreativeInput } from './types';
import { compareDirectorDraft } from './directorDraftComparison';
export function DirectorDraftComparison({local,server}:{local:CreativeInput;server:CreativeInput}){
  const rows=useMemo(()=>compareDirectorDraft(local,server),[local,server]);
  const [page,setPage]=useState(0);
  useEffect(()=>setPage(0),[local,server]);
  const excerpt=(value:string)=>value.length>3000?`${value.slice(0,3000)}…（仅显示前 3000 字符；完整内容仍在原草稿中）`:value||'（空／不存在）';
  return <section aria-label="导演本地与服务端差异"><h3>放弃前核对差异</h3>
    <p>本地草稿与刚读取的服务端快照有 {rows.length} 项导演作者字段差异。这里只读展示，不自动合并；服务端仍可能继续变化。</p>
    <p>比较标题、来源设置、视觉目标、场景、对白及导演调度。ID、排列和作者依据按原值展示；不包含运行记录、审批状态或权限。</p>
    {!rows.length&&<p>已比较的作者字段一致；这不证明未知保存请求已经成功。</p>}
    <ol>{rows.slice(page*20,(page+1)*20).map(row=><li key={row.path}><details><summary>{row.label}</summary><p>本地：{excerpt(row.local)}</p><p>服务端：{excerpt(row.server)}</p></details></li>)}</ol>
    {rows.length>20&&<><Button type="button" disabled={!page} onClick={()=>setPage(value=>Math.max(0,value-1))}>上一页导演差异</Button><span>第 {page+1} / {Math.ceil(rows.length/20)} 页</span><Button type="button" disabled={(page+1)*20>=rows.length} onClick={()=>setPage(value=>value+1)}>下一页导演差异</Button></>}
  </section>;
}
