import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { ComicImageGenerationHost } from '../experimental/ComicLayoutsPanel';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { mediaProviderKey } from './useStudioMediaExecution';
import type { ProductionJob, ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { checkedComicImageCommand, checkedComicImageSource } from './studioComicImageContract';
import { comicImageJobMatches, type ComicImageRequest, type StudioComicImageClient } from './studioComicImageClient';

type Props = ComicImageGenerationHost & { client: StudioComicImageClient; production: StudioProductionClient; canMutate: boolean; canReview: boolean };
const parameters = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'] as const;
const labels = { width: '宽度', height: '高度', steps: '采样步数', seed: '种子', negative_prompt: '负向提示词', size: '图片规格', quality: '图片质量' };
const empty = () => Object.fromEntries(parameters.map(key => [key, ''])) as Record<typeof parameters[number], string>;
const stale = () => new ApiError({ status: 409, code: 'COMIC_IMAGE_VIEW_CHANGED', message: '当前漫画页面、格框或身份已变化，请重新打开。' });
const NO_ASSETS: [] = [];
/** The Comic page owns selection and adoption; the original Image controller owns every production/review action. */
export function StudioComicImageGeneration(props: Props) {
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), revision = useRef(0), pending = useRef(false), activeOperations = useRef(0), revoked = useRef(false);
  const [panelId, setPanelId] = useState(''), [providers, setProviders] = useState<ProductionProvider[]>([]), [providerKey, setProviderKey] = useState('');
  const [values, setValues] = useState(empty), [request, setRequest] = useState<ComicImageRequest>(), [job, setJob] = useState<ProductionJob>();
  const [recoverId, setRecoverId] = useState(''), [recoveredJob, setRecoveredJob] = useState<ProductionJob>();
  const exclusiveRef = useRef(false);
  const [exclusive, setExclusive] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [adoptUncertain, setAdoptUncertain] = useState(false);
  const authority = JSON.stringify([props.page.id, props.page.version, props.disabled, props.canMutate, props.canReview, props.isCurrent()]);
  const authorityRef = useRef(authority);
  if (authorityRef.current !== authority) { authorityRef.current = authority; revision.current++; if (!props.isCurrent()) revoked.current = true; }
  const owners = useRef([props.client, props.production, props.page]);
  if (owners.current[0] !== props.client || owners.current[1] !== props.production || owners.current[2] !== props.page) { owners.current = [props.client, props.production, props.page]; revision.current++; }
  const renderedRevision = revision.current;
  const jobRef = useRef<ProductionJob>();
  const selected = props.page.document?.panels.find(panel => panel.id === panelId);
  const provider = providers.find(row => mediaProviderKey(row) === providerKey);
  const current = () => renderedRevision === revision.current && alive.current && !revoked.current && latest.current.isCurrent() && !latest.current.disabled;
  const dirty = !!recoverId || !!request || !!providerKey || Object.values(values).some(Boolean);
  useEffect(() => { latest.current.onDirtyChange(dirty); }, [dirty]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; latest.current.onDirtyChange(false); latest.current.onBusyChange(false); }; }, []);
  useEffect(() => { activeOperations.current = 0; exclusiveRef.current = false; setExclusive(false); pending.current = false; setBusy(false); latest.current.onBusyChange(false); }, [authority]);
  const markBusy = (value: boolean) => { pending.current = value; setBusy(value); latest.current.onBusyChange(value); };
  async function guarded<T>(work: () => Promise<T>, concurrentRead = false): Promise<T> {
    if (!current() || pending.current && (!concurrentRead || exclusiveRef.current)) throw stale();
    const ticket = revision.current; activeOperations.current++; if (!concurrentRead) { exclusiveRef.current = true; setExclusive(true); } markBusy(true);
    try { const value = await work(); if (!current() || ticket !== revision.current) throw stale(); return value; }
    finally { if (alive.current && ticket === revision.current) { activeOperations.current = Math.max(0, activeOperations.current - 1); if (!concurrentRead) { exclusiveRef.current = false; setExclusive(false); } markBusy(activeOperations.current > 0); } }
  }
  const failure = (reason: unknown) => { if (current()) setError(apiErrorView(reason, '漫画图片操作未完成。请核对原记录。').message); };
  const change = (work: () => void) => { if (!current() || pending.current || request) return; revision.current++; work(); setError(''); setJob(undefined); };
  const clear = () => {
    if (renderedRevision !== revision.current || !alive.current || !latest.current.isCurrent() || pending.current) return;
    revision.current++; jobRef.current = undefined; setRequest(undefined); setJob(undefined); setRecoveredJob(undefined); setRecoverId(''); setProviderKey(''); setValues(empty()); setError(''); setAdoptUncertain(false); latest.current.onDirtyChange(false);
  };
  const blocked = !current() || busy;
  const unsupported = parameters.filter(key => values[key] !== '' && !provider?.supported_parameters.includes(key));
  const reason = !selected ? '先明确选择已保存的图片格框。' : selected.artwork_mode === 'BLANK' ? '留白格框不生成图片。请先修改画面类型并保存。'
    : selected.appearance_references?.length ? '当前只支持文字生成图片，不支持人物外观参考。不会忽略参考或自动换路线；请使用原图片制作入口，或明确移除参考并保存后再准备。'
    : !selected.image_brief?.trim() ? '请先填写图片简报并保存漫画页面。' : !provider ? '请明确选择本地服务商与模型。'
    : unsupported.length ? `所选配置不支持已填写的参数：${unsupported.map(key => labels[key]).join('、')}。输入不会自动丢弃。`
    : provider.supported_parameters.includes('seed') && !values.seed ? '请明确填写种子，固定本次请求。'
    : !values.size && !(values.width && values.height) ? '请明确填写宽度和高度，或选择图片规格。' : '';
  async function prepare() {
    if (!current() || blocked || !latest.current.canMutate || reason || request || !provider || !selected) return;
    const chosen = selected.id, ticket = revision.current;
    const options = Object.fromEntries(parameters.filter(key => values[key] !== '').map(key => [key, ['width', 'height', 'steps', 'seed'].includes(key) ? Number(values[key]) : values[key]]));
    if (Object.values(options).some(value => typeof value === 'number' && !Number.isFinite(value))) { setError('图片参数必须为有效数字。'); return; }
    try {
      const result = await guarded(() => props.client.request(props.page, chosen, { request_id: crypto.randomUUID(), provider_id: provider.provider_id, model_id: provider.model_id, parameters: options }));
      if (current() && revision.current === ticket) { revision.current++; jobRef.current = undefined; setRequest(result); setJob(undefined); setError(''); latest.current.onDirtyChange(true); }
    } catch (reason) { failure(reason); }
  }
  async function recover() {
    if (!current() || blocked || request || !selected || selected.artwork_mode === 'BLANK' || selected.appearance_references?.length || !recoverId.trim()) return;
    const ticket = revision.current;
    try {
      const value = await guarded(() => props.production.get('image', recoverId.trim()));
      const command = checkedComicImageCommand(value.command), source = checkedComicImageSource(command.source_snapshots[0]);
      const recovered: ComicImageRequest = { contract: 'studio-comic-image-request/1', source_snapshot: source, command,
        product_acceptance: 'LOCAL_REQUIRED', automatic_dispatch: false, model_called: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
      if (source.id !== props.page.id || source.version !== props.page.version || source.comic_panel.panel_id !== selected.id
        || command.prompt !== selected.image_brief || !comicImageJobMatches(recovered, value)) throw stale();
      if (current() && ticket === revision.current) { revision.current++; jobRef.current = value; setRequest(recovered); setRecoveredJob(value); setJob(value); setError(''); latest.current.onDirtyChange(true); }
    } catch (reason) { failure(reason); }
  }
  async function adopt() {
    if (!current() || blocked || !latest.current.canMutate || !request || !job || jobRef.current !== job || adoptUncertain || !comicImageJobMatches(request, job) || job.status !== 'APPROVED') return;
    const ticket = revision.current;
    // An ambiguous write is never replayed from this view. Reopen the original page to establish its current version.
    setAdoptUncertain(true);
    try {
      const page = await guarded(() => props.client.adopt(props.page, panelId, request, job));
      if (current() && revision.current === ticket) { latest.current.onDirtyChange(false); latest.current.onAdopt(page); }
    } catch (reason) { failure(reason); }
  }
  return <Panel title="为已保存格框生成图片">
    <p>只使用本地文字生成图片。准备请求不会调用模型；预览、入队、执行、原图片人工审核和采用到漫画草稿分别确认。采用后仍须重新预检、查看页面像素和审核布局。</p>
    {props.disabled && <StatusMessage tone="warning">请先保存页面和其它本地输入，并核对当前页面版本。</StatusMessage>}
    <fieldset disabled={blocked || !!request}>
      <label>生成图片的漫画格框<select value={panelId} onChange={event => change(() => setPanelId(event.target.value))}><option value="">明确选择格框</option>{props.page.document?.panels.map(panel => <option key={panel.id} value={panel.id}>格框 {panel.order} · {panel.artwork_mode === 'BLANK' ? '留白' : '图片'}</option>)}</select></label>
      {selected && <label>已保存的格框图片简报<textarea readOnly rows={3} value={selected.image_brief || ''} /></label>}
      <Button onClick={() => { if (!current() || blocked || request) return; void guarded(() => props.production.providers()).then(rows => { if (current()) { revision.current++; setProviders(rows.filter(row => row.operation_id === 'm5.image.t2i' && row.local)); setError(''); } }).catch(failure); }}>读取本地图片配置</Button>
      <label>漫画图片本地服务商与模型<select value={providerKey} onChange={event => change(() => { setProviderKey(event.target.value); latest.current.onDirtyChange(true); })}><option value="">明确选择配置</option>{providers.map(row => <option key={mediaProviderKey(row)} value={mediaProviderKey(row)}>{row.provider_id} · {row.model_id} · 本地</option>)}</select></label>
      {!providers.length && <p>尚未读取到本地文字生成图片配置；不会自动启用、下载模型或切换云端。</p>}
      {parameters.filter(key => provider?.supported_parameters.includes(key) || values[key] !== '').map(key => <label key={key}>漫画图片{labels[key]}<input type={['width', 'height', 'steps', 'seed'].includes(key) ? 'number' : 'text'} value={values[key]} maxLength={8000} onChange={event => change(() => { setValues(old => ({ ...old, [key]: event.target.value })); latest.current.onDirtyChange(true); })} /></label>)}
      {reason && <StatusMessage tone="warning">{reason}</StatusMessage>}
      <Button disabled={!!reason || !props.canMutate} onClick={() => void prepare()}>明确准备此格框图片请求</Button>
    </fieldset>
    {!request && <fieldset disabled={blocked}><legend>恢复已保存的原图片任务</legend>
      <p>明确选择同一已保存格框后，填写原任务 ID。只读取原图片任务，核对原页面版本、格框与请求；不会重新生成。原页面已变化时须回原任务查看，不能采用到新页面版本。</p>
      <label>漫画格框原图片任务 ID<input value={recoverId} maxLength={240} onChange={event => change(() => { setRecoverId(event.target.value); latest.current.onDirtyChange(true); })} /></label>
      <Button disabled={!selected || selected.artwork_mode === 'BLANK' || !!selected.appearance_references?.length || !recoverId.trim()} onClick={() => void recover()}>读取此格框原图片任务</Button>
    </fieldset>}
    {revoked.current && !busy && <Button onClick={clear}>关闭失效图片请求并保留原记录</Button>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {!request && dirty && <Button disabled={blocked} onClick={clear}>放弃漫画图片本地输入</Button>}
    {request && <StudioMediaExecutionPanel key={request.command.request_id} client={props.production} assets={NO_ASSETS} canMutate={props.canMutate} canReview={props.canReview}
      externalJob={recoveredJob} busy={exclusive} isCurrent={current} preparedIsCurrent={current} preparedCommand={request.command}
      read={work => guarded(work, true)} mutate={guarded} onDirtyChange={() => {}} onUnavailable={() => { revoked.current = true; setError('原图片权限或来源已变化，请重新打开漫画。'); }}
      onPreparedClose={clear} onJob={value => { const next = current() && comicImageJobMatches(request, value) ? value : undefined; jobRef.current = next; setJob(next); }} />}
    {request && job?.status === 'APPROVED' && <><p>原图片任务已审核。采用只更新当前格框的图片引用，并创建新的漫画 DRAFT 版本；不会自动批准或导出漫画。</p>
      <Button disabled={blocked || !props.canMutate || adoptUncertain || !comicImageJobMatches(request, job)} onClick={() => void adopt()}>明确采用已审核图片到此格框草稿</Button></>}
    {adoptUncertain && <StatusMessage tone="warning">采用已发送，请勿重复操作。若没有新页面回执，请关闭当前请求视图，再刷新原漫画页面核对。</StatusMessage>}
  </Panel>;
}
