import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Details, ErrorMessage, Field } from './shared';
import { styleDimensions, type StyleCatalog, type StyleProfileInput, type StyleResolution, type StyleReviewClient, type StyleRules, type StyleTarget } from './styleReviewClient';
const labels = { writing_tone: '文字语气', camera_language: '镜头语言', composition: '构图', color: '色彩', linework_halftone: '线条与网点', character_design: '角色设计', sound: '声音', music_theme: '音乐主题' };
const empty = (): StyleProfileInput => ({ title: '', instructions: '', rules: [], chapter_ids: [], character_ids: [], style_dna: { schema_version: 1, global_rules: {}, overrides: [] } });
const editable = (row: StyleProfileInput) => !!row.style_dna && row.style_dna.overrides.length <= 1 && row.style_dna.overrides.every(item => item.target.level === 'CHAPTER');
const clean = (rules: StyleRules) => Object.fromEntries(Object.entries(rules).filter(([, text]) => text?.trim()).map(([key, text]) => [key, text!.trim()])) as StyleRules;
type Props = { api: StyleReviewClient; catalog?: StyleCatalog; available: boolean; error?: unknown; onRefresh: () => void };
let ownerSequence = 0;
export function StyleDNAEditor(props: Props) {
  const identity = useMemo(() => ++ownerSequence, [props.api]);
  return <StyleDNAEditorBody key={identity} {...props} />;
}
function StyleDNAEditorBody({ api, catalog, available, error, onRefresh }: Props) {
  const [id, setId] = useState(''), [version, setVersion] = useState(0), [draft, setDraft] = useState(empty), [dirty, setDirty] = useState(false), [notice, setNotice] = useState('');
  const [targetId, setTargetId] = useState(''), [result, setResult] = useState<StyleResolution>(), [failure, setFailure] = useState<unknown>(), [busy, setBusy] = useState(false), [quarantined, setQuarantined] = useState(false);
  const epoch = useRef(0), running = useRef(false), alive = useRef(true);
  const row = catalog?.styles.find(item => item.id === id && item.style_dna);
  const lost = !!id && available && !row;
  const visible = available && !error && !lost && !quarantined;
  const stale = !!row?.style_dna_resolution?.stale;
  const drift = !!row && row.version !== version;
  const supported = editable(draft);
  const invalidate = () => { epoch.current++; setResult(undefined); setFailure(undefined); };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, [api]);
  // Quarantine persisted content immediately in render; clear it before a later permission recovery.
  useLayoutEffect(() => {
    const denied = error instanceof ApiError && [401, 403, 404].includes(error.problem.status);
    if (error || lost) invalidate();
    if (denied || lost) { setDraft(empty()); setDirty(false); setQuarantined(true); }
  }, [error, lost]);
  useLayoutEffect(() => { invalidate(); }, [available, catalog, row?.version, row?.style_dna_resolution?.source_digest, stale]);
  useEffect(() => { if (!dirty) return; const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard); }, [dirty]);
  const select = (next: string) => {
    if (dirty && !window.confirm('放弃未保存的 Style DNA 修改？')) return;
    invalidate(); setNotice(''); setId(next); setTargetId(''); setQuarantined(false); setDirty(false);
    const value = catalog?.styles.find(item => item.id === next && item.style_dna);
    setVersion(value?.version || 0); setDraft(value ? { title: value.title, instructions: value.instructions, rules: value.rules, chapter_ids: value.chapter_ids, character_ids: value.character_ids, style_dna: structuredClone(value.style_dna) } : empty());
  };
  const change = (next: StyleProfileInput) => { invalidate(); setNotice(''); setDraft(next); setDirty(true); };
  const execute = async (operation: () => Promise<void>) => {
    if (running.current || !visible) return;
    running.current = true; setBusy(true); setFailure(undefined);
    const ticket = epoch.current;
    try { await operation(); } catch (value) {
      if (alive.current && ticket === epoch.current) {
        setFailure(value); setResult(undefined);
        if (value instanceof ApiError && [401, 403, 404].includes(value.problem.status)) { setQuarantined(true); setDraft(empty()); setDirty(false); onRefresh(); }
      }
    } finally { running.current = false; if (alive.current) setBusy(false); }
  };
  const save = () => {
    const ticket = epoch.current;
    const dna = draft.style_dna!;
    const body = { ...draft, style_dna: { ...dna, global_rules: clean(dna.global_rules), overrides: dna.overrides.map(item => ({ ...item, rules: clean(item.rules) })) } };
    void execute(async () => {
      const saved = id ? await api.updateProfile(id, version, body) : await api.createProfile(body);
      if (!alive.current || ticket !== epoch.current) return;
      setId(id); setVersion(id ? saved.version : 0); setDraft(id ? body : empty()); setDirty(false); invalidate(); setNotice('草稿已保存。请从档案列表重新打开并核对，再审核。'); onRefresh();
    });
  };
  const chapters = catalog?.chapters.filter(item => /^[a-f0-9]{64}$/.test(item.content_digest || '')) || [];
  const pin = (chapterId: string): StyleTarget | undefined => { const chapter = chapters.find(item => item.id === chapterId); return chapter ? { level: 'CHAPTER', chapter: { id: chapter.id, version: chapter.version, digest: chapter.content_digest! } } : undefined; };
  const override = draft.style_dna?.overrides[0];
  const valid = !!draft.title.trim() && !!draft.instructions.trim() && (!!Object.keys(clean(draft.style_dna!.global_rules)).length || !!override) && (!override || !!Object.keys(clean(override.rules)).length);
  const target = targetId ? pin(targetId) : { level: 'GLOBAL' } as StyleTarget;
  const ruleFields = (scope: string, rules: StyleRules, update: (rules: StyleRules) => void) => <div className="experimental-grid">{styleDimensions.map(key => <Field key={key} label={`${scope} · ${labels[key]}`}><textarea maxLength={2000} value={rules[key] || ''} onChange={event => update({ ...rules, [key]: event.target.value })} /></Field>)}</div>;
  return <Panel title="Style DNA · 多模态风格规则">
    <Badge>人工规则 · 只读解析 · 不调用模型</Badge>
    <p>本版支持全局规则与一个精确章节覆盖。场景、镜头及多个覆盖的编辑界面尚未开放；不会自动改写导演、镜头或正文。</p>
    <Field label="Style DNA 档案"><select disabled={!available || busy} value={id} onChange={event => select(event.target.value)}><option value="">新建多模态风格档案</option>{available && catalog?.styles.filter(item => item.style_dna).map(item => <option value={item.id} key={item.id}>{item.title} · v{item.version} · {item.status}</option>)}{id && !row && <option value={id}>档案不可用</option>}</select></Field>
    {!visible && <StatusMessage tone="warning">来源或权限正在核对，档案内容与解析已隐藏。恢复后请核对来源与输入。</StatusMessage>}
    {quarantined && available && row && <Button onClick={() => select(id)}>重新打开当前档案</Button>}
    {visible && <>
      {notice && <StatusMessage tone="success">{notice}</StatusMessage>}
      {drift && <Button disabled={busy} onClick={() => select(id)}>重新打开服务器当前版本</Button>}
      {row && <p>原 STYLE 档案 v{row.version} · {row.status}{stale ? ' · 来源已变化，仅可修订' : ''}</p>}
      <StatusMessage>多模态档案尚不支持 A02 文风统计、模型解读或生成注入。以下解析只展示人工规则的覆盖关系，不验证语义冲突。</StatusMessage>
      <Button disabled>A02 分析不可用</Button><Button disabled>执行采用不可用</Button>
      {!supported ? <><StatusMessage tone="warning">此档案含本版界面尚不支持的层级或多个覆盖，已锁定编辑，避免丢失原规则。</StatusMessage><Details value={draft.style_dna} label="只读查看完整规则" /></> : <form className="experimental-form" onSubmit={event => { event.preventDefault(); if (valid && !busy && !drift) save(); }}>
        <fieldset className="experimental-form" disabled={busy}>
          <legend>人工编写八维风格（留空表示未知）</legend>
          <Field label="Style DNA 标题"><input required maxLength={200} value={draft.title} onChange={event => change({ ...draft, title: event.target.value })} /></Field>
          <Field label="Style DNA 简短说明"><textarea required maxLength={120} value={draft.instructions} onChange={event => change({ ...draft, instructions: event.target.value })} /></Field>
          {ruleFields('全局', draft.style_dna!.global_rules, rules => change({ ...draft, style_dna: { ...draft.style_dna!, global_rules: rules } }))}
          <Field label="精确章节覆盖"><select value={override?.target.chapter?.id || ''} onChange={event => { const chosen = pin(event.target.value); change({ ...draft, style_dna: { ...draft.style_dna!, overrides: chosen ? [{ target: chosen, rules: override?.rules || {} }] : [] } }); }}><option value="">不添加章节覆盖</option>{chapters.map(item => <option key={item.id} value={item.id}>{item.title} · v{item.version}</option>)}{override && !chapters.some(item => item.id === override.target.chapter?.id) && <option value={override.target.chapter?.id}>原章节不可用</option>}</select></Field>
          {override && <><Details value={override.target} label="核对保存的精确章节版本与摘要" /><Button type="button" disabled={!pin(override.target.chapter!.id)} onClick={() => change({ ...draft, style_dna: { ...draft.style_dna!, overrides: [{ ...override, target: pin(override.target.chapter!.id)! }] } })}>明确更新至当前章节版本</Button>{ruleFields('章节覆盖', override.rules, rules => change({ ...draft, style_dna: { ...draft.style_dna!, overrides: [{ ...override, rules }] } }))}</>}
        </fieldset>
        {drift && <StatusMessage tone="warning">服务器版本已变化，输入保留但禁止覆盖。请重新打开当前档案并核对。</StatusMessage>}
        <div className="experimental-actions"><Button type="submit" disabled={busy || !valid || drift}>{id ? '保存 Style DNA 新草稿版本' : '保存 Style DNA 草稿'}</Button><Button type="button" disabled={busy} onClick={() => select(id)}>取消修改并重新打开</Button></div>
      </form>}
      {dirty && <StatusMessage tone="warning">有未保存修改。切换档案或取消须确认放弃；离开此工作区前请保存。</StatusMessage>}
      <Button disabled={busy || dirty || drift || stale || row?.status !== 'DRAFT'} onClick={() => { const ticket = epoch.current; void execute(async () => { const approved = await api.transitionProfile(row!, 'approve'); if (alive.current && ticket === epoch.current) { setVersion(approved.version); invalidate(); setNotice('已审核当前版本，可明确选择目标进行只读解析。'); onRefresh(); } }); }}>审核当前 Style DNA 版本</Button>
      <Field label="只读解析目标"><select disabled={busy} value={targetId} onChange={event => { invalidate(); setTargetId(event.target.value); }}><option value="">全局</option>{chapters.map(item => <option key={item.id} value={item.id}>{item.title} · v{item.version}</option>)}</select></Field>
      <Button disabled={busy || dirty || drift || stale || !target || row?.status !== 'APPROVED' || !row.style_dna_resolution?.source_digest} onClick={() => { const ticket = epoch.current; void execute(async () => { const value = await api.resolveStyle(row!, target!); if (alive.current && ticket === epoch.current) setResult(value); }); }}>解析当前已审核风格</Button>
      {result && <section aria-label="Style DNA 只读解析"><h4>当前生效规则</h4>{styleDimensions.filter(key => result.effective[key]).map(key => <p key={key}>{labels[key]}：{result.effective[key]!.value} · {result.effective[key]!.level}</p>)}<p>未知维度：{result.uncovered_dimensions.map(key => labels[key]).join('、') || '无空缺（仍未验证语义）'}</p><Details value={{ source: result.style_source, target: result.target, contributors: result.contributors, overrides: result.conflicts }} label="核对来源、赢家与覆盖记录" /><p>仅覆盖人工规则；未调用模型、未修改目标、不可直接执行。</p></section>}
    </>}
    {!!failure && <><ErrorMessage error={failure} /><StatusMessage tone="warning">操作未完成。刷新来源后核对版本；不会自动重试或自动审核。</StatusMessage></>}
  </Panel>;
}
