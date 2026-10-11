import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { MEDIA_OPERATION_LABELS, MEDIA_STATUS_LABELS, mediaProviderKey, useStudioMediaExecution, type MediaParameter, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { MediaOperation } from './studioProductionClient';
import { StudioTimelineMeasurement } from './StudioTimelineMeasurement';

export type { StudioMediaExecutionProps } from './useStudioMediaExecution';
const labels: Record<MediaParameter, string> = { width: '宽度（64–2048）', height: '高度（64–2048）', steps: '采样步数（1–150）', seed: '种子（0–2147483647）',
  negative_prompt: '负向提示词', size: '图片规格', quality: '图片质量', duration_seconds: '时长（1–600 秒）', frame_rate: '帧率（1–60）', voice_id: '语音标识',
  speech_rate: '语速（0.5–2）', in_ms: '来源起点（毫秒）', out_ms: '来源终点（毫秒）' };
const ranges: Partial<Record<MediaParameter, [number, number, number]>> = { width: [64, 2048, 8], height: [64, 2048, 8], steps: [1, 150, 1], seed: [0, 2147483647, 1],
  duration_seconds: [1, 600, 1], frame_rate: [1, 60, 1], speech_rate: [0.5, 2, 0.1], in_ms: [0, 600000, 1], out_ms: [1, 600000, 1] };
const kindLabels = { image: '图片', video: '视频', audio: '音频' };

/** A replaceable presentation over the original receipt-aware media controller. */
export function StudioMediaExecutionPanel(props: StudioMediaExecutionProps) {
  const state = useStudioMediaExecution(props), draft = state.draft, job = state.selected;
  const providers = state.providers.filter(row => row.operation_id === draft.operation);
  const sourceAssets = props.assets.filter(asset => asset.kind === state.requiredSourceKind && !asset.deleted_at);
  const selectedIds = draft.sources.map(source => source.id), trim = draft.operation === 'm8.audio.trim';
  function parameter(name: MediaParameter) {
    const value = draft.parameters[name];
    if (name === 'negative_prompt') return <label key={name}>{labels[name]}<textarea maxLength={8000} disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)} /></label>;
    if (name === 'size' || name === 'quality') {
      const options = name === 'size' ? ['auto', '1024x1024', '1536x1024', '1024x1536'] : ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
      return <label key={name}>{labels[name]}<select disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)}><option value="">使用服务商默认值</option>{options.map(option => <option key={option} value={option}>{option}</option>)}</select></label>;
    }
    const range = ranges[name];
    return <label key={name}>{labels[name]}<input type={range ? 'number' : 'text'} min={range?.[0]} max={range?.[1]} step={range?.[2]} maxLength={name === 'voice_id' ? 240 : undefined}
      disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)} /></label>;
  }
  return <Panel title="媒体制作与审核" className="studio-graph-run">
    <p>预览、入队、执行和审核分别确认。候选先保持私有，人工审核后再入素材库。完整本机验收仍待完成（LOCAL_REQUIRED）。</p>
    {state.error && <StatusMessage tone="error">{state.error}</StatusMessage>}
    {state.notice && <StatusMessage>{state.notice}</StatusMessage>}
    {state.uncertain && <StatusMessage tone="warning">操作结果尚未确认，已阻止继续发送。请读取原任务核对；不会自动重试。</StatusMessage>}
    {state.repeatBlocked && <StatusMessage tone="warning">当前版本已有发送记录。相同动作不会再次发送，请继续读取原记录核对。</StatusMessage>}
    {state.uncertainRequestId && <p>待核对的原请求：<code>{state.uncertainRequestId}</code>。使用“读取任务列表”寻找已保存回执。</p>}
    <section aria-label="媒体制作输入">
      <h3>制作输入</h3>
      <label>操作<select disabled={!state.canEdit} value={draft.operation} onChange={event => state.changeOperation(event.target.value as MediaOperation)}>
        {Object.entries(MEDIA_OPERATION_LABELS).map(([id, title]) => <option key={id} value={id}>{title}</option>)}
      </select></label>
      {!trim && <>
        <label>服务商与模型<select disabled={!state.canEdit || state.providerLoading} value={draft.providerKey} onChange={event => state.changeField('providerKey', event.target.value)}>
          <option value="">明确选择当前配置</option>{providers.map(row => <option key={mediaProviderKey(row)} value={mediaProviderKey(row)}>{row.provider_id} · {row.model_id} · {row.local ? '本地' : '云端'}</option>)}
        </select></label>
        <p>配置参考不代表服务已验证可用。{!state.providerLoading && !providers.length && '暂无对应配置，请先完成服务商与模型配置。'}</p>
        <Button disabled={!state.canRead || state.providerLoading} loading={state.providerLoading} onClick={() => void state.loadProviders()}>重新读取配置</Button>
        <label>本次提示词<textarea maxLength={16000} disabled={!state.canEdit} value={draft.prompt} onChange={event => state.changeField('prompt', event.target.value)} /></label>
        {state.provider && !state.provider.local && <label><input type="checkbox" disabled={!state.canEdit} checked={draft.allowCloud} onChange={event => state.changeField('allowCloud', event.target.checked)} />确认本次允许将提示词及选中的参考素材发送到该云端服务，可能产生费用</label>}
      </>}
      {state.requiredSourceKind && <fieldset disabled={!state.canEdit}><legend>{kindLabels[state.requiredSourceKind]}来源 · {draft.operation === 'm5.image.i2i' ? '选取 1–5 张' : '选取 1 个'}</legend>
        {!sourceAssets.length && <p>当前素材库没有对应类型的可用来源。</p>}
        {sourceAssets.map(asset => <label key={asset.id}><input type="checkbox" checked={selectedIds.includes(asset.id)} onChange={event => state.selectSource(asset.id, event.target.checked)} />{asset.filename} · v{asset.version}</label>)}
        {!!draft.sources.length && <><ul>{draft.sources.map(source => <li key={source.id}>已绑定来源 {props.assets.find(row => row.id === source.id)?.filename || source.id} · v{source.version}</li>)}</ul>
          {!state.freshSources && <StatusMessage tone="warning">来源已变化或不可用，先重新选取版本再预览。</StatusMessage>}
          <Button disabled={!state.canEdit} onClick={state.refreshSources}>明确选取当前来源版本</Button>
          <Button disabled={!state.canEdit} onClick={() => draft.sources.forEach(source => state.selectSource(source.id, false))}>移除已选来源</Button>
        </>}
      </fieldset>}
      <fieldset disabled={!state.canEdit}><legend>处理参数</legend><p>{state.provider || trim ? '仅列所选配置支持的参数；可选项留空时使用原服务商默认值。' : '先选择服务商，再填写它支持的参数。'}{trim && '片段最长 120 秒；起止点还须在真实来源时长内。'}</p>{state.parameterNames.map(parameter)}
        {!!state.unsupportedParameters.length && <><StatusMessage tone="warning">所选配置不支持已填写的参数：{state.unsupportedParameters.map(name => labels[name]).join('、')}。这些输入不会自动丢弃。</StatusMessage><Button disabled={!state.canEdit} onClick={state.clearUnsupportedParameters}>明确清空不支持的参数</Button></>}
      </fieldset>
      <label>来源与授权说明<input maxLength={2000} disabled={!state.canEdit} value={draft.licenseNote} onChange={event => state.changeField('licenseNote', event.target.value)} /></label>
      {state.inputError && <p>{state.inputError}</p>}
      <div className="studio-graph-actions"><Button disabled={!state.canInspect} loading={state.pending === 'PREVIEW'} onClick={() => void state.inspect()}>读取制作预览</Button><Button disabled={!state.canEdit} onClick={state.clearInputs}>清空本地输入</Button></div>
      {state.preview && <section aria-label="制作预览确认"><h4>确认本次预览</h4><p>{MEDIA_OPERATION_LABELS[state.preview.operation_id]} · {state.preview.provider ? `${state.preview.provider.provider_id} / ${state.preview.provider.model_id} · ${state.preview.provider.local ? '本地' : '云端'}` : '本地截取'}</p>
        <p>预览绑定当前输入、来源版本与服务商路线。创建仅保存任务，尚不执行。</p>
        <details><summary>核对本次执行接口、默认参数与工作流</summary><p>本次预览的接口记录，不代表服务商或模型已成功运行。</p><pre>{JSON.stringify(state.preview.execution_recipe, null, 2)}</pre></details>
        <label><input type="checkbox" disabled={state.locked || !props.canMutate} checked={state.previewReviewed} onChange={event => state.confirmPreview(event.target.checked)} />已核对本次输入、来源和处理边界</label>
        <Button disabled={!state.canCreate} loading={state.pending === 'CREATE'} onClick={() => void state.create()}>仅创建任务并入队</Button>
      </section>}
    </section>
    <section aria-label="原媒体任务记录"><h3>任务记录</h3><Button disabled={!state.canRead} loading={state.pending === 'LIST'} onClick={() => void state.listJobs()}>读取任务列表</Button>
      {!state.jobs.length && <p>读取后可选择已保存的任务，不会自动创建或执行。</p>}
      {!!state.jobs.length && <label>已保存任务<select disabled={!state.canRead} value={job ? `${job.owner}:${job.id}` : ''} onChange={event => { const selected = state.jobs.find(row => `${row.owner}:${row.id}` === event.target.value); if (selected) void state.openJob(selected); }}>
        <option value="">选择原任务记录</option>{state.jobs.map(row => <option key={`${row.owner}:${row.id}`} value={`${row.owner}:${row.id}`}>{MEDIA_OPERATION_LABELS[row.operation_id as MediaOperation] || '多轨合成'} · {MEDIA_STATUS_LABELS[row.status]} · v{row.version} · {row.id}</option>)}
      </select></label>}
      {job && <section aria-label="当前媒体任务"><Badge>{MEDIA_STATUS_LABELS[job.status]}</Badge><p>任务 {job.id} · v{job.version}</p>
        <details><summary>本任务已确认的输入与处理记录</summary>
          <p>这里显示刚读取的服务端公共回执，不会替换当前制作输入，也不代表本机能力验收已通过。</p>
          {job.command ? <>
            <label>原提示词<textarea readOnly rows={4} value={job.command.prompt} aria-label="原任务已确认的提示词" /></label>
            <h4>原任务参数</h4>
            {Object.keys(job.command.parameters).length ? <dl>{Object.entries(job.command.parameters).map(([name, value]) => <div key={name}>
              <dt>{labels[name as MediaParameter] || name}</dt><dd>{value === null ? '未显式指定' : String(value)}</dd>
            </div>)}</dl> : <p>原请求未显式填写处理参数；实际处理记录以执行接口记录和回执为准。</p>}
            <p>云端发送确认：{job.command.allow_cloud ? '本请求已明确允许' : '本请求未允许'}。</p>
            {!!job.command.license_note && <label>原来源与授权说明<textarea readOnly rows={2} value={job.command.license_note} /></label>}
          </> : <p>该任务没有媒体制作输入投影，请核对其绑定的原时间线记录。</p>}
          {job.provider ? <dl>
            <dt>服务商与模型</dt><dd>{job.provider.provider_id} / {job.provider.model_id} · {job.provider.local ? '本地' : '云端'}</dd>
            <dt>已绑定路线摘要</dt><dd><code>{job.provider.route_digest}</code></dd>
          </dl> : <p>该任务没有外部服务商路线投影。</p>}
          <dl><dt>原请求摘要</dt><dd><code>{job.request_digest}</code></dd>
            <dt>原结果回执摘要</dt><dd>{job.receipt_digest ? <code>{job.receipt_digest}</code> : '尚未形成结果回执摘要'}</dd></dl>
          <details><summary>执行接口记录与技术摘要</summary><p>已确认的接口、参数和工作流记录；这些元数据不证明远端结果或本机验收。</p>
            <pre>{JSON.stringify(job.execution_recipe, null, 2)}</pre>
          </details>
        </details>
        {job.timeline_snapshot && <details><summary>来源时间线 {job.timeline_snapshot.id} · v{job.timeline_snapshot.version}</summary><p>原执行入口会再次核对摘要：<code>{job.timeline_snapshot.digest}</code></p></details>}
        {job.owner === 'timeline' && <StudioTimelineMeasurement measurement={job.media_measurement} />}
        {!!job.sources.length && <details><summary>本任务绑定的来源版本</summary><ul>{job.sources.map(source => <li key={`${source.kind}:${source.id}`}>{source.kind === 'ASSET' ? props.assets.find(row => row.id === source.id)?.filename || source.id : source.id} · v{source.version}<p>来源摘要：<code>{source.digest}</code></p></li>)}</ul></details>}
        {!state.jobSourcesFresh && <StatusMessage tone="warning">本任务的素材来源已变化，当前不可继续执行或审核。保留原记录供读取核对。</StatusMessage>}
        {job.status === 'UNKNOWN' && <StatusMessage tone="warning">无法确认先前分派结果，禁止再次执行。同一原任务只能继续读取核对或丢弃本地结果。</StatusMessage>}
        {job.status === 'REVIEWING' && <StatusMessage tone="warning">原审核可能已经提交。先读取任务和候选，再确认原审核；不会重新生成。</StatusMessage>}
        {job.error_code && <details><summary>任务回执细节</summary><p>{job.error_code}</p></details>}
        <Button disabled={!state.canRead} loading={state.pending === 'GET'} onClick={() => void state.openJob(job)}>读取当前任务核对</Button>
        <Button disabled={!state.canRead} onClick={state.downloadReceipt}>下载当前已读回执（JSON）</Button>
        <div className="studio-graph-actions">
          <Button disabled={!state.canAction('execute')} loading={state.pending === 'execute'} onClick={() => void state.action('execute')}>明确执行当前入队任务</Button>
          {job.owner === 'video' && <Button disabled={!state.canAction('refresh')} loading={state.pending === 'refresh'} onClick={() => void state.action('refresh')}>核对已有远端进度</Button>}
          {['RUNNING', 'SEND_RESERVED'].includes(job.status) && <Button disabled={!state.canAction('reconcile')} loading={state.pending === 'reconcile'} onClick={() => void state.action('reconcile')}>核对中断状态，不重新发送</Button>}
          {(job.owner !== 'timeline' || ['RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status)) && <Button variant="danger" disabled={!state.canAction('cancel')} loading={state.pending === 'cancel'} onClick={() => void state.action('cancel')}>{job.owner === 'timeline' && job.status === 'RUNNING' ? '明确取消本地渲染' : '丢弃未采用的本地结果'}</Button>}
        </div>
        <p>{job.owner === 'timeline' ? '时间线取消会请求原本地渲染停止或撤销未审核候选的采用权限，保留原回执与已有候选；已进入审核或已入库的结果不能从这里取消。' : '丢弃仅撤销本地采用结果的权限，保留原记录；远端计算可能继续。'}</p>
        {job.output_candidate && <section aria-label="媒体候选预览与审核"><h4>候选结果</h4><p>{kindLabels[job.output_candidate.kind]}候选 · v{job.output_candidate.version}</p>
          <Button disabled={!state.canLoadCandidate} loading={state.pending === 'CANDIDATE'} onClick={() => void state.loadCandidate()}>读取并核对候选媒体</Button>
          {state.candidate?.kind === 'image' && <img src={state.candidate.url} style={{ maxWidth: '100%', maxHeight: 'var(--layout-inspector-width)' }} alt="本任务经摘要核对的图片候选" onError={() => state.mediaFailed(state.candidate?.binding || '')} />}
          {state.candidate?.kind === 'video' && <video src={state.candidate.url} style={{ maxWidth: '100%', maxHeight: 'var(--layout-inspector-width)' }} controls preload="metadata" aria-label="本任务的视频候选" onError={() => state.mediaFailed(state.candidate?.binding || '')} />}
          {state.candidate?.kind === 'audio' && <audio src={state.candidate.url} style={{ maxWidth: '100%' }} controls preload="metadata" aria-label="本任务的音频候选" onError={() => state.mediaFailed(state.candidate?.binding || '')} />}
          {['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING'].includes(job.status) && <><label><input type="checkbox" disabled={state.locked || !props.canReview || state.uncertain || !state.candidate} checked={state.outputReviewed} onChange={event => state.confirmReview(event.target.checked)} />已查看本次候选，确认采用当前任务版本与输出摘要</label>
            <Button disabled={!state.canAction('review')} loading={state.pending === 'review'} onClick={() => void state.action('review')}>明确审核并入素材库</Button></>}
          {job.status === 'APPROVED' && <StatusMessage tone="success">原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。</StatusMessage>}
        </section>}
      </section>}
    </section>
  </Panel>;
}
