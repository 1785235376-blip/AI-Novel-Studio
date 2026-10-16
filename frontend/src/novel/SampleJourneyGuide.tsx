import { useEffect, useMemo, useState } from 'react';
import type { Chapter, CollaborationContext } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { firstUseClient, type FirstUseReceipt } from './firstUseClient';
import './firstUse.css';

type Props = { novelId: string; context: CollaborationContext; chapter?: Chapter; saved: boolean; onNavigate?: (feature: 'editor' | 'exports') => void };
/** Mount only when workspace_tools_v2 is enabled. Observes original receipts,
 * never saves, reloads an editor, alters a draft, or marks an export completed. */
export function SampleJourneyGuide(props: Props) {
  return <Journey key={JSON.stringify([props.novelId, props.context.sessionToken, props.context.scope])} {...props} />;
}
function Journey({ novelId, context, chapter, saved, onNavigate }: Props) {
  const client = useMemo(() => firstUseClient(context), [context.sessionToken, context.scope?.workspaceId]);
  const [item, setItem] = useState<FirstUseReceipt | null>(null), [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    void client.read(abort.signal).then(result => { if (!abort.signal.aborted && result.item?.project_id === novelId && result.item.can_open) setItem(result.item); }).catch(() => {});
    return () => abort.abort();
  }, [client, novelId]);
  if (!item) return null;
  if (collapsed) return <Button variant="ghost" onClick={() => setCollapsed(false)}>重新打开独立练习指引</Button>;
  const changedAndSaved = !!chapter && chapter.id === item.chapter_id && saved && !!item.seed_version && chapter.version > item.seed_version;
  return <Panel title="独立练习 · 写作到导出" className="first-use first-use--journey" actions={<Button variant="ghost" onClick={() => setCollapsed(true)}>收起练习指引</Button>}>
    <ol>
      <li>新建：已建立单独的原创合成项目。</li>
      <li>写作：在正文编辑器中添加一句自己的续文。</li>
      <li>保存：使用编辑器“保存”，等到“已保存”。{changedAndSaved ? ` 当前已保存自己的版本 v${chapter!.version}。` : ' 目前尚未核实练习之后的新保存版本。'}</li>
      <li>重开：确认已保存后，重新打开应用或刷新页面，确认当前小说是“灯塔来信 · 独立练习”，再核对刚写的句子。</li>
      <li>导出：打开导出中心，选择“TXT 小说”，等待任务完成后下载，核对文件内的句子。</li>
    </ol>
    {!saved && <StatusMessage tone="warning">当前正文尚未确认保存。先处理保存或冲突，再重开与导出；指引不会替换当前草稿。</StatusMessage>}
    <div className="first-use__actions">{onNavigate && <><Button onClick={() => onNavigate('editor')}>返回正文</Button><Button disabled={!saved} onClick={() => onNavigate('exports')}>打开练习导出中心</Button></>}</div>
  </Panel>;
}
