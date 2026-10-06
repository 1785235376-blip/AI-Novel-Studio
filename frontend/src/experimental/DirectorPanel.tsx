import { useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { directorClient, newGrammar, type CameraCheck, type CameraGrammar, type DirectorComparison, type DirectorScreenplay, type ShotPatch } from './directorClient';

let nextScope = 0;
export function DirectorPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++nextScope, [client]);
  return <DirectorContent key={identity} client={client} />;
}
function DirectorContent({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => directorClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]);
  const plans = useResource(signal => api.plans(signal), [api]);
  const action = useReviewAction();
  const [selected, setSelected] = useState<DirectorScreenplay>();
  const [title, setTitle] = useState(''); const [shots, setShots] = useState<ShotPatch[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]); const [comparison, setComparison] = useState<DirectorComparison>();
  const [reviewed, setReviewed] = useState(false); const epoch = useRef(0);
  const available = !catalog.loading && !catalog.error && !!catalog.data;
  const plansAvailable = !plans.loading && !plans.error && !!plans.data;
  const current = available && catalog.data!.screenplays.find(row => row.id === selected?.id);
  const changed = !!selected && (!current || selected.edit_version !== current.edit_version);
  const invalidate = () => { epoch.current++; setComparison(undefined); setReviewed(false); };
  const refresh = () => { invalidate(); catalog.reload(); plans.reload(); };
  const select = (id: string) => {
    invalidate(); setCompareIds([]);
    const row = catalog.data?.screenplays.find(value => value.id === id); setSelected(row);
    setShots(row?.shots.map(shot => ({ shot_id: shot.id, shot_size: shot.shot_size, camera_angle: shot.camera_angle, camera_motion: shot.camera_motion, duration_seconds: shot.duration_seconds, director: structuredClone(shot.director || newGrammar()) })) || []);
  };
  const edit = (index: number, patch: Partial<ShotPatch>) => { invalidate(); setShots(rows => rows.map((row, i) => i === index ? { ...row, ...patch } : row)); };
  const candidates = plansAvailable ? plans.data!.items.filter(row => !selected || row.screenplay_id === selected.id) : [];
  const safeComparison = available && plansAvailable && comparison && catalog.data!.screenplays.some(row => row.id === comparison.screenplay_id && row.edit_version === comparison.screenplay_version)
    && comparison.candidates.every(row => plans.data!.items.some(plan => plan.id === row.id && plan.version === row.version && !plan.stale && plan.status === 'DRAFT')) ? comparison : undefined;
  return <section className="experimental-section" aria-label="镜头导演与空间检查">
    <div className="experimental-actions"><h3>镜头导演</h3><Badge>本地确定性检查 · 手工候选方案</Badge><Button disabled={action.busy || catalog.loading || plans.loading} onClick={refresh}>刷新镜头与方案（保留输入）</Button></div>
    <p>沿用原剧本、镜头编号、人物和审核流程。没有可靠几何时显示信息不足；此处不会生成图片或视频。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对功能开关、会话与项目分支权限后刷新。未保存的表单仍保留。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <datalist id="director-camera-motions">{['STATIC', 'TRACKING', 'DOLLY', 'PAN', 'TILT'].map(value => <option key={value} value={value} />)}</datalist>
    <Panel title="从原镜头创建候选方案">
      <Field label="导演方案来源剧本"><select disabled={!available || action.busy} value={selected?.id || ''} onChange={e => select(e.target.value)}><option value="">请选择已建立镜头的剧本</option>{available && catalog.data!.screenplays.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.edit_version}</option>)}</select></Field>
      {available && !catalog.data!.screenplays.length && <EmptyState title="暂无当前可用剧本" detail="先在原剧本工作区建立并批准剧本，再规划镜头。来源过期的剧本需先核对。" />}
      {selected && <><Field label="候选镜头方案名称"><input maxLength={240} value={title} onChange={e => { invalidate(); setTitle(e.target.value); }} /></Field>
        {changed && <StatusMessage tone="warning">原剧本已变化或不可用。输入已保留；请重新选择当前剧本并核对，不能把旧方案覆盖到新版本。</StatusMessage>}
        {!shots.length && <StatusMessage>此剧本还没有镜头，请先在原剧本区规划镜头，再刷新。</StatusMessage>}
        {shots.map((shot, index) => <article className="experimental-record" key={shot.shot_id} aria-label={`镜头 ${selected.shots[index].number} 导演设置`}>
          <h4>镜头 {selected.shots[index].number}</h4>
          <div className="experimental-grid"><Field label={`镜头 ${index + 1} 景别`}><select value={shot.shot_size} disabled={action.busy} onChange={e => edit(index, { shot_size: e.target.value })}>{['EXTREME_WIDE', 'WIDE', 'MEDIUM', 'CLOSE', 'EXTREME_CLOSE'].map(v => <option key={v}>{v}</option>)}</select></Field><Field label={`镜头 ${index + 1} 机位角度`}><input maxLength={80} value={shot.camera_angle} disabled={action.busy} onChange={e => edit(index, { camera_angle: e.target.value })} /></Field><Field label={`镜头 ${index + 1} 摄影机运动`}><input list="director-camera-motions" maxLength={80} value={shot.camera_motion} disabled={action.busy} onChange={e => edit(index, { camera_motion: e.target.value })} /></Field><Field label={`镜头 ${index + 1} 预计时长（秒）`}><input type="number" min={1} max={600} step={1} value={shot.duration_seconds} disabled={action.busy} onChange={e => edit(index, { duration_seconds: Number(e.target.value) })} /></Field></div>
          <GrammarEditor value={shot.director} onChange={director => edit(index, { director })} characters={available ? catalog.data!.characters : []} disabled={action.busy} label={`镜头 ${index + 1}`} />
        </article>)}
        <Button disabled={action.busy || !available || changed || !title.trim() || !shots.length || shots.some(row => !row.shot_size || !row.camera_angle || !row.camera_motion || !Number.isInteger(row.duration_seconds) || row.duration_seconds < 1 || row.duration_seconds > 600 || ((row.director.intentional_axis_crossing || row.director.intentions.length > 0) && !row.director.override_reason.trim()))} onClick={() => void action.run(async isCurrent => { await api.save(selected, title, shots); if (isCurrent()) { invalidate(); plans.reload(); } }, '候选方案已保存为草稿。原镜头未改动，请先对比再应用。')}>保存候选镜头草稿</Button>
      </>}
    </Panel>
    <Panel title="对比候选与原镜头">
      <ResourceState loading={plans.loading} error={plans.error} />
      {plansAvailable && !candidates.length && <EmptyState title="还没有候选方案" detail="保存一个或多个手工方案后，可选择最多四个并排核对。" />}
      {candidates.map(row => <article className="experimental-record" key={row.id}><div className="experimental-actions"><strong>{row.title}</strong><Badge>{row.status} · v{row.version}</Badge>{row.stale && <Badge tone="warning">来源已变化</Badge>}</div>
        {row.stale ? <p>过期方案的镜头与几何已隐藏，请依据当前来源创建新方案。</p> : <Checks rows={row.checks || []} />}
        <div className="experimental-actions"><label className="experimental-check"><input type="checkbox" disabled={action.busy || row.stale || row.status !== 'DRAFT' || (!compareIds.includes(row.id) && compareIds.length >= 4)} checked={compareIds.includes(row.id)} onChange={() => { invalidate(); setCompareIds(values => values.includes(row.id) ? values.filter(id => id !== row.id) : [...values, row.id]); }} />对比方案 {row.title}</label>{row.status === 'DRAFT' && <Button disabled={action.busy} onClick={() => void action.run(async isCurrent => { await api.reject(row); if (isCurrent()) refresh(); }, '方案已驳回，历史仍保留。')}>驳回方案 {row.title}</Button>}</div>
      </article>)}
      <Button disabled={action.busy || !available || !plansAvailable || !compareIds.length} onClick={() => void action.run(async isCurrent => { const ticket = ++epoch.current; setReviewed(false); const result = await api.compare(compareIds); if (isCurrent() && ticket === epoch.current) setComparison(result); })}>读取原镜头与候选对比</Button>
      {safeComparison && <section aria-label="导演方案对比结果"><Details value={safeComparison.original} label="原镜头的完整对比字段" open />{safeComparison.candidates.map(row => <article className="experimental-record" key={row.id}><h4>{row.title}</h4><Details value={row.shots} label={`${row.title} 候选字段`} open /><Checks rows={row.checks || []} /></article>)}
        <StatusMessage tone="warning">应用会新增原剧本的镜头草稿版本。旧分镜、转场和生成任务转为历史待复核；必须回原剧本区重新批准镜头并规划后续产物。</StatusMessage>
        <label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy} onChange={e => setReviewed(e.target.checked)} />已核对原镜头、候选字段与旧产物失效影响</label>
        {safeComparison.candidates.map(row => <Button key={row.id} disabled={action.busy || !reviewed} onClick={() => void action.run(async isCurrent => { await api.apply(row, safeComparison.application_digests[row.id]); if (isCurrent()) refresh(); }, '已应用为原剧本的新镜头草稿版本。请回原剧本区审核镜头，尚未生成媒体。')}>采用方案 {row.title} 为镜头草稿</Button>)}
      </section>}
    </Panel>
  </section>;
}
function Checks({ rows }: { rows: CameraCheck[] }) {
  return <ul>{rows.map((row, index) => <li key={index}><Badge tone={row.state === 'AXIS_CROSSING' || row.state === 'DIRECTION_MISMATCH' || row.state === 'REVIEW_SUGGESTION' ? 'warning' : 'neutral'}>{row.state}</Badge> {row.message}{row.cross_products && ` 叉积：${row.cross_products.join(' / ')}`}</li>)}</ul>;
}
function GrammarEditor({ value, onChange, characters, disabled, label }: { value: CameraGrammar; onChange: (value: CameraGrammar) => void; characters: { id: string; name: string }[]; disabled: boolean; label: string }) {
  const change = (patch: Partial<CameraGrammar>) => onChange({ ...value, ...patch });
  const axisPick = (index: number, id: string) => { const axis = [...value.axis]; axis[index] = id; change({ axis, character_positions: { ...value.character_positions, ...(id ? { [id]: value.character_positions[id] || { x: index * 10, y: 0 } } : {}) } }); };
  return <fieldset className="experimental-form" disabled={disabled}><legend>{label} 场面调度</legend>
    <Field label={`${label} 镜头功能`}><select value={value.shot_function || 'UNSPECIFIED'} onChange={e => change({ shot_function: e.target.value as CameraGrammar['shot_function'] })}>{['UNSPECIFIED', 'ESTABLISHING', 'OTS', 'POV', 'INSERT'].map(item => <option key={item}>{item}</option>)}</select></Field>
    <Field label={`${label} 焦点意图`}><select value={value.focus_intent || 'UNSPECIFIED'} onChange={e => change({ focus_intent: e.target.value as CameraGrammar['focus_intent'] })}>{['UNSPECIFIED', 'HOLD', 'RACK_FOCUS'].map(item => <option key={item}>{item}</option>)}</select></Field>
    <Field label={`${label} 场景目的`}><textarea maxLength={2000} value={value.scene_purpose} onChange={e => change({ scene_purpose: e.target.value })} /></Field>
    <Field label={`${label} 视点`}><input maxLength={500} value={value.viewpoint} onChange={e => change({ viewpoint: e.target.value })} /></Field>
    <Field label={`${label} 屏幕方向`}><select value={value.screen_direction} onChange={e => change({ screen_direction: e.target.value as CameraGrammar['screen_direction'] })}><option value="UNKNOWN">未知</option><option value="LEFT_TO_RIGHT">从左向右</option><option value="RIGHT_TO_LEFT">从右向左</option><option value="STATIONARY">无横向移动</option></select></Field>
    <details className="experimental-details"><summary>可选：明确空间坐标与轴线</summary><p>二维世界坐标 x 向右、y 向上；摄影机朝向轴线中点。不同机位需使用相同坐标系与人物位置。不会从文字猜测位置。</p>
      <Field label={`${label} 坐标系名称`}><input maxLength={120} value={value.coordinate_system} onChange={e => change({ coordinate_system: e.target.value })} /></Field>
      {[0, 1].map(index => <div key={index}><Field label={`${label} 轴线人物 ${index + 1}`}><select value={value.axis[index] || ''} onChange={e => axisPick(index, e.target.value)}><option value="">未指定</option>{characters.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>{value.axis[index] && <div className="experimental-grid">{(['x', 'y'] as const).map(coordinate => <Field key={coordinate} label={`${label} 人物 ${index + 1} ${coordinate}`}><input type="number" value={value.character_positions[value.axis[index]]?.[coordinate] || 0} onChange={e => change({ character_positions: { ...value.character_positions, [value.axis[index]]: { ...value.character_positions[value.axis[index]], [coordinate]: Number(e.target.value) } } })} /></Field>)}</div>}</div>)}
      <label className="experimental-check"><input type="checkbox" checked={!!value.camera_position} onChange={e => change({ camera_position: e.target.checked ? { x: 5, y: 5 } : null })} />{label} 已知摄影机位置</label>
      {value.camera_position && <div className="experimental-grid">{(['x', 'y'] as const).map(coordinate => <Field key={coordinate} label={`${label} 摄影机 ${coordinate}`}><input type="number" value={value.camera_position![coordinate]} onChange={e => change({ camera_position: { ...value.camera_position!, [coordinate]: Number(e.target.value) } })} /></Field>)}</div>}
      <label className="experimental-check"><input type="checkbox" checked={!!value.subject_movement} onChange={e => change({ subject_movement: e.target.checked ? { start: { x: 0, y: 0 }, end: { x: 1, y: 0 } } : null })} />{label} 已知主体移动轨迹</label>
      {value.subject_movement && <div className="experimental-grid">{(['start', 'end'] as const).flatMap(end => (['x', 'y'] as const).map(coordinate => <Field key={end + coordinate} label={`${label} 移动${end === 'start' ? '起点' : '终点'} ${coordinate}`}><input type="number" value={value.subject_movement![end][coordinate]} onChange={e => change({ subject_movement: { ...value.subject_movement!, [end]: { ...value.subject_movement![end], [coordinate]: Number(e.target.value) } } })} /></Field>))}</div>}
      <Button type="button" onClick={() => change({ axis: [], character_positions: {}, camera_position: null, subject_movement: null, coordinate_system: '' })}>清除此镜头几何资料</Button>
    </details>
    <label className="experimental-check"><input type="checkbox" checked={value.intentional_axis_crossing} onChange={e => change({ intentional_axis_crossing: e.target.checked })} />{label} 有意越轴</label>
    {(['LONG_TAKE', 'JUMP_CUT'] as const).map(kind => <label className="experimental-check" key={kind}><input type="checkbox" checked={value.intentions.includes(kind)} onChange={() => change({ intentions: value.intentions.includes(kind) ? value.intentions.filter(x => x !== kind) : [...value.intentions, kind] })} />{label} {kind === 'LONG_TAKE' ? '有意长镜头' : '有意跳切'}</label>)}
    <Field label={`${label} 有意处理理由`}><textarea maxLength={2000} required={value.intentional_axis_crossing || value.intentions.length > 0} value={value.override_reason} onChange={e => change({ override_reason: e.target.value })} /></Field>
  </fieldset>;
}
