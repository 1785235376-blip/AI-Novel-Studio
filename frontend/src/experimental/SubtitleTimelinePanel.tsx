import { useId, useLayoutEffect, useMemo, useRef, useState, type SetStateAction } from 'react';
import { reviewCaptionTransfer } from './captionTransferReview';
import { CaptionHistory } from './CaptionHistory';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { voiceSubtitleClient, downloadCaption, type CaptionCue, type CaptionTrack, type AudioPlan, readCaptionImport, CaptionImportError, type CaptionImportPreview } from './voiceSubtitleClient';
let identity=0;
const newCue=():CaptionCue=>({id:crypto.randomUUID(),start_tick:0,end_tick:1000,text:'',segment_id:null,overlap_reason:''});
export function SubtitleTimelinePanel(props:{client:ExperimentalClient;onOpenAudiobook?:()=>void}) {const key=useMemo(()=>++identity,[props.client]);return <SubtitleContent key={key} {...props}/>;}
function SubtitleContent({client,onOpenAudiobook}:{client:ExperimentalClient;onOpenAudiobook?:()=>void}) {
 const api=useMemo(()=>voiceSubtitleClient(client),[client]);const catalog=useResource(s=>api.captionCatalog(s),[api]);const records=useResource(s=>api.tracks(s),[api]);const action=useReviewAction();
 const [asset,setAsset]=useState(''),[plan,setPlan]=useState(''),[title,setTitle]=useState('字幕'),[rate,setRate]=useState('1000/1');
 const available=!catalog.loading&&!catalog.error&&!!catalog.data;
 const admissionEpoch=useRef(0);
 const refresh=()=>{admissionEpoch.current++;catalog.reload();records.reload();};
 return <section className="experimental-section" aria-label="字幕时间轴"><div className="experimental-actions"><h3>字幕时间轴</h3><Button disabled={action.busy||catalog.loading||records.loading} onClick={refresh}>刷新字幕来源与记录</Button>{onOpenAudiobook&&<Button onClick={onOpenAudiobook}>打开原有声书审核</Button>}</div>
 <StatusMessage>人工时间标记，可编辑整数 tick。媒体时长来自实测；只有 PCM16 WAV 显示实际采样波形。自动 ASR / 音素或逐字对齐、字幕压制均未配置。</StatusMessage>
 <ResourceState loading={catalog.loading} error={catalog.error}/>{!!action.error&&<ErrorMessage error={action.error}/>}<p role="status">{action.notice}</p>
 <Panel title="绑定现有媒体创建字幕版本"><Field label="字幕标题"><input value={title} onChange={e=>setTitle(e.target.value)}/></Field><Field label="字幕绑定媒体"><select disabled={!available||action.busy} value={asset} onChange={e=>setAsset(e.target.value)}><option value="">选择原资产库的音频 / 视频</option>{available&&catalog.data!.assets.map(a=><option key={a.id} value={a.id}>{a.filename} · v{a.version}</option>)}</select></Field>
 <Field label="字幕说话人来源计划"><select disabled={!available||action.busy} value={plan} onChange={e=>setPlan(e.target.value)}><option value="">不关联说话人</option>{available&&catalog.data!.plans.filter(p=>!p.stale).map(p=><option key={p.id} value={p.id}>{p.title} · v{p.version}</option>)}</select></Field>
 <Field label="字幕时间基准"><select value={rate} disabled={action.busy} onChange={e=>setRate(e.target.value)}><option value="1000/1">1000 tick/秒（毫秒）</option><option value="24/1">24 帧/秒</option><option value="24000/1001">24000/1001 帧/秒</option><option value="30000/1001">30000/1001 帧/秒</option></select></Field>
 <Button disabled={action.busy||!available||!asset||!title.trim()} onClick={()=>void action.run(async current=>{const [numerator,denominator]=rate.split('/').map(Number);const selected=catalog.data!.plans.find(p=>p.id===plan);await api.createTrack({asset_id:asset,title,plan_id:plan||null,expected_plan_version:selected?.version??null,timebase:{numerator,denominator},cues:[],language:'zh'});if(current())records.reload();},'字幕草稿已绑定实测媒体，等待填写人工时间标记')}>创建字幕草稿</Button>
 {available&&!catalog.data!.assets.length&&<EmptyState title="暂无可绑定媒体" detail="先在原资产库导入或批准音频 / 视频。这里不会制造时长或假波形。"/>}</Panel>
 <ResourceState loading={records.loading} error={records.error}/>{!records.loading&&!records.error&&!records.data?.items.length&&<EmptyState title="还没有字幕版本" detail="选择实际媒体建立字幕，再逐条编辑时间和文本。"/>}
 {records.data?.items.map(row=><CaptionEditor key={row.id} client={client} admissionEpoch={admissionEpoch} current={row} plans={catalog.data?.plans||[]} available={!records.loading&&!records.error&&available} refresh={records.reload}/>)}
 <StatusMessage>导出支持纯文本 SRT / WebVTT，毫秒量化向下取整并进行实际文件读回校验。目标字幕软件显示：NOT_RUN。字幕元数据导出不会渲染媒体。</StatusMessage>
 </section>;
}
function CaptionEditor({client,current,plans,available,refresh,admissionEpoch}:{admissionEpoch:{current:number};client:ExperimentalClient;current:CaptionTrack;plans:AudioPlan[];available:boolean;refresh:()=>void}) {
 const api=useMemo(()=>voiceSubtitleClient(client),[client]);const action=useReviewAction();const [captured,setCaptured]=useState(current),[cues,updateCues]=useState(current.cues||[]),[split,updateSplit]=useState<Record<string,{tick:string;left:string;right:string}>>({});
 const draftEpoch=useRef(0);
 const [restoreHistoryVersion,setRestoreHistoryVersion]=useState<number>();
 const setSplit=(value:SetStateAction<Record<string,{tick:string;left:string;right:string}>>)=>{draftEpoch.current++;updateSplit(value);};
 const renderedDraft=draftEpoch.current,renderedAdmission=admissionEpoch.current;
 // Reuse semantic epochs: rerenders alone must not retire a valid action.
 // useReviewAction independently fences the keyed client owner and unmount.
 const runAction:typeof action.run=(...args)=>{if(draftEpoch.current!==renderedDraft||admissionEpoch.current!==renderedAdmission)return Promise.resolve();draftEpoch.current++;return action.run(...args);};
 const splitDirty=Object.values(split).some(value=>value.tick||value.left||value.right);
 const setCues=(value:SetStateAction<CaptionCue[]>)=>{draftEpoch.current++;updateCues(value);};
 const changed=current.version!==captured.version, dirty=JSON.stringify(cues)!==JSON.stringify(captured.cues);const unavailable=!available||action.busy||current.stale||changed;
 const plan=plans.find(p=>p.id===current.plan_id);
 const edit=(index:number,key:keyof CaptionCue,value:any)=>setCues(old=>old.map((r,i)=>i===index?{...r,[key]:value}:r));
 const accept=(row:CaptionTrack)=>{setRestoreHistoryVersion(undefined);setCaptured(row);setCues(row.cues);setSplit({});refresh();};
 const waveform=current.media?.waveform;
 const [reviewOpen,setReviewOpen]=useState(false);const reviewId=useId();const cueInputs=useRef<(HTMLTextAreaElement|null)[]>([]);
 const review=useMemo(()=>reviewOpen&&!unavailable?reviewCaptionTransfer(captured,cues):{issues:[],cues:[],speakerCount:0,overlapCount:0},[reviewOpen,unavailable,captured,cues]);
 if(current.stale)return <Panel title="字幕来源已变化"><StatusMessage tone="warning">媒体、说话人或原文已变化。旧字幕和波形已隐藏，导出已停止；请按当前来源创建新字幕版本。</StatusMessage></Panel>;
 return <Panel title={`${current.title} · v${current.version}`}><Badge>人工时间标记 · {current.timebase.numerator}/{current.timebase.denominator} tick/秒</Badge><p>实测媒体：{current.media.duration_seconds.numerator}/{current.media.duration_seconds.denominator} 秒</p>
 {changed&&<StatusMessage tone="warning">字幕版本已变化，本地编辑仍保留。请检查并载入当前版本后继续。</StatusMessage>}{!!action.error&&<ErrorMessage error={action.error}/>}<p role="status">{action.notice}</p>
 <Button disabled={action.busy} onClick={()=>{setRestoreHistoryVersion(undefined);setCaptured(current);setCues(current.cues);setSplit({});}}>载入当前字幕并替换本地输入</Button>
 <p role="status">{dirty?'未保存：本地字幕已修改。':'本地字幕与已载入版本一致。'}</p>
 {restoreHistoryVersion!==undefined&&<StatusMessage>本地字幕来自历史 v{restoreHistoryVersion}，尚未保存；后续编辑仍保留历史来源校验。保存将创建新版本，不恢复审批或处理任务权限。</StatusMessage>}
 <CaptionHistory client={client} row={captured} cues={cues} binding={JSON.stringify({current,captured,available,unavailable,draftEpoch:draftEpoch.current,admissionEpoch:admissionEpoch.current})} disabled={!!unavailable} dirty={dirty||splitDirty} draftEpoch={draftEpoch} admissionEpoch={admissionEpoch} replace={(value,version)=>{setRestoreHistoryVersion(version);setCues(value);setSplit({});}}/>
 <CaptionImport client={client} row={captured} binding={JSON.stringify({current,captured,available,unavailable,draftEpoch:draftEpoch.current,admissionEpoch:admissionEpoch.current})} disabled={!!unavailable} dirty={dirty||splitDirty} draftEpoch={draftEpoch} admissionEpoch={admissionEpoch} replace={value=>{setRestoreHistoryVersion(undefined);setCues(value);setSplit({});}}/>
 {waveform?.status==='MEASURED_PCM16_PEAKS'&&waveform.peaks?<details className="experimental-details"><summary>实测 PCM16 波形</summary><svg role="img" aria-label="实际音频采样峰值波形" viewBox={`0 0 ${waveform.peaks.length} 100`} width="100%" height="100" preserveAspectRatio="none"><path stroke="currentColor" fill="none" d={waveform.peaks.map((p,i)=>`M${i} ${50-p*50}V${50+p*50}`).join(' ')}/></svg><p>峰值包络；不是语音或单词对齐。</p></details>:<p>此媒体无可用实测波形，仍可人工编辑时间。</p>}
 <ol aria-label="字幕轨道预览">{cues.map(c=><li key={c.id}>{c.start_tick} → {c.end_tick} tick · {c.segment_id?current.speakers?.[c.segment_id]?.name||'说话人待刷新':'无说话人标签'} · {c.text}</li>)}</ol>
 {cues.map((cue,index)=><article className="experimental-record" key={cue.id}><h4>字幕 {index+1}</h4><div className="experimental-grid"><Field label={`字幕 ${index+1} 开始 tick`}><input type="number" min={0} disabled={unavailable} value={cue.start_tick} onChange={e=>edit(index,'start_tick',Number(e.target.value))}/></Field><Field label={`字幕 ${index+1} 结束 tick`}><input type="number" min={1} disabled={unavailable} value={cue.end_tick} onChange={e=>edit(index,'end_tick',Number(e.target.value))}/></Field></div>
 <Field label={`字幕 ${index+1} 文本`}><textarea ref={element=>{cueInputs.current[index]=element;}} disabled={unavailable} value={cue.text} onChange={e=>edit(index,'text',e.target.value)}/></Field><Field label={`字幕 ${index+1} 说话人片段`}><select disabled={unavailable||!plan} value={cue.segment_id||''} onChange={e=>edit(index,'segment_id',e.target.value||null)}><option value="">无说话人标签</option>{plan?.segments?.map(s=><option key={s.id} value={s.id}>{s.character_id||'未分配'} · {s.text.slice(0,40)}</option>)}</select></Field>
 <Field label={`字幕 ${index+1} 有意重叠说明`}><input disabled={unavailable} value={cue.overlap_reason} onChange={e=>edit(index,'overlap_reason',e.target.value)}/></Field><Button disabled={unavailable} onClick={()=>setCues(old=>old.filter(c=>c.id!==cue.id))}>删除本地字幕行 {index+1}</Button>
 <details className="experimental-details"><summary>拆分 / 合并字幕 {index+1}</summary><p>先保存现有编辑；拆分点和左右文本需人工指定。</p><Field label={`字幕 ${index+1} 拆分 tick`}><input type="number" value={split[cue.id]?.tick||''} onChange={e=>setSplit(old=>({...old,[cue.id]:{...(old[cue.id]||{tick:'',left:'',right:''}),tick:e.target.value}}))}/></Field><Field label={`字幕 ${index+1} 拆分左文`}><textarea value={split[cue.id]?.left||''} onChange={e=>setSplit(old=>({...old,[cue.id]:{...(old[cue.id]||{tick:'',left:'',right:''}),left:e.target.value}}))}/></Field><Field label={`字幕 ${index+1} 拆分右文`}><textarea value={split[cue.id]?.right||''} onChange={e=>setSplit(old=>({...old,[cue.id]:{...(old[cue.id]||{tick:'',left:'',right:''}),right:e.target.value}}))}/></Field>
 <Button disabled={unavailable||dirty||restoreHistoryVersion!==undefined||!split[cue.id]?.left||!split[cue.id]?.right} onClick={()=>void runAction(async isCurrent=>{const value=split[cue.id];const row=await api.split(captured,cue,Number(value.tick),value.left,value.right);if(isCurrent())accept(row);},'字幕已按人工时间点拆分')}>拆分字幕 {index+1}</Button><Button disabled={unavailable||dirty||restoreHistoryVersion!==undefined||index===cues.length-1} onClick={()=>void runAction(async isCurrent=>{const row=await api.merge(captured,cue,cues[index+1]);if(isCurrent())accept(row);},'相邻同说话人字幕已合并')}>合并下一条字幕</Button></details></article>)}
 <div className="experimental-actions"><Button disabled={unavailable} onClick={()=>setCues(old=>[...old,newCue()])}>添加人工字幕行</Button><Button disabled={unavailable||(!dirty&&restoreHistoryVersion===undefined)} onClick={()=>void runAction(async isCurrent=>{const row=await api.saveCues(captured,cues,restoreHistoryVersion);if(isCurrent())accept(row);},'字幕已保存；来源版本和媒体绑定保持校验')}>保存字幕版本</Button>{(['srt','vtt'] as const).map(format=><Button key={format} disabled={unavailable||dirty||!cues.length} onClick={()=>void runAction(async isCurrent=>{const blob=await api.download(captured,format);if(isCurrent())downloadCaption(blob,`captions-${captured.id}.${format}`);},'字幕文件已通过读回检查并准备下载')}>下载 {format.toUpperCase()}</Button>)}</div>
 <Button disabled={unavailable} aria-expanded={reviewOpen} aria-controls={reviewId} onClick={()=>setReviewOpen(value=>!value)}>检查字幕交付兼容性</Button>
 {reviewOpen&&!unavailable&&<section id={reviewId} aria-label="字幕交付兼容性检查"><h4>本地字幕交付检查</h4>
 <p>原字幕 {captured.id} · v{captured.version}{dirty?' · 当前未保存输入；先保存并重新核对说话人绑定，再下载。':''} · 媒体 {captured.asset_id}{captured.asset_snapshot&&<> · v{captured.asset_snapshot.version} · {captured.asset_snapshot.digest}</>}</p>
 <StatusMessage tone={review.issues.length?'warning':'info'}>{review.issues.length?`${review.issues.length} 项需要处理`:'本地时间与纯文字检查通过；目标时间线时长、文件字节数和当前来源仍须原服务校验。'}</StatusMessage>
 <ul>{review.issues.map((issue,index)=><li key={index}>{issue.cue!==null?`字幕 ${issue.cue}：`:''}{issue.message}{issue.cue!==null&&<Button onClick={()=>cueInputs.current[issue.cue!-1]?.focus()}>定位字幕 {issue.cue}</Button>}</li>)}</ul>
 <p>以下为毫秒向下量化预览。{review.speakerCount} 条说话人标签成为普通文本，{review.overlapCount} 条重叠需人工核对；原说话人 ID、重叠说明、字幕版本和媒体来源绑定不会随 SRT/VTT 传入 Timeline。</p>
 <ol aria-label="字幕毫秒交付预览">{review.cues.map((cue,index)=><li key={index}>{cue.startMs} → {cue.endMs} ms{cue.quantized?' · 有亚毫秒精度损失':''} · {cue.text}</li>)}</ol>
 <p>保存后使用原下载 SRT / VTT。到原 Timeline 的“时间线与字幕交换”选择导入和对应文件，读取转换预览，核对目标媒体、时长及被替换的全部字幕，再明确确认保存新版本。导入替换全部字幕；不会自动偏移、缩放或绑定来源，也没有跨模块一键回滚。</p>
 </section>}
 {!!current.warnings?.length&&<Details label="读速 / 行长提示（未经语言校准的启发式）" value={current.warnings}/>}</Panel>;
}

// Preview is read-only. Its lifetime is narrower than the editor's local draft.
function CaptionImport({client,row,binding,disabled,dirty,draftEpoch,admissionEpoch,replace}:{admissionEpoch:{current:number};client:ExperimentalClient;row:CaptionTrack;binding:string;disabled:boolean;dirty:boolean;draftEpoch:{current:number};replace:(cues:CaptionCue[])=>void}) {
 const api=useMemo(()=>voiceSubtitleClient(client),[client]);
 const alive=useRef(true), owner=useRef({binding,client}), selection=useRef(0), pending=useRef<object|null>(null);
 const [file,setFile]=useState<File|null>(null),[busyOwner,setBusyOwner]=useState<object|null>(null),[error,setError]=useState<unknown>(),[preview,setPreview]=useState<{value:CaptionImportPreview;owner:object;selection:number;draft:number}|null>(null);
 if(owner.current.binding!==binding||owner.current.client!==client){owner.current={binding,client};pending.current=null;}
 const capturedOwner=owner.current, capturedSelection=selection.current, capturedDraft=draftEpoch.current, capturedAdmission=admissionEpoch.current;
 const busy=busyOwner===capturedOwner;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;pending.current=null;};},[]);
 const active=()=>alive.current&&!disabled&&owner.current===capturedOwner&&admissionEpoch.current===capturedAdmission&&draftEpoch.current===capturedDraft&&selection.current===capturedSelection;
 const valid=preview&&preview.owner===capturedOwner&&preview.selection===capturedSelection&&preview.draft===capturedDraft&&!disabled;
 const start=async()=>{
  if(!active()||!file||pending.current)return;
  const ticket={};pending.current=ticket;setBusyOwner(capturedOwner);setError(undefined);setPreview(null);
  const current=()=>active()&&pending.current===ticket;
  try {
   const bytes=await readCaptionImport(file);if(!current())return;
   const value=await api.importPreview(row,bytes.format,bytes.content_base64);if(!current())return;
   if(value.record_id!==row.id||value.expected_version!==row.version||value.asset_id!==row.asset_id||!value.asset_snapshot||value.asset_snapshot.version!==row.asset_snapshot?.version||value.asset_snapshot.digest!==row.asset_snapshot?.digest||value.timebase?.numerator!==row.timebase.numerator||value.timebase?.denominator!==row.timebase.denominator||value.content_sha256!==bytes.content_sha256||value.byte_length!==bytes.byte_length||value.format!==bytes.format||!Array.isArray(value.cues)||!value.cues.length||value.cues.length>500||!value.cues.every(c=>typeof c.id==='string'&&c.id.trim().length>0&&Array.from(c.id).length<=240&&Number.isSafeInteger(c.start_tick)&&Number.isSafeInteger(c.end_tick)&&c.start_tick>=0&&c.end_tick>c.start_tick&&typeof c.text==='string'&&c.text.trim().length>0&&Array.from(c.text).length<=10000&&c.segment_id===null&&c.overlap_reason==='')||new Set(value.cues.map(c=>c.id)).size!==value.cues.length||!Array.isArray(value.warnings))throw new CaptionImportError('导入预览与当前文件或媒体绑定不匹配，请重新读取预览。');
   setPreview({value,owner:capturedOwner,selection:capturedSelection,draft:capturedDraft});
  } catch(value) {if(current())setError(value);}
  finally {if(pending.current===ticket){pending.current=null;if(alive.current)setBusyOwner(null);}}
 };
 return <section aria-label="导入字幕文件"><h4>导入 SRT / VTT</h4>
 <p>选择 UTF-8 文件（最多 192000 字节），先读取转换预览。所有时间必须精确表示为当前整数 tick；不会自动调整时间或绑定说话人。</p>
 <Field label="字幕导入文件"><input type="file" accept=".srt,.vtt" disabled={disabled} onChange={event=>{if(!active())return;selection.current++;pending.current=null;setBusyOwner(null);setFile(event.target.files?.[0]||null);setPreview(null);setError(undefined);}}/></Field>
 <Button disabled={disabled||busy||!file} onClick={()=>void start()}>{busy?'正在读取字幕预览':'读取字幕导入预览'}</Button>
 {!!error&&(error instanceof CaptionImportError?<StatusMessage tone="error">{error.message}</StatusMessage>:<ErrorMessage error={error}/>)}
 {preview&&!valid&&<StatusMessage tone="warning">文件、字幕输入或来源已变化，旧导入预览已失效。请重新读取预览；本地输入仍保留。</StatusMessage>}
 {valid&&<section aria-label="字幕导入转换预览"><p>{file?.name} · {preview.value.byte_length} 字节 · {preview.value.format.toUpperCase()} · {preview.value.cues.length} 条字幕</p>
 <p>目标字幕 {row.id} · v{row.version} · 媒体 {row.asset_id} · {row.timebase.numerator}/{row.timebase.denominator} tick/秒</p>
 <StatusMessage tone="warning">{dirty?'将替换全部本地字幕，包括尚未保存的修改及拆分输入。':'将替换全部本地字幕。'}确认后仍为未保存输入，请核对后使用“保存字幕版本”。</StatusMessage>
 <ol aria-label="导入字幕预览行">{preview.value.cues.map(c=><li key={c.id}>{c.start_tick} → {c.end_tick} tick · {c.text}</li>)}</ol>
 {!!preview.value.warnings.length&&<Details label="导入读速 / 行长提示" value={preview.value.warnings}/>}
 <Button disabled={disabled||busy} onClick={()=>{if(!active()||!valid||preview.owner!==owner.current||preview.selection!==selection.current||preview.draft!==draftEpoch.current)return;selection.current++;setPreview(null);setError(undefined);replace(preview.value.cues.map(c=>({id:c.id,start_tick:c.start_tick,end_tick:c.end_tick,text:c.text,segment_id:c.segment_id,overlap_reason:c.overlap_reason})));}}>确认替换全部本地字幕（尚未保存）</Button>
 </section>}
 </section>;
}
