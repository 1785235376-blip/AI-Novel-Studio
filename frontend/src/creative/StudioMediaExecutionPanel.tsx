import { IMAGE_REFERENCE_PURPOSES, IMAGE_REFERENCE_PURPOSE_LABELS } from './studioImageRuntimeContract';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { MEDIA_OPERATION_LABELS, MEDIA_STATUS_LABELS, mediaProviderKey, useStudioMediaExecution, type MediaParameter, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { MediaOperation } from './studioProductionClient';
import { usableCutoutSource } from './studioCutoutContract';
import { StudioTimelineMeasurement } from './StudioTimelineMeasurement';

export type { StudioMediaExecutionProps } from './useStudioMediaExecution';
const labels: Record<MediaParameter, string> = { scale: '超分倍率', width: '宽度（64–2048）', height: '高度（64–2048）', steps: '采样步数（1–150）', seed: '种子（0–2147483647）',
  negative_prompt: '负向提示词', size: '图片规格', quality: '图片质量', denoising_strength: '重绘强度（大于 0 至 1，可选）', duration_seconds: '时长（1–600 秒）', frame_rate: '帧率（1–60）', voice_id: '语音标识',
  speech_rate: '语速（0.5–2）', in_ms: '来源起点（毫秒）', out_ms: '来源终点（毫秒）', gain_db: '增益（-60–12 dB，可选）', sample_rate: '输出采样率（8000–96000 Hz，可选）', channels: '输出声道（可选）', output_format: '独立音频交付格式（可选）' };
const ranges: Partial<Record<MediaParameter, [number, number, number]>> = { width: [64, 2048, 8], height: [64, 2048, 8], steps: [1, 150, 1], seed: [0, 2147483647, 1],
  denoising_strength: [0.01, 1, 0.01], duration_seconds: [1, 600, 1], frame_rate: [1, 60, 1], speech_rate: [0.5, 2, 0.1], in_ms: [0, 600000, 1], out_ms: [1, 600000, 1], gain_db: [-60, 12, 0.1], sample_rate: [8000, 96000, 1] };
const kindLabels = { image: '图片', video: '视频', audio: '音频' };

/** A replaceable presentation over the original receipt-aware media controller. */
export function StudioMediaExecutionPanel(props: StudioMediaExecutionProps) {
  const state = useStudioMediaExecution(props), draft = state.draft, job = state.selected;
  const providers = state.providers.filter(row => row.operation_id === draft.operation);
  const upscale = draft.operation === 'm5.image.upscale';
  const cutout = draft.operation === 'm5.image.cutout';
  const inpaint = draft.operation === 'm5.image.inpaint', reference = draft.operation === 'm5.image.reference';
  const sourceAssets = props.assets.filter(asset => asset.kind === state.requiredSourceKind && !asset.deleted_at && (!(cutout || inpaint) || usableCutoutSource(asset) && !asset.manual_mask));
  const selectedIds = draft.sources.map(source => source.id), trim = draft.operation === 'm8.audio.trim';
  function parameter(name: MediaParameter) {
    const value = draft.parameters[name];
    if (name === 'output_format') return <label key={name}>{labels[name]}<select disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)}><option value="">默认 WAV，保持原请求</option><option value="FLAC">FLAC · 处理后 S16 无损压缩</option><option value="MP3">MP3 · 有损压缩（固定码率）</option></select></label>;
    if (name === 'negative_prompt') return <label key={name}>{labels[name]}<textarea maxLength={8000} disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)} /></label>;
    if (name === 'scale') return <label key={name}>{labels[name]}<select disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)}><option value="">明确选择倍率</option><option value="2">2 倍</option><option value="4">4 倍</option></select></label>;
    if (name === 'channels') return <label key={name}>{labels[name]}<select disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)}><option value="">默认双声道（2）</option><option value="1">单声道（1）</option><option value="2">双声道（2）</option></select></label>;
    if (name === 'size' || name === 'quality') {
      const options = name === 'size' ? ['auto', '1024x1024', '1536x1024', '1024x1536'] : ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
      return <label key={name}>{labels[name]}<select disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)}><option value="">使用服务商默认值</option>{options.map(option => <option key={option} value={option}>{option}</option>)}</select></label>;
    }
    const range = ranges[name];
    return <label key={name}>{labels[name]}<input type={range ? 'number' : 'text'} min={range?.[0]} max={range?.[1]} step={name === 'gain_db' ? 'any' : range?.[2]} maxLength={name === 'voice_id' ? 240 : undefined}
      disabled={!state.canEdit} value={value} onChange={event => state.changeParameter(name, event.target.value)} /></label>;
  }
  return <Panel title="媒体制作与审核" className="studio-graph-run">
    <p>预览、入队、执行和审核分别确认。候选先保持私有，人工审核后再入素材库。完整本机验收仍待完成（LOCAL_REQUIRED）。</p>
    {state.error && <StatusMessage tone="error">{state.error}</StatusMessage>}
    {state.notice && <StatusMessage>{state.notice}</StatusMessage>}
    {state.uncertain && <StatusMessage tone="warning">操作结果尚未确认，已阻止继续发送。请读取原任务核对；不会自动重试。</StatusMessage>}
    {state.repeatBlocked && <StatusMessage tone="warning">当前版本已有发送记录。相同动作不会再次发送，请继续读取原记录核对。</StatusMessage>}
    {state.uncertainRequestId && <p>待核对的原请求：<code>{state.uncertainRequestId}</code>。使用“读取任务列表”寻找已保存回执。</p>}
    <section aria-label="媒体制作输入">{props.preparedCommand ? <><h3>{props.preparedCommand.operation_id.startsWith("m7.") ? "原分镜视频请求" : "原分镜图片请求"}</h3><p>输入来自已核对的分镜与镜头版本；更换参数须返回原分镜明确准备新请求。预览、入队、执行与审核仍分别确认。</p><details><summary>核对完整来源与输入</summary><pre>{JSON.stringify(props.preparedCommand, null, 2)}</pre></details><Button disabled={!state.canRead || state.providerLoading} onClick={() => void state.loadProviders()}>明确读取当前请求服务配置</Button><Button disabled={!state.canInspect} onClick={() => void state.inspect()}>读取制作预览</Button><Button disabled={!state.canClosePrepared} onClick={state.clearInputs}>关闭当前请求视图，保留原任务</Button></> : <>
      <h3>制作输入</h3>
      <label>操作<select disabled={!state.canEdit} value={draft.operation} onChange={event => state.changeOperation(event.target.value as MediaOperation)}>
        {Object.entries(MEDIA_OPERATION_LABELS).map(([id, title]) => <option key={id} value={id}>{title}</option>)}
      </select></label>
      {cutout && <p>本地 CPU 使用已保存的手绘二值遮罩：白色保留来源像素，黑色变为透明且清零颜色。输出同尺寸 PNG；不使用服务商、模型、提示词或云端。仅接受 64–1024、宽高为 8 的倍数的 PNG 来源与对应遮罩，执行时再次核对真实字节。</p>}
      {!trim && !cutout && <>
        <label>服务商与模型<select disabled={!state.canEdit || state.providerLoading} value={draft.providerKey} onChange={event => state.changeField('providerKey', event.target.value)}>
          <option value="">明确选择当前配置</option>{providers.map(row => <option key={mediaProviderKey(row)} value={mediaProviderKey(row)}>{row.provider_id} · {row.model_id} · {row.local ? '本地' : '云端'}</option>)}
        </select></label>
        <p>配置参考不代表服务已验证可用。{!state.providerLoading && !providers.length && '暂无对应配置，请先完成服务商与模型配置。'}</p>
        {state.provider?.image_capabilities && <p>当前图片配方：{state.provider.image_capabilities.recipe_id}。输入结构已核对，真实推理尚未验证。参考图最多 {state.provider.image_capabilities.reference_limit} 张；{state.provider.image_capabilities.reference_semantics === 'WEIGHTED_PIXEL_INITIALIZATION' ? '权重用于归一化混合参考像素后初始化生成，不代表角色或风格识别质量。' : '当前路线采用单图初始化。'}</p>}
        <Button disabled={!state.canRead || state.providerLoading} loading={state.providerLoading} onClick={() => void state.loadProviders()}>重新读取配置</Button>
        {!upscale && <label>本次提示词<textarea maxLength={16000} disabled={!state.canEdit} value={draft.prompt} onChange={event => state.changeField('prompt', event.target.value)} /></label>}
        {state.provider && !state.provider.local && <label><input type="checkbox" disabled={!state.canEdit} checked={draft.allowCloud} onChange={event => state.changeField('allowCloud', event.target.checked)} />确认本次允许将提示词及选中的参考素材发送到该云端服务，可能产生费用</label>}
      </>}
      {state.requiredSourceKind && !reference && <fieldset disabled={!state.canEdit}><legend>{kindLabels[state.requiredSourceKind]}来源 · {draft.operation === 'm5.image.i2i' && !state.imageInputs ? '选取 1–5 张' : '选取 1 个'}</legend>
        {!sourceAssets.length && <p>当前素材库没有对应类型的可用来源。</p>}
        {sourceAssets.map(asset => <label key={asset.id}><input type="checkbox" checked={cutout ? draft.sources[0]?.id === asset.id : state.imageInputs ? draft.imageSource?.id === asset.id : selectedIds.includes(asset.id)} onChange={event => state.selectSource(asset.id, event.target.checked)} />{asset.filename} · v{asset.version}</label>)}
        {!!draft.sources.length && <><ul>{draft.sources.map(source => <li key={source.id}>已绑定来源 {props.assets.find(row => row.id === source.id)?.filename || source.id} · v{source.version}</li>)}</ul>
          {!state.freshSources && (!cutout || draft.sources.length === 2) && <StatusMessage tone="warning">来源已变化或不可用，先重新选取版本再预览。</StatusMessage>}
          <Button disabled={!state.canEdit} onClick={state.refreshSources}>明确选取当前来源版本</Button>
          <Button disabled={!state.canEdit} onClick={state.clearSources}>移除已选来源</Button>
        </>}
      </fieldset>}
      {(cutout || inpaint) && <fieldset disabled={!state.canEdit}><legend>已保存的手绘二值遮罩</legend>
        {inpaint && <p>沿用原手绘遮罩：白色像素保留原图，黑色区域重绘。后端转换处理语义并保护白色区域；原图与遮罩版本必须匹配。结果仍为私有候选，须人工审核。</p>}
        <label>绑定当前来源版本的遮罩<select value={inpaint ? draft.maskSource?.id || '' : draft.sources[1]?.id || ''} onChange={event => state.selectMask(event.target.value)}><option value="">明确选择一个已核对的遮罩</option>{state.eligibleMasks.map(mask => <option key={mask.id} value={mask.id}>{mask.filename} · v{mask.version} · {mask.manual_mask!.width} × {mask.manual_mask!.height}</option>)}</select></label>
        {!draft.sources.length ? <p>先选取 PNG 来源，再选择为该来源版本保存的遮罩。</p> : !state.eligibleMasks.length && <p>当前没有匹配此来源版本的可用手绘遮罩。请在素材工作区选择来源、绘制并保存二值遮罩，再读取当前素材版本。</p>}
        {draft.sources[1] && !state.freshSources && <StatusMessage tone="warning">来源或遮罩已变化、删除或失去核对信息。原预览与确认已失效；重新读取并明确选择当前版本。</StatusMessage>}
      </fieldset>}
      {state.imageInputs && !inpaint && !upscale && <fieldset disabled={!state.canEdit}><legend>图片参考与权重 · 绑定确切版本</legend>
        <p>{reference ? '选择 1–5 张参考图；当前服务的上限见配方说明。' : '基础图独立绑定；可再明确选择配方支持的辅助参考。'}权重须大于 0 且不超过 1；按当前配方初始化像素，不保证语义或风格一致性。</p>
        {props.assets.filter(asset => asset.kind === 'image' && !asset.deleted_at && !asset.manual_mask).map(asset => <label key={asset.id}><input type="checkbox" checked={draft.imageReferences.some(row => row.source.id === asset.id)} onChange={event => state.selectReference(asset.id, event.target.checked)} />参考 {asset.filename} · v{asset.version}</label>)}
        {draft.imageReferences.map(row => <section key={row.source.id}><label>参考权重 · {props.assets.find(asset => asset.id === row.source.id)?.filename || row.source.id} · v{row.source.version}<input aria-label={`参考权重 · ${props.assets.find(asset => asset.id === row.source.id)?.filename || row.source.id} · v${row.source.version}`} type="number" min={0.01} max={1} step={0.01} value={row.weight} onChange={event => state.changeReferenceWeight(row.source.id, event.target.value)} /><code>{row.source.digest}</code></label><label>参考用途 · {row.source.id}<select value={row.purpose || ''} onChange={event => state.changeReferenceMetadata(row.source.id, 'purpose', event.target.value)}><option value="">未指定用途</option>{IMAGE_REFERENCE_PURPOSES.map(purpose => <option key={purpose} value={purpose}>{IMAGE_REFERENCE_PURPOSE_LABELS[purpose]}</option>)}</select></label><label>参考来源说明 · {row.source.id}<input maxLength={500} value={row.source_note || ''} onChange={event => state.changeReferenceMetadata(row.source.id, 'source_note', event.target.value)} /></label></section>)}
        {!!draft.sources.length && <><Button disabled={!state.canEdit} onClick={state.refreshSources}>明确选取当前参考版本</Button><Button disabled={!state.canEdit} onClick={state.clearSources}>移除图片输入绑定</Button></>}
        {!state.freshSources && draft.imageReferences.length > 0 && <StatusMessage tone="warning">已绑定的图片版本变化；旧预览与确认失效，请明确重新选择。</StatusMessage>}
      </fieldset>}
      {draft.operation === 'm7.video.v2v' && <label>参考视频用途<select value={draft.videoReferencePurpose || ''} disabled={!state.canEdit} onChange={event => state.changeField('videoReferencePurpose', event.target.value)}><option value="">普通视频来源</option><option value="style">风格参考</option><option value="action">动作参考</option><option value="camera">摄影机参考</option></select></label>}
      {state.provider?.video_capabilities && <p>本地视频配方 {state.provider.video_capabilities.recipe_id}：已核对节点结构，真实推理尚未验证。64–1024、宽高为 32 的倍数，1–10 秒、1–30 fps；输出按模型帧步长取整后的 VP9 WebM。当前本地路线不执行参考视频。</p>}
      {upscale && <p>原图片版本进入已启用的本地超分模型，再统一到所选倍率的 PNG 尺寸。输出最大 4096×4096、25 MiB，仍需人工审核。不会下载或启动模型；模型质量与本机推理尚未验收。</p>}
      {draft.operation.startsWith('m5.image.') && <p>Depth / Pose / Edge / Mask / Layout 控制 Adapter 已保留边界，尚未提供执行能力。</p>}
      {!cutout && <fieldset disabled={!state.canEdit}><legend>处理参数</legend><p>{trim ? draft.parameters.output_format === 'MP3' ? '本地截取输出有损 MP3，片段为 10 毫秒至 120 秒。需已安装的 libmp3lame；32000–48000 Hz 固定 128 kb/s，更低支持采样率固定 64 kb/s。支持 8000、11025、12000、16000、22050、24000、32000、44100、48000 Hz；留空为 48000 Hz、双声道。解码 S16 不代表无损。' : draft.parameters.output_format === 'FLAC' ? '本地截取输出处理后的 S16 FLAC。片段最长 120 秒，起止点须在真实来源时长内；先按所选增益、采样率与声道处理，再无损压缩。' : '本地截取输出 PCM 16 位 WAV。片段最长 120 秒；起止点还须在真实来源时长内。可选项留空保持原行为：不加增益、48000 Hz、双声道。增益过高可能造成削波。' : state.provider ? '仅列所选配置支持的参数；可选项留空时使用原服务商默认值。' : '先选择服务商，再填写它支持的参数。'}</p>{state.parameterNames.map(parameter)}
        {!!state.unsupportedParameters.length && <><StatusMessage tone="warning">所选配置不支持已填写的参数：{state.unsupportedParameters.map(name => labels[name]).join('、')}。这些输入不会自动丢弃。</StatusMessage><Button disabled={!state.canEdit} onClick={state.clearUnsupportedParameters}>明确清空不支持的参数</Button></>}
      </fieldset>}
      <label>来源与授权说明<input maxLength={2000} disabled={!state.canEdit} value={draft.licenseNote} onChange={event => state.changeField('licenseNote', event.target.value)} /></label>
      {state.inputError && <p>{state.inputError}</p>}
      <div className="studio-graph-actions"><Button disabled={!state.canInspect} loading={state.pending === 'PREVIEW'} onClick={() => void state.inspect()}>读取制作预览</Button><Button disabled={!state.canEdit} onClick={state.clearInputs}>清空本地输入</Button></div>
    </>}
      {state.preview && <section aria-label="制作预览确认"><h4>确认本次预览</h4><p>{MEDIA_OPERATION_LABELS[state.preview.operation_id]} · {state.preview.provider ? `${state.preview.provider.provider_id} / ${state.preview.provider.model_id} · ${state.preview.provider.local ? '本地' : '云端'}` : state.preview.operation_id === 'm5.image.cutout' ? '本地 CPU 二值遮罩抠图' : '本地截取'}</p>
        <p>预览绑定当前输入、来源版本与处理接口。创建仅保存任务，尚不执行。</p>
        <details><summary>核对本次执行接口、默认参数与工作流</summary><p>本次预览的接口记录，不代表处理已成功执行。</p><pre>{JSON.stringify(state.preview.execution_recipe, null, 2)}</pre></details>
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
            {job.operation_id === 'm5.image.cutout' && <p>原任务为本地 CPU 二值遮罩抠图，无服务商、模型、提示词或云端发送。来源顺序：原图片，然后是手绘遮罩。</p>}
            {job.operation_id !== 'm5.image.cutout' && <label>原提示词<textarea readOnly rows={4} value={job.command.prompt} aria-label="原任务已确认的提示词" /></label>}
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
        {job.operation_id === 'm8.audio.trim' && (job.media_measurement && ['PCM_DECODED', 'FLAC_STREAMINFO_PCM_VERIFIED', 'MP3_GAPLESS_PCM_VERIFIED'].includes(job.media_measurement.profile_validation ?? '') ? <section aria-label="音频实际输出测量"><h4>实际输出测量</h4><Badge>{job.media_measurement.container === 'mp3' ? '原服务 MP3 流信息与无间隙解码核对' : job.media_measurement.container === 'flac' ? '原服务 FLAC 流信息与 PCM 解码核对' : '原服务 PCM 解码测量回执'}</Badge>
          <dl><dt>媒体时长</dt><dd>{job.media_measurement.duration_ms} 毫秒</dd><dt>实际大小</dt><dd>{job.media_measurement.byte_count} 字节</dd>
            <dt>实际声音</dt><dd>{job.media_measurement.sample_rate} Hz · {job.media_measurement.channels} 声道 · {job.media_measurement.container === 'mp3' ? `MP3 · ${Number(job.media_measurement.bit_rate) / 1000} kb/s` : job.media_measurement.container === 'flac' ? '16 位 S16 FLAC' : '16 位 PCM WAV'}</dd>
            <dt>输出摘要</dt><dd><code>{job.media_measurement.output_sha256}</code></dd></dl>
          {job.media_measurement.container === 'flac' && <details><summary>FLAC 样本与解码证明</summary><p>{job.media_measurement.total_samples} 个样本 · 解码 {job.media_measurement.decoded_pcm_bytes} 字节 S16</p><p>PCM SHA256：<code>{job.media_measurement.decoded_pcm_sha256}</code></p><p>流信息 MD5：<code>{job.media_measurement.streaminfo_md5}</code></p></details>}
          {job.media_measurement.container === 'mp3' && <details><summary>MP3 样本与有损解码证明</summary><p>{job.media_measurement.total_samples} 个样本 · 解码 {job.media_measurement.decoded_pcm_bytes} 字节 S16 · 容器时长 {job.media_measurement.container_duration_ms} 毫秒（含编码延迟与帧填充）</p><p>解码 PCM SHA256：<code>{job.media_measurement.decoded_pcm_sha256}</code></p></details>}
          <p>{job.media_measurement.container === 'mp3' ? '以上为实际 MP3 的解码测量；MP3 为有损格式，解码摘要用于识别本次输出，不证明与原音频相同或音质合格。候选仍须核对并人工审核。' : job.media_measurement.container === 'flac' ? '以上为服务端解码实际 FLAC 的测量；S16 处理后的无损压缩不代表原作未经变更。候选仍须读取实际字节、核对摘要并人工审核。' : '以上为服务端解码实际 WAV 的测量，不代表增益已测量。候选仍须读取实际字节、核对摘要并人工审核。'}</p>
        </section> : <p>尚未读取到已核对的音频输出测量；原请求参数与执行配方不代表实际输出。</p>)}
        {job.processing_proof?.contract === 'studio-image-upscale-proof/1' && <details><summary>图片超分尺寸与摘要证明</summary><p>{job.processing_proof.source_width} × {job.processing_proof.source_height} → {job.processing_proof.output_width} × {job.processing_proof.output_height} · {job.processing_proof.scale} 倍 · PNG {job.processing_proof.output_bytes} 字节</p><code>{job.processing_proof.output_sha256}</code></details>}
        {job.processing_proof?.contract === 'cpu-binary-mask-cutout/1' && <details><summary>本地 CPU 处理证明</summary><p>{job.processing_proof.width} × {job.processing_proof.height} · 保留 {job.processing_proof.keep_pixels} 像素 · 移除 {job.processing_proof.remove_pixels} 像素 · PNG {job.processing_proof.output_bytes} 字节</p><p>输出摘要：<code>{job.processing_proof.output_sha256}</code></p></details>}
        {!!job.sources.length && <details><summary>本任务绑定的来源版本</summary><ul>{job.sources.map(source => <li key={`${source.kind}:${source.id}`}>{source.kind === 'ASSET' ? props.assets.find(row => row.id === source.id)?.filename || source.id : source.id} · v{source.version}<p>来源摘要：<code>{source.digest}</code></p></li>)}</ul></details>}
        {!state.jobSourcesFresh && <StatusMessage tone="warning">本任务的素材来源已变化，当前不可继续执行或审核。保留原记录供读取核对。</StatusMessage>}
        {job.status === 'UNKNOWN' && <StatusMessage tone="warning">无法确认先前分派结果，禁止再次执行。同一原任务只能继续读取核对或丢弃本地结果。</StatusMessage>}
        {job.status === 'REVIEWING' && <StatusMessage tone="warning">原审核可能已经提交。先读取任务和候选，再确认原审核；不会重新生成。</StatusMessage>}
        {job.error_code && <details><summary>任务回执细节</summary><p>{job.error_code}</p></details>}
        <Button disabled={!state.canRead} loading={state.pending === 'GET'} onClick={() => void state.openJob(job)}>读取当前任务核对</Button>
        <Button disabled={!state.canRead} onClick={state.downloadReceipt}>下载当前已读回执（JSON）</Button>
        {state.pending === 'execute' && job.operation_id === 'm5.image.cutout' && props.cutoutExecution && <section aria-label="正在执行的本地抠图控制"><p>本地执行请求尚未返回。可读取同一原任务，或明确取消；其它制作修改保持锁定。</p>
          <Button disabled={!state.canControlRunning} loading={state.runningControl === 'read'} onClick={() => void state.controlRunningCutout('read')}>读取运行中的原抠图任务</Button>
          <Button variant="danger" disabled={!state.canControlRunning || !state.canCancelRunning || job.status === 'CANCELLED'} loading={state.runningControl === 'cancel'} onClick={() => void state.controlRunningCutout('cancel')}>明确取消运行中的原抠图任务</Button>
        </section>}
        <div className="studio-graph-actions">
          <Button disabled={!state.canAction('execute')} loading={state.pending === 'execute'} onClick={() => void state.action('execute')}>明确执行当前入队任务</Button>
          {job.owner === 'video' && <Button disabled={!state.canAction('refresh')} loading={state.pending === 'refresh'} onClick={() => void state.action('refresh')}>核对已有远端进度</Button>}
          {(['RUNNING', 'SEND_RESERVED'].includes(job.status) || job.operation_id === 'm8.audio.trim' && ['UNKNOWN', 'REVIEWING'].includes(job.status) || job.operation_id === 'm5.image.cutout' && (['UNKNOWN', 'REVIEWING'].includes(job.status) || job.status === 'CANCELLED' && !!job.processing_proof && !job.output_candidate)) && <Button disabled={!state.canAction('reconcile')} loading={state.pending === 'reconcile'} onClick={() => void state.action('reconcile')}>核对中断状态，不重新发送</Button>}
          {(job.owner !== 'timeline' || ['RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status)) && <Button variant="danger" disabled={!state.canAction('cancel')} loading={state.pending === 'cancel'} onClick={() => void state.action('cancel')}>{job.operation_id === 'm5.image.cutout' ? '明确取消本地抠图或丢弃候选' : job.owner === 'timeline' && job.status === 'RUNNING' ? '明确取消本地渲染' : '丢弃未采用的本地结果'}</Button>}
        </div>
        <p>{job.operation_id === 'm5.image.cutout' ? '取消会请求原本地处理停止，或撤销未审核候选的采用权限；保留原记录，不会重新处理或入库。' : job.owner === 'timeline' ? '时间线取消会请求原本地渲染停止或撤销未审核候选的采用权限，保留原回执与已有候选；已进入审核或已入库的结果不能从这里取消。' : '丢弃仅撤销本地采用结果的权限，保留原记录；远端计算可能继续。'}</p>
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
