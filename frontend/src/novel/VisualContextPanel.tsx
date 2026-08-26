import {useMemo,useState} from 'react';
import {Image,RefreshCw,SlidersHorizontal} from 'lucide-react';
import {useQueries,useQuery} from '@tanstack/react-query';
import {api} from '../api';
import {Badge,Button,EmptyState,Panel,Spinner,StatusMessage} from '../ui/primitives';
import './VisualContextPanel.css';

type Props={novelId?:string;characterId?:string;sceneId?:string;chapterId?:string};
const text=(v:unknown,f='未记录')=>typeof v==='string'&&v.trim()?v.trim():f;
export function VisualContextPanel({novelId,characterId,sceneId,chapterId}:Props){
 const [include,setInclude]=useState<Record<string,boolean>>({character:true,location:true,scene:true,chapter:true,assets:true});
 const novel=useQuery({queryKey:['visual-novel',novelId],queryFn:()=>api.novel(novelId!),enabled:!!novelId});
 const resources=['characters','locations','volumes','scenes'];
 const qs=useQueries({queries:resources.map(resource=>({queryKey:['visual-context',novelId,resource],queryFn:()=>api.resource(novelId!,resource),enabled:!!novelId}))});
 const chapters=useQuery({queryKey:['visual-chapters',novelId],queryFn:()=>api.chapters(novelId!),enabled:!!novelId});
 const assets=useQuery({queryKey:['visual-assets',novelId,characterId,sceneId],queryFn:()=>api.assets(novelId!,undefined,characterId,sceneId),enabled:!!novelId});
 const rows=useMemo(()=>({characters:(qs[0].data||[]) as any[],locations:(qs[1].data||[]) as any[],volumes:(qs[2].data||[]) as any[],scenes:(qs[3].data||[]) as any[]}),[qs]);
 if(!novelId)return <Panel title="Visual Context"><EmptyState title="尚未打开小说" detail="打开小说项目后，图片生成会读取真实视觉上下文。"/></Panel>;
 const loading=novel.isLoading||chapters.isLoading||assets.isLoading||qs.some(q=>q.isLoading),error=novel.error||chapters.error||assets.error||qs.find(q=>q.error)?.error;
 const character=rows.characters.find(r=>String(r.id)===String(characterId)),scene=rows.scenes.find(r=>String(r.id)===String(sceneId)),chapter=(chapters.data||[]).find((r:any)=>String(r.id)===String(chapterId||scene?.chapter_id)),volume=rows.volumes.find(r=>String(r.id)===String(scene?.volume_id));
 const context=[['character','角色设定',character&&`${text(character.name||character.title)} · 身份：${text(character.role)} · 年龄：${text(character.age)} · 外貌：${text(character.appearance||character.personality)} · 服装：${text(character.clothing)}`],['location','当前地点',scene?.location_id?text(rows.locations.find(r=>String(r.id)===String(scene.location_id))?.name):'未关联地点'],['scene','场景',scene&&`${text(scene.title)} · 目标：${text(scene.purpose)} · 冲突：${text(scene.conflict)}`],['chapter','剧情位置',chapter&&`第 ${chapter.number||''} 章 · ${text(chapter.title)}${volume?` · ${text(volume.title)}`:''}`],['assets','关联视觉资产',assets.data?.length?`${assets.data.length} 个已保存资产`:'暂无已关联视觉资产']] as const;
 return <Panel title="Visual Context" actions={<Button variant="ghost" onClick={()=>{void novel.refetch();void chapters.refetch();void assets.refetch();qs.forEach(q=>void q.refetch())}}><RefreshCw aria-hidden="true"/>刷新</Button>}>
   <section className="visual-context" aria-label="图片生成视觉上下文"><header><div><strong>{text(novel.data?.title,'当前小说')}</strong><p>生成前确认实际纳入提示词的上下文，不会修改 Canon。</p></div><Badge tone="info"><Image aria-hidden="true"/>只读预览</Badge></header>
   {loading?<div className="visual-context__loading" role="status"><Spinner size="sm"/>正在读取视觉上下文…</div>:error?<StatusMessage tone="error">视觉上下文读取失败，请重试。</StatusMessage>:<><div className="visual-context__controls"><strong>纳入提示词</strong>{context.map(([key,label])=><label key={key}><input type="checkbox" checked={include[key]} onChange={e=>setInclude(v=>({...v,[key]:e.target.checked}))}/>{label}</label>)}<SlidersHorizontal aria-hidden="true"/></div><dl>{context.map(([key,label,value])=>include[key]&&<div key={key}><dt>{label}</dt><dd>{value||'未记录'}</dd></div>)}</dl>{!context.some(([key])=>include[key])&&<EmptyState title="尚未选择上下文" detail="勾选需要纳入提示词的真实资料。"/>}</>}
   </section>
 </Panel>;
}
