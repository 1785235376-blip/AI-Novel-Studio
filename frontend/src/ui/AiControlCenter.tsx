import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCw, ShieldCheck, TestTube2, Trash2, XCircle } from 'lucide-react';
import { api, ApiError, type CredentialStatus, type ReleaseReadiness } from '../api';
import { useStudio } from '../store';
import { Badge, Button, Panel } from './primitives';
import './AiControlCenter.css';

type Provider = { id: string; name: string; roles: string };
const providers: Provider[] = [
  { id: 'deepseek', name: 'DeepSeek', roles: '主控 / 文本' },
  { id: 'ddshub', name: 'DDSHub', roles: '图片（img2）' },
  { id: 'openai', name: 'OpenAI', roles: '视觉 / 配音' },
  { id: 'custom', name: '自定义 Provider', roles: '图片 / 配音 / 视频' },
];

export function AiControlCenter() {
  const [credentialStatuses, setCredentialStatuses] = useState<Record<string, CredentialStatus>>({});
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [states, setStates] = useState<Record<string, string>>({});
  const [models, setModels] = useState<any[]>([]);
  const [media, setMedia] = useState<any>(null);
  const selection = useStudio(s => s.textModel);
  const setSelection = useStudio(s => s.setTextModel);
  const [message, setMessage] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [asking, setAsking] = useState(false);
  const [preferences, setPreferences] = useState<{enabled:boolean;share_enabled:boolean;harness_enabled:boolean;items:{key:string;content:string}[]}>({enabled:true,share_enabled:false,harness_enabled:false,items:[]});
  const [preferenceDraft, setPreferenceDraft] = useState('');
  const [harness, setHarness] = useState<{configured:boolean;reachable:boolean;compatible?:boolean;version?:string}>({configured:false,reachable:false});
  const [harnessProcess, setHarnessProcess] = useState<{running:boolean;pid:number|null;last_action?:string;last_action_at?:string}>({running:false,pid:null});
  const [audit, setAudit] = useState<{at:string;novel_id:string;chapter:number;agent_id:string;scopes:string[];outcome:string}[]>([]);
  const [auditFilters, setAuditFilters] = useState({novel_id:'',agent_id:'',outcome:''});
  const [readiness, setReadiness] = useState<ReleaseReadiness | null>(null);
  const [readinessError, setReadinessError] = useState(false);
  const refresh = async () => {
    setReadinessError(false);
    const gateRequest=api.releaseReadiness().then(setReadiness).catch(()=>{setReadiness(null);setReadinessError(true)});
    const statuses = await Promise.all(providers.map(async p => [p.id, await api.credentialStatus(p.id)] as const));
    setCredentialStatuses(Object.fromEntries(statuses));
    const [text, health, prefs, harnessStatus, processStatus, accessAudit] = await Promise.all([api.textModels(), api.multimodalHealth(), api.userPreferences(), api.harnessStatus(), api.harnessProcess(), api.harnessAccessAudit(auditFilters)]);
    setModels(Array.isArray(text) ? text : (text as any).items || []); setMedia(health); setPreferences({...prefs,harness_enabled: prefs.harness_enabled ?? false}); setHarness(harnessStatus); setHarnessProcess(processStatus);
    setAudit(accessAudit.items || []);
    await gateRequest;
  };
  useEffect(() => { refresh().catch(() => {setReadinessError(true);setMessage('状态读取失败，请检查服务连接')}); }, []);
  const save = async (id: string) => { if (!keys[id]) return; const status=await api.saveCredential(id, keys[id]); setKeys(v => ({ ...v, [id]: '' })); setCredentialStatuses(v => ({ ...v, [id]: status })); setMessage(status.persistent?`${id} 凭据已持久保存`:`${id} 凭据仅保存于当前进程`); };
  const test = async (id: string) => { const result = await api.testCredential(id); setStates(v => ({ ...v, [id]: result.reachable ? '可连接' : '不可达' })); };
  const remove = async (id: string) => { const status=await api.deleteCredential(id); setCredentialStatuses(v => ({ ...v, [id]: status })); setStates(v => ({ ...v, [id]: '凭据已删除' })); };
  const ask = async () => { if (!question.trim() || !selection) return; setAsking(true); setAnswer(''); try { const result=await api.agentChat({message:question,provider_id:selection.providerId,model_id:selection.modelId}); setAnswer(result.message); } catch (error) { setAnswer(error instanceof ApiError && error.problem.code === 'TEXT_PROVIDER_NOT_CONFIGURED' ? '未配置可用文本模型，未调用 DeepSeek，不能当作主控问答完成。' : '主控模型当前不可用，请检查模型与凭据配置。'); } finally { setAsking(false); } };
  const savePreference = async () => { const content=preferenceDraft.trim(); if (!content) return; const item=await api.saveUserPreference(`preference-${Date.now()}`,content); setPreferences(v=>({...v,items:[...v.items,item]})); setPreferenceDraft(''); };
  const startHarness = async () => { try { setHarnessProcess(await api.startHarness()); } catch { setMessage('Harness 未通过授权或就绪检查'); } };
  const stopHarness = async () => { try { setHarnessProcess(await api.stopHarness()); } catch { setMessage('Harness 停止失败'); } };
  return <Panel title="AI 主控中心" actions={<Button title="刷新状态" aria-label="刷新状态" onClick={() => void refresh().catch(()=>setMessage('状态读取失败，请检查服务连接'))}><RefreshCw size={16} /></Button>} className="ai-control-center">
    <p className="novel-help">统一管理云端与本地模型的接入状态。凭据只进入运行时保险库，不写入小说、日志或 URL。</p>
    <section className={`ai-control-center__readiness ai-control-center__readiness--${readiness?.status.toLowerCase() || 'loading'}`} aria-live="polite">
      <div className="ai-control-center__readiness-head">
        {readiness?.status==='READY'?<CheckCircle2 size={18}/>:readiness?.status==='BLOCKED'?<XCircle size={18}/>:<AlertTriangle size={18}/>}
        <div><h3>发布就绪门禁</h3><span>{readinessError?'读取失败':readiness?.status==='READY'?'可以进入发布验收':readiness?.status==='BLOCKED'?'存在发布阻断项':readiness?.status==='DEGRADED'?'开发可用，尚未达到发布标准':'正在读取真实运行时状态'}</span></div>
        <Badge tone={readiness?.status==='READY'?'success':readiness?.status==='BLOCKED'?'error':'warning'}>{readinessError?'未知':readiness?.status||'读取中'}</Badge>
      </div>
      {readiness&&<div className="ai-control-center__readiness-grid">
        <div><span>凭据库</span><strong>{readiness.checks.vault.persistent?`${readiness.checks.vault.backend} · 持久化`:`${readiness.checks.vault.backend} · 仅当前进程`}</strong></div>
        <div><span>Session 边界</span><strong>{readiness.checks.session_boundary.status==='PASS'?'有效':'不完整'}</strong></div>
        <div><span>Provider</span><strong>{readiness.checks.providers.status==='PASS'?'全部就绪':'部分配置'}</strong></div>
        <div><span>插件执行</span><strong>延期 · DENY_ALL</strong></div>
      </div>}
      {readiness?.blockers.length?<div className="ai-control-center__readiness-list"><strong>阻断</strong>{readiness.blockers.map(item=><code key={item}>{item}</code>)}</div>:null}
      {readiness?.warnings.length?<div className="ai-control-center__readiness-list"><strong>警告</strong>{readiness.warnings.map(item=><code key={item}>{item}</code>)}</div>:null}
    </section>
    <div className="ai-control-center__providers">{providers.map(p => {const status=credentialStatuses[p.id];const temporary=Boolean(status?.configured&&!status.persistent);return <article className="ai-control-center__provider" key={p.id}>
      <div className="ai-control-center__head"><KeyRound size={17} /><div><h3>{p.name}</h3><span>{p.roles}</span></div><Badge tone={temporary?'warning':status?.configured?'success':'neutral'}>{temporary?'仅当前进程':status?.configured?'已持久保存':'未配置'}</Badge></div>
      <div className="ai-control-center__actions"><input type="password" value={keys[p.id] || ''} onChange={e => setKeys(v => ({ ...v, [p.id]: e.target.value }))} placeholder="输入 API Key / Token" autoComplete="off" /><Button onClick={() => save(p.id)}>保存</Button><Button onClick={() => test(p.id)} title="测试连接" aria-label={`测试 ${p.name} 连接`}><TestTube2 size={15} /></Button>{status?.configured && <Button onClick={() => remove(p.id)} title="删除凭据" aria-label={`删除 ${p.name} 凭据`}><Trash2 size={15} /></Button>}</div>
      {status?.degraded_reason&&<small role="status">系统凭据库不可用：{status.degraded_reason}。当前凭据不会跨进程保留。</small>}{states[p.id] && <small>{states[p.id]}</small>}
    </article>})}</div>
    <section className="ai-control-center__status"><h3>能力状态</h3><p><ShieldCheck size={15} /> 主控问答：<strong>只读模式</strong></p><p>DeepSeek Harness：<strong>{harnessProcess.running ? `进程运行中（PID ${harnessProcess.pid}）` : harness.reachable ? (harness.compatible === false ? '版本不兼容' : '服务已连接') : '未运行'}</strong></p><div className="ai-control-center__harness-actions"><Button onClick={startHarness} disabled={harnessProcess.running || !preferences.harness_enabled || harness.compatible === false}>启动 Harness</Button><Button onClick={stopHarness} disabled={!harnessProcess.running}>停止 Harness</Button></div>{harnessProcess.last_action && <small>最近动作：{harnessProcess.last_action === 'started' ? '启动' : '停止'}{harnessProcess.last_action_at ? ` · ${new Date(harnessProcess.last_action_at).toLocaleString()}` : ''}</small>}<p>文本模型：{models.length ? `${models.filter(m => m.available).length} 个可用` : '未读取'}</p><p>图片 / 视觉 / 配音：{media ? '已读取运行时状态' : '未读取'}</p><p>视频：配置入口已保留，具体可用性取决于 Provider 健康检查。</p></section>
    <section className="ai-control-center__audit">
      <h3>最近 Harness 读取</h3>
      <div className="ai-control-center__audit-filters">
        <input aria-label="按小说筛选" placeholder="小说 ID" value={auditFilters.novel_id} onChange={e=>setAuditFilters(v=>({...v,novel_id:e.target.value}))}/>
        <input aria-label="按 Agent 筛选" placeholder="Agent ID" value={auditFilters.agent_id} onChange={e=>setAuditFilters(v=>({...v,agent_id:e.target.value}))}/>
        <select aria-label="按结果筛选" value={auditFilters.outcome} onChange={e=>setAuditFilters(v=>({...v,outcome:e.target.value}))}><option value="">全部结果</option><option value="success">成功</option><option value="not_found">未找到</option></select>
        <Button onClick={()=>refresh()}>筛选</Button>
        <a className="button" aria-label="导出 Harness 审计 CSV" href={api.harnessAccessAuditCsv(auditFilters)} download>导出 CSV</a>
        <Button className="danger" aria-label="清空 Harness 读取记录" onClick={async()=>{if(window.confirm('确定清空全部 Harness 读取记录吗？')){await api.clearHarnessAccessAudit();await refresh();}}}>清空记录</Button>
      </div>
      {audit.length ? audit.map(item=><div className="ai-control-center__audit-item" key={`${item.at}-${item.novel_id}-${item.chapter}`}><span>{item.novel_id} · 第 {item.chapter} 章 · {item.agent_id}</span><small>{new Date(item.at).toLocaleString()} · {item.outcome} · {item.scopes.join('、')}</small></div>) : <p className="novel-help">暂无读取记录</p>}
    </section>    <section className="ai-control-center__routing"><h3>默认主控与写作模型</h3><select value={selection ? `${selection.providerId}:${selection.modelId}` : ''} onChange={e => { const [providerId, modelId] = e.target.value.split(':'); setSelection(providerId && modelId ? { providerId, modelId } : null); }}><option value="">跟随运行时默认</option>{models.map(m => <option key={`${m.provider_id}:${m.model_id}`} value={`${m.provider_id}:${m.model_id}`} disabled={!m.available}>{m.display_name} · {m.provider_id}{m.available ? '' : '（不可用）'}</option>)}</select><p className="novel-help">该选择会同步到写作与生成流程；本地模型是否可用由后端运行时报告。</p></section>
    <section className="ai-control-center__assistant"><h3>询问主控</h3><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="询问软件能力、创作流程或当前模型配置" rows={3}/><Button onClick={ask} disabled={asking||!question.trim()||!selection}>{asking?'回答中…':'发送'}</Button>{answer&&<div className="ai-control-center__answer">{answer}</div>}<p className="novel-help">当前为只读问答，不会修改小说、调用生成任务、删除数据或发布内容。</p></section>
    <section className="ai-control-center__preferences"><h3>用户习惯记忆</h3><label><input type="checkbox" checked={preferences.enabled} onChange={async e=>{const enabled=e.target.checked; await api.setUserPreferencesEnabled(enabled); setPreferences(v=>({...v,enabled}));}} />允许保存偏好</label><label><input type="checkbox" checked={preferences.share_enabled} onChange={async e=>{const share_enabled=e.target.checked; await api.setUserPreferencesShareEnabled(share_enabled); setPreferences(v=>({...v,share_enabled}));}} />允许主控读取偏好</label><div className="ai-control-center__preference-entry"><input value={preferenceDraft} onChange={e=>setPreferenceDraft(e.target.value)} placeholder="例如：章节通常控制在 3000 字左右" /><Button onClick={savePreference} disabled={!preferences.enabled||!preferenceDraft.trim()}>保存偏好</Button></div>{preferences.items.map(item=><div className="ai-control-center__preference" key={item.key}><span>{item.content}</span><Button title="删除偏好" aria-label="删除偏好" onClick={async()=>{await api.deleteUserPreference(item.key);setPreferences(v=>({...v,items:v.items.filter(x=>x.key!==item.key)}));}}><Trash2 size={15}/></Button></div>)}<p className="novel-help">默认不发送给主控；可随时关闭或删除。</p></section>
    {message && <p className="notice">{message}</p>}
  </Panel>;
}

