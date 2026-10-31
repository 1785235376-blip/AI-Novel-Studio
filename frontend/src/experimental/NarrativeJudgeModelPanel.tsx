import { useLayoutEffect, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { ErrorMessage, Field } from './shared';
import { useReviewAction, type JudgeModelCatalog, type JudgeRun, type StyleReviewClient } from './styleReviewClient';

type Props = { api: StyleReviewClient; run: JudgeRun; chapter?: Chapter; onChanged: () => void };
export function NarrativeJudgeModelPanel({ api, run, chapter, onChanged }: Props) {
  const [catalog, setCatalog] = useState<JudgeModelCatalog>();
  const [route, setRoute] = useState(run.model_preview?.broker.chosen?.route_id || '');
  const [reviewed, setReviewed] = useState(false), [hidden, setHidden] = useState(false);
  const action = useReviewAction(), epoch = useRef(0);
  const chapterKey = `${chapter?.id}:${chapter?.version}`, previousChapter = useRef(chapterKey);
  useLayoutEffect(() => {
    if (previousChapter.current !== chapterKey) { epoch.current++; setReviewed(false); setHidden(true); previousChapter.current = chapterKey; }
  }, [chapterKey]);
  useLayoutEffect(() => { setReviewed(false); }, [run.model_preview?.preview_digest]);
  const preview = !run.stale && !hidden && run.model_preview;
  const execution = run.model_execution;
  const load = () => action.run(async current => {
    const ticket = ++epoch.current; const result = await api.judgeModelCatalog();
    if (current() && ticket === epoch.current) setCatalog(result);
  });
  const prepare = () => action.run(async current => {
    const ticket = ++epoch.current; await api.previewJudgeModel(run, route);
    if (current() && ticket === epoch.current) { setReviewed(false); setHidden(false); onChanged(); }
  });
  const dispatch = () => action.run(async current => {
    const ticket = ++epoch.current; setReviewed(false);
    await api.dispatchJudgeModel(run);
    if (current() && ticket === epoch.current) onChanged();
  });
  const reconcile = (cancel = false) => action.run(async current => {
    const ticket = ++epoch.current;
    await (cancel ? api.cancelJudgeModel(run) : api.refreshJudgeModel(run));
    if (current() && ticket === epoch.current) onChanged();
  });
  return <Panel title="可选的已注册模型审稿"><section aria-label="已注册模型审稿">
    <p>仅处理本次检查选定的已保存章节。先查看准确请求，再单独确认发送。只支持 LOCAL_ONLY 与已知零费用预占；不自动更换模型、重试或执行修订。</p>
    <StatusMessage>模型身份与独立性需要分开核对。相同模型不同提示不构成独立审稿；多个模型一致也不保证正确。没有模型配置时仍可使用确定性规则。</StatusMessage>
    {!execution && <><Button disabled={action.busy || run.stale} onClick={() => void load()}>查看已注册本地审稿路线</Button>
      {catalog && <><Field label="已注册本地审稿模型"><select disabled={action.busy} value={route} onChange={event => { epoch.current++; setRoute(event.target.value); setReviewed(false); setHidden(true); }}><option value="">请选择本地模型</option>{catalog.routes.map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.display_name} · {row.provider_id}/{row.model_id}{row.synthetic ? ' · 合成协议测试' : ''}{!row.available ? ' · 不可用' : ''}</option>)}</select></Field>
        {!catalog.routes.length && <EmptyState title="没有已注册的本地文本模型" detail="请在现有模型中心完成配置后刷新路线；本页不会安装模型或自动改用云端。" />}
        {catalog.routes.filter(row => !row.available).map(row => <StatusMessage key={row.route_id} tone="warning">{row.provider_id}/{row.model_id}：{row.reasons.join('；')}</StatusMessage>)}
        <Button disabled={action.busy || run.stale || !route || !catalog.routes.some(row => row.route_id === route && row.available)} onClick={() => void prepare()}>准备准确模型审稿预览</Button>
      </>}
    </>}
    {preview && <section aria-label="准确模型审稿预览">
      <Badge>{preview.quality_verification === 'SYNTHETIC_PROTOCOL_ONLY' ? '合成协议测试，未验证真实模型' : '文学质量未验证'}</Badge>
      <p>Actor：{preview.actor} · Rubric：{preview.rubric.id} v{preview.rubric.version}</p>
      <p>本次已保存来源：{Object.entries(preview.sources).map(([id, source]) => `${id} v${source.version}`).join('；')}。不截断；Token 数未知。</p>
      <p>输出上限 {preview.max_output_bytes} 字节；时间上限 {preview.timeout_seconds} 秒。项目预算版本 {preview.broker.budget_version}。</p>
      <Field label="准确模型请求（含完整选中证据）"><textarea readOnly rows={10} value={JSON.stringify(preview.request, null, 2)} /></Field>
      <Field label="准确模型身份、价格与预算预览"><textarea readOnly rows={6} value={JSON.stringify({ actor: preview.actor, scope: preview.scope, sources: preview.sources, previewed_at: preview.previewed_at, budget: preview.budget, broker: preview.broker }, null, 2)} /></Field>
      <p>明确排除：{preview.excluded.join('、')}。正文证据是资料，不构成工具或写入授权。</p>
      {!preview.execution_available && <StatusMessage tone="warning">此路线未满足当前价格、预算或权限条件。请核对预览中的原因后重新准备；不会发送。</StatusMessage>}
      {!execution && <><label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || !preview.execution_available} onChange={event => setReviewed(event.target.checked)} />已核对完整证据、版本、模型身份与零费用预占</label><Button disabled={action.busy || !reviewed || !preview.execution_available || run.stale} onClick={() => void dispatch()}>明确发送此次本地模型审稿</Button></>}
    </section>}
    {hidden && !execution && <StatusMessage tone="warning">范围或选择已变化，旧预览不能发送。请重新准备准确预览。</StatusMessage>}
    {execution && <section aria-label="原始模型任务状态"><p>原任务 {execution.job_id} · {execution.status} · {execution.receipt_state}</p>
      <p>{execution.model_called ? '已发生适配器调度；已发送的数据不能撤回。' : '尚未确认适配器调度。'} 用量状态：{execution.usage_state}</p>
      {execution.failure_code && <StatusMessage tone="warning">{execution.failure_code}。无效输出不会进入模型意见。</StatusMessage>}
      {execution.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY' && <StatusMessage tone="warning">原任务状态未知。请检查原任务和预算账本；不会自动重放、另建任务或释放未知预占。</StatusMessage>}
      {execution.accounting && <Field label="原任务预算结算"><textarea readOnly value={JSON.stringify(execution.accounting, null, 2)} /></Field>}
      <Button disabled={action.busy || run.stale} onClick={() => void reconcile()}>查询原任务并核对模型证据</Button>
      <Button disabled={action.busy || ['COMPLETED', 'FAILED', 'CANCELLED'].includes(execution.status)} onClick={() => void reconcile(true)}>取消原模型任务</Button>
      <p>查询只读取原任务；有效模型意见显示于下方并单独标注，不会修改正文或 Canon。</p>
    </section>}
    {!!action.error && <><ErrorMessage error={action.error} /><StatusMessage tone="warning">请求未确认。可刷新原检查记录核对状态；不会自动再次发送。若缺少主机会话、功能开关、价格或运行时，请先完成对应配置。</StatusMessage></>}
  </section></Panel>;
}
