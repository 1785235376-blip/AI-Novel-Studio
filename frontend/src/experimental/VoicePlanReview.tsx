import { useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { Details } from './shared';
import type { AudioPlan, AudioSegment, VoiceCatalog } from './voiceSubtitleClient';

// Read only: these are saved owner records, never inferred speakers or runtime capabilities.
export function voiceAssignmentIssues(plan: AudioPlan, item: AudioSegment, catalog: VoiceCatalog): string[] {
 const issues: string[] = [];
 const characters = catalog.characters.filter(c => c.id === item.character_id);
 const profiles = catalog.profiles.filter(p => p.id === item.profile_id);
 if (!item.id || plan.segments?.filter(s => s.id === item.id).length !== 1) issues.push('片段 ID 缺失或重复，不能精确定位');
 if (item.kind === 'DIALOGUE' && (!item.character_id || characters.length !== 1 || item.character_id === '__narrator__')) issues.push('对白说话人未分配、缺失或有歧义');
 if (item.kind === 'NARRATION' && item.character_id !== '__narrator__') issues.push('旁白归属与原旁白 ID 不一致');
 if (item.attribution_status === 'NEEDS_REVIEW') issues.push('说话人归属仍待人工核对');
 if (!item.profile_id || profiles.length !== 1) issues.push('声音 Profile 未分配、缺失或有歧义');
 const profile = profiles.length === 1 ? profiles[0] : undefined;
 if (profile && (!Number.isSafeInteger(item.profile_version) || profile.version !== item.profile_version)) issues.push('声音 Profile 版本不一致或未记录；不会自动改绑');
 const emotion = item.direction?.emotion ?? item.emotion ?? 'neutral';
 if (emotion !== 'neutral' && profile?.supports_emotion !== true) issues.push('已保存情绪缺少 Profile 支持声明；实际运行能力仍未验证');
 if (!item.direction?.text_reviewed) issues.push('朗读文本尚未人工确认');
 if (!item.direction?.voice_authorized) issues.push('声音使用授权尚未人工确认');
 if (item.character_id && (plan.segments || []).some(s => s.character_id === item.character_id && s.profile_id && item.profile_id && (s.profile_id !== item.profile_id || s.profile_version !== item.profile_version))) issues.push('同一说话人在本计划使用不同声音或版本；请确认是否有意安排');
 return issues;
}
export function VoicePlanReview({plan,catalog,available,onLocate}:{plan:AudioPlan;catalog:VoiceCatalog;available:boolean;onLocate:(item:AudioSegment)=>void}) {
 const [page,setPage]=useState(0);
 const segments=plan.segments || [], pages=Math.max(1,Math.ceil(segments.length/20)), current=Math.min(page,pages-1);
 return <Panel title="已保存声音分配核对">
  <StatusMessage>核对计划 {plan.id} · v{plan.version} 的已保存片段，不包含下方未保存输入。仅提示配置一致性；同人多音色可能是作者意图，情绪支持声明不代表实际验证。定位只聚焦原编辑器，修改后仍须手动保存和审核。</StatusMessage>
  <Details label="原章节版本与摘要快照（非历史正文回放）" value={plan.sources || {}}/>
  <p>第 {current+1} / {pages} 页，每页最多 20 个已保存片段。</p>
  <Button disabled={current===0} onClick={()=>setPage(current-1)}>上一页声音核对</Button><Button disabled={current+1>=pages} onClick={()=>setPage(current+1)}>下一页声音核对</Button>
  <ol start={current*20+1}>{segments.slice(current*20,current*20+20).map((item,index)=>{
   const issues=voiceAssignmentIssues(plan,item,catalog);
   const profile=catalog.profiles.filter(p=>p.id===item.profile_id);
   const unique=!!item.id&&segments.filter(s=>s.id===item.id).length===1;
   return <li key={`${current*20+index}:${item.id}`}>
    <p>片段 {current*20+index+1} · {item.id} · {item.kind} · 说话人 {item.character_id || '未分配'} · Profile {item.profile_id || '未分配'} / v{item.profile_version ?? '未知'} · 情绪 {item.direction?.emotion ?? item.emotion ?? 'neutral'}</p>
    {issues.length?<ul>{issues.map(issue=><li key={issue}>{issue}</li>)}</ul>:<p>已保存配置未发现上述问题；不代表音色质量、运行能力或审核通过。</p>}
    <Details label={`片段 ${current*20+index+1} 原来源与音频证据`} value={{source_start:item.source_start,source_end:item.source_end,source_text_digest:item.source_text_digest,character_snapshot:plan.character_snapshots?.[item.character_id || ''],audio_asset_id:item.audio_asset_id,audio_source:item.audio_source,start_ms:item.start_ms,end_ms:item.end_ms,profile:profile.length===1?{id:profile[0].id,version:profile[0].version,provider_id:profile[0].provider_id,model_id:profile[0].model_id,voice_id:profile[0].voice_id,supports_emotion:profile[0].supports_emotion}:null}}/>
    <Button disabled={!available||!unique} onClick={()=>onLocate(item)}>定位声音片段 {current*20+index+1}</Button>
   </li>;
  })}</ol>
 </Panel>;
}
