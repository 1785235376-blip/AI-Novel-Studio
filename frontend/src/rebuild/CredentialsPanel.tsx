// [HERMIA-FE-20261022 REBUILD-2] 密钥与模型能力：/credentials/{provider} + /model-center/health。
// 极简「能力状态 + 填密钥」。密钥只写不回显；未配置/退化/不可达都如实标注。
import { useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { StateTag, WithQuery } from './primitives';
import './rebuild.css';
import { rb, rbError, CREDENTIAL_PROVIDERS, type CredentialStatus } from './rebuildApi';

const NAMES: Record<string, string> = { openai: 'OpenAI', claude: 'Claude', gemini: 'Gemini', deepseek: 'DeepSeek', 'aliyun-bailian': '阿里云百炼', siliconflow: '硅基流动', kling: '可灵', runway: 'Runway', minimax: 'MiniMax', seedance: 'Seedance' };

function ProviderRow({ provider, status, error }: { provider: string; status?: CredentialStatus; error?: unknown }) {
  const qc = useQueryClient();
  const [key, setKey] = useState('');
  const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'warn'; text: string } | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['rb', 'cred', provider] });
  const save = useMutation({ mutationFn: () => rb.setCredential(provider, key.trim()), onSuccess: () => { setKey(''); setNote({ tone: 'ok', text: '已保存' }); refresh(); }, onError: e => setNote({ tone: 'err', text: `保存失败：${rbError(e)}` }) });
  const clear = useMutation({ mutationFn: () => rb.deleteCredential(provider), onSuccess: () => { setNote(null); refresh(); }, onError: e => setNote({ tone: 'err', text: `清除失败：${rbError(e)}` }) });
  const test = useMutation({ mutationFn: () => rb.testCredential(provider), onSuccess: r => setNote(r.reachable ? { tone: 'ok', text: '连通' } : { tone: 'warn', text: r.configured ? '已配置但不可达' : '未配置，无法测试' }), onError: e => setNote({ tone: 'err', text: `测试失败：${rbError(e)}` }) });
  const tag = error ? <StateTag tone="err">{rbError(error)}</StateTag>
    : !status ? <StateTag tone="muted">读取中</StateTag>
    : status.configured ? <StateTag tone={status.degraded ? 'warn' : 'ok'}>{status.degraded ? '已配置·未持久' : '已配置'}</StateTag>
    : <StateTag tone="muted">未配置</StateTag>;
  return <li className="rb-row" data-provider={provider} style={{ flexWrap: 'wrap' }}>
    <span className="rb-row__main" style={{ flex: '0 0 96px' }}>{NAMES[provider] || provider}</span>
    {tag}
    <input className="rb-input" style={{ flex: 1 }} type="password" autoComplete="off" aria-label={`${NAMES[provider] || provider} 密钥`} placeholder={status?.configured ? '已保存（不回显），可覆盖' : '粘贴密钥'} value={key} onChange={e => setKey(e.target.value)} />
    <button type="button" className="rb-btn rb-btn--primary" disabled={!key.trim() || save.isPending} onClick={() => save.mutate()}>保存</button>
    <button type="button" className="rb-btn" disabled={test.isPending} onClick={() => test.mutate()}>测试</button>
    {status?.configured ? <button type="button" className="rb-btn" disabled={clear.isPending} onClick={() => clear.mutate()}>清除</button> : null}
    {note ? <StateTag tone={note.tone}>{note.text}</StateTag> : null}
  </li>;
}

export function CredentialsPanel() { return <WithQuery><CredentialsPanelInner /></WithQuery>; }
function CredentialsPanelInner() {
  const health = useQuery({ queryKey: ['rb', 'model-health'], queryFn: rb.modelHealth, retry: false });
  const creds = useQueries({ queries: CREDENTIAL_PROVIDERS.map(p => ({ queryKey: ['rb', 'cred', p], queryFn: () => rb.credential(p), retry: false })) });
  const anyDegraded = creds.find(c => c.data?.degraded)?.data;
  const h = health.data;
  return <section className="rb-panel" data-rebuild="credentials" aria-label="密钥与模型能力">
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <h2 className="rb-h">能力状态</h2>
      {health.isError ? <StateTag tone="err">模型中心：{rbError(health.error)}</StateTag>
        : !h ? <StateTag tone="muted">读取中</StateTag>
        : <><StateTag tone={h.status === 'READY' ? 'ok' : 'warn'}>模型中心 {h.status === 'READY' ? '就绪' : h.status}</StateTag>
            <StateTag tone="muted">可用模型 {h.ready_models}/{h.models}</StateTag><StateTag tone="muted">运行时 {h.runtimes}</StateTag>
            {h.mutation_authorization && !h.mutation_authorization.can_mutate ? <StateTag tone="warn">修改模型需登录会话</StateTag> : null}</>}
    </div>
    {anyDegraded ? <p className="rb-note" data-tone="err">系统密钥库不可用（{anyDegraded.degraded_reason || 'degraded'}）：密钥只存在内存，重启后丢失。</p> : null}
    <h2 className="rb-h">密钥</h2>
    <ul className="rb-list">{CREDENTIAL_PROVIDERS.map((p, i) => <ProviderRow key={p} provider={p} status={creds[i].data} error={creds[i].error} />)}</ul>
  </section>;
}
