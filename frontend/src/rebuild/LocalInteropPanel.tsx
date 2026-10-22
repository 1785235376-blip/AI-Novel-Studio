// [HERMIA-FE-20261022 REBUILD-5] 插件页「连接本地软件」：复用 interop/client（/local-interop/status|connect|disconnect）。
// 只允许本机回环地址（后端同样强制 http://127.0.0.1:端口）；没连上就不显示绿标。
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getCollaborationContext } from '../api';
import { useStudio } from '../store';
import { interopClient, interopErrorMessage, newInteropRequestId, type InteropSession } from '../interop/client';
import { StateTag, WithQuery } from './primitives';

const PRESETS = [{ id: 'comfyui', label: 'ComfyUI 桥接', endpoint: 'http://127.0.0.1:8188' }, { id: 'tutor', label: '本机 Tutor', endpoint: 'http://127.0.0.1:47831' }, { id: 'custom', label: '自定义', endpoint: '' }];
export const isLoopbackEndpoint = (v: string) => /^http:\/\/127\.0\.0\.1:\d{2,5}\/?$/.test(v.trim());

function Body() {
  const novelId = useStudio(s => s.novelId);
  const qc = useQueryClient();
  const client = interopClient(getCollaborationContext());
  const [preset, setPreset] = useState('comfyui');
  const [endpoint, setEndpoint] = useState(PRESETS[0].endpoint);
  const [session, setSession] = useState<InteropSession | null>(null);
  const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'warn'; text: string } | null>(null);
  const status = useQuery({ queryKey: ['rb', 'interop-status', session?.session_id || ''], queryFn: () => client.status(undefined, session?.session_id), retry: false });
  const connect = useMutation({
    mutationFn: () => client.connect({ request_id: newInteropRequestId(), endpoint: endpoint.trim().replace(/\/$/, ''), project_id: novelId, module: 'plugin', surface: 'plugin-page' }),
    onSuccess: s => { setSession(s); setNote({ tone: s.mode === 'MOCK_ONLY' ? 'warn' : 'ok', text: s.mode === 'MOCK_ONLY' ? `已连接（模拟模式）：${s.product?.name || '本地软件'}` : `已连接：${s.product?.name || '本地软件'}` }); qc.invalidateQueries({ queryKey: ['rb', 'interop-status'] }); },
    onError: e => setNote({ tone: 'err', text: `连接失败：${interopErrorMessage(e)}` }),
  });
  const disconnect = useMutation({ mutationFn: () => client.disconnect(session!.session_id), onSettled: () => { setSession(null); setNote({ tone: 'warn', text: '已断开' }); } });
  const st = status.data;
  const valid = isLoopbackEndpoint(endpoint);
  return <section className="rb-panel" data-rebuild="local-interop" aria-label="连接本地软件">
    <div className="rb-field" style={{ flexWrap: 'wrap' }}><h2 className="rb-h">连接本地软件</h2>
      {status.isError ? <StateTag tone="warn">{interopErrorMessage(status.error)}</StateTag>
        : !st ? <StateTag tone="muted">读取中</StateTag>
        : !st.feature_enabled ? <StateTag tone="muted">后端未开启本地互通</StateTag>
        : !st.enabled ? <StateTag tone="muted">互通已关闭（主控里开启）</StateTag>
        : <><StateTag tone="muted">互通可用</StateTag>{st.capabilities.length ? <StateTag tone="muted">能力 {st.capabilities.length}</StateTag> : null}</>}
      {session ? <StateTag tone={session.mode === 'MOCK_ONLY' ? 'warn' : 'ok'}>{session.mode === 'MOCK_ONLY' ? '模拟连接' : '已连接'}</StateTag> : <StateTag tone="muted">未连接</StateTag>}
    </div>
    <p className="rb-sub">只连本机（127.0.0.1）。连接后才会按你逐项确认的范围共享内容，默认不共享正文。</p>
    <div className="rb-field" style={{ flexWrap: 'wrap' }}>
      <select className="rb-select" aria-label="本地软件" value={preset} onChange={e => { const p = PRESETS.find(x => x.id === e.target.value)!; setPreset(p.id); if (p.endpoint) setEndpoint(p.endpoint); }}>{PRESETS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
      <input className="rb-input" style={{ flex: 1, minWidth: 200 }} aria-label="本机地址" value={endpoint} onChange={e => { setEndpoint(e.target.value); setPreset('custom'); }} placeholder="http://127.0.0.1:端口" />
      {session ? <button type="button" className="rb-btn" disabled={disconnect.isPending} onClick={() => disconnect.mutate()}>断开</button>
        : <button type="button" className="rb-btn rb-btn--primary" disabled={!valid || !novelId || connect.isPending} onClick={() => connect.mutate()}>{connect.isPending ? '连接中…' : '连接'}</button>}
    </div>
    {!valid ? <p className="rb-note" data-tone="err">地址必须是 http://127.0.0.1:端口</p> : null}
    {!novelId ? <p className="rb-note">先打开一部作品，连接会绑定到当前作品。</p> : null}
    {note ? <p className="rb-note" data-tone={note.tone === 'err' ? 'err' : undefined} role="status">{note.text}</p> : null}
  </section>;
}
export function LocalInteropPanel() { return <WithQuery><Body /></WithQuery>; }
