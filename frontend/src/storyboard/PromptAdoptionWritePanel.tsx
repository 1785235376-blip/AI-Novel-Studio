import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import type { CreativeDocument } from '../creative/types';
import { createPromptClient } from '../prompt/promptClient';
import type { PromptEntry, PromptRevisionBody } from '../prompt/promptTypes';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { createPromptAdoptionWriteClient, type PromptAdoptionCapability,
  type PromptAdoptionCommit, type PromptAdoptionRequest, type PromptAdoptionTarget } from './promptAdoptionWriteClient';
import './promptAdoptionWrite.css';

type Source = { detail: PromptEntry; body: PromptRevisionBody };
type Pending = { target: PromptAdoptionTarget; request: PromptAdoptionRequest; source: Source;
  commit?: PromptAdoptionCommit };
type Props = {
  projectId: string; identity: string; target: PromptAdoptionTarget | null;
  transport: StudioGraphTransport; enabled: boolean; writable: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  readDocument: (id: string) => Promise<CreativeDocument>;
  onCommitted: (document: CreativeDocument, expectedTargetVersion: number) => Promise<void>;
  onUnavailable?: () => void;
};

const sameTarget = (a: PromptAdoptionTarget | null, b: PromptAdoptionTarget) =>
  a?.documentId === b.documentId && a.shotId === b.shotId && a.version === b.version && a.digest === b.digest;
function sourceValid({ detail, body }: Source): boolean {
  return detail.headAssetId === body.assetId && detail.familyId === body.familyId
    && detail.revision === body.revision && detail.assetVersion === body.assetVersion
    && !detail.redacted && detail.historyComplete && detail.readComplete
    && detail.versions.some(row => row.assetId === body.assetId && row.revision === body.revision
      && row.available && !row.redacted)
    && body.state === 'COMPLETE' && body.available && body.verified && body.readComplete
    && !body.truncated && body.decodable && typeof body.value === 'string'
    && body.digestOf === 'ORIGINAL_BYTES' && typeof body.digest === 'string'
    && /^[0-9a-f]{64}$/.test(body.digest) && detail.body.digest === body.digest;
}

/** Separate from the frozen read-only provenance panel. Nothing is read until explicitly asked. */
export function PromptAdoptionWritePanel(props: Props) {
  const binding = [props.identity, props.projectId, props.target?.documentId ?? '',
    props.target?.shotId ?? '', props.target?.version ?? '', props.target?.digest ?? '',
    props.enabled ? '1' : '0', props.writable ? '1' : '0'].join('\u0000');
  return <AdoptionWriteSession key={binding} {...props} />;
}

function AdoptionWriteSession(props: Props) {
  const client = useMemo(() => createPromptAdoptionWriteClient(props.projectId, props.transport),
    [props.projectId, props.transport]);
  const prompts = useMemo(() => createPromptClient(props.projectId, props.transport),
    [props.projectId, props.transport]);
  const [capability, setCapability] = useState<PromptAdoptionCapability | null>(null);
  const [families, setFamilies] = useState<PromptEntry[]>([]);
  const [familyId, setFamilyId] = useState('');
  const [source, setSource] = useState<Source | null>(null);
  const [consent, setConsent] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [loading, setLoading] = useState(false);
  const [denied, setDenied] = useState(false);
  const [notice, setNotice] = useState('');
  const [problem, setProblem] = useState('');
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), running = useRef(false), epoch = useRef(0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const current = () => alive.current && latest.current.enabled && latest.current.isCurrent() && !denied;
  const own = (id: number) => id === epoch.current && current();
  const begin = () => {
    if (!current() || latest.current.busy || running.current) return null;
    running.current = true; setLoading(true); setProblem(''); setNotice('');
    return ++epoch.current;
  };
  const finish = (id: number) => {
    if (id === epoch.current) { running.current = false; if (alive.current) setLoading(false); }
  };
  const failure = (error: unknown, fallback: string) => {
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      setDenied(true); setSource(null); setFamilies([]); setConsent(''); setCapability(null);
      props.onUnavailable?.();
      setProblem('会话或项目权限已变化，请重新打开工作区。采用结果需由原记录核对。');
    } else {
      const code = error instanceof ApiError ? `（${error.problem.code}）` : '';
      setProblem(`${fallback}${code}`);
    }
  };
  const readSource = async (id: string): Promise<Source> => {
    const detail = await props.read(() => prompts.readFamily(id));
    const body = await props.read(() => prompts.readRevisionBody(id, detail.headAssetId));
    const found = { detail, body };
    if (detail.familyId !== id || !sourceValid(found)) throw new Error('source unavailable');
    return found;
  };

  const inspect = async () => {
    const target = props.target, id = begin();
    if (id === null) return;
    if (!target) { finish(id); return; }
    setCapability(null); setFamilies([]); setSource(null); setConsent(''); setFamilyId('');
    try {
      const found = await props.read(() => client.read(target.documentId));
      if (!own(id) || !sameTarget(latest.current.target, target)) return;
      if (found.version !== target.version || found.digest !== target.digest) {
        setProblem('分镜版本已变化，请先重新读取已保存分镜，再核对采用条件。'); return;
      }
      setCapability(found);
      if (!found.writeEnabled || !props.writable) return;
      const library = await props.read(() => prompts.readLibrary());
      if (!own(id)) return;
      setFamilies(library.entries);
      if (!library.readComplete) setNotice('列表未完整读取；只能核对当前可读家族，不能据此判断全部来源。');
    } catch (error) { if (own(id)) failure(error, '无法核对 Prompt 采用条件，请重新读取。'); }
    finally { finish(id); }
  };
  const inspectSource = async () => {
    if (!familyId || pending) return;
    const id = begin(); if (id === null) return;
    setSource(null); setConsent('');
    try { const found = await readSource(familyId); if (own(id)) setSource(found); }
    catch (error) { if (own(id)) failure(error, '无法核实所选修订的完整原文，请重新读取来源。'); }
    finally { finish(id); }
  };
  const approve = async () => {
    if (!props.writable || !source || pending || !sourceValid(source) || source.detail.assetVersion === null) return;
    const id = begin(); if (id === null) return;
    setConsent('');
    const held = source;
    try {
      await props.mutate(() => prompts.approveRevision(held.detail.familyId,
        held.detail.headAssetId, held.detail.assetVersion!));
      const found = await readSource(held.detail.familyId);
      if (!own(id)) return;
      if (found.body.assetId !== held.body.assetId || found.body.digest !== held.body.digest
          || !found.detail.approved || found.detail.reviewStatus !== 'APPROVED') {
        setSource(null); setProblem('审批后来源发生变化或未确认批准，请重新读取所选修订。'); return;
      }
      setSource(found); setNotice('已回读并确认所选 Prompt 修订获批。');
    } catch (error) { if (own(id)) { setSource(null); failure(error, '审批结果尚未确认，请重新读取所选修订。'); } }
    finally { finish(id); }
  };

  const verifyReadback = async (held: Pending, id: number) => {
    const projection = await props.read(() => client.read(held.target.documentId));
    if (!own(id)) return;
    const document = await props.read(() => props.readDocument(held.target.documentId));
    if (!own(id)) return;
    const proof = projection.adoptions.find(row => row.requestId === held.request.request_id);
    if (!held.commit || document.id !== held.target.documentId || document.mode !== 'STORYBOARD'
        || document.version !== held.commit.version || projection.version !== held.commit.version
        || projection.digest !== held.commit.digest || !proof
        || proof.shotId !== held.target.shotId || proof.familyId !== held.request.family_id
        || proof.assetId !== held.request.asset_id || proof.revision !== held.request.revision
        || proof.digest !== held.request.expected_digest || proof.resultVersion !== held.commit.resultVersion) {
      throw new Error('readback differs');
    }
    // A replay can refer to an older committed revision. It proves history, not current application.
    if (held.commit.version !== held.commit.resultVersion || !proof.stillApplied || !proof.sourceReadable
        || document.shots.find(shot => shot.id === held.target.shotId)?.frame_prompt !== held.source.body.value) {
      throw new Error('current application unconfirmed');
    }
    await props.onCommitted(document, held.target.version);
    if (!own(id)) return;
    setPending(null); setCapability(null); setSource(null); setConsent('');
    setNotice('已回读确认：Prompt 已采用到当前镜头，来源修订保持固定。');
  };
  const submit = async (retry?: Pending) => {
    const target = props.target;
    if (!props.writable || !retry && (!target || !source || !ready || consent !== consentKey)) return;
    const id = begin(); if (id === null) return;
    let held = retry ?? { target: { ...target! }, source: source!, request: {
      shot_id: target!.shotId, family_id: source!.detail.familyId, asset_id: source!.body.assetId,
      revision: source!.body.revision, expected_digest: source!.body.digest!,
      expected_version: target!.version, expected_digest_target: target!.digest,
      request_id: crypto.randomUUID(),
    } };
    setPending(held); setConsent('');
    try {
      if (!held.commit) {
        const committed = await props.mutate(() => client.adopt(held.target, held.request));
        if (!own(id)) return;
        held = { ...held, commit: committed }; setPending(held);
      }
      await verifyReadback(held, id);
    } catch (error) {
      if (!own(id)) return;
      if (held.commit) failure(error, '服务端已确认提交，但当前镜头与来源回读尚未完成。请重新核对采用结果。');
      else if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 408) {
        setPending(null); setSource(null); setCapability(null);
        failure(error, '采用请求被拒绝，请重新核对来源与分镜版本。');
      } else failure(error, '采用结果未知。仅可重试原请求，不能更换来源或目标版本。');
    } finally { finish(id); }
  };

  const target = props.target;
  const ready = props.writable && !!target && capability?.writeEnabled === true
    && capability.version === target.version && capability.digest === target.digest
    && !!source && sourceValid(source) && source.detail.approved && source.detail.reviewStatus === 'APPROVED';
  const consentKey = ready ? [target!.documentId, target!.shotId, target!.version, target!.digest,
    source!.body.assetId, source!.body.digest].join('|') : '';
  const locked = loading || props.busy || !current();
  return <section className="prompt-adoption-write" aria-label="Prompt 采用操作">
    <Button disabled={locked || !target || !!pending} onClick={() => void inspect()}>
      核对 Prompt 采用条件
    </Button>
    {problem && <StatusMessage tone="error">{problem}</StatusMessage>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
    {capability && !capability.writeEnabled && <StatusMessage>当前环境未开放 Prompt 采用写入。</StatusMessage>}
    {capability?.writeEnabled && !props.writable && <StatusMessage>当前工作区仅可读取，无法审批或采用 Prompt。</StatusMessage>}
    {capability?.writeEnabled && props.writable && current() && <Panel title="采用 Prompt 到当前镜头">
      <p>采用会替换当前镜头的画面提示词，并使分镜重新等待审核。</p>
      <dl><dt>目标文档</dt><dd>{target?.documentId} · v{target?.version}</dd>
        <dt>目标镜头</dt><dd>{target?.shotId}</dd><dt>目标摘要</dt><dd><code>{target?.digest}</code></dd></dl>
      <label>Prompt 来源家族
        <select value={familyId} disabled={locked || !!pending} onChange={event => {
          setFamilyId(event.target.value); setSource(null); setConsent(''); setNotice('');
        }}><option value="">选择来源家族</option>{families.map(row =>
          <option key={row.familyId} value={row.familyId}>{row.familyId} · r{row.revision} · {row.purpose}</option>)}</select>
      </label>
      <Button disabled={locked || !familyId || !!pending} onClick={() => void inspectSource()}>读取所选 Prompt 修订</Button>
      {source && <section aria-label="已核对的 Prompt 修订">
        <dl><dt>来源家族</dt><dd>{source.detail.familyId}</dd>
          <dt>来源修订</dt><dd>{source.body.assetId} · r{source.body.revision}</dd>
          <dt>来源摘要</dt><dd><code>{source.body.digest}</code></dd>
          <dt>审批状态</dt><dd>{source.detail.approved ? '已批准' : '尚未批准'}</dd></dl>
        <pre className="prompt-adoption-write__body">{source.body.value}</pre>
        {!source.detail.approved && <Button disabled={locked || source.detail.assetVersion === null || !!pending}
          onClick={() => void approve()}>批准所选 Prompt 修订</Button>}
      </section>}
      <label><input type="checkbox" checked={!!consentKey && consent === consentKey}
        disabled={locked || !ready || !!pending} onChange={event => setConsent(event.target.checked ? consentKey : '')} />
        我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。
      </label>
      <Button variant="primary" disabled={locked || !ready || consent !== consentKey || !!pending}
        onClick={() => void submit()}>采用到当前镜头</Button>
    </Panel>}
    {pending && current() && <Button disabled={locked} onClick={() => void submit(pending)}>
      {pending.commit ? '重新核对采用结果' : '重试原采用请求'}
    </Button>}
  </section>;
}
