import type { CreativeInput } from './types';
export type DirectorDraftDifference = { path: string; label: string; local: string; server: string };
const text = (value: unknown): string => value == null ? '' : typeof value === 'string' ? value : JSON.stringify(value, null, 2) ?? '';
const fields = (record: unknown, keys: readonly string[]) => Object.fromEntries(keys.map(key => [key, record && typeof record === 'object' ? (record as Record<string, unknown>)[key] ?? null : null]));
const noteKeys = ['number', 'scene_id', 'note', 'blocking', 'shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'emotion', 'pacing', 'performance', 'shot_suggestion', 'composition', 'lens', 'character_state', 'lighting', 'color_palette', 'material', 'transition'] as const;
const labels: Record<string, string> = { title:'标题',mode:'类型',source_independent:'独立创作',source_chapter_ids:'章节来源',sequence:'场景顺序',source_chapter_id:'场景章节来源',heading:'场景标题',time:'时间',location:'地点',characters:'角色',action:'动作',dialogue:'对白',emotion:'情绪',number:'调度编号',scene_id:'调度场景',note:'导演意图',blocking:'场面调度',shot_size:'景别',camera_angle:'机位角度',camera_motion:'运镜',duration_seconds:'时长',pacing:'节奏',performance:'表演指导',shot_suggestion:'镜头建议',composition:'构图',lens:'焦距',character_state:'角色状态',lighting:'灯光',color_palette:'色彩',material:'材质',transition:'转场',performances:'角色表演',planning:'理由与依据',style:'视觉风格',atmosphere:'氛围',reference_works:'参考作品',color:'视觉色彩',rhythm:'视觉节奏',genre:'题材' };
function authorNote(value: any) {
  return { ...fields(value,noteKeys), performances:(value?.performances || []).map((row: unknown)=>fields(row,['character','action','expression','state'])), planning:value?.planning ? {
    ...fields(value.planning,['rationale','sequence_reason','duration_reason','uncertainty','assumptions']),
    alternatives:(value.planning.alternatives||[]).map((row:unknown)=>fields(row,['choice','tradeoff'])),
    evidence:(value.planning.evidence||[]).map((row:unknown)=>fields(row,['scene_id','field','dialogue_index','excerpt'])) } : null };
}
/** Explicit author-field projection: never compare/export server metadata or unknown properties. */
export function compareDirectorDraft(local: CreativeInput, server: CreativeInput): DirectorDraftDifference[] {
  const left = new Map<string,{label:string;value:unknown}>(), right = new Map<string,{label:string;value:unknown}>();
  function collect(draft:CreativeInput, result:typeof left) {
    const add=(path:string,label:string,value:unknown)=>result.set(path,{label,value});
    for(const key of ['title','mode','source_independent','source_chapter_ids'] as const) add(key,labels[key],draft[key]);
    for(const key of ['style','atmosphere','reference_works','color','rhythm','genre'] as const) add(`visual/${key}`,`视觉目标 · ${labels[key]}`,draft.visual_target?.[key]);
    add('scene-order','场景排列',draft.scenes.map(row=>row.id));
    add('note-order','导演调度排列',draft.director_notes.map(row=>row.id));
    function notes(rows:any[],prefix:string,label:string){for(const row of rows){add(JSON.stringify([prefix,row.id,'exists']),`${label} ${row.number ?? row.id} · 存在`,true);for(const [key,value] of Object.entries(authorNote(row)))add(JSON.stringify([prefix,row.id,key]),`${label} ${row.number ?? row.id} · ${labels[key] || key}`,value);}}
    for(const scene of draft.scenes){const prefix=JSON.stringify(['scene',scene.id]),label=`场景 ${scene.sequence}`;add(`${prefix}/exists`,`${label} · 存在`,true);
      for(const key of ['sequence','source_chapter_id','heading','time','location','characters','action','emotion'] as const)add(`${prefix}/${key}`,`${label} · ${labels[key]}`,scene[key]);
      add(`${prefix}/dialogue`,`${label} · 对白`,scene.dialogue.map(row=>fields(row,['speaker','text','delivery'])));
      add(`${prefix}/note-order`,`${label} · 内嵌调度排列`,scene.director_notes.map(row=>row.id));notes(scene.director_notes,`${prefix}/notes`,`${label} 内嵌调度`);
    }
    notes(draft.director_notes,'notes','导演调度');
  }
  collect(local,left);collect(server,right);
  return [...new Set([...left.keys(),...right.keys()])].flatMap(path=>{
    const a=left.get(path),b=right.get(path),local=text(a?.value),server=text(b?.value);
    return local===server?[]:[{path,label:b?.label||a!.label,local,server}];
  });
}
