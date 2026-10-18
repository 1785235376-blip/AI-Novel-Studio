import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { segment } from './api';
import { Field } from './shared';

type Output = { proposal_id: string; candidate_index: number };
type Props = {
  client: ExperimentalClient;
  manifestId: string;
  manifestVersion: number;
  receiptIdentity: string;
  outputs: Output[];
};
type DownloadState = { status: 'idle' | 'loading' | 'downloaded' | 'cancelled' } | { status: 'error'; message: string };
// The server permits a 25 MiB original image plus bounded JSON/text reports.
// Leave room for ZIP headers, but never hand an unexpectedly large blob to a URL.
const MAX_PASSPORT_BYTES = 28 * 1024 * 1024;
const identityText = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0 && value.length <= 240;
function validOutputs(outputs: Output[]) {
  return Array.isArray(outputs) && outputs.length <= 8
    && outputs.every(output => output && identityText(output.proposal_id) && Number.isSafeInteger(output.candidate_index) && output.candidate_index >= 0 && output.candidate_index < 8)
    && new Set(outputs.map(output => output.proposal_id)).size === outputs.length
    && new Set(outputs.map(output => output.candidate_index)).size === outputs.length;
}
function failureMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return '当前会话或权限不允许下载。请重新核对授权后明确重试。';
    if (error.status === 404) return 'Passport 功能或原始输出不可用。请刷新清单并核对原任务。';
    if (error.status === 409) return '清单、来源或批准状态已变化。请刷新清单并核对原任务后重试。';
  }
  return 'Passport 下载未完成：请核对原始输出已批准、内容可用且未超出范围后重试。不会自动重试或批准产物。';
}

function PassportDownload({ client, manifestId, manifestVersion, outputs }: Props) {
  const [selected, setSelected] = useState('');
  const [state, setState] = useState<DownloadState>({ status: 'idle' });
  const active = useRef<AbortController>();
  // Retire authority during commit, before a late promise can trigger a download.
  useLayoutEffect(() => () => { active.current?.abort(); active.current = undefined; }, []);
  const valid = identityText(manifestId) && Number.isSafeInteger(manifestVersion) && manifestVersion > 0 && validOutputs(outputs);
  const choices = valid ? outputs : [];
  const output = choices.find(item => item.proposal_id === selected);
  const cancel = () => { active.current?.abort(); active.current = undefined; };
  const download = async () => {
    if (active.current || !valid || !output) return;
    const controller = new AbortController();
    active.current = controller;
    const current = () => active.current === controller && !controller.signal.aborted;
    setState({ status: 'loading' });
    try {
      const blob = await client.blob(`/production/manifests/${segment(manifestId)}/outputs/${segment(output.proposal_id)}/passport?expected_version=${manifestVersion}`, controller.signal);
      if (!current()) return;
      if (!(blob instanceof Blob) || blob.type.split(';')[0] !== 'application/zip' || blob.size === 0 || blob.size > MAX_PASSPORT_BYTES) {
        setState({ status: 'error', message: '服务器未返回有效的有界 ZIP 下载包。请核对服务状态后重试。' });
        return;
      }
      const url = URL.createObjectURL(blob);
      try {
        if (!current()) return;
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'production-passport-unsigned.zip';
        anchor.click();
        if (current()) setState({ status: 'downloaded' });
      } finally { URL.revokeObjectURL(url); }
    } catch (error) {
      if (current()) setState({ status: 'error', message: failureMessage(error) });
    } finally {
      if (active.current === controller) active.current = undefined;
    }
  };
  return <section className="experimental-section" aria-label="未签名 Production Passport">
    <div className="experimental-actions"><h3>Production Passport 下载</h3><Badge tone="warning">未签名 · 有界导出</Badge></div>
    <StatusMessage>仅支持本清单中已批准的原始媒体图像输出；候选列表本身不表示已批准。下载时由服务端重新核对权限、版本、批准状态和内容。成片、漫画及派生产物链尚不支持。</StatusMessage>
    <p>包内报告只提供 SHA-256 字节哈希一致性与已记录来源，不是作者身份认证、C2PA 凭证或法律版权认证，也不代表完整 DIF12 验收。若输出与报告同时被替换，未签名包不能检测。</p>
    <p>此操作只下载，不会创建任务、重放、修改来源或自动批准产物。</p>
    {!valid && <StatusMessage tone="error">清单版本或输出标识不完整，下载已禁用。请刷新清单后核对。</StatusMessage>}
    {valid && !choices.length && <EmptyState title="没有可选择的原始输出" detail="请在原媒体任务中核对输出与批准状态，再刷新生产清单。" />}
    <Field label="Passport 原始输出候选"><select value={selected} disabled={!valid || !choices.length} onChange={event => { cancel(); setSelected(event.target.value); setState({ status: 'idle' }); }}>
      <option value="">选择一个原始输出</option>
      {choices.map(item => <option key={item.proposal_id} value={item.proposal_id}>候选 {item.candidate_index + 1} · {item.proposal_id}</option>)}
    </select></Field>
    <div className="experimental-actions">
      <Button type="button" disabled={!output || state.status === 'loading'} loading={state.status === 'loading'} onClick={() => { void download(); }}>{state.status === 'loading' ? '正在准备 Passport…' : state.status === 'error' ? '重试下载未签名 Passport ZIP' : state.status === 'downloaded' ? '重新下载未签名 Passport ZIP' : '下载未签名 Passport ZIP'}</Button>
      {state.status === 'loading' && <Button type="button" onClick={() => { cancel(); setState({ status: 'cancelled' }); }}>取消下载准备</Button>}
    </div>
    {state.status === 'loading' && <StatusMessage>正在读取已授权的原始输出与有界报告…</StatusMessage>}
    {state.status === 'error' && <StatusMessage tone="error">{state.message}</StatusMessage>}
    {state.status === 'cancelled' && <StatusMessage>已取消下载准备。再次下载需要明确操作。</StatusMessage>}
    {state.status === 'downloaded' && <StatusMessage tone="success">已发起未签名 Passport ZIP 下载。请以浏览器实际保存结果为准。</StatusMessage>}
  </section>;
}

export function ProductionPassportSidecar(props: Props) {
  // Monotonic lifetime keys fence even A → B → A and clients that ignore abort.
  const source = JSON.stringify([props.manifestId, props.manifestVersion, props.receiptIdentity, props.outputs]);
  const identity = useRef({ client: props.client, source, generation: 0 });
  if (identity.current.client !== props.client || identity.current.source !== source) {
    identity.current = { client: props.client, source, generation: identity.current.generation + 1 };
  }
  return <PassportDownload key={identity.current.generation} {...props} />;
}
