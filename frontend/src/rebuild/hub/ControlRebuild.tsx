/* [HERMIA-FE-20261022 R7] AI 主控按原型 aiHubHTML 重写为单页 .ws-full（不再三页签）：
   ① 模型与提供方（/api/providers 文本 · /api/model-center/models 本机 · /api/asset-providers 图片 · /api/video-providers 视频 · /api/audio/providers 声音）
   ② 预算与任务（/api/agent-queue；不会自动扣费）③ 密钥（复用 REBUILD-2 CredentialsPanel，/credentials/*）④ 高级（旧 AiControlCenter / ModelCenter / MediaProviderSettings，默认折叠）。
   原型主按钮「试派发」按规格改为「验证连接」：重新读取各服务状态，并对已填密钥的云端服务调 /credentials/{p}/test。模拟服务、未验证服务都不给绿标。 */
import {useCallback, useEffect, useState, type ReactNode} from 'react';
import {api, call} from '../../api';
import {rb, rbError, CREDENTIAL_PROVIDERS} from '../rebuildApi';
import {CredentialsPanel} from '../CredentialsPanel';
import './hubRebuild.css';

export type HubRow = {key: string; group: '文本' | '本机模型' | '图片' | '视频' | '声音'; name: string; configured: boolean; verified: boolean | null; where: '本地' | '需本机运行' | '需密钥' | '云端'; simulated?: boolean};
const TEXT_NAMES: Record<string, string> = {ollama: 'Ollama（本地）', mock: '演示用模拟服务', openai: 'OpenAI', deepseek: 'DeepSeek', openrouter: 'OpenRouter', claude: 'Claude', gemini: 'Gemini', anthropic: 'Anthropic'};

export function hubRowsFrom(d: {text?: Record<string, any> | null; models?: any[] | null; image?: any[] | null; video?: any[] | null; audio?: any[] | null}): HubRow[] {
  const out: HubRow[] = [];
  for (const [k, v] of Object.entries(d.text || {})) {
    const sim = k === 'mock' || v?.execution_mode === 'mock_standin';
    out.push({key: `t:${k}`, group: '文本', name: TEXT_NAMES[k] || k, configured: !!v?.configured, verified: sim ? null : !!v?.available, where: v?.kind === 'local' ? '本地' : v?.configured ? '云端' : '需密钥', simulated: sim});
  }
  for (const m of d.models || []) out.push({key: `m:${m.id}`, group: '本机模型', name: m.display_name || '本机模型', configured: m.status === 'READY' || m.status === 'INSTALLED', verified: m.verified ? true : null, where: '需本机运行'});
  for (const p of d.image || []) out.push({key: `i:${p.provider_id}`, group: '图片', name: p.display_name || '图片服务', configured: !!p.configured, verified: p.reachable ? true : p.configured ? false : null, where: p.local ? '本地' : p.credential_configured ? '云端' : '需密钥'});
  for (const p of d.video || []) out.push({key: `v:${p.id}`, group: '视频', name: p.display_name || '视频服务', configured: !!(p.registered || p.available), verified: p.reachable ? true : null, where: p.local ? '本地' : p.credential_configured ? '云端' : '需密钥'});
  for (const p of d.audio || []) out.push({key: `a:${p.provider_id}`, group: '声音', name: p.display_name || '声音服务', configured: !!p.configured, verified: p.reachable === true ? true : null, where: p.local ? '本地' : p.credential_configured ? '云端' : '需密钥'});
  return out;
}

const Badge = ({tone, children}: {tone: 'ok' | 'part' | 'off' | 'local'; children: ReactNode}) => <span className={`hub-badge hub-badge--${tone}`}>{children}</span>;

export function ControlRebuild({advanced, onOpenWorkflow}: {advanced?: ReactNode; onOpenWorkflow?: () => void}) {
  const [data, setData] = useState<Parameters<typeof hubRowsFrom>[0] | null>(null);
  const [queue, setQueue] = useState<{n: number} | {err: string} | null>(null);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState('');
  const load = useCallback(async () => {
    const safe = <T,>(p: Promise<T>) => p.catch(() => null);
    const [text, models, image, video, audio] = await Promise.all([
      safe(call<Record<string, any>>('/api/providers')), safe(api.modelCenterModels()), safe(api.assetProviders()), safe(api.videoProviders()), safe(api.audioProviders())]);
    setData({text, models: models?.items ?? null, image: image?.items ?? null, video: video?.items ?? null, audio: audio?.items ?? null});
    api.agentQueue().then(q => setQueue({n: (q.items || []).filter((j: any) => !/DONE|COMPLETED|FAILED|CANCEL/i.test(String(j?.status || ''))).length})).catch(e => setQueue({err: rbError(e)}));
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function verify() {
    setChecking(true); setNote('');
    try {
      const st = await Promise.all(CREDENTIAL_PROVIDERS.map(p => rb.credential(p).catch(() => null)));
      const filled = CREDENTIAL_PROVIDERS.filter((_, i) => st[i]?.configured);
      const res = await Promise.all(filled.map(p => rb.testCredential(p).then(r => r.reachable).catch(() => false)));
      await load();
      setNote(filled.length ? `已检查 ${filled.length} 个填了密钥的服务：${res.filter(Boolean).length} 个能连上，${res.filter(x => !x).length} 个连不上。` : '没有填密钥的云端服务；本地服务状态已重新读取。');
    } finally { setChecking(false); }
  }
  const rows = data ? hubRowsFrom(data) : [];
  const groups = (['文本', '本机模型', '图片', '视频', '声音'] as const).map(g => [g, rows.filter(r => r.group === g)] as const).filter(([, r]) => r.length);
  const anyConfigured = rows.some(r => r.configured && !r.simulated);
  const anyVerified = rows.some(r => r.verified === true);

  return (
    <div className="ws-full hub-ws" data-hub="control" aria-label="AI 主控">
      <div className="ws-head"><h2>AI 主控</h2><span className="nv-spacer" />
        <button type="button" className="nv-btn nv-btn--primary" id="aiVerify" disabled={checking} onClick={() => void verify()}>{checking ? '验证中…' : '验证连接'}</button></div>
      <div className="ws-body ai-hub">
        <div className="hub-note hub-note--info">从设置或命令面板打开。不会自动花钱；没验证过的服务不能派发任务。</div>
        {note ? <div className="hub-note" role="status">{note}</div> : null}
        <section className="hub-sec" aria-label="模型与提供方"><h4>模型与提供方</h4>
          {data === null ? <p className="hub-muted">读取中…</p>
            : !anyConfigured ? <div className="hub-empty" role="status"><p>还没有接任何 AI。接一个本地模型最省事，也可以填云端密钥。</p>
              <div className="nv-row"><a className="nv-btn nv-btn--primary" href="#hub-keys">添加服务</a><button type="button" className="nv-btn" onClick={() => void load()}>检测本机模型</button></div></div>
            : !anyVerified ? <div className="hub-note hub-note--warn" role="status">这些服务还没验证，生成按钮会保持灰色。</div> : null}
          {groups.map(([g, rs]) => <div key={g} className="hub-group"><div className="hub-gh">{g}</div>
            {rs.map(r => <div key={r.key} className="model-row" data-hub-row={r.group}>
              <b>{r.name}</b>
              {r.simulated ? <Badge tone="part">模拟</Badge> : <Badge tone={r.configured && r.verified ? 'ok' : r.configured ? 'part' : 'off'}>{r.configured ? '已配置' : '未配置'}</Badge>/* [HERMIA-FE-20261022 R7-FIX] 未验证/连不上时「已配置」用中性色，不给绿 */}
              <Badge tone={r.verified ? 'ok' : 'off'}>{r.verified ? '已验证' : r.verified === false ? '连不上' : '未验证'}</Badge>
              <span className="hub-where">{r.where}</span></div>)}
          </div>)}
        </section>
        <section className="hub-sec" aria-label="预算与任务"><h4>预算与任务</h4>
          <dl className="hub-kv"><dt>本会话预算</dt><dd>本地优先 · 云端额度未授权，不会自动扣费</dd>
            <dt>排队任务</dt><dd>{queue === null ? '读取中…' : 'err' in queue ? `暂时看不到（${queue.err}）` : queue.n === 0 ? '现在没有在跑的任务。' : `${queue.n} 个`}</dd></dl>
          <div className="nv-row"><button type="button" className="nv-btn" onClick={onOpenWorkflow}>打开工作流编排</button></div>
          <div className="hub-note hub-note--warn">没验证的服务、要本机运行但没启动的服务，都会拒绝派发，不会假装成功。</div>
        </section>
        <section className="hub-sec" id="hub-keys" aria-label="密钥"><h4>密钥</h4>
          <p className="hub-muted">密钥只写不回显。保存后可以点「测试」确认能不能连上。</p>
          <CredentialsPanel /></section>
        {advanced ? <details className="hub-sec hub-adv"><summary><h4>高级 · 本机模型管理与媒体服务细节</h4></summary>{advanced}</details> : null}
      </div>
    </div>
  );
}
