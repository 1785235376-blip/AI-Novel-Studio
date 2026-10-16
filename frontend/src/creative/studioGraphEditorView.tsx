import { IMAGE_REFERENCE_PURPOSES, IMAGE_REFERENCE_PURPOSE_LABELS } from './studioImageRuntimeContract';
import { AssetInspector } from '../novel/AssetInspector';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { GraphCanvas } from './GraphCanvas';
import { removeGraphNodes } from './graphCanvasGeometry';
import { GraphRunPanel } from './GraphRunPanel';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId } from './studioGraphTypes';
import { GRAPH_VIDEO_OPERATIONS, GRAPH_IMAGE_OPERATIONS, GRAPH_MEDIA_OPERATIONS } from './studioGraphTypes';
import { connectionIssue } from './graphDraft';
import { GRAPH_IMAGE_OPERATION_LABELS, GRAPH_MEDIA_OPERATION_LABELS, mediaProviderKey } from './useStudioMediaExecution';
import type { GraphMediaOperation } from './studioGraphTypes';
import { GRAPH_MEDIA_PARAMETER_LABELS, graphMediaParameterNames } from './useStudioGraphEditorController';
import type { StudioGraphEditorController, StudioGraphEditorProps } from './useStudioGraphEditorController';
import { StudioGraphTimelineNodeEditor } from './StudioGraphTimelineNodeEditor';
// UX-PRODUCT batch 2 (UX-04): node palette, selection/history bar, connection advice,
// change-impact classification and a deterministic layout preview. Additive: the
// original controls above stay intact and the rail only calls the controller's own
// callbacks, so connectivity legality remains `connectionIssue`'s alone.
import { CanvasOpsRail } from '../canvasops/CanvasOpsRail';
import type { LocalCanvasState } from '../canvasops/canvasOpsTypes';
import './studioGraph.css';

const portKey = (node: string, port: string) => JSON.stringify([node, port]);
/** Explain the pending connection using the ORIGINAL authority only.
 *
 * The rail must never re-derive legality, so a provisional edge is built from the
 * controller's own port keys and handed to the existing `connectionIssue`; an
 * incomplete or malformed selection yields no explanation instead of a guess.
 */
function pendingConnectionIssue(definition: StudioGraphDefinition, catalog: readonly StudioGraphCatalogDefinition[],
  sourcePort: string, targetPort: string): string | undefined {
  if (!sourcePort || !targetPort) return undefined;
  try {
    const source = JSON.parse(sourcePort) as unknown, target = JSON.parse(targetPort) as unknown;
    if (!Array.isArray(source) || !Array.isArray(target) || source.length !== 2 || target.length !== 2
      || typeof source[0] !== 'string' || typeof source[1] !== 'string'
      || typeof target[0] !== 'string' || typeof target[1] !== 'string') return undefined;
    return connectionIssue(definition, catalog, { id: 'pending-connection', source_node_id: source[0],
      source_port: source[1], target_node_id: target[0], target_port: target[1] });
  } catch { return undefined; }
}
function connectionNodeIds(...keys: string[]): string[] {
  return keys.flatMap(key => {
    try { const value: unknown = JSON.parse(key); return Array.isArray(value) && value.length === 2 && typeof value[0] === 'string' && typeof value[1] === 'string' ? [value[0]] : []; }
    catch { return []; }
  });
}
/** Render only. UI refactors consume the same controller without replacing operation contracts. */
export function studioGraphEditorView(controller: StudioGraphEditorController, props: StudioGraphEditorProps,
  canvas?: { local: LocalCanvasState; onLocal: (next: LocalCanvasState) => void }) {
  if (controller.retired) return {
    content: <section className="studio-graph-editor" aria-label="独立创作图编辑器"><Panel title="创作图 · 本地输入只读">
      <StatusMessage tone="warning">身份或项目已改变，服务端目录、预览和运行回执已关闭。仅保留未保存的作者文字，请重新打开工作区。</StatusMessage>
      <label>创作图标题<input value={controller.retainedTitle} disabled readOnly /></label>
      {controller.retainedText.map((input, index) => <label key={index}>{input.label}<textarea value={input.value} disabled readOnly /></label>)}
    </Panel></section>,
    inspector: <EmptyState title="原范围信息已关闭" detail="重新核对身份后再读取图节点、来源与运行记录。" />,
  };
  const { client, busy, externalDirty, canMutate, canReview, read, mutate, identity, requestedRunId } = props;
  const {
    providerPicker, catalog, records, base, draft, selected, past, future, loading, error, notice, blocked,
    candidate, replaceConfirmed, checking, pendingNavigation, discardConfirmed, kind, sourcePort, targetPort,
    assets, assetChoice, assetLoading, preview, previewState, refreshPreview, downloadPreviewAsset, current, dirty, editable, protectedNodes, node,
    load, loadImageCatalog, loadProductionCatalog, loadVideoCatalog, videoSchemaConfirmed, confirmVideoSchema, upgradeVideoSchema, shotParent, chooseShotParent, shotReceipt, shotChoice, chooseShot, shotLoading, loadShotReceipt, planningDocuments, planningChoice, planningLoading, choosePlanningDocument, loadPlanningDocuments, updateProductionField, updateShotBinding, updateReferenceMetadata, change, navigate, open, newGraph, save, checkServer, loadAssets, addNode, connect, travel, confirmNavigation, adoptCandidate,
    setReplaceConfirmed, setCandidate, setDiscardConfirmed, setPendingNavigation, setKind, setAssetChoice,
    setSourcePort, setTargetPort, setSelected, reportRunSelection,
    mediaSchemaConsent, setMediaSchemaConsent, upgradeMediaSchema, executionDirty, setExecutionDirty,
    updateMediaField, updateMediaParameter, clearUnsupportedMediaParameters, clearMediaTrimInputs, timelineEditor,
    imageSchemaConfirmed, confirmImageSchema, upgradeImageSchema, updateImagePrompt, updateImageReference,
  } = controller;
  const mediaEnabled = catalog?.capabilities.media_execution === true && catalog.capabilities.media_execution_contract === 'creative-graph-media/1';
  const videoGraph = draft.schema_version === 5;
  const imageGraph = draft.schema_version === 4;
  const nodeLimit = draft.schema_version >= 3 ? catalog?.media_limits?.nodes || 24 : catalog?.limits.nodes || 16;
  const schemaRequired = !imageGraph && !videoGraph && (kind === 'media_generate' || kind === 'media_review' || kind === 'timeline_export' || kind === 'asset_reference' && mediaEnabled);
  const mediaOperation = node?.parameters.operation_id, parameterNames = mediaOperation ? graphMediaParameterNames(mediaOperation, ['image_generate', 'image_upscale'].includes(node?.definition_id || '')) : [];
  const unsupported = Object.entries(node?.parameters.parameters || {}).filter(([key, value]) => value !== null && !parameterNames.includes(key)).map(([key]) => key);
  function mediaParameter(name: string) {
    const value = node?.parameters.parameters?.[name] ?? '', label = GRAPH_MEDIA_PARAMETER_LABELS[name];
    if (name === 'scale') return <label key={name}>{label}<select value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)}><option value="">明确选择倍率</option><option value="2">2 倍</option><option value="4">4 倍</option></select></label>;
    if (name === 'negative_prompt') return <label key={name}>{label}<textarea maxLength={8000} value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)} /></label>;
    if (name === 'size' || name === 'quality') {
      const options = name === 'size' ? ['auto', '1024x1024', '1536x1024', '1024x1536'] : ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
      return <label key={name}>{label}<select value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)}><option value="">服务商默认值</option>{options.map(option => <option key={option} value={option}>{option}</option>)}</select></label>;
    }
    const ranges: Record<string, [number, number, number]> = { width: [64, 2048, 8], height: [64, 2048, 8], steps: [1, 150, 1], seed: [0, 2147483647, 1], denoising_strength: [0.01, 1, 0.01],
      duration_seconds: [1, 600, 1], frame_rate: [1, 60, 1], speech_rate: [0.5, 2, 0.1], in_ms: [0, 600000, 1], out_ms: [1, 600000, 1] }, range = ranges[name];
    return <label key={name}>{label}<input type={range ? 'number' : 'text'} min={range?.[0]} max={range?.[1]} step={range?.[2]} maxLength={name === 'voice_id' ? 240 : undefined}
      value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)} /></label>;
  }
  const providerControl = node && <fieldset><legend>节点服务配置</legend>
    {node.definition_id !== 'image_upscale' && <label>节点制作路线<select value={providerPicker.route} disabled={!providerPicker.canEdit} onChange={event => providerPicker.chooseRoute(event.target.value)}><option value="local">本地</option><option value="cloud">云端</option></select></label>}
    <p>{node.definition_id === 'image_upscale' ? '超分仅列出本地配置，不使用云端回退。' : '默认查看本地配置；可自行切换云端或返回本地。切换只改变列表，不改写节点或授权发送。'}</p>
    <Button disabled={!providerPicker.canRead || providerPicker.loading} loading={providerPicker.loading} onClick={() => void providerPicker.load()}>读取节点服务配置</Button>
    <label>节点服务商与模型<select value={providerPicker.choice} disabled={!providerPicker.canEdit} onChange={event => providerPicker.choose(event.target.value)}><option value="">明确选择配置</option>{providerPicker.rows.map(row => <option key={mediaProviderKey(row)} value={mediaProviderKey(row)}>{row.provider_id} · {row.model_id} · {row.local ? '本地' : '云端'}</option>)}</select></label>
    <p>节点当前标识：{node.parameters.provider_id || '未选择服务商'} / {node.parameters.model_id || '未选择模型'}。</p>
    {providerPicker.loaded && !providerPicker.matched && (node.parameters.provider_id || node.parameters.model_id) && <StatusMessage tone="warning">当前配置目录没有匹配的节点标识；原标识保持，只有明确选择才会替换。</StatusMessage>}
    {providerPicker.loaded && !providerPicker.rows.length && <p>当前操作暂无{providerPicker.route === 'local' ? '本地' : '云端'}配置，不会自动回退或替换。</p>}
    {providerPicker.error && <StatusMessage tone="warning">{providerPicker.error}</StatusMessage>}
    <p>配置未验证实际推理；选择同时更新服务商与模型并清除云端许可。路线摘要仅用于当前列表识别，执行仍须按原流程重新预览、确认与审核。</p>
  </fieldset>;
  const content = <section className="studio-graph-editor" aria-label="独立创作图编辑器">
    <Panel title="创作图 · 手工编排"><p>空图和不相连的组件都可以保存。导演备注可选，可随时移除；连接类型由服务端定义。</p>{catalog?.capabilities.model_execution && <p>可选本地文字模型节点需单独预览输入并明确确认一次调用。每次运行最多一个文字模型节点，输出必须人工审核；不自动调用、重试或转云端。</p>}
      {videoGraph ? <p>视频图 v5：原导演与已批准分镜 → 版本绑定镜头 → 视频生成 → 原媒体审核 → 正式视频，可再连接原时间线。各次模型调用、入队、执行与审核单独确认。</p> : imageGraph ? <p>图片图 v4：资产引用 → 图片参考与权重 → 图片提示词 → 图片生成 → 媒体审核 → 正式素材。各节点可独立编排；最多四个图片生成节点。保存、预览、入队、执行和审核分别操作，真实推理与完整流程验收仍待完成。</p>
        : mediaEnabled ? <p>媒体图 v3 使用原任务服务逐项入队和执行。候选只能进入人工审核，审核后的当前素材才能用于下游。每图最多四个媒体制作节点；本机与完整流程验收仍待完成。</p> : <p>当前保留本地文本与手工工作流。旧图中的资产节点保持只读引用，不执行媒体处理。</p>}
      <Button disabled={loading || busy || externalDirty || executionDirty} onClick={() => void loadImageCatalog()}>明确读取图片节点目录</Button>
      <Button disabled={loading || busy || externalDirty || executionDirty || !client.graphs.videoCatalog} onClick={() => void loadVideoCatalog()}>明确读取视频图节点目录</Button>
      <Button disabled={loading || busy || externalDirty || executionDirty || !client.graphs.productionCatalog} onClick={() => void loadProductionCatalog()}>明确读取导演、分镜与视觉制作节点目录</Button>
      {catalog?.capabilities.production_graph && <p>已读取视觉制作扩展：已保存导演与分镜版本 → 镜头提示词 → 风格 → 图片生成；或正式图片 → 超分 → 原媒体审核。控制 Adapter 尚未执行，模型质量验收待完成。</p>}
      <div className="studio-graph-actions"><Button disabled={busy || externalDirty || executionDirty} onClick={() => navigate(newGraph)}>新建空图</Button><Button disabled={loading || busy} onClick={() => void load()}>刷新创作图目录</Button></div>
      <label>已保存创作图<select aria-label="已保存创作图" disabled={busy || externalDirty || executionDirty} value={base?.id || ''} onChange={event => { const id = event.target.value; if (id) navigate(() => void open(id)); }}><option value="">未选择已保存图</option>{records.map(row => <option key={row.id} value={row.id}>{row.definition.title} · v{row.version}</option>)}</select></label>
      <label>创作图标题<input maxLength={160} value={draft.title} disabled={!editable} onChange={event => change({ ...draft, title: event.target.value })} /></label>
      <Badge tone={dirty || blocked ? 'warning' : 'neutral'}>{base ? `v${base.version}` : '尚未保存'} · {dirty ? '未保存修改' : '无未保存修改'}</Badge>
      <div className="studio-graph-actions"><Button variant="primary" disabled={!editable || !draft.title.trim() || !!base && !dirty} onClick={() => void save()}>保存创作图</Button><Button disabled={!editable || !past.length} onClick={() => travel(false)}>撤销图编辑</Button><Button disabled={!editable || !future.length} onClick={() => travel(true)}>重做图编辑</Button><Button disabled={busy || !base} onClick={() => navigate(() => void open(base!.id))}>重新读取创作图</Button></div>
    </Panel>
    {loading && <StatusMessage>正在读取当前范围的节点目录…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {externalDirty && <StatusMessage tone="warning">请先保存或处理导演／资产／偏好输入，再修改创作图。</StatusMessage>}
    {executionDirty && <StatusMessage tone="warning">当前图媒体有待确认输入或不确定回执。先在原运行中取消确认或读取核对，再切换或修改图。</StatusMessage>}
    {timelineEditor.formDirty && <StatusMessage tone="warning">尚有未加入图草稿的剪辑输入，请明确加入或放弃后保存。<Button disabled={busy || timelineEditor.loading} onClick={timelineEditor.clearForm}>放弃尚未加入的剪辑输入</Button></StatusMessage>}
    {base?.can_edit === false && <StatusMessage tone="warning">图中包含不可见的资产引用，当前仅可查看。原绑定不会被省略、删除或重新保存；需恢复访问后重新读取。</StatusMessage>}
    {blocked && <section className="studio-graph-conflict" role="alert"><p>保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。</p><Button disabled={busy || checking} onClick={() => void checkServer()}>核对图服务端版本</Button>{!base && <Button disabled={busy || checking || !canMutate} onClick={() => void save(true)}>使用同一请求重试保存</Button>}</section>}
    {checking && <StatusMessage>正在核对图服务端版本；当前草稿保持。</StatusMessage>}
    {candidate && <section className="studio-graph-conflict" aria-label="图服务端版本"><p>服务端 v{candidate.version} · {candidate.definition.title} · {candidate.definition.nodes.length} 节点 / {candidate.definition.edges.length} 连接</p><label><input type="checkbox" disabled={busy || externalDirty} checked={replaceConfirmed} onChange={event => setReplaceConfirmed(event.target.checked)} />确认放弃当前图草稿，采用已核对服务端版本</label><Button disabled={!replaceConfirmed || busy || externalDirty} onClick={adoptCandidate}>采用图服务端版本</Button><Button onClick={() => setCandidate(undefined)}>保留图草稿</Button></section>}
    {pendingNavigation && <section role="alert" className="studio-graph-conflict"><p>当前图有未保存输入，切换会放弃本页草稿。</p><label><input type="checkbox" disabled={busy || externalDirty} checked={discardConfirmed} onChange={event => setDiscardConfirmed(event.target.checked)} />确认放弃图草稿</label><Button disabled={!discardConfirmed || busy || externalDirty} onClick={confirmNavigation}>确认切换创作图</Button><Button onClick={() => setPendingNavigation(undefined)}>继续编辑创作图</Button></section>}
    {catalog && <>{mediaEnabled && <section aria-label="媒体图版本"><p>当前图格式：v{draft.schema_version}。旧图保持原行为，升级只在明确保存后生效，不自动执行。</p>{draft.schema_version < 3 && <><label><input type="checkbox" checked={mediaSchemaConsent} disabled={!editable} onChange={event => setMediaSchemaConsent(event.target.checked)} />确认升级为媒体图 v3；已有资产引用将可以作为当前版本来源执行读取</label><Button disabled={!editable || !mediaSchemaConsent} onClick={upgradeMediaSchema}>明确升级当前草稿为媒体图 v3</Button></>}</section>}
      {catalog.capabilities.video_graph && !videoGraph && <section aria-label="视频图版本确认"><p>视频图 v5 保留旧图，只在明确确认与保存后采用；不兼容节点不会自动移除。</p><label><input type="checkbox" checked={videoSchemaConfirmed} disabled={!editable} onChange={event => confirmVideoSchema(event.target.checked)} />确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务</label><Button disabled={!editable || !videoSchemaConfirmed} onClick={upgradeVideoSchema}>明确采用视频图 v5</Button></section>}
      {catalog.capabilities.image_graph && !imageGraph && <section aria-label="图片图版本确认"><p>图片图 v4 只接收图片来源、文本输入与引用、图片参考、图片提示词、图片生成和媒体审核。已有其他节点不会自动转换或移除；可明确新建空图。</p><label><input type="checkbox" checked={imageSchemaConfirmed} disabled={!editable} onChange={event => confirmImageSchema(event.target.checked)} />确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核</label><Button disabled={!editable || !imageSchemaConfirmed} onClick={upgradeImageSchema}>明确采用图片图 v4</Button></section>}
      <section className="studio-graph-controls" aria-label="添加与连接节点"><label>节点类型<select aria-label="节点类型" value={kind} disabled={!editable} onChange={event => { const value = event.target.value as StudioGraphDefinitionId; setKind(value); if (value === 'asset_reference') void loadAssets(); }}>{catalog.definitions.map(row => <option value={row.id} key={row.id}>{GRAPH_NODE_LABELS[row.id]}</option>)}</select></label>
      {kind === 'asset_reference' && <><label>原资产<select aria-label="原资产" disabled={!editable || assetLoading} value={assetChoice} onChange={event => setAssetChoice(event.target.value)}><option value="">选择已保存原资产</option>{assets.filter(row => !imageGraph || row.kind === 'image').map(row => <option value={row.id} key={row.id}>{row.filename} · {row.kind} · v{row.version}</option>)}</select></label><Button disabled={assetLoading || busy} onClick={() => void loadAssets()}>刷新图引用资产</Button><p>只保存原资产 ID、版本和摘要；不复制文件。保存后的引用暂不能移除或重绑，可禁用节点。</p></>}
      {['director_plan', 'storyboard_plan'].includes(kind) && <><Button disabled={!editable || planningLoading || !client.graphs.planningDocuments} onClick={() => void loadPlanningDocuments()}>明确读取已保存导演与分镜文档</Button><label>原创作文档<select disabled={!editable || planningLoading} value={planningChoice} onChange={event => choosePlanningDocument(event.target.value)}><option value="">选择当前已保存版本</option>{planningDocuments.filter(row => row.mode === (kind === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD')).map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></label><p>只绑定原文档 ID、版本与摘要，不创建副本。文档修改或权限变化后旧绑定不可继续采用；新节点不执行模型、不改写作品。</p></>}
      {kind === 'storyboard_shot' && <><label>图中分镜来源<select disabled={!editable || shotLoading} value={shotParent} onChange={event => chooseShotParent(event.target.value)}><option value="">选择已绑定分镜节点</option>{draft.nodes.filter(node => node.definition_id === 'storyboard_plan' && node.parameters.document_snapshot).map(node => <option key={node.id} value={node.id}>{node.id} · v{node.parameters.document_snapshot!.version}</option>)}</select></label><Button disabled={!editable || shotLoading || !shotParent} onClick={() => void loadShotReceipt()}>明确读取来源分镜镜头</Button><label>原分镜镜头<select disabled={!editable || shotLoading} value={shotChoice} onChange={event => chooseShot(event.target.value)}><option value="">选择确切镜头版本</option>{shotReceipt?.shots.map(shot => <option key={shot.shot_id} value={shot.shot_id}>SHOT {shot.shot.number} · {shot.shot_id} · v{shot.shot_version}</option>)}</select></label><p>镜头节点保留原编号、版本和摘要；请连接对应分镜节点的 Storyboard Data。视频调用前必须批准当前分镜。</p></>}
      {kind === 'timeline_export' && <><Button disabled={!timelineEditor.canLoad} loading={timelineEditor.loading} onClick={() => void timelineEditor.loadRows()}>明确读取原时间线目录</Button><label>原时间线<select disabled={!editable || timelineEditor.loading} value={timelineEditor.choice} onChange={event => timelineEditor.choose(event.target.value)}><option value="">选择已有时间线</option>{timelineEditor.rows.map(row => <option key={row.id} value={row.id}>{row.title} · {row.id} · v{row.version}</option>)}</select></label>{timelineEditor.chosen && <p>确切来源摘要：<code>{timelineEditor.chosen.timeline_digest}</code></p>}<p>使用原时间线；新增节点不保存剪辑、不入队、不渲染。</p>{timelineEditor.error && <StatusMessage tone="error">{timelineEditor.error}</StatusMessage>}</>}
      {schemaRequired && draft.schema_version !== 3 && <p>添加可执行资产来源或媒体节点前，先明确升级当前草稿为 v3。</p>}
      <Button disabled={!editable || draft.nodes.length >= nodeLimit || schemaRequired && draft.schema_version !== 3 || ['media_generate', 'timeline_export'].includes(kind) && draft.nodes.filter(row => ['media_generate', 'timeline_export'].includes(row.definition_id)).length >= 4
        || ['image_generate', 'image_upscale'].includes(kind) && draft.nodes.filter(row => ['image_generate', 'image_upscale'].includes(row.definition_id)).length >= 4 || ['director_plan', 'storyboard_plan'].includes(kind) && !planningDocuments.some(row => row.id === planningChoice && row.mode === (kind === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD')) || kind === 'storyboard_shot' && !shotReceipt?.shots.some(shot => shot.shot_id === shotChoice) || videoGraph && ['video_generate', 'timeline_export'].includes(kind) && draft.nodes.filter(row => ['video_generate', 'timeline_export'].includes(row.definition_id)).length >= 4 || kind === 'asset_reference' && !assetChoice || kind === 'timeline_export' && !timelineEditor.chosen} onClick={addNode}>添加节点</Button>
      <label>起始输出端口<select aria-label="起始输出端口" disabled={!editable} value={sourcePort} onChange={event => setSourcePort(event.target.value)}><option value="">选择输出端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.outputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <label>目标输入端口<select aria-label="目标输入端口" disabled={!editable} value={targetPort} onChange={event => setTargetPort(event.target.value)}><option value="">选择输入端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.inputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <Button disabled={!editable || !sourcePort || !targetPort || draft.edges.length >= catalog.limits.edges} onClick={connect}>连接所选端口</Button></section>
      {/* The controller's catalog is a union that differs only in the optional video-graph
          capability flags; the rail reads `definitions` / `limits` / `media_limits` only. */}
      {canvas && <CanvasOpsRail catalog={catalog as StudioGraphCatalog} definition={draft} base={base?.definition} selected={selected}
        past={past.length} future={future.length} editable={editable} protectedNodeIds={protectedNodes} kind={kind}
        sourcePort={sourcePort} targetPort={targetPort} connectionExplanation={pendingConnectionIssue(draft, catalog.definitions, sourcePort, targetPort)}
        local={canvas.local} onLocal={canvas.onLocal}
        onKind={value => setKind(value as StudioGraphDefinitionId)} onSourcePort={setSourcePort} onTargetPort={setTargetPort}
        onApplyLayout={controller.applyAutoLayout} onAddNode={addNode} onConnect={connect} onSelect={setSelected} onTravel={direction => travel(direction === 'REDO')} />}
      <section aria-label="同图复制预览">
        <h3>复制所选节点</h3>
        <p>仅当前项目的当前图、当前草稿预览；不使用系统剪贴板，不支持跨画布。来源版本与摘要保持；保存时仍由原来源权限校验。</p>
        <Button disabled={!editable || !selected.length || timelineEditor.formDirty} onClick={controller.previewSelectionCopy}>预览复制所选节点</Button>
        {controller.currentCopy && <div role="status">
          <p>新增 {controller.currentCopy.nodeCount} 个节点、{controller.currentCopy.edgeCount} 条内部连接；排除 {controller.currentCopy.excludedEdges} 条外部连接。缺少输入时需重新连接；不复制分组或运行结果。</p>
          <p>统一偏移：{controller.currentCopy.delta.x}, {controller.currentCopy.delta.y}。粘贴仅修改本地草稿，可一次撤销；未保存、未执行。</p>
          <Button disabled={!editable || timelineEditor.formDirty} onClick={controller.pasteSelectionCopy}>粘贴到当前图</Button>
          <Button onClick={controller.cancelSelectionCopy}>取消复制预览</Button>
        </div>}
      </section>
      <GraphCanvas connectionNodeIds={connectionNodeIds(sourcePort, targetPort)} definition={draft} nodeDefinitions={catalog.definitions} selectedNodeIds={selected} onSelectionChange={setSelected} onDefinitionChange={change} readonly={!editable} busy={busy} protectedNodeIds={protectedNodes} interactionKey={`${identity}:${base?.id || 'new'}`} onPortSelect={port => { if (port.direction === 'output') setSourcePort(portKey(port.nodeId, port.portId)); else setTargetPort(portKey(port.nodeId, port.portId)); }} />
      <section aria-label="图连接列表"><h3>已保存到草稿的连接</h3>{!draft.edges.length && <p>暂无连接；不相连节点可以独立保存。</p>}<ul>{draft.edges.map(edge => <li key={edge.id}>{edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}<Button disabled={!editable} onClick={() => change({ ...draft, edges: draft.edges.filter(row => row.id !== edge.id) })}>移除连接 {edge.id}</Button></li>)}</ul></section>
      <GraphRunPanel client={client.graphs} graph={base} targetNodeIds={selected} dirty={dirty || blocked} busy={busy} canMutate={canMutate && !externalDirty} canReview={canReview && !externalDirty} modelExecutionEnabled={!videoGraph && catalog.capabilities.model_execution && catalog.capabilities.model_execution_contract === 'creative-graph-model/1'} mediaExecutionEnabled={mediaEnabled} onDirtyChange={setExecutionDirty} isCurrent={current} read={read} mutate={mutate} requestedRunId={requestedRunId} onRunSelectionChange={reportRunSelection} />
    </>}
  </section>;
  const referenceState = base?.reference_states.find(row => row.node_id === node?.id)?.state;
  const inspector = <section className="studio-graph-inspector" aria-label="创作图节点检查器">{node ? <><h2>{GRAPH_NODE_LABELS[node.definition_id]}</h2><p>{node.id} · 定义 v{node.definition_version}</p><label><input type="checkbox" checked={node.enabled} disabled={!editable} onChange={event => change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, enabled: event.target.checked } : row) })} />启用当前节点</label>
    {(['text_input', 'manual_transform', 'director_note'] as const).includes(node.definition_id as 'text_input') && <label>{node.definition_id === 'text_input' ? '作者输入文本' : node.definition_id === 'manual_transform' ? '手工处理结果' : '可选导演备注'}<textarea maxLength={node.definition_id === 'director_note' ? 4000 : 8000} disabled={!editable} value={String(node.parameters[node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'] || '')} onChange={event => { const key = node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'; change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { [key]: event.target.value } } : row) }); }} /></label>}
    {node.definition_id === 'text_generate' && <><label>本地模型写作指令<textarea maxLength={4000} disabled={!editable} value={node.parameters.instruction || ''} onChange={event => change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { ...row.parameters, instruction: event.target.value } } : row) })} /></label><label>最大输出 token<input type="number" min={1} max={2048} step={1} disabled={!editable} value={node.parameters.max_output_tokens ?? 512} onChange={event => { const value = Number(event.target.value); if (Number.isSafeInteger(value) && value >= 1 && value <= 2048) change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { ...row.parameters, max_output_tokens: value } } : row) }); }} /></label><p>保存节点不调用模型。将草稿输出连接到人工审核节点后，创建运行并单独核对本地路由和完整输入。</p></>}
    {node.definition_id === 'image_reference' && <><p>每个端口绑定一张原图片或已审核素材。权重在原路线中归一化后用于像素初始化；不能据此宣称角色、风格或构图一致性。</p>
      {Array.from({ length: 5 }, (_, index) => `source_${index + 1}`).map(port => {
        const binding = node.parameters.bindings?.find(binding => binding.port === port), edge = draft.edges.find(edge => edge.target_node_id === node.id && edge.target_port === port);
        return <fieldset disabled={!editable} key={port}><legend>图片参考 {port}</legend><p>{edge ? `已连接 ${edge.source_node_id}.${edge.source_port}` : '尚未连接图片素材端口'}</p><label><input type="checkbox" checked={!!binding} onChange={event => updateImageReference(port, event.target.checked ? '1' : '')} />明确使用参考端口 {port}</label>{binding && <><label>参考权重 {port}<input type="number" min={0.01} max={1} step={0.01} value={binding.weight} onChange={event => updateImageReference(port, event.target.value)} /></label><label>参考用途 {port}<select value={binding.purpose || ''} onChange={event => updateReferenceMetadata(port, 'purpose', event.target.value)}><option value="">未指定用途</option>{IMAGE_REFERENCE_PURPOSES.map(purpose => <option value={purpose} key={purpose}>{IMAGE_REFERENCE_PURPOSE_LABELS[purpose]}</option>)}</select></label><label>参考来源说明 {port}<input maxLength={500} value={binding.source_note || ''} onChange={event => updateReferenceMetadata(port, 'source_note', event.target.value)} /></label></>}</fieldset>;
      })}<p>连接和权重必须对应；未接入来源的绑定需明确移除。保存不读取真实字节或调用模型。</p></>}
    {node.definition_id === 'image_prompt' && <><label>图片提示词<textarea maxLength={8000} disabled={!editable} value={node.parameters.prompt || ''} onChange={event => updateImagePrompt(event.target.value)} /></label><p>可以使用本节点提示词，或连接文本输入／引用的 TEXT 端口。两者均有内容时会拒绝含糊输入；不会自动拼接或改写。图片参考经 references 端口沿原版本绑定传递。</p></>}
    {node.definition_id === 'storyboard_shot' && <><p>镜头 {node.parameters.shot_id} · 原镜头 v{node.parameters.shot_version}</p><code>{node.parameters.shot_digest}</code><p>绑定来自读取的原分镜回执；不自动重新选取已修改镜头或批准内容。</p></>}
    {node.definition_id === 'video_generate' && <><label><input type="checkbox" disabled={!editable || node.parameters.bind_shot !== true && !draft.edges.some(edge => edge.target_node_id === node.id && edge.target_port === 'shot')} checked={node.parameters.bind_shot === true} onChange={event => updateShotBinding(event.target.checked)} />绑定镜头来源</label><p>绑定保留当前镜头与文档版本，审核后可明确采用为该镜头的视频；须连接 shot 端口。取消绑定仍可独立生产，不自动补写旧节点。</p><label>视频操作<select value={mediaOperation || 'm7.video.t2v'} disabled={!editable} onChange={event => updateMediaField('operation_id', event.target.value)}>{GRAPH_VIDEO_OPERATIONS.map(operation => <option key={operation} value={operation}>{GRAPH_MEDIA_OPERATION_LABELS[operation]}</option>)}</select></label>{providerControl}<label>视频提示词<textarea maxLength={16000} disabled={!editable} value={node.parameters.prompt || ''} onChange={event => updateMediaField('prompt', event.target.value)} /></label>{parameterNames.map(mediaParameter)}{mediaOperation === 'm7.video.v2v' && <label>参考视频用途<select disabled={!editable} value={node.parameters.reference_purpose || ''} onChange={event => updateProductionField('reference_purpose', event.target.value)}><option value="">普通来源，不指定参考用途</option><option value="style">风格</option><option value="action">动作</option><option value="camera">摄影机</option></select></label>}<label><input type="checkbox" disabled={!editable} checked={node.parameters.allow_cloud === true} onChange={event => updateMediaField('allow_cloud', event.target.checked)} />允许本次向已配置云端视频服务发送输入，可能产生费用</label><label>视频授权说明<input maxLength={2000} disabled={!editable} value={node.parameters.license_note || ''} onChange={event => updateMediaField('license_note', event.target.value)} /></label><p>shot 仅接已批准当前分镜的确切镜头；I2V 使用该镜头绑定的正式图片，V2V 来源与 reference 互斥。VIDEO_CANDIDATE 只能进入原媒体审核。模型结构已适配，真实模型和 GPU 验收仍待完成。</p></>}
    {node.definition_id === 'image_style' && <><p>Style 节点明确将作者风格、氛围与色彩要求加入原图片提示词，保留参考来源与权重；不代表模型有独立风格控制能力。</p>{([['style', '图片风格'], ['atmosphere', '图片氛围'], ['color_palette', '图片色彩']] as const).map(([key, label]) => <label key={key}>{label}<textarea maxLength={key === 'style' ? 2000 : 1000} disabled={!editable} value={node.parameters[key] || ''} onChange={event => updateProductionField(key, event.target.value)} /></label>)}</>}
    {['director_plan', 'storyboard_plan'].includes(node.definition_id) && <><p>原文档引用状态：{referenceState || '待保存核对'}</p>{node.parameters.document_snapshot ? <><p>绑定 {node.parameters.document_snapshot.id} · v{node.parameters.document_snapshot.version}</p><code>{node.parameters.document_snapshot.digest}</code></> : <StatusMessage tone="warning">当前文档来源不可查看，原绑定信息已隐藏。</StatusMessage>}<p>节点读取已保存作者内容。导演输出供分镜节点核对；不会覆盖分镜，也不会修改来源。保存后的文档绑定不能自动移除或重绑，可禁用节点。</p></>}
    {node.definition_id === 'storyboard_prompt' && <><label>镜头 ID<input maxLength={240} disabled={!editable} value={node.parameters.shot_id || ''} onChange={event => updateProductionField('shot_id', event.target.value)} /></label><p>连接 Storyboard Data，选择原分镜里的镜头 ID。输出闭合图片提示词，并保留原文档版本；图片生成仍需预览与明确执行。</p></>}
    {node.definition_id === 'image_upscale' && <><p>source 连接当前正式图片，candidate 只能进入原媒体审核节点。沿原 ImageJob 使用已启用本地超分模型，输出 PNG；真实推理尚待验收。</p>{providerControl}{parameterNames.map(mediaParameter)}<label>超分来源与授权说明<input maxLength={2000} disabled={!editable} value={node.parameters.license_note || ''} onChange={event => updateMediaField('license_note', event.target.value)} /></label><p>最大尺寸 4096×4096、25 MiB；不使用提示词、云端回退或自动下载。</p></>}
    {node.definition_id === 'image_generate' && <>
      <label>图片操作<select disabled={!editable} value={mediaOperation || 'm5.image.t2i'} onChange={event => updateMediaField('operation_id', event.target.value)}>{GRAPH_IMAGE_OPERATIONS.map(operation => <option value={operation} key={operation}>{GRAPH_IMAGE_OPERATION_LABELS[operation]}</option>)}</select></label>
      {providerControl}
      <p>读取原服务配置后明确选择；预览核对原路线，不安装或启动模型。</p>
      <p>控件列出闭合的通用输入；具体服务不支持的参数会在预览时拒绝，不会忽略后继续生成。非文字生成的尺寸来自输入图片，不自动改变尺寸。</p>
      <p>prompt 接图片提示词。文字生成不接素材；参考生成只用参考图；I2I 另接 source 基础图；局部重绘须接 source 和该版本的手绘 mask，不接辅助参考。</p>
      <p>局部重绘沿原二值遮罩：白色保留原图，黑色重绘。候选经原任务保持私有，独立人工审核后才输出素材。</p>
      <fieldset disabled={!editable}><legend>图片处理参数</legend>{parameterNames.map(mediaParameter)}{!!unsupported.length && <><StatusMessage tone="warning">当前操作不支持已保留参数：{unsupported.join('、')}。输入未自动删除。</StatusMessage><Button disabled={!editable} onClick={clearUnsupportedMediaParameters}>明确清空本操作不支持的参数</Button></>}</fieldset>
      <label><input type="checkbox" disabled={!editable} checked={node.parameters.allow_cloud === true} onChange={event => updateMediaField('allow_cloud', event.target.checked)} />本节点明确允许发送提示词及版本绑定素材到已配置云端服务，可能产生费用</label><label>图片来源与授权说明<input maxLength={2000} disabled={!editable} value={node.parameters.license_note || ''} onChange={event => updateMediaField('license_note', event.target.value)} /></label>
      <p>candidate 须连接唯一原媒体审核节点。不会自动生成、采用候选或执行下游；超分由独立图片超分节点接入；不会自动执行。</p>
    </>}
    {node.definition_id === 'media_generate' && <>
      <label>媒体操作<select disabled={!editable} value={mediaOperation || 'm5.image.t2i'} onChange={event => updateMediaField('operation_id', event.target.value as GraphMediaOperation)}>{GRAPH_MEDIA_OPERATIONS.map(operation => <option key={operation} value={operation}>{GRAPH_MEDIA_OPERATION_LABELS[operation]}</option>)}</select></label>
      {mediaOperation !== 'm8.audio.trim' ? <><label>已配置服务商 ID<input maxLength={240} disabled={!editable} value={node.parameters.provider_id || ''} onChange={event => updateMediaField('provider_id', event.target.value)} /></label><label>已配置模型 ID<input maxLength={240} disabled={!editable} value={node.parameters.model_id || ''} onChange={event => updateMediaField('model_id', event.target.value)} /></label><p>填写原服务商配置中已有的准确标识；预览会核对配置，不启动或安装模型。</p><label>媒体提示词<textarea maxLength={16000} disabled={!editable} value={node.parameters.prompt || ''} onChange={event => updateMediaField('prompt', event.target.value)} /></label><p>文本输入端口与本提示词组成预览中的完整输入；须在调用前重新核对。</p><label><input type="checkbox" disabled={!editable} checked={node.parameters.allow_cloud === true} onChange={event => updateMediaField('allow_cloud', event.target.checked)} />本节点允许将提示词与已绑定参考素材发送到明确配置的云端服务，可能产生费用</label></> : <><p>音频截取仅在本地执行，须连接一个当前音频来源；最长片段 120 秒。</p>{(node.parameters.provider_id != null || node.parameters.model_id != null || node.parameters.prompt || node.parameters.allow_cloud) && <Button disabled={!editable} onClick={clearMediaTrimInputs}>明确清空截取操作不使用的服务商、模型、提示词与云端许可</Button>}</>}
      <fieldset disabled={!editable}><legend>媒体处理参数</legend>{parameterNames.map(mediaParameter)}{unsupported.length > 0 && <><StatusMessage tone="warning">当前操作不支持已保留的参数：{unsupported.map(name => GRAPH_MEDIA_PARAMETER_LABELS[name] || name).join('、')}。输入不会自动丢弃。</StatusMessage><Button disabled={!editable} onClick={clearUnsupportedMediaParameters}>明确清空本操作不支持的参数</Button></>}</fieldset>
      <label>来源与授权说明<input maxLength={2000} disabled={!editable} value={node.parameters.license_note || ''} onChange={event => updateMediaField('license_note', event.target.value)} /></label>
      <p>媒体文本可选择 TEXT 或已审核 DRAFT，两种输入互斥。使用模型结果时，先连接文字模型 draft → 人工审核 draft，再连接该审核节点 reviewed_draft → 本节点 draft；原文字私有档案须实际批准后才能预览媒体输入。</p>
      <p>制作候选输出必须连接到唯一的媒体审核节点。仅审核完成后的素材端口可以用于下游；保存和连接不会调用服务。</p>
    </>}
    {node.definition_id === 'human_review' && draft.schema_version === 3 && <p>明确批准此节点后，才输出 reviewed_draft。只有直接审核原文字模型提案并批准其私有档案的节点可给媒体 draft 提供文字；审核不自动调用媒体，也不发布文字。</p>}
    {node.definition_id === 'timeline_export' && <StudioGraphTimelineNodeEditor node={node} state={timelineEditor} editable={editable} connectedPorts={draft.edges.filter(edge => edge.target_node_id === node.id).map(edge => edge.target_port)} />}
    {node.definition_id === 'media_review' && <p>连接一个媒体制作候选。运行时先读取候选、核对摘要并明确批准或拒绝；批准入库后才输出素材引用，不自动执行下游。</p>}
    <div className="studio-graph-position">{(['x', 'y'] as const).map(axis => <label key={axis}>节点 {axis.toUpperCase()}<input type="number" min={-100000} max={100000} value={node.position[axis]} disabled={!editable} onChange={event => { const value = Number(event.target.value); if (Number.isFinite(value) && value >= -100000 && value <= 100000) change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, position: { ...row.position, [axis]: value } } : row) }); }} /></label>)}</div>
    {node.definition_id === 'asset_reference' && <><p>图读取时引用状态：{referenceState || '待保存核对'} · {draft.schema_version >= 3 ? '执行时核对当前来源版本和真实内容' : '旧图只读引用，不执行媒体处理'}</p>{node.parameters.asset_id ? <p>原资产 {node.parameters.asset_id} · 绑定 v{node.parameters.version}</p> : <p>引用不可用或无权访问，原详情已隐藏。</p>}{previewState === 'READING' && <StatusMessage>正在核对引用资产版本与摘要…</StatusMessage>}{previewState === 'STALE' && <StatusMessage tone="warning">当前资产与图中绑定不同，未显示为原绑定版本。请核对图服务端版本与来源状态。</StatusMessage>}{previewState === 'UNAVAILABLE' && <StatusMessage tone="warning">引用资产当前不可读取，原绑定保持。</StatusMessage>}{node.parameters.asset_id && <Button disabled={busy || previewState === 'READING'} onClick={refreshPreview}>核对引用资产</Button>}{preview && <AssetInspector asset={preview} downloadAsset={downloadPreviewAsset} isCurrent={current} showReferences={false} />}</>}
    <Button variant="danger" disabled={!editable || protectedNodes.includes(node.id)} onClick={() => { change(removeGraphNodes(draft, [node.id], protectedNodes)); setSelected([]); }}>移除当前节点</Button><p>移除节点只修改本图，不删除任何原资产、章节或运行记录。</p>
    </> : <EmptyState title="未选择图节点" detail="在画布或键盘节点列表中选择一个节点，编辑其参数和位置。" />}</section>;
  return { content, inspector };
}
