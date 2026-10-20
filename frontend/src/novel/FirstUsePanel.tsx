import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError, type WorkspaceNavigationPath } from '../api';
import { enabled, experimentalFeatures, type ExperimentalFlags } from '../experimental/api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { firstUseClient, type FirstUseReceipt } from './firstUseClient';
import './firstUse.css';

type Props = {
  sessionToken: string; workspaceId?: string;
  onOpenLocal?: (id: string) => void; onOpenScoped?: (path: WorkspaceNavigationPath) => void;
  onChooseWriting?: () => void; onChooseImport?: () => void;
};

export function FirstUsePanel(props: Props) {
  return <FirstUseBody key={JSON.stringify([props.sessionToken, props.workspaceId])} {...props} />;
}
function FirstUseBody({ sessionToken, workspaceId, onOpenLocal, onOpenScoped, onChooseWriting, onChooseImport }: Props) {
  const client = useMemo(() => firstUseClient({ sessionToken }, workspaceId), [sessionToken, workspaceId]);
  const [flags, setFlags] = useState<ExperimentalFlags>();
  const [receipt, setReceipt] = useState<FirstUseReceipt | null>(null);
  const [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const alive = useRef(true), working = useRef(false);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const abort = new AbortController();
    void experimentalFeatures(abort.signal, { sessionToken }).then(async value => {
      if (!alive.current || abort.signal.aborted) return;
      setFlags(value);
      if (!enabled(value, 'workspace_tools_v2')) return;
      const result = await client.read(abort.signal);
      if (alive.current && !abort.signal.aborted) { setReceipt(result.item); setLoaded(true); }
    }).catch(() => { if (alive.current && !abort.signal.aborted) setError('无法读取使用指引状态。手工新建与导入仍可使用。'); });
    return () => abort.abort();
  }, [client, sessionToken]);
  async function run(kind: 'read' | 'start' | 'recover' | 'open') {
    if (working.current) return;
    working.current = true; setBusy(true); setError('');
    try {
      const result = await (kind === 'start' ? client.start() : kind === 'recover' ? client.recover() : client.read());
      if (!alive.current) return;
      setReceipt(result.item); setLoaded(true);
      if (kind === 'open' && result.item?.can_open) {
        if (result.item.path) onOpenScoped?.(result.item.path);
        else if (!workspaceId && result.item.project_id) onOpenLocal?.(result.item.project_id);
      }
    } catch (reason) {
      if (alive.current) {
        setLoaded(false); // Uncertain POST never offers a blind retry.
        setError(reason instanceof ApiError ? reason.message : '请求结果未知。已创建的内容会保留，请先核对状态。');
      }
    } finally { working.current = false; if (alive.current) setBusy(false); }
  }
  if (!enabled(flags, 'workspace_tools_v2')) return null;
  if (collapsed) return <Button variant="ghost" onClick={() => setCollapsed(false)}>重新打开首次使用指引</Button>;
  const canOpen = workspaceId ? !!onOpenScoped : !!onOpenLocal;
  return <Panel title="从一个真实任务开始" className="first-use" actions={<Button variant="ghost" onClick={() => setCollapsed(true)}>跳过指引</Button>}>
    <p>未配置模型也能写作。练习只建立新的原创合成作品，不会更改现有作品、开启功能或调用模型。</p>
    <div className="first-use__scenarios" aria-label="首次使用场景">
      <section><h3>纯写作</h3><p>新建小说，写下第一章。保存与导出不需要模型或 Key。</p>{onChooseWriting && <Button onClick={onChooseWriting}>填写新小说名称</Button>}</section>
      <section><h3>导入长篇</h3><p>选择自己的文件，先检查章节预览，再明确确认导入。AI 资料审查需要另外配置。</p>{onChooseImport && <Button onClick={onChooseImport}>选择导入文件</Button>}</section>
      <details><summary>做剧本与分镜</summary><p>打开作品后，从既有“剧本与镜头”入口准备剧本。图片生成需有可用适配器；没有适配器时不会生成分镜图片。</p></details>
      <details><summary>有声书</summary><p>{enabled(flags, 'audiobook_v2') ? '有声书入口已启用。打开作品后选择已有工具；合成需要已配置且支持任务的声音适配器。' : '有声书实验功能未启用，当前不能从此指引创建音频。'}不会自动启动合成或启用开关。</p></details>
      <details><summary>本地模型</summary><p>打开作品后，可在既有模型诊断入口查看配置。尚未安装或启动模型不影响手工写作；指引不会安装软件、下载模型或启动运行时。</p></details>
    </div>
    <section className="first-use__sample" aria-label="独立合成练习">
      <h3>用独立练习走完一次写作</h3>
      <p>新建 → 写一句自己的续文 → 保存 → 重开并核对 → 导出 TXT。练习名为“灯塔来信 · 独立练习”，内容完全原创合成。</p>
      {!loaded && !error && <p role="status">正在核对练习记录…</p>}
      {loaded && !receipt && <Button variant="primary" disabled={busy || !canOpen} onClick={() => void run('start')}>创建独立练习（不需要 Key）</Button>}
      {receipt && <>
        <StatusMessage tone={receipt.stage === 'READY' ? 'success' : 'warning'}>{receiptMessage(receipt)}</StatusMessage>
        <div className="first-use__actions">
          {receipt.can_open && <Button variant="primary" disabled={busy || !canOpen} onClick={() => void run('open')}>{receipt.stage === 'READY' ? '打开独立练习' : '打开已保留的练习项目'}</Button>}
          {receipt.can_recover && <Button disabled={busy} onClick={() => void run('recover')}>继续已确认的练习步骤</Button>}
          <Button disabled={busy} onClick={() => void run('read')}>核对练习状态</Button>
        </div>
      </>}
      {!canOpen && <p>当前入口尚未接入作品跳转，请使用上方手工新建。</p>}
      {error && <><StatusMessage tone="error">{error}</StatusMessage>{!receipt && <Button disabled={busy} onClick={() => void run('read')}>核对练习状态</Button>}</>}
      {busy && <p role="status">正在处理，请保留此页面；收起指引不会取消已发送的请求。</p>}
    </section>
  </Panel>;
}

export function receiptMessage(item: FirstUseReceipt) {
  if (item.availability === 'UNAVAILABLE') return '原练习项目已删除或当前不可访问。不会自动重建；请检查作品列表与当前权限。';
  if (item.stage === 'READY') return '独立练习已保存。现在可以打开，写下你自己的续文。';
  if (item.stage === 'SOURCE_CHANGED') return '练习正文已被修改，已停止填入合成文本以保护你的版本。可以打开现有内容继续写作。';
  if (item.stage === 'CREATING_PROJECT') return '项目创建结果尚未确认。不会重复创建，请核对状态与作品列表中的“灯塔来信 · 独立练习”；不要因超时再次新建。';
  if (item.stage === 'CREATING_CHAPTER') return '练习项目已保留，章节创建结果未知。不会重复创建章节；请打开该项目检查并手工继续。';
  return '练习在中途停止，已确认的项目和章节会保留。可明确继续剩余步骤，也可打开项目手工写作。';
}
