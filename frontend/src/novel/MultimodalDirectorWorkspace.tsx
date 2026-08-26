import { useEffect, useState } from 'react';
import { Film, Image, Plus, Trash2 } from 'lucide-react';
import { Button, Panel } from '../ui/primitives';
import { api } from '../api';
import { DirectorShotCard } from './DirectorShotCard';
import { DirectorShotList } from './DirectorShotList';
import { useMultimodalBindingManifest } from './useMultimodalBindingManifest';
import { BindingManifestPanel } from './BindingManifestPanel';
import { useMultimodalWorkspacePersistence } from './useMultimodalWorkspacePersistence';
import { ConstraintImportPreview } from './ConstraintImportPreview';
import './MultimodalDirectorWorkspace.css';
export type DirectorShot = { shot_id?: string; screenplay_id?: string; motion_task_id?: string; binding_candidates?: string[]; binding_source?: 'auto' | 'manual'; constraint_status?: 'saving' | 'confirmed' | 'pending_confirmation' | 'failed'; transition?: string; transition_duration?: string; keyframes?: string[]; name: string; duration: string; camera: string; action: string; profile?: string; props?: string; dialogue?: string; ambience?: string; sound_effect?: string; music?: string; subtitle?: string; voice?: string; emotion?: string };

export function MultimodalDirectorWorkspace({ mode, novelId, onConstraintsChange, onShotsChange }: { mode: 'image' | 'video'; novelId?: string; onConstraintsChange?: (constraints: Record<string, unknown>) => void; onShotsChange?: (shots: DirectorShot[]) => void }) {
  const [uri, setUri] = useState(''); const [role, setRole] = useState(mode === 'image' ? '角色' : '白膜');
  const defaultShot: DirectorShot = { shot_id: 'shot-01', name: '镜头 01', duration: '4s', camera: '中近景，缓慢推进', action: '角色抬头，光线从左侧掠过', profile: '', props: '' };
  const persistence = useMultimodalWorkspacePersistence(`multimodal-workspace:${novelId || 'workspace'}:${mode}`, [defaultShot]);
  const refs = persistence.refs; const setRefs = persistence.setRefs;
  const shots = persistence.shots.length ? persistence.shots : [defaultShot]; const setShots = persistence.setShots;
  const [assets, setAssets] = useState<any[]>([]);
  const [voiceResults, setVoiceResults] = useState<Record<number,{loading?:boolean;uri?:string;error?:string}>>({});
  const [snapshotNote, setSnapshotNote] = useState('');
  const [importMessage, setImportMessage] = useState('');
  const [importMeta, setImportMeta] = useState<{mode?:string;editor_view?:string;status?:string}>({});
  const [pendingImport, setPendingImport] = useState<any>(null);
  const advancedShotsKey = `multimodal-advanced-shots:${novelId || 'workspace'}`;
  const [advancedShots, setAdvancedShots] = useState(() => { try { return localStorage.getItem(advancedShotsKey) === 'true'; } catch { return false; } });
  useEffect(() => { try { localStorage.setItem(advancedShotsKey, String(advancedShots)); } catch { /* optional */ } }, [advancedShots, advancedShotsKey]);
  const [consistency, setConsistency] = useState({ character: '', wardrobe: '', scene: '', lighting: '', time: '', props: '' });
  const bindings = useMultimodalBindingManifest(`multimodal-bindings:${novelId || 'workspace'}`);
  const [consistencyLocked, setConsistencyLocked] = useState(false);
  const [propAssetIds, setPropAssetIds] = useState<string[]>([]);
  const [profiles, setProfiles] = useState<{name:string;data:typeof consistency;locked?:boolean}[]>([]); const [profileName, setProfileName] = useState('默认档案');
  const consistencyKey = `multimodal-consistency:${novelId || 'workspace'}:${mode}`;
  useEffect(() => { try { const saved = localStorage.getItem(consistencyKey); if (saved) setConsistency(v => ({ ...v, ...JSON.parse(saved) })); } catch { /* local-only memory is optional */ } }, [consistencyKey]);
  useEffect(() => { try { localStorage.setItem(consistencyKey, JSON.stringify(consistency)); } catch { /* storage may be disabled */ } }, [consistency, consistencyKey]);
  const profileKey = `${consistencyKey}:profiles`;
  useEffect(() => { try { const saved = localStorage.getItem(profileKey); if (saved) setProfiles(JSON.parse(saved)); } catch { setProfiles([]); } }, [profileKey]);
  useEffect(() => { try { localStorage.setItem(profileKey, JSON.stringify(profiles)); } catch { /* optional */ } }, [profiles, profileKey]);
  const saveProfile = () => { const name = profileName.trim(); if (name) setProfiles(v => [...v.filter(p => p.name !== name), { name, data: consistency, locked: consistencyLocked }]); };
  const exportProfiles = () => { const blob = new Blob([JSON.stringify(profiles, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'multimodal-consistency-profiles.json'; a.click(); URL.revokeObjectURL(url); };
  const importProfiles = (event: React.ChangeEvent<HTMLInputElement>) => { const file = event.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = () => { try { const value = JSON.parse(String(reader.result)); if (Array.isArray(value)) setProfiles(value.filter(item => item?.name && item?.data)); } catch { /* invalid local profile file */ } }; reader.readAsText(file); event.target.value = ''; };
  useEffect(() => { if (novelId) api.assets(novelId, 'image').then(setAssets).catch(() => setAssets([])); }, [novelId]);
  const addRef = () => { if (uri.trim()) { setRefs(v => [...v, {uri: uri.trim(), role, x: 16 + (v.length % 3) * 190, y: 16 + Math.floor(v.length / 3) * 90}]); setUri(''); } };
  useEffect(() => { refs.forEach(ref => { if (ref.role === '角色') bindings.add('characters', ref.uri); if (ref.role === '场景') bindings.add('scenes', ref.uri); if (ref.role === '服装') bindings.add('characters', `服装：${ref.uri}`); }); }, [refs]);
  useEffect(() => {
    const selected = new Set(propAssetIds);
    assets.forEach(asset => {
      const label = `${asset.filename} · ${asset.id}`;
      if (selected.has(asset.id)) bindings.add('props', label);
      else if (bindings.manifest.props.includes(label)) bindings.remove('props', label);
    });
  }, [propAssetIds, assets]);
  const synthesizeShot = async (shot: DirectorShot, index: number) => { setVoiceResults(v=>({...v,[index]:{loading:true}})); try { const result=await api.synthesizeDirectorShotDialogue(shot,{provider_id:'openai',model_id:'gpt-4o-mini-tts',voice:shot.voice||'',emotion:shot.emotion||'neutral',novel_id:novelId}); setVoiceResults(v=>({...v,[index]:{uri:result.audio_uri}})); } catch { setVoiceResults(v=>({...v,[index]:{error:'配音生成失败，请检查声音模型与凭据。'}})); } };
  const consistencyWarnings = [!consistency.character && '未填写角色外观', !consistency.scene && '未填写场景结构', !consistency.lighting && '未填写光线', mode === 'video' && shots.some(shot => !shot.profile) && '存在未绑定一致性档案的镜头', consistency.props && !propAssetIds.length && '已描述关键道具但未绑定道具图片'].filter(Boolean) as string[];
  const constraintPayload = { mode, editor_view: mode === 'video' ? (advancedShots ? 'advanced_shot_cards' : 'legacy_shots') : 'infinite_canvas', bindings: bindings.manifest, consistency: { ...consistency, prop_asset_ids: propAssetIds }, consistency_check: { status: consistencyWarnings.length ? 'warning' : 'passed', warnings: consistencyWarnings }, references: refs.map(ref => ({ uri: ref.uri, role: ref.role, position: { x: ref.x, y: ref.y } })), shots: mode === 'video' ? shots : undefined };
  const copyConstraints = async () => { await navigator.clipboard?.writeText(JSON.stringify(constraintPayload, null, 2)); };
  const exportConstraints = () => { const blob = new Blob([JSON.stringify(constraintPayload, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `multimodal-constraints-${mode}.json`; anchor.click(); URL.revokeObjectURL(url); };
  const importConstraints = (event: React.ChangeEvent<HTMLInputElement>) => { const file = event.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = () => { try { const data=JSON.parse(String(reader.result)); if(data&&typeof data==='object'&&(Array.isArray(data.references)||Array.isArray(data.shots))) setPendingImport(data); else setImportMessage('约束包格式无效'); } catch { setImportMessage('约束包读取失败'); } }; reader.readAsText(file); event.target.value = ''; };
  const applyPendingImport = () => { if (!pendingImport) return; const imported=persistence.importWorkspace(pendingImport); if (pendingImport.bindings) ['characters','scenes','props'].forEach(kind => (pendingImport.bindings[kind] || []).forEach((item:string) => bindings.add(kind as 'characters'|'scenes'|'props', item))); const mismatch=pendingImport.mode && pendingImport.mode!==mode; setImportMessage(imported ? (mismatch ? `约束包已导入，但模式不匹配（${pendingImport.mode}）` : '约束包已导入') : '约束包格式无效'); setImportMeta({mode:pendingImport.mode,editor_view:pendingImport.editor_view,status:pendingImport.consistency_check?.status}); setPendingImport(null); };
  const clearWorkspace = () => { if (!window.confirm('确定清空当前图片/视频工作区的本地编排数据吗？')) return; persistence.clear(snapshotNote); setSnapshotNote(''); };
  const restoreSnapshot = () => { persistence.restore(); };
  useEffect(() => { onConstraintsChange?.(constraintPayload); }, [refs, shots, mode, consistency, propAssetIds]);
  useEffect(() => { onShotsChange?.(shots); }, [shots]);
  return <Panel title={mode === 'image' ? '图片无限画布 · 多图约束' : '视频导演台 · 白膜参考'} actions={<><Button variant="ghost" onClick={copyConstraints}>复制约束包</Button><Button variant="ghost" onClick={exportConstraints}>导出 JSON</Button><label className="button"><input hidden type="file" accept="application/json" onChange={importConstraints}/>导入 JSON</label><Button variant="ghost" aria-label="恢复工作区快照" onClick={restoreSnapshot}>恢复快照</Button><Button variant="ghost" aria-label="清空本地工作区" onClick={clearWorkspace}>清空工作区</Button></>} className="multimodal-director">
    {pendingImport && <ConstraintImportPreview value={pendingImport} currentMode={mode} onConfirm={applyPendingImport} onCancel={()=>setPendingImport(null)}/>} {importMessage && <p className="notice" role="status">{importMessage}{importMeta.editor_view && ` · ${importMeta.editor_view}`}{importMeta.status && ` · 一致性 ${importMeta.status}`}</p>}
    <div className="multimodal-director__snapshot-note"><input aria-label="快照备注" placeholder="清理前备注（可选）" value={snapshotNote} onChange={e=>setSnapshotNote(e.target.value)}/></div>{persistence.snapshots.length > 0 && <details><summary>历史快照（{persistence.snapshots.length}）</summary>{persistence.snapshots.map(snapshot => <p className="novel-help" key={snapshot.at}>{new Date(snapshot.at).toLocaleString()} · {snapshot.note || '无备注'} · {snapshot.refs.length} 个参考 · {snapshot.shots.length} 个镜头 <Button variant="ghost" onClick={() => persistence.restore(snapshot)}>恢复</Button></p>)}</details>}
    {mode === 'video' && <label><input type="checkbox" checked={advancedShots} onChange={e=>setAdvancedShots(e.target.checked)}/>使用高级镜头卡片</label>}{mode === 'video' && advancedShots && <DirectorShotList shots={shots} profiles={profiles} novelId={novelId} references={constraintPayload.references} onChange={setShots}/>} 
    {mode === 'image' ? <div className="multimodal-director__canvas">{refs.map((ref, i) => <article draggable style={{left:ref.x,top:ref.y}} onDragEnd={e=>{const box=e.currentTarget.parentElement?.getBoundingClientRect();if(box)setRefs(v=>v.map((item,j)=>j===i?{...item,x:Math.max(0,e.clientX-box.left-70),y:Math.max(0,e.clientY-box.top-20)}:item));}} key={`${ref.uri}-${i}`}><Image size={14}/><span>{ref.role} · {ref.uri}</span><Button aria-label="删除参考" onClick={() => setRefs(v => v.filter((_, j) => j !== i))}><Trash2 size={14}/></Button></article>)}</div> : <div className="multimodal-director__stage"><header><Film size={16}/>导演台<Button onClick={() => setShots(v => [...v, { name: `镜头 ${String(v.length + 1).padStart(2, '0')}`, duration: '3s', camera: '固定机位', action: '填写动作与表演' }])}><Plus size={14}/>新增镜头</Button></header>{shots.map((shot, i) => <article key={i}><input aria-label="镜头名称" value={shot.name} onChange={e => setShots(v => v.map((s,j)=>j===i?{...s,name:e.target.value}:s))}/><input aria-label="镜头时长" value={shot.duration} onChange={e => setShots(v => v.map((s,j)=>j===i?{...s,duration:e.target.value}:s))}/><input aria-label="镜头运动" value={shot.camera} onChange={e => setShots(v => v.map((s,j)=>j===i?{...s,camera:e.target.value}:s))}/><textarea aria-label="镜头动作" rows={2} value={shot.action} onChange={e => setShots(v => v.map((s,j)=>j===i?{...s,action:e.target.value}:s))}/><select aria-label="镜头一致性档案" value={shot.profile||""} onChange={e => setShots(v => v.map((s,j)=>j===i?{...s,profile:e.target.value}:s))}><option value="">不绑定档案</option>{profiles.map(p=><option key={p.name}>{p.name}</option>)}</select><input aria-label="镜头对白" placeholder="对白 / 旁白" value={shot.dialogue||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,dialogue:e.target.value}:s))}/><input aria-label="镜头环境音" placeholder="环境音" value={shot.ambience||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,ambience:e.target.value}:s))}/><input aria-label="镜头音效" placeholder="动作音效" value={shot.sound_effect||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,sound_effect:e.target.value}:s))}/><input aria-label="镜头音乐" placeholder="音乐情绪 / 入点" value={shot.music||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,music:e.target.value}:s))}/><input aria-label="镜头字幕" placeholder="字幕文本" value={shot.subtitle||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,subtitle:e.target.value}:s))}/><input aria-label="镜头声音" placeholder="声音档案" value={shot.voice||""} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,voice:e.target.value}:s))}/><select aria-label="镜头情绪" value={shot.emotion||"neutral"} onChange={e=>setShots(v=>v.map((s,j)=>j===i?{...s,emotion:e.target.value}:s))}><option value="neutral">中性</option><option value="calm">平静</option><option value="urgent">紧迫</option><option value="sad">悲伤</option></select></article>)}</div>}
    <section><h3>{mode === 'image' ? '多图约束' : '白膜参考'}</h3>{assets.length > 0 && <div className="multimodal-director__asset-picks">{assets.map(asset => <Button key={asset.id} variant="ghost" onClick={() => setRefs(v => [...v, { uri: `${asset.filename} · ${asset.id}`, role, x: 16 + (v.length % 3) * 190, y: 16 + Math.floor(v.length / 3) * 90 }])}>{asset.filename}</Button>)}</div>}<div className="multimodal-director__entry"><select aria-label="参考语义" value={role} onChange={e=>setRole(e.target.value)}>{(mode === 'image' ? ['角色','场景','服装','构图'] : ['白膜','角色','场景','动作']).map(item=><option key={item}>{item}</option>)}</select><input placeholder="粘贴本地或已上传图片地址" value={uri} onChange={e=>setUri(e.target.value)}/><Button onClick={addRef} disabled={!uri.trim()}><Plus size={14}/>添加</Button></div>{!refs.length&&<p className="novel-help">尚未添加参考图。生成能力由已配置 Provider 决定。</p>}</section>
    <section><h3>一致性锁定</h3><Button variant="ghost" onClick={()=>setConsistencyLocked(v=>!v)}>{consistencyLocked?"解锁编辑":"锁定一致性"}</Button><p className="novel-help">已绑定道具：{propAssetIds.length} 个</p><p className="novel-help">绑定清单：角色 {bindings.manifest.characters.length} · 场景 {bindings.manifest.scenes.length} · 道具 {bindings.manifest.props.length}</p><BindingManifestPanel manifest={bindings.manifest} onRemove={bindings.remove}/><div className="multimodal-director__profiles"><select aria-label="一致性档案" value={profileName} onChange={e=>{setProfileName(e.target.value);const found=profiles.find(p=>p.name===e.target.value);if(found){setConsistency(found.data);setConsistencyLocked(Boolean(found.locked))}}}><option value="">选择档案</option>{profiles.map(p=><option key={p.name}>{p.name}</option>)}</select><input aria-label="档案名称" placeholder="档案名称" value={profileName} onChange={e=>setProfileName(e.target.value)}/><Button onClick={saveProfile}>保存档案</Button><Button variant="ghost" onClick={exportProfiles}>导出档案</Button><label className="button"><input hidden type="file" accept="application/json" onChange={importProfiles}/>导入档案</label>{profileName && profiles.some(p=>p.name===profileName)&&<Button variant="ghost" aria-label="删除当前档案" onClick={()=>{if(window.confirm("确定删除当前一致性档案吗？"))setProfiles(v=>v.filter(p=>p.name!==profileName))}}>删除档案</Button>}</div><div className="multimodal-director__consistency">{([['character','角色外观'],['wardrobe','服装'],['scene','场景结构'],['lighting','光线'],['time','时间/天气'],['props','关键道具']] as const).map(([key,label]) => <input key={key} aria-label={label} placeholder={label} value={consistency[key]} disabled={consistencyLocked} onChange={e=>setConsistency(v=>({...v,[key]:e.target.value}))}/>)}</div><div className="multimodal-director__asset-picks">{assets.filter(asset=>asset.media_type?.startsWith("image/")).map(asset=><label key={asset.id}><input type="checkbox" checked={propAssetIds.includes(asset.id)} onChange={e=>setPropAssetIds(v=>e.target.checked?[...v,asset.id]:v.filter(id=>id!==asset.id))}/>{asset.filename}</label>)}</div>{consistencyWarnings.length>0?<div className="notice" role="status"><strong>一致性检查</strong>{consistencyWarnings.map(item=><p key={item}>{item}</p>)}</div>:<p className="novel-help">一致性检查通过</p>}<p className="novel-help">这些约束会随约束包导出，并可传入图片或视频任务。</p></section>
  </Panel>;
}

















