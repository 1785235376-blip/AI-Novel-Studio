import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, FileSearch, FileUp } from "lucide-react";
import { aiAnalyzeImportReview, api, apiErrorView, createChapterKnowledgeReview, createNovelKnowledgeReview, type ImportReview, type Novel } from "../api";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";
import "./NovelImportPanel.css";

type ImportPreview = {
  title: string;
  chapter_count: number;
  word_count: number;
  chapters: { number: number; title: string; word_count: number }[];
  warnings: string[];
  knowledge_base?: { status: string; candidates?: CandidateGroups };
};
type Candidate = Record<string, unknown>;
type CandidateGroups = Record<string, Candidate[]>;
type ReviewState = {novel:Novel; candidates:CandidateGroups; selected:Record<string,boolean[]>; reviewId?:string; analysis?:ImportReview['analysis']};
type ImportStage="SELECT"|"PARSING"|"PREVIEW"|"IMPORTING"|"REVIEW";
export type NovelImportSource={format:"txt"|"markdown"|"json"|"docx"|"word"|"pdf";content:string;contentBase64?:string;name:string};
export type NovelImportPlan={format:string;title:string;chapters:{number:number;title:string;content:string}[]};
/** Keep browser and DesktopHost import payloads bounded before reading files. */
export const MAX_IMPORT_BYTES=25*1024*1024;

/** Convert a binary file to base64 without placing its bytes in persistent storage. */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

export function NovelImportPanel({ onImported, onConfirm, novelId, chapterId }: { onImported?: (novel: Novel) => void; onConfirm?: (source:NovelImportSource,preview:ImportPreview,plan:NovelImportPlan,report:(message:string)=>void)=>Promise<void>; novelId?:string; chapterId?:string }) {
  const [source, setSource] = useState<NovelImportSource>();
  const [preview, setPreview] = useState<ImportPreview>();
  const [plan, setPlan] = useState<NovelImportPlan>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [status, setStatus] = useState("");
  const [review, setReview] = useState<ReviewState>();
  const [pendingError,setPendingError]=useState<unknown>();
  const [pendingLoading,setPendingLoading]=useState(false);
  const [aiReviewError,setAiReviewError]=useState<unknown>();
  const [stage,setStage]=useState<ImportStage>("SELECT");
  const confirmingRef=useRef(false);
  const interactionRef=useRef(0);
  function reviewState(record:ImportReview):ReviewState{
    const candidates=(record.candidates||{}) as CandidateGroups;
    const selected=record.selected||Object.fromEntries(Object.entries(candidates).map(([kind,items])=>[kind,items.map(()=>false)]));
    return {novel:{id:record.novel_id,title:'当前小说',genre:'',chapter_count:0,word_count:0,status:'ACTIVE'},candidates,selected,reviewId:record.id,analysis:record.analysis};
  }
  useEffect(()=>{
    let active=true;
    setReview(undefined);
    if(!novelId){setPendingError(undefined);setPendingLoading(false);return()=>{active=false}};
    const interaction=interactionRef.current;setPendingLoading(true);setPendingError(undefined);
    void api.importReviewList(novelId).then(result=>{if(active&&interaction===interactionRef.current&&result.pending){setReview(current=>current||reviewState(result.pending!));setStage("REVIEW")}}).catch(reason=>{if(active&&interaction===interactionRef.current)setPendingError(reason)}).finally(()=>{if(active)setPendingLoading(false)});
    return()=>{active=false};
  },[novelId]);

  async function choose(file?: File) {
    if (!file) return;
    interactionRef.current+=1;
    const extension = file.name.split(".").pop()?.toLowerCase();
    const format: NovelImportSource["format"] | undefined = extension === "json" ? "json" : extension === "md" || extension === "markdown" ? "markdown" : extension === "txt" ? "txt" : extension === "docx" ? "docx" : extension === "pdf" ? "pdf" : undefined;
    if (!format) { resetSelection(); setError(new Error("仅支持 TXT、Markdown、JSON、Word (.docx) 和 PDF 文件。")); return; }
    if (file.size===0) { resetSelection(); setError(new Error("不能导入空文件。")); return; }
    if (file.size>MAX_IMPORT_BYTES) { resetSelection(); setError(new Error("导入文件不能超过 25 MiB。")); return; }
    setBusy(true); setStage("PARSING"); setError(undefined); setStatus(""); setSource(undefined); setPreview(undefined); setPlan(undefined);
    try {
      const binary = format === "docx" || format === "pdf";
      const next: NovelImportSource = binary
        ? { format, content: "", contentBase64: bytesToBase64(new Uint8Array(await file.arrayBuffer())), name: file.name }
        : { format, content: await file.text(), name: file.name };
      setSource(next);
      const result = await api.importNovel(next.format, next.content, false, next.contentBase64);
      setPreview(result.preview);
      setPlan(result.plan); setStage("PREVIEW"); setStatus(`已解析 ${result.plan.chapters.length} 章，可确认导入。`);
    } catch (reason) { setError(reason); setStage("SELECT"); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (confirmingRef.current || !source || !preview || !plan) return;
    confirmingRef.current=true;setBusy(true); setStage("IMPORTING"); setError(undefined); setStatus(`正在导入，共 ${plan.chapters.length} 章…`);
    try {
      if(onConfirm) await onConfirm(source,preview,plan,setStatus);
      else {
        const result = await api.importNovel(source.format, source.content, true, source.contentBase64);
        const persisted=result.knowledge_review as ImportReview|undefined;
        const candidates=(persisted?.candidates || result.preview?.knowledge_base?.candidates || {}) as CandidateGroups;
        const groups=(persisted?.selected || Object.fromEntries(Object.entries(candidates).filter(([,items])=>Array.isArray(items)&&items.length).map(([kind,items])=>[kind,items.map(()=>false)]))) as Record<string,boolean[]>;
        if(result.novel && Object.keys(groups).length) {
          setReview({novel:result.novel,candidates,selected:groups,reviewId:persisted?.id});
          setStage("REVIEW");
          setStatus("小说已导入，知识库候选等待审核。正文不会因审核操作被改写。");
        } else if(result.novel) onImported?.(result.novel);
        else throw new Error("导入响应缺少小说项目");
      }
    }
    catch (reason) { setError(reason); setStage("PREVIEW"); setStatus("导入已暂停；再次确认同一文件可从断点继续。"); }
    finally { confirmingRef.current=false;setBusy(false); }
  }

  function resetSelection(){
    interactionRef.current+=1;confirmingRef.current=false;setSource(undefined);setPreview(undefined);setPlan(undefined);setError(undefined);setStatus("");setStage("SELECT");
  }

  async function prepareKnowledgeReview(scope:"chapter"|"project"){
    if(!novelId)return;
    interactionRef.current+=1;setBusy(true);setError(undefined);setAiReviewError(undefined);
    try{
      const record=scope==="chapter"&&chapterId?await createChapterKnowledgeReview(novelId,chapterId):await createNovelKnowledgeReview(novelId);
      setReview(reviewState(record));setStage("REVIEW");setStatus(scope==="chapter"?"已建立当前章节审查任务，可调用 AI 提取资料候选。":"已建立整本小说审查任务，可调用 AI 提取资料候选。");
    }catch(reason){setError(reason)}finally{setBusy(false)}
  }

  async function submitReview(decision:"ACCEPTED"|"REJECTED"|"SKIPPED") {
    if(!review)return;
    setBusy(true);setError(undefined);
    try {
      const selected=decision==='ACCEPTED'?Object.fromEntries(Object.entries(review.candidates).map(([kind,items])=>[kind,items.filter((_,index)=>review.selected[kind]?.[index])]).filter(([,items])=>items.length)):{};
      await api.reviewImportKnowledge(review.novel.id,decision,selected,{reviewId:review.reviewId,selected:review.selected});
      setReview(undefined);setStage("SELECT");setStatus(decision==='ACCEPTED'?"知识库候选已审核并写入所选条目。":decision==='SKIPPED'?"已标记跳过，未写入知识库实体。":"已拒绝本次知识库候选，未写入实体。");onImported?.(review.novel);
    } catch(reason) { setError(reason); }
    finally { setBusy(false); }
  }

  function toggleCandidate(kind:string,index:number) {
    setReview(current=>current?{...current,selected:{...current.selected,[kind]:current.selected[kind].map((value,itemIndex)=>itemIndex===index?!value:value)}}:current);
  }

  function editCandidate(kind:string,index:number,field:string,value:string) {
    setReview(current=>{
      if(!current)return current;
      const items=[...(current.candidates[kind]||[])];
      items[index]={...items[index],[field]:value};
      return {...current,candidates:{...current.candidates,[kind]:items}};
    });
  }

  async function saveReviewDraft(){
    if(!review?.reviewId)return;
    setBusy(true);setError(undefined);
    try{
      const saved=await api.updateImportReview(review.novel.id,review.reviewId,review.candidates,review.selected);
      setReview({...review,...reviewState(saved),novel:review.novel});
      setStatus("候选修改与勾选状态已保存，可稍后继续审核。");
    }catch(reason){setError(reason)}finally{setBusy(false)}
  }

  async function runAiReview(){
    if(!review?.reviewId)return;
    setBusy(true);setError(undefined);setAiReviewError(undefined);setStatus("AI 正在阅读章节并复核资料库候选…");
    try{
      const result=await aiAnalyzeImportReview(review.novel.id,review.reviewId);
      setReview({...review,...reviewState(result.review),novel:review.novel});
      setStatus(`AI 已审查 ${result.analysis.chapter_count||0} 个章节片段，请逐项确认后再写入资料库。`);
    }catch(reason){setAiReviewError(reason);setStatus("AI 审查未完成，已保留原有本地分析候选。")}finally{setBusy(false)}
  }

  function selectAllCandidates() {
    setReview(current=>current?{...current,selected:Object.fromEntries(Object.entries(current.candidates).map(([kind,items])=>[kind,items.map(()=>true)]))}:current);
  }

  return <Panel title={novelId?"资料提取与导入":"导入小说"}>
    {novelId&&!review&&<section className="novel-knowledge-audit"><header><div><h3>从已写章节提取资料</h3><p>AI 只生成待审候选，不会直接改写人物、地点、时间线或伏笔。</p></div><div>{chapterId&&<Button type="button" variant="secondary" disabled={busy} onClick={()=>void prepareKnowledgeReview("chapter")}>审查当前章节</Button>}<Button type="button" variant="secondary" disabled={busy} onClick={()=>void prepareKnowledgeReview("project")}>审查整本小说</Button></div></header></section>}
    <ol className="novel-import-steps" aria-label="导入进度">
      <li className={stage==="SELECT"||stage==="PARSING"?"is-current":"is-complete"}><FileUp aria-hidden="true"/><span>选择文件</span></li>
      <li className={stage==="PREVIEW"||stage==="IMPORTING"?"is-current":stage==="REVIEW"?"is-complete":""}><FileSearch aria-hidden="true"/><span>检查章节</span></li>
      <li className={stage==="REVIEW"?"is-current":""}><Check aria-hidden="true"/><span>导入与资料审核</span></li>
    </ol>
    <label className="novel-import-picker"><FileUp aria-hidden="true"/><span>{busy ? "正在处理…" : source?.name || "选择小说文件"}</span><input type="file" aria-label="选择要导入的小说文件" accept=".txt,.md,.markdown,.json,.docx,.pdf,text/plain,text/markdown,application/json,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf" disabled={busy} onChange={event => {const file=event.target.files?.[0];event.target.value="";void choose(file)}}/></label>
    <p className="novel-help">支持 TXT、Markdown、JSON、Word 和 PDF，单个文件不超过 25 MiB。导入前会先生成预览，不会立即改写项目。</p>
    {Boolean(error) && <ImportError error={error} fallback="无法解析文件。"/>}
    {status && <p className="novel-help" role="status">{status}</p>}
    {!preview && !busy && !review && <EmptyState title="尚未选择文件" detail="选择文件后先检查章节结构，不会立即写入项目。"/>}
    {preview && !review && <div className="novel-import-preview">
      <p><strong>{preview.title}</strong> · {preview.chapter_count} 章 · {preview.word_count} 字</p>
      {preview.warnings.map(item => <p className="novel-help" key={item}>{item}</p>)}
      {preview.knowledge_base?.status === 'CANDIDATES_REVIEW_REQUIRED' && <KnowledgeReviewPlaceholder candidates={preview.knowledge_base.candidates || {}} />}
      <ol>{preview.chapters.map((item,index) => <li key={`${index}:${item.number}:${item.title}`}><span>{item.title}</span><small>{item.word_count} 字</small></li>)}</ol>
      <div className="novel-import-preview__actions"><Button variant="ghost" disabled={busy} onClick={resetSelection}><ArrowLeft aria-hidden="true"/>重新选择文件</Button><Button variant="primary" disabled={busy} onClick={() => void confirm()}>{busy ? "正在导入…" : "确认导入并打开"}</Button></div>
    </div>}
    {pendingLoading&&<p className="novel-help" role="status">正在恢复待审核的知识库候选…</p>}
    {Boolean(pendingError)&&<ImportError error={pendingError} fallback="无法恢复待审核的知识库候选。"/>}
    {Boolean(aiReviewError)&&<ImportError error={aiReviewError} fallback="AI 阅读审查失败，本地候选已保留。"/>}
    {review && <KnowledgeReviewPanel review={review} busy={busy} onAiReview={()=>void runAiReview()} onToggle={toggleCandidate} onEdit={editCandidate} onSelectAll={selectAllCandidates} onSave={()=>void saveReviewDraft()} onAccept={()=>void submitReview("ACCEPTED")} onReject={()=>void submitReview("REJECTED")} onSkip={()=>void submitReview("SKIPPED")} />}
  </Panel>;
}

function KnowledgeReviewPlaceholder({candidates}:{candidates:CandidateGroups}) {
  const labels:Record<string,string>={characters:'人物',locations:'地点',timeline_events:'时间线事件',foreshadowing:'伏笔'};
  const groups=Object.entries(candidates).filter(([,items])=>Array.isArray(items)&&items.length>0);
  const count=groups.reduce((total,[,items])=>total+items.length,0);
  return <section className="novel-import-review-placeholder" aria-labelledby="novel-import-review-title">
    <header><strong id="novel-import-review-title">知识库候选审核</strong><Badge tone="warning">待审核</Badge></header>
    <p>已发现 {count} 项候选。导入阶段不会自动写入人物、地点、时间线或伏笔。</p>
    <dl>{groups.map(([kind,items])=><div key={kind}><dt>{labels[kind] || kind}</dt><dd>{items.length} 项</dd></div>)}</dl>
    <p className="novel-help">服务归属：Novel Knowledge Base Review · API：<code>/api/v1/novels/{'{id}'}/import/knowledge-base/review</code></p>
    <Button type="button" disabled aria-describedby="novel-import-review-help">确认导入后进入审核窗口</Button>
    <p id="novel-import-review-help" className="novel-help">确认导入后会打开基础审核窗口，可逐项接受、全部拒绝或暂缓处理。</p>
  </section>;
}

function KnowledgeReviewPanel({review,busy,onAiReview,onToggle,onEdit,onSelectAll,onSave,onAccept,onReject,onSkip}:{review:ReviewState;busy:boolean;onAiReview:()=>void;onToggle:(kind:string,index:number)=>void;onEdit:(kind:string,index:number,field:string,value:string)=>void;onSelectAll:()=>void;onSave:()=>void;onAccept:()=>void;onReject:()=>void;onSkip:()=>void}) {
  const labels:Record<string,string>={characters:'人物',locations:'地点',timeline_events:'时间线事件',foreshadowing:'伏笔'};
  const groups=Object.entries(review.candidates).filter(([,items])=>items.length);
  const selectedCount=Object.values(review.selected).reduce((total,items)=>total+items.filter(Boolean).length,0);
  function title(item:Candidate,kind:string,index:number){return String(item.name||item.title||item.description||`${labels[kind]||kind} ${index+1}`)}
  return <section className="novel-import-review-panel" aria-labelledby="novel-import-review-panel-title">
    <header><div><strong id="novel-import-review-panel-title">知识库候选审核</strong><p className="novel-help">项目“{review.novel.title}” · 共 {groups.reduce((sum,[,items])=>sum+items.length,0)} 项候选</p></div><Badge tone="warning">等待作者决定</Badge></header>
    <p>勾选后接受的候选才会写入人物、地点、时间线和伏笔资料库；正文和章节版本不会被改写。</p>
    {review.reviewId&&<div className="novel-import-ai-review"><Button type="button" variant="secondary" onClick={onAiReview} disabled={busy}>{busy?'AI 正在阅读…':'AI 阅读审查'}</Button><p className="novel-help">点击后会把有限长度的章节片段发送给主控中配置的文本模型。AI 只更新候选草稿，仍需你确认。</p>{review.analysis?.source==='AI_REVIEW'&&<Badge tone="success">已由 AI 复核 · {review.analysis.model_id||'已配置模型'}</Badge>}</div>}
    <div className="novel-import-review-panel__actions"><Button type="button" variant="ghost" onClick={onSelectAll} disabled={busy}>全选候选</Button>{review.reviewId&&<Button type="button" variant="secondary" onClick={onSave} disabled={busy}>保存候选修改</Button>}<span className="novel-help" aria-live="polite">已选 {selectedCount} 项</span></div>
    {groups.length?<div className="novel-import-review-panel__groups">{groups.map(([kind,items])=><fieldset key={kind}><legend>{labels[kind]||kind}</legend>{items.map((item,index)=>{const field='name' in item?'name':'title' in item?'title':'description';return <label key={`${kind}:${index}`}><input type="checkbox" checked={!!review.selected[kind]?.[index]} disabled={busy} onChange={()=>onToggle(kind,index)}/><input className="novel-import-candidate-title" aria-label={`${labels[kind]||kind}候选 ${index+1}`} value={String(item[field]||title(item,kind,index))} disabled={busy} onChange={event=>onEdit(kind,index,field,event.target.value)}/><small>{String(item.evidence||item.description||'')}</small></label>})}</fieldset>)}</div>:<p className="novel-import-review-panel__empty">当前还没有资料候选。点击“AI 阅读审查”后，模型会依据章节正文生成待确认项目。</p>}
    <p className="novel-help">服务归属：Novel Knowledge Base Review · API：<code>/api/v1/novels/{'{id}'}/import/knowledge-base/review</code></p>
    <footer className="novel-import-review-panel__footer"><Button type="button" variant="primary" disabled={busy||selectedCount===0} onClick={onAccept}>{busy?'处理中…':'接受选中并打开'}</Button><Button type="button" variant="danger" disabled={busy} onClick={onReject}>全部拒绝并打开</Button><Button type="button" variant="ghost" disabled={busy} onClick={onSkip}>标记跳过并打开</Button></footer>
  </section>;
}

function ImportError({error,fallback}:{error:unknown;fallback:string}){
  const view=apiErrorView(error,fallback);
  return <div className="novel-import-error" role="alert"><p className="novel-error">{view.message}</p><p className="novel-import-error__meta">{view.code&&<span>代码：<code>{view.code}</code></span>}{view.requestId&&<span>请求 ID：<code>{view.requestId}</code></span>}{view.details&&<span>详情：<code>{view.details}</code></span>}</p></div>;
}
