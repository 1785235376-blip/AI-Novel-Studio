import { AssetInspector } from '../novel/AssetInspector';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { GraphCanvas } from './GraphCanvas';
import { GraphRunPanel } from './GraphRunPanel';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphDefinitionId } from './studioGraphTypes';
import { MEDIA_OPERATION_LABELS } from './useStudioMediaExecution';
import type { MediaOperation } from './studioProductionClient';
import { GRAPH_MEDIA_PARAMETER_LABELS, graphMediaParameterNames } from './useStudioGraphEditorController';
import type { StudioGraphEditorController, StudioGraphEditorProps } from './useStudioGraphEditorController';
import { StudioGraphTimelineNodeEditor } from './StudioGraphTimelineNodeEditor';
import './studioGraph.css';

const portKey = (node: string, port: string) => JSON.stringify([node, port]);
/** Render only. UI refactors consume the same controller without replacing operation contracts. */
export function studioGraphEditorView(controller: StudioGraphEditorController, props: StudioGraphEditorProps) {
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
    catalog, records, base, draft, selected, past, future, loading, error, notice, blocked,
    candidate, replaceConfirmed, checking, pendingNavigation, discardConfirmed, kind, sourcePort, targetPort,
    assets, assetChoice, assetLoading, preview, previewState, refreshPreview, downloadPreviewAsset, current, dirty, editable, protectedNodes, node,
    load, change, navigate, open, newGraph, save, checkServer, loadAssets, addNode, connect, travel, confirmNavigation, adoptCandidate,
    setReplaceConfirmed, setCandidate, setDiscardConfirmed, setPendingNavigation, setKind, setAssetChoice,
    setSourcePort, setTargetPort, setSelected, reportRunSelection,
    mediaSchemaConsent, setMediaSchemaConsent, upgradeMediaSchema, executionDirty, setExecutionDirty,
    updateMediaField, updateMediaParameter, clearUnsupportedMediaParameters, clearMediaTrimInputs, timelineEditor,
  } = controller;
  const mediaEnabled = catalog?.capabilities.media_execution === true && catalog.capabilities.media_execution_contract === 'creative-graph-media/1';
  const nodeLimit = draft.schema_version === 3 ? catalog?.media_limits?.nodes || 24 : catalog?.limits.nodes || 16;
  const schemaRequired = kind === 'media_generate' || kind === 'media_review' || kind === 'timeline_export' || kind === 'asset_reference' && mediaEnabled;
  const mediaOperation = node?.parameters.operation_id, parameterNames = mediaOperation ? graphMediaParameterNames(mediaOperation) : [];
  const unsupported = Object.entries(node?.parameters.parameters || {}).filter(([key, value]) => value !== null && !parameterNames.includes(key)).map(([key]) => key);
  function mediaParameter(name: string) {
    const value = node?.parameters.parameters?.[name] ?? '', label = GRAPH_MEDIA_PARAMETER_LABELS[name];
    if (name === 'negative_prompt') return <label key={name}>{label}<textarea maxLength={8000} value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)} /></label>;
    if (name === 'size' || name === 'quality') {
      const options = name === 'size' ? ['auto', '1024x1024', '1536x1024', '1024x1536'] : ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
      return <label key={name}>{label}<select value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)}><option value="">服务商默认值</option>{options.map(option => <option key={option} value={option}>{option}</option>)}</select></label>;
    }
    const ranges: Record<string, [number, number, number]> = { width: [64, 2048, 8], height: [64, 2048, 8], steps: [1, 150, 1], seed: [0, 2147483647, 1],
      duration_seconds: [1, 600, 1], frame_rate: [1, 60, 1], speech_rate: [0.5, 2, 0.1], in_ms: [0, 600000, 1], out_ms: [1, 600000, 1] }, range = ranges[name];
    return <label key={name}>{label}<input type={range ? 'number' : 'text'} min={range?.[0]} max={range?.[1]} step={range?.[2]} maxLength={name === 'voice_id' ? 240 : undefined}
      value={String(value)} disabled={!editable} onChange={event => updateMediaParameter(name, event.target.value)} /></label>;
  }
  const content = <section className="studio-graph-editor" aria-label="独立创作图编辑器">
    <Panel title="创作图 · 手工编排"><p>空图和不相连的组件都可以保存。导演备注可选，可随时移除；连接类型由服务端定义。</p>{catalog?.capabilities.model_execution && <p>可选本地文字模型节点需单独预览输入并明确确认一次调用。每次运行最多一个文字模型节点，输出必须人工审核；不自动调用、重试或转云端。</p>}
      {mediaEnabled ? <p>媒体图 v3 使用原任务服务逐项入队和执行。候选只能进入人工审核，审核后的当前素材才能用于下游。每图最多四个媒体制作节点；本机与完整流程验收仍待完成。</p> : <p>当前保留本地文本与手工工作流。旧图中的资产节点保持只读引用，不执行媒体处理。</p>}
      <div className="studio-graph-actions"><Button disabled={busy || externalDirty || executionDirty} onClick={() => navigate(newGraph)}>新建空图</Button><Button disabled={loading || busy} onClick={() => void load()}>刷新创作图目录</Button></div>
      <label>已保存创作图<select aria-label="已保存创作图" disabled={busy || externalDirty || executionDirty} value={base?.id || ''} onChange={event => { const id = event.target.value; if (id) navigate(() => void open(id)); }}><option value="">未选择已保存图</option>{records.map(row => <option key={row.id} value={row.id}>{row.definition.title} · v{row.version}</option>)}</select></label>
      <label>创作图标题<input maxLength={160} value={draft.title} disabled={!editable} onChange={event => change({ ...draft, title: event.target.value })} /></label>
      <Badge tone={dirty || blocked ? 'warning' : 'neutral'}>{base ? `v${base.version}` : '尚未保存'} · {dirty ? '未保存修改' : '无未保存修改'}</Badge>
      <div className="studio-graph-actions"><Button variant="primary" disabled={!editable || !draft.title.trim() || !!base && !dirty} onClick={() => void save()}>保存创作图</Button><Button disabled={!editable || !past.length} onClick={() => travel(false)}>撤销图编辑</Button><Button disabled={!editable || !future.length} onClick={() => travel(true)}>重做图编辑</Button><Button disabled={busy || !base} onClick={() => navigate(() => void open(base!.id))}>重新读取创作图</Button></div>
    </Panel>
    {loading && <StatusMessage>正在读取当前范围的节点目录…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {externalDirty && <StatusMessage tone="warning">请先保存或放弃资产/偏好输入，再修改创作图。</StatusMessage>}
    {executionDirty && <StatusMessage tone="warning">当前图媒体有待确认输入或不确定回执。先在原运行中取消确认或读取核对，再切换或修改图。</StatusMessage>}
    {timelineEditor.formDirty && <StatusMessage tone="warning">尚有未加入图草稿的剪辑输入，请明确加入或放弃后保存。<Button disabled={busy || timelineEditor.loading} onClick={timelineEditor.clearForm}>放弃尚未加入的剪辑输入</Button></StatusMessage>}
    {base?.can_edit === false && <StatusMessage tone="warning">图中包含不可见的资产引用，当前仅可查看。原绑定不会被省略、删除或重新保存；需恢复访问后重新读取。</StatusMessage>}
    {blocked && <section className="studio-graph-conflict" role="alert"><p>保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。</p><Button disabled={busy || checking} onClick={() => void checkServer()}>核对图服务端版本</Button>{!base && <Button disabled={busy || checking || !canMutate} onClick={() => void save(true)}>使用同一请求重试保存</Button>}</section>}
    {checking && <StatusMessage>正在核对图服务端版本；当前草稿保持。</StatusMessage>}
    {candidate && <section className="studio-graph-conflict" aria-label="图服务端版本"><p>服务端 v{candidate.version} · {candidate.definition.title} · {candidate.definition.nodes.length} 节点 / {candidate.definition.edges.length} 连接</p><label><input type="checkbox" disabled={busy || externalDirty} checked={replaceConfirmed} onChange={event => setReplaceConfirmed(event.target.checked)} />确认放弃当前图草稿，采用已核对服务端版本</label><Button disabled={!replaceConfirmed || busy || externalDirty} onClick={adoptCandidate}>采用图服务端版本</Button><Button onClick={() => setCandidate(undefined)}>保留图草稿</Button></section>}
    {pendingNavigation && <section role="alert" className="studio-graph-conflict"><p>当前图有未保存输入，切换会放弃本页草稿。</p><label><input type="checkbox" disabled={busy || externalDirty} checked={discardConfirmed} onChange={event => setDiscardConfirmed(event.target.checked)} />确认放弃图草稿</label><Button disabled={!discardConfirmed || busy || externalDirty} onClick={confirmNavigation}>确认切换创作图</Button><Button onClick={() => setPendingNavigation(undefined)}>继续编辑创作图</Button></section>}
    {catalog && <>{mediaEnabled && <section aria-label="媒体图版本"><p>当前图格式：v{draft.schema_version}。旧图保持原行为，升级只在明确保存后生效，不自动执行。</p>{draft.schema_version !== 3 && <><label><input type="checkbox" checked={mediaSchemaConsent} disabled={!editable} onChange={event => setMediaSchemaConsent(event.target.checked)} />确认升级为媒体图 v3；已有资产引用将可以作为当前版本来源执行读取</label><Button disabled={!editable || !mediaSchemaConsent} onClick={upgradeMediaSchema}>明确升级当前草稿为媒体图 v3</Button></>}</section>}
      <section className="studio-graph-controls" aria-label="添加与连接节点"><label>节点类型<select aria-label="节点类型" value={kind} disabled={!editable} onChange={event => { const value = event.target.value as StudioGraphDefinitionId; setKind(value); if (value === 'asset_reference') void loadAssets(); }}>{catalog.definitions.map(row => <option value={row.id} key={row.id}>{GRAPH_NODE_LABELS[row.id]}</option>)}</select></label>
      {kind === 'asset_reference' && <><label>原资产<select aria-label="原资产" disabled={!editable || assetLoading} value={assetChoice} onChange={event => setAssetChoice(event.target.value)}><option value="">选择已保存原资产</option>{assets.map(row => <option value={row.id} key={row.id}>{row.filename} · {row.kind} · v{row.version}</option>)}</select></label><Button disabled={assetLoading || busy} onClick={() => void loadAssets()}>刷新图引用资产</Button><p>只保存原资产 ID、版本和摘要；不复制文件。保存后的引用暂不能移除或重绑，可禁用节点。</p></>}
      {kind === 'timeline_export' && <><Button disabled={!timelineEditor.canLoad} loading={timelineEditor.loading} onClick={() => void timelineEditor.loadRows()}>明确读取原时间线目录</Button><label>原时间线<select disabled={!editable || timelineEditor.loading} value={timelineEditor.choice} onChange={event => timelineEditor.choose(event.target.value)}><option value="">选择已有时间线</option>{timelineEditor.rows.map(row => <option key={row.id} value={row.id}>{row.title} · {row.id} · v{row.version}</option>)}</select></label>{timelineEditor.chosen && <p>确切来源摘要：<code>{timelineEditor.chosen.timeline_digest}</code></p>}<p>使用原时间线；新增节点不保存剪辑、不入队、不渲染。</p>{timelineEditor.error && <StatusMessage tone="error">{timelineEditor.error}</StatusMessage>}</>}
      {schemaRequired && draft.schema_version !== 3 && <p>添加可执行资产来源或媒体节点前，先明确升级当前草稿为 v3。</p>}
      <Button disabled={!editable || draft.nodes.length >= nodeLimit || schemaRequired && draft.schema_version !== 3 || ['media_generate', 'timeline_export'].includes(kind) && draft.nodes.filter(row => ['media_generate', 'timeline_export'].includes(row.definition_id)).length >= 4 || kind === 'asset_reference' && !assetChoice || kind === 'timeline_export' && !timelineEditor.chosen} onClick={addNode}>添加节点</Button>
      <label>起始输出端口<select aria-label="起始输出端口" disabled={!editable} value={sourcePort} onChange={event => setSourcePort(event.target.value)}><option value="">选择输出端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.outputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <label>目标输入端口<select aria-label="目标输入端口" disabled={!editable} value={targetPort} onChange={event => setTargetPort(event.target.value)}><option value="">选择输入端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.inputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <Button disabled={!editable || !sourcePort || !targetPort || draft.edges.length >= catalog.limits.edges} onClick={connect}>连接所选端口</Button></section>
      <GraphCanvas definition={draft} nodeDefinitions={catalog.definitions} selectedNodeIds={selected} onSelectionChange={setSelected} onDefinitionChange={change} readonly={!editable} busy={busy} protectedNodeIds={protectedNodes} interactionKey={`${identity}:${base?.id || 'new'}`} onPortSelect={port => { if (port.direction === 'output') setSourcePort(portKey(port.nodeId, port.portId)); else setTargetPort(portKey(port.nodeId, port.portId)); }} />
      <section aria-label="图连接列表"><h3>已保存到草稿的连接</h3>{!draft.edges.length && <p>暂无连接；不相连节点可以独立保存。</p>}<ul>{draft.edges.map(edge => <li key={edge.id}>{edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}<Button disabled={!editable} onClick={() => change({ ...draft, edges: draft.edges.filter(row => row.id !== edge.id) })}>移除连接 {edge.id}</Button></li>)}</ul></section>
      <GraphRunPanel client={client.graphs} graph={base} targetNodeIds={selected} dirty={dirty || blocked} busy={busy} canMutate={canMutate && !externalDirty} canReview={canReview && !externalDirty} modelExecutionEnabled={catalog.capabilities.model_execution && catalog.capabilities.model_execution_contract === 'creative-graph-model/1'} mediaExecutionEnabled={mediaEnabled} onDirtyChange={setExecutionDirty} isCurrent={current} read={read} mutate={mutate} requestedRunId={requestedRunId} onRunSelectionChange={reportRunSelection} />
    </>}
  </section>;
  const referenceState = base?.reference_states.find(row => row.node_id === node?.id)?.state;
  const inspector = <section className="studio-graph-inspector" aria-label="创作图节点检查器">{node ? <><h2>{GRAPH_NODE_LABELS[node.definition_id]}</h2><p>{node.id} · 定义 v{node.definition_version}</p><label><input type="checkbox" checked={node.enabled} disabled={!editable} onChange={event => change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, enabled: event.target.checked } : row) })} />启用当前节点</label>
    {(['text_input', 'manual_transform', 'director_note'] as const).includes(node.definition_id as 'text_input') && <label>{node.definition_id === 'text_input' ? '作者输入文本' : node.definition_id === 'manual_transform' ? '手工处理结果' : '可选导演备注'}<textarea maxLength={node.definition_id === 'director_note' ? 4000 : 8000} disabled={!editable} value={String(node.parameters[node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'] || '')} onChange={event => { const key = node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'; change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { [key]: event.target.value } } : row) }); }} /></label>}
    {node.definition_id === 'text_generate' && <><label>本地模型写作指令<textarea maxLength={4000} disabled={!editable} value={node.parameters.instruction || ''} onChange={event => change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { ...row.parameters, instruction: event.target.value } } : row) })} /></label><label>最大输出 token<input type="number" min={1} max={2048} step={1} disabled={!editable} value={node.parameters.max_output_tokens ?? 512} onChange={event => { const value = Number(event.target.value); if (Number.isSafeInteger(value) && value >= 1 && value <= 2048) change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { ...row.parameters, max_output_tokens: value } } : row) }); }} /></label><p>保存节点不调用模型。将草稿输出连接到人工审核节点后，创建运行并单独核对本地路由和完整输入。</p></>}
    {node.definition_id === 'media_generate' && <>
      <label>媒体操作<select disabled={!editable} value={mediaOperation || 'm5.image.t2i'} onChange={event => updateMediaField('operation_id', event.target.value as MediaOperation)}>{Object.entries(MEDIA_OPERATION_LABELS).map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select></label>
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
    {node.definition_id === 'asset_reference' && <><p>图读取时引用状态：{referenceState || '待保存核对'} · {draft.schema_version === 3 ? '执行时核对当前来源版本和真实内容' : '旧图只读引用，不执行媒体处理'}</p>{node.parameters.asset_id ? <p>原资产 {node.parameters.asset_id} · 绑定 v{node.parameters.version}</p> : <p>引用不可用或无权访问，原详情已隐藏。</p>}{previewState === 'READING' && <StatusMessage>正在核对引用资产版本与摘要…</StatusMessage>}{previewState === 'STALE' && <StatusMessage tone="warning">当前资产与图中绑定不同，未显示为原绑定版本。请核对图服务端版本与来源状态。</StatusMessage>}{previewState === 'UNAVAILABLE' && <StatusMessage tone="warning">引用资产当前不可读取，原绑定保持。</StatusMessage>}{node.parameters.asset_id && <Button disabled={busy || previewState === 'READING'} onClick={refreshPreview}>核对引用资产</Button>}{preview && <AssetInspector asset={preview} downloadAsset={downloadPreviewAsset} isCurrent={current} showReferences={false} />}</>}
    <Button variant="danger" disabled={!editable || protectedNodes.includes(node.id)} onClick={() => { change({ ...draft, nodes: draft.nodes.filter(row => row.id !== node.id), edges: draft.edges.filter(edge => edge.source_node_id !== node.id && edge.target_node_id !== node.id) }); setSelected([]); }}>移除当前节点</Button><p>移除节点只修改本图，不删除任何原资产、章节或运行记录。</p>
    </> : <EmptyState title="未选择图节点" detail="在画布或键盘节点列表中选择一个节点，编辑其参数和位置。" />}</section>;
  return { content, inspector };
}
