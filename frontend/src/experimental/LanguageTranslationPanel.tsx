import { useEffect, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { Field, ResourceState, useAction, useResource } from './shared';
import { multilingualEditionsClient, type EditionSegment, type LanguageEdition, type TranslationRun } from './multilingualEditionsClient';
type Props = { api: ReturnType<typeof multilingualEditionsClient>; edition: LanguageEdition; segment: EditionSegment; blocked: boolean; perform: (operation: () => Promise<LanguageEdition>, message: string) => void };
export function LanguageTranslationPanel(props: Props) {
  const [open, setOpen] = useState(false);
  return <section className="experimental-section" aria-label="本段模型翻译">
    <Button disabled={props.blocked} aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? '收起本段模型翻译' : '打开本段模型翻译'}</Button>
    {open && <TranslationBody {...props} />}
  </section>;
}
function TranslationBody({ api, edition, segment, blocked, perform }: Props) {
  const routes = useResource(signal => api.translationRoutes(signal), [api]);
  const runs = useResource(signal => api.translationRuns(edition, signal), [api, edition.id, edition.version]);
  const [route, setRoute] = useState(''), [synthetic, setSynthetic] = useState(false), [run, setRun] = useState<TranslationRun>();
  const [consent, setConsent] = useState(false), [adopt, setAdopt] = useState(false);
  const action = useAction(); const alive = useRef(true), epoch = useRef(0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { epoch.current++; setConsent(false); setAdopt(false); }, [route, synthetic, blocked]);
  const selectedRoute = routes.data?.items.find(item => item.route_id === route);
  const disabled = blocked || action.busy;
  const update = (next: TranslationRun) => { setRun(next); setConsent(false); setAdopt(false); runs.reload(); };
  const execute = (operation: () => Promise<TranslationRun>, message: string) => void action.run(async () => {
    const ticket = ++epoch.current; const result = await operation(); if (alive.current && ticket === epoch.current) update(result);
  }, message);
  const canDispatch = !!run?.preview?.execution_available && run.status === 'PREVIEW' && !run.stale && !run.execution;
  const canAdopt = !!run?.candidate && run.status === 'CANDIDATE' && !run.content_withheld && run.edition_version === edition.version;
  return <>
    <p>仅翻译所选已保存段落，附带本版本批准的术语、别名与风格。LOCAL_ONLY，费用预留必须明确为 USD 0。输出是未审核候选，采用后仍需逐段审核。</p>
    <ResourceState loading={routes.loading} error={routes.error} empty={!routes.data?.items.length} />
    {routes.error && <StatusMessage tone="warning">模型功能、主机身份或配置不可用。手工双语编辑仍可使用；不会发送模型请求。</StatusMessage>}
    <Field label="本段翻译本地模型路线"><select value={route} disabled={disabled || routes.loading} onChange={e => { setRoute(e.target.value); setRun(undefined); }}><option value="">选择已注册路线</option>{routes.data?.items.map(item => <option key={item.route_id} value={item.route_id} disabled={!item.available}>{item.display_name} · {item.provider_id}/{item.model_id}{item.synthetic ? ' · 合成协议测试' : ''}{item.available ? '' : ` · ${item.reasons.join('、')}`}</option>)}</select></Field>
    {selectedRoute?.synthetic && <label className="experimental-check"><input type="checkbox" checked={synthetic} disabled={disabled} onChange={e => { setSynthetic(e.target.checked); setRun(undefined); }} />允许合成协议测试路线，不代表真实翻译质量</label>}
    <div className="experimental-actions"><Button disabled={disabled || !selectedRoute?.available || (selectedRoute.synthetic && !synthetic)} onClick={() => execute(() => api.translationPreview(edition, segment, route, synthetic), '已生成本段精确请求，尚未调用模型。')}>预览本段翻译请求与费用</Button><Button disabled={disabled || routes.loading} onClick={routes.reload}>刷新翻译路线</Button><Button disabled={disabled || runs.loading} onClick={runs.reload}>找回本段翻译任务</Button></div>
    <ResourceState loading={runs.loading} error={runs.error} empty={!runs.data?.items.filter(item => item.segment_id === segment.id).length} />
    {runs.data?.items.filter(item => item.segment_id === segment.id).map(item => <Button key={item.id} disabled={disabled} aria-pressed={run?.id === item.id} onClick={() => { epoch.current++; update(item); }}>翻译任务 {item.id.slice(0, 8)} · {item.status}{item.stale ? ' · 已过期' : ''}</Button>)}
    {runs.data?.truncated && <p>仅显示最近 50 个任务。</p>}
    {run && <section aria-label="本段翻译任务详情"><Badge>状态 {run.status}</Badge><p>任务 {run.id} · 绑定语言版本 v{run.edition_version} · 语言质量 NOT_RUN</p>
      {run.content_withheld && <StatusMessage tone="warning">来源、语言版本、路线或执行身份已变化。候选内容停止展示与采用；不会自动重试。</StatusMessage>}
      {run.preview && <>
        {run.preview.blocked_reason && <StatusMessage tone="warning">{run.preview.blocked_reason}</StatusMessage>}
        <p>输出上限 {run.preview.max_output_bytes} 字节 · 执行时限 {run.preview.timeout_seconds} 秒 · 预算版本 {run.preview.broker.budget_version}</p>
        {run.preview.broker.chosen ? <><p>本地路线：{run.preview.broker.chosen.provider_id}/{run.preview.broker.chosen.model_id}{run.preview.broker.chosen.synthetic ? ' · 合成协议测试' : ''}</p><Field label="本段翻译价格依据"><textarea readOnly value={JSON.stringify(run.preview.broker.chosen.price, null, 2)} /></Field></> : <StatusMessage tone="warning">没有可执行路线：{run.preview.broker.candidates.filter(item => item.route_id === route).flatMap(item => item.reasons).join('、') || 'NO_REGISTERED_ROUTE_SATISFIES_CURRENT_CONSTRAINTS'}</StatusMessage>}
        {run.preview.request && <><Field label="本段翻译精确提示词"><textarea readOnly value={run.preview.request.prompt} /></Field><Field label="本段翻译精确上下文"><textarea readOnly value={JSON.stringify(run.preview.request.context, null, 2)} /></Field><p>已排除：{run.preview.excluded.join('、')}</p></>}
        {canDispatch && <><label className="experimental-check"><input type="checkbox" checked={consent} disabled={disabled} onChange={e => setConsent(e.target.checked)} />已核对本段原文、术语、目标语言、本地路线和零成本预留</label><Button disabled={disabled || !consent} onClick={() => execute(() => api.translationAction(edition, run, 'dispatch'), '已记录原任务身份。关闭面板后可找回，不会重复启动。')}>明确启动本段翻译</Button></>}
      </>}
      {run.execution && <><p>原模型任务 {run.execution.job_id} · {run.execution.receipt_state} · 用量 {run.execution.usage_state}</p><p>账本 {run.execution.accounting?.status || '尚未核对'} · 实际费用 {run.execution.accounting?.actual_microusd == null ? '未知' : `${run.execution.accounting.actual_microusd} 微美元`}</p>{run.execution.failure_code && <StatusMessage tone="warning">{run.execution.failure_code}</StatusMessage>}<Button disabled={disabled || run.status === 'ADOPTED'} onClick={() => execute(() => api.translationAction(edition, run, 'refresh'), '已核对原任务与费用回执，没有启动新任务。')}>刷新原翻译任务并核对候选</Button></>}
      {!['ADOPTED', 'CANCELLED'].includes(run.status) && <Button disabled={disabled} onClick={() => execute(() => api.translationAction(edition, run, 'cancel'), '本翻译任务已取消，迟到候选不会采用。')}>取消本段翻译任务</Button>}
      {canAdopt && <><Field label="本段未审核翻译候选"><textarea readOnly value={run.candidate!.text} lang={edition.target_language} dir={edition.direction} /></Field><label className="experimental-check"><input type="checkbox" checked={adopt} disabled={disabled} onChange={e => setAdopt(e.target.checked)} />确认将候选替换本段已保存译文为草稿，之后另行审核</label><Button disabled={disabled || !adopt} onClick={() => perform(() => api.translationAdopt(edition, run), '候选已采用到本段译文草稿，仍需提交与逐段审核。')}>仅采用到本段译文草稿</Button></>}
    </section>}{action.feedback}
  </>;
}
