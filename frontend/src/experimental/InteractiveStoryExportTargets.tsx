import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Details, ErrorMessage, useAction } from './shared';
import type { interactiveStoryClient, InteractiveStory, StoryExportPreview, StoryExportResult, StoryExportTarget, StoryExportTargets } from './interactiveStoryClient';
import { artifactEvidenceRows, artifactEvidenceStatusLabel, artifactEvidenceStatusTone, capabilitySummaryText, compatibleIssueText, evidenceMatchText, formatDigest, historicalEvidenceText, probeDescription, runtimeClaimText, splitCapabilities, targetKindLabel, targetLossRows, targetReadiness } from './interactiveStoryExportPresentation';

type Api = ReturnType<typeof interactiveStoryClient>;
type Receipt<T> = { owner: object; value: T };
type Artifact = { url: string; filename: string; result: StoryExportResult };

function policyText(policy: string): string {
  if (policy === 'INDEPENDENT_EVIDENCE_LEVELS; GENERATION_IS_NOT_RUNTIME; MISSING_ENGINE_BLOCKS_RUNTIME_NOT_SAFE_EXPORT') {
    return '证据按独立等级记录；生成成功不等于运行成功；缺少引擎只会阻止运行验证，不会阻止安全生成与导出。';
  }
  return policy;
}

function previewLosses(preview: StoryExportPreview, target: StoryExportTarget | undefined): string[] {
  const losses: string[] = [];
  for (const loss of [...(preview.losses ?? []), ...targetLossRows(target)]) {
    if (typeof loss === 'string' && loss && !losses.includes(loss)) losses.push(loss);
  }
  return losses;
}

function TargetSection({ target, selected, storyStatus, analysisCanReview, blocked, busy, onSelect }: {
  target: StoryExportTarget; selected: boolean; storyStatus: string; analysisCanReview: boolean;
  blocked: boolean; busy: boolean; onSelect: (targetId: string) => void;
}) {
  const readiness = targetReadiness(target, storyStatus, analysisCanReview);
  const probe = probeDescription(target.engine_probe);
  const claim = runtimeClaimText(target.runtime_claim);
  const capabilities = splitCapabilities(target.compatibility.capabilities);
  const losses = targetLossRows(target);
  const runnable = target.kind === 'RUNNABLE_PROJECT';
  const selectable = runnable && target.export_ready && readiness.exportReady;
  return <article className="experimental-record" aria-label={`导出目标 ${target.target_id}`}>
    <div className="experimental-actions"><Badge tone={target.export_ready ? 'success' : 'warning'}>{target.export_ready ? '当前可安全导出' : '当前不可导出'}</Badge><Badge tone="neutral">{targetKindLabel(target.kind)}</Badge><strong>{target.display_name}</strong></div>
    <p>{target.target_id} · 格式 {target.format_version} · 适配器修订 r{target.adapter_revision}{target.engine ? ` · 需要 ${target.engine.name} ≥ ${target.engine.minimum_version}` : ' · 无需外部引擎'}</p>
    {runnable
      ? <div className="experimental-actions"><Button disabled={blocked || busy || !selectable} aria-pressed={selected} onClick={() => onSelect(target.target_id)}>选择目标 {target.display_name}</Button>{!selectable && <Badge tone="warning">需要 APPROVED 修订、通过的路径分析与目标兼容性</Badge>}</div>
      : <StatusMessage tone="info">兼容性条目，仅包含在旧的多样式导出包中；此目标不提供单目标项目包下载。</StatusMessage>}
    {!readiness.exportReady && !!readiness.reasons.length && <section aria-label={`不可导出原因 ${target.target_id}`}><p>不可导出原因：</p><ul>{readiness.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></section>}
    <section aria-label={`引擎探测 ${target.target_id}`}><h4>引擎探测（生成不要求引擎就绪）</h4><p><Badge tone={probe.tone}>{probe.headline}</Badge></p><p>{probe.detail}</p>
      {target.engine && <p>候选可执行文件：{target.engine.executables.length ? target.engine.executables.join('、') : '（未声明）'}{target.engine.env_override ? ` · 环境变量覆盖 ${target.engine.env_override}` : ''}{target.engine.gui ? ' · GUI 应用' : ''}{target.engine.note ? ' · ' + target.engine.note : ''}</p>}</section>
    <section aria-label={`当前产物验证 ${target.target_id}`}><h4>当前产物验证（仅绑定当前作品/修订/产物摘要）</h4><p><Badge tone={claim.tone}>{claim.text}</Badge></p>
      <p><Badge tone={artifactEvidenceStatusTone(target.artifact_evidence_status, target.artifact_evidence?.levels)}>{artifactEvidenceStatusLabel(target.artifact_evidence_status)}</Badge></p>
      {!!target.artifact_evidence?.reason && <p>{target.artifact_evidence.reason}</p>}
      <ul>{artifactEvidenceRows(target.artifact_evidence?.levels).map(row => <li key={row.level}><Badge tone={row.tone}>{row.status}</Badge> {row.label}（{row.level}）</li>)}</ul>
      {!!target.artifact_evidence?.matched_receipt && <p>{evidenceMatchText(target.artifact_evidence.matched_receipt)}</p>}
      {!!target.artifact_evidence?.export_record && <p>最近导出产物：修订 v{String(target.artifact_evidence.export_record.revision)} · ZIP sha256 {formatDigest(String(target.artifact_evidence.export_record.artifact_sha256))} · 已记录验证回执 {target.artifact_evidence.checked_receipts} 条</p>}
      {!!target.artifact_evidence?.stale_receipts?.length && <><p>被拒绝/过期的验证回执：</p><ul>{target.artifact_evidence.stale_receipts.map((item, index) => <li key={index}>{item.code}：{item.detail}</li>)}</ul></>}
    </section>
    <section aria-label={`历史验证 ${target.target_id}`}><h4>模板/适配器历史验证（不代表当前作品）</h4><p>{historicalEvidenceText(target.historical_evidence)}</p>
      <ul>{artifactEvidenceRows(target.historical_evidence).map(row => <li key={row.level}><Badge tone={row.tone}>{row.status}</Badge> {row.label}（{row.level}）</li>)}</ul></section>
    <section aria-label={`能力与损失 ${target.target_id}`}><h4>能力与损失</h4><p>{capabilitySummaryText(target.compatibility.capabilities)}</p>
      {!!capabilities.unsupported.length && <><p>不支持能力：</p><ul>{capabilities.unsupported.map(row => <li key={row.key}>{row.label}（{row.key}）{row.note ? ' — ' + row.note : ''}</li>)}</ul></>}
      {!!capabilities.lossy.length && <><p>有损能力：</p><ul>{capabilities.lossy.map(row => <li key={row.key}>{row.label}（{row.key}）{row.note ? ' — ' + row.note : ''}</li>)}</ul></>}
      {!!losses.length && <><p>兼容性损失：</p><ul>{losses.map(loss => <li key={loss}>{loss}</li>)}</ul></>}
      {!!target.compatibility.issues.length && <><p>兼容性问题：</p><ul>{target.compatibility.issues.map((issue, index) => <li key={index}>{compatibleIssueText(issue)}</li>)}</ul></>}
      {!!target.compatibility.notes.length && <p>说明：{target.compatibility.notes.join('；')}</p>}</section>
    <section aria-label={`使用步骤 ${target.target_id}`}><h4>导出后使用步骤</h4><p>{target.launch_instructions}</p>{!!target.runtime_requirements.length && <p>运行时要求：{target.runtime_requirements.join('；')}</p>}
      <Details label={`${target.display_name} 集成说明与完整描述`} value={{ target_id: target.target_id, kind: target.kind, format_version: target.format_version, adapter_revision: target.adapter_revision, integration_notes: target.integration_notes, descriptor_losses: target.losses, runtime_requirements: target.runtime_requirements }} /></section>
  </article>;
}

/** Target-aware export workflow. Generation is a pure conversion; runtime
 * evidence stays independent and a missing engine never blocks safe export. */
export function InteractiveStoryExportTargets({ api, story, blocked }: { api: Api; story: InteractiveStory; blocked: boolean }) {
  const [targets, setTargets] = useState<Receipt<StoryExportTargets>>();
  const [targetId, setTargetId] = useState<string>();
  const [preview, setPreview] = useState<Receipt<StoryExportPreview>>();
  const [confirmed, setConfirmed] = useState(false);
  const [artifact, setArtifact] = useState<Receipt<Artifact>>();
  const alive = useRef(true), urlRef = useRef<string>();
  const targetsEpoch = useRef(0), previewEpoch = useRef(0), exportEpoch = useRef(0);
  const targetsAction = useAction(), previewAction = useAction(), exportAction = useAction();
  const actionOwners = useRef<{ targets?: object; preview?: object; export?: object }>({});
  const values = [api, story, blocked], owner = useRef({ values, token: {} });
  if (values.some((value, index) => value !== owner.current.values[index])) owner.current = { values, token: {} };
  const token = owner.current.token;
  const liveStory = useRef(story); liveStory.current = story;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; targetsEpoch.current++; previewEpoch.current++; exportEpoch.current++; if (urlRef.current) URL.revokeObjectURL(urlRef.current); urlRef.current = undefined; }; }, []);
  useEffect(() => { setPreview(undefined); setConfirmed(false); }, [story.id, story.version]);
  // A receipt from another client/story/version must never revive or leak its object URL.
  useEffect(() => {
    if (artifact && artifact.owner !== token && urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = undefined; setArtifact(undefined); }
  }, [token, artifact]);
  const ownerCurrent = () => alive.current && owner.current.token === token && !blocked
    && !liveStory.current.stale && !liveStory.current.content_withheld && liveStory.current.status !== 'ARCHIVED';
  const busy = targetsAction.busy || previewAction.busy || exportAction.busy;
  const view = targets && targets.owner === token ? targets.value : undefined;
  const selected = view && targetId ? view.targets.find(target => target.target_id === targetId) : undefined;
  const previewValue = preview && preview.owner === token ? preview.value : undefined;
  const activePreview = previewValue && selected && previewValue.target_id === selected.target_id ? previewValue : undefined;
  const currentArtifact = artifact && artifact.owner === token ? artifact.value : undefined;
  const loadTargets = () => {
    if (!ownerCurrent() || busy) return;
    actionOwners.current.targets = token;
    void targetsAction.run(async () => {
      const ticket = ++targetsEpoch.current;
      setTargets(undefined); setTargetId(undefined); setPreview(undefined); setConfirmed(false); setArtifact(undefined);
      const value = await api.targets(liveStory.current);
      if (ownerCurrent() && ticket === targetsEpoch.current) setTargets({ owner: token, value });
    }, '导出目标、引擎探测与独立证据已读取（未运行任何引擎）。');
  };
  const selectTarget = (id: string) => {
    if (!ownerCurrent() || busy) return;
    setPreview(undefined); setConfirmed(false);
    setTargetId(old => old === id ? undefined : id);
  };
  const preflight = () => {
    const target = selected; if (!ownerCurrent() || !target || busy) return;
    actionOwners.current.preview = token;
    void previewAction.run(async () => {
      const ticket = ++previewEpoch.current;
      setPreview(undefined); setConfirmed(false);
      const value = await api.exportPreview(liveStory.current, target.target_id);
      if (ownerCurrent() && ticket === previewEpoch.current) setPreview({ owner: token, value });
    }, '所选目标的导出预检完成；仍需确认损失才会生成下载。');
  };
  const generate = () => {
    const target = selected, active = activePreview;
    if (!ownerCurrent() || !target || !active || !confirmed || busy) return;
    actionOwners.current.export = token;
    void exportAction.run(async () => {
      const ticket = ++exportEpoch.current;
      setArtifact(undefined);
      const result = await api.export(liveStory.current, active, target.target_id);
      if (!(ownerCurrent() && ticket === exportEpoch.current)) return;
      const bytes = Uint8Array.from(atob(result.content_base64), character => character.charCodeAt(0));
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      const url = URL.createObjectURL(new Blob([bytes], { type: result.mime }));
      urlRef.current = url;
      setArtifact({ owner: token, value: { url, filename: result.filename, result } });
    }, '所选目标包已生成并可下载；生成不等于目标引擎运行验证。');
  };
  const archived = story.status === 'ARCHIVED';
  return <Panel title="导出目标与独立证据"><p>读取每个导出目标的兼容性、损失、所需引擎探测与独立证据等级，再选择可运行目标单独下载项目包。生成是纯转换，不等于目标引擎运行成功；缺少引擎只会阻止运行验证，不会阻止安全生成与导出。不选择目标时，上方「审核与独立导出」仍保留旧的多目标包流程。</p>
    <div className="experimental-actions"><Button disabled={blocked || archived || busy} onClick={loadTargets}>读取导出目标</Button>{view && <Badge tone="info">已读取 {view.targets.length} 个目标</Badge>}</div>
    {archived && <StatusMessage tone="warning">归档版本不能导出；请先恢复为待审草稿。</StatusMessage>}
    {actionOwners.current.targets === token && targetsAction.feedback}
    {view && <section aria-label="导出目标列表">
      <p>目标清单契约：{view.contract_schema} v{view.contract_version} · 清单 {view.schema} · 改编 v{view.adaptation.version}（{view.adaptation.status}）</p>
      <p>故事：{view.story.title} · {view.story.nodes} 节点 · {view.story.variables} 变量 · {view.story.endings} 结局 · 步数上限 {view.story.max_steps}</p>
      <p>版本摘要：spec {formatDigest(view.story.spec_digest)} · 来源 {formatDigest(view.story.source_digest)}</p>
      <StatusMessage tone={view.can_export_any ? 'success' : 'warning'}>{view.can_export_any ? '当前已批准修订至少有一个可运行目标可安全生成；仍不代表目标引擎运行验证成功。' : story.status !== 'APPROVED' ? '当前修订不是 APPROVED：只能查看兼容性、引擎探测与证据，不能生成导出。' : '当前修订没有可安全生成的可运行目标；请先解决路径与兼容性问题。'}</StatusMessage>
      <p>{policyText(view.target_runtime_policy)}</p>
      {view.targets.map(target => <TargetSection key={target.target_id} target={target} selected={selected?.target_id === target.target_id} storyStatus={story.status} analysisCanReview={view.analysis.can_review} blocked={blocked || archived} busy={busy} onSelect={selectTarget} />)}
    </section>}
    {selected && <section aria-label="所选目标导出"><h3>所选目标：{selected.display_name}（{selected.target_id}）</h3>
      {!selected.compatibility.can_export && <StatusMessage tone="warning">该目标与当前故事内容不兼容；预检会列出损失与问题，不能生成导出。</StatusMessage>}
      <div className="experimental-actions"><Button disabled={blocked || archived || busy} onClick={preflight}>预检所选目标导出</Button>{activePreview && <Button disabled={busy} onClick={preflight}>重新预检所选目标</Button>}</div>
      {actionOwners.current.preview === token && previewAction.feedback}
      {activePreview && <section aria-label="所选目标导出预检">
        <StatusMessage tone={activePreview.can_export ? 'success' : 'warning'}>{activePreview.can_export ? '所选目标可在当前已批准修订上安全生成；这不代表目标引擎已运行。' : '所选目标当前不能导出；请先解决审核状态、路径问题或兼容性问题。'}</StatusMessage>
        <p>目标：{activePreview.target_id ?? selected.target_id} · 预检摘要 {formatDigest(activePreview.preview_digest)} · 缺失资源 {activePreview.media_manifest.filter(item => item.missing).length} / 引用 {activePreview.media_manifest.length} 项（媒体字节不随包导出）</p>
        <p>损失与不支持项：</p><ul>{previewLosses(activePreview, selected).map(loss => <li key={loss}>{loss}</li>)}</ul>
        <label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={!activePreview.can_export || busy} onChange={event => setConfirmed(event.target.checked)} />已核对所选目标的兼容性损失、不支持能力与缺失项，确认生成 {selected.display_name} 下载</label>
        <Button disabled={!confirmed || !activePreview.can_export || blocked || busy} onClick={generate}>生成所选目标包</Button>
        {actionOwners.current.export === token && exportAction.feedback}
      </section>}
      {!!activePreview?.artifact_evidence && <p><Badge tone={artifactEvidenceStatusTone(activePreview.artifact_evidence.status, activePreview.artifact_evidence.levels)}>{artifactEvidenceStatusLabel(activePreview.artifact_evidence.status)}</Badge> 预检同时读取了当前产物验证状态；它只对已记录且绑定该产物摘要的验证回执生效。</p>}
      {activePreview && !currentArtifact && <p>下载状态：尚未生成。生成只会下载确定性 ZIP，不会安装或运行引擎，也不会上传作品。</p>}
      {currentArtifact && <section aria-label="所选目标下载状态"><StatusMessage tone="success">目标包已生成，可下载；生成不等于目标引擎运行验证。</StatusMessage>
        <a href={currentArtifact.url} download={currentArtifact.filename}>下载 {currentArtifact.filename}</a>
        <ul><li>target_id：{currentArtifact.result.target_id}</li><li>格式版本：{currentArtifact.result.target_format_version}</li><li>适配器修订：{currentArtifact.result.adapter_revision}</li><li>文件数：{currentArtifact.result.file_count}</li><li>ZIP sha256：{currentArtifact.result.sha256}</li><li>文件集合摘要：{currentArtifact.result.files_digest}</li></ul>
        <p><Badge tone={runtimeClaimText(currentArtifact.result.runtime_claim).tone}>{runtimeClaimText(currentArtifact.result.runtime_claim).text}</Badge></p>
        {!!currentArtifact.result.artifact_evidence && <p><Badge tone={artifactEvidenceStatusTone(currentArtifact.result.artifact_evidence_status, currentArtifact.result.artifact_evidence.levels)}>{artifactEvidenceStatusLabel(currentArtifact.result.artifact_evidence_status)}</Badge>{!!currentArtifact.result.artifact_evidence.reason && ' · ' + currentArtifact.result.artifact_evidence.reason}</p>}
        {!!currentArtifact.result.artifact_evidence && <ul>{artifactEvidenceRows(currentArtifact.result.artifact_evidence.levels).map(row => <li key={row.level}><Badge tone={row.tone}>{row.status}</Badge> {row.label}（{row.level}）</li>)}</ul>}
        {!!currentArtifact.result.verification && <Details label="如何记录该产物的运行时验证回执" value={currentArtifact.result.verification} />}
        <p>运行验证来自独立证据记录，不因生成成功而升级；新作品、修改后的作品、旧摘要或错误目标/运行时的回执都不会让当前产物变成 PASS。</p></section>}
    </section>}
    {!view && <StatusMessage tone="info">尚未读取导出目标。读取只返回兼容性、引擎探测与证据；不会生成文件、安装引擎或运行目标。</StatusMessage>}
  </Panel>;
}
