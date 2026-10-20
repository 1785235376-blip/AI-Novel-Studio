import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Details, ErrorMessage, Field, ResourceState } from './shared';
import { templateHistoryDiff } from './templateCopyEditing';
import type { AgentDefinition, AgentHistoryDetail, AgentHistoryItem, AgentHistoryPage, AuthoredWorkflow, declarativeAgentsClient } from './declarativeAgentsClient';

type Props = { api: ReturnType<typeof declarativeAgentsClient>; saved: AgentDefinition; editorRevision: number; dirty: boolean; disabled: boolean; onFill: (definition: AuthoredWorkflow) => void; onDiscard: () => void };

/** Read-only authoring history. Only the parent editor's existing save can write. */
export function AgentDefinitionHistory(props: Props) {
  return <HistoryBody key={`${props.saved.id}:${props.saved.version}:${props.saved.definition_digest}`} {...props} />;
}

function HistoryBody({ api, saved, editorRevision, dirty, disabled, onFill, onDiscard }: Props) {
  const [page, setPage] = useState<AgentHistoryPage>(), [detail, setDetail] = useState<AgentHistoryDetail>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(), [changed, setChanged] = useState(false);
  const alive = useRef(false), epoch = useRef(0), controller = useRef<AbortController>();
  useLayoutEffect(() => {
    alive.current = true; setPage(undefined); setDetail(undefined); setBusy(false); setError(undefined); setChanged(false);
    return () => { alive.current = false; epoch.current++; controller.current?.abort(); };
  }, [api]);
  useLayoutEffect(() => {
    epoch.current++; controller.current?.abort(); setDetail(undefined); setBusy(false);
  }, [editorRevision]);
  const matchesCurrent = (value: AgentHistoryPage | AgentHistoryDetail) => value.definition_id === saved.id
    && value.current_version === saved.version && value.current_definition_digest === saved.definition_digest;
  const begin = () => {
    controller.current?.abort(); controller.current = new AbortController();
    const ticket = ++epoch.current; setBusy(true); setError(undefined); setDetail(undefined); setChanged(false);
    return { signal: controller.current.signal, current: () => alive.current && ticket === epoch.current };
  };
  const loadPage = async (before?: number) => {
    if (disabled || busy) return;
    const request = begin(); setPage(undefined);
    try {
      const value = await api.history(saved.id, before, request.signal);
      if (!request.current()) return;
      if (!matchesCurrent(value)) { setChanged(true); return; }
      setPage(value);
    } catch (cause) { if (request.current()) setError(cause); }
    finally { if (request.current()) setBusy(false); }
  };
  const loadVersion = async (item?: AgentHistoryItem) => {
    if (disabled || busy) return;
    const request = begin();
    if (!item) { setBusy(false); return; }
    try {
      const value = await api.historyVersion(saved.id, item.version, request.signal);
      if (!request.current()) return;
      if (!matchesCurrent(value)) { setPage(undefined); setChanged(true); return; }
      if (value.version !== item.version || value.definition_digest !== item.definition_digest) throw new Error('Historical definition identity changed');
      setDetail(value);
    } catch (cause) { if (request.current()) { setPage(undefined); setError(cause); } }
    finally { if (request.current()) setBusy(false); }
  };
  const comparison = useMemo(() => detail && templateHistoryDiff(detail.definition, saved.definition), [detail, saved.definition]);
  return <section className="experimental-record" aria-label="Agent 定义历史">
    <h4>Agent 定义历史</h4>
    <p>只读取自己在当前项目与分支保存的定义。选择历史不会保存或运行；填入表单后，须明确保存为新的当前版本，并重新验证与审核。旧运行不会恢复授权。</p>
    <p>每页最多 20 个历史版本。单个历史详情上限为 128000 UTF-8 字节；过大或当前编辑器不支持的原始结构仍保存在历史中，但无法通过此编辑路径恢复，不会截断或补齐后载入。</p>
    <Button disabled={disabled || busy} onClick={() => void loadPage()}>读取最新定义历史</Button>
    <ResourceState loading={busy} empty={!!page && !page.items.length} />
    {!!error && <><ErrorMessage error={error} /><StatusMessage tone="warning">历史详情不可用；可能已失去访问权限、超出详情上限或当前结构不支持。表单草稿保持原样，请刷新后核对。</StatusMessage></>}
    {changed && <StatusMessage tone="warning">已保存定义已变化。请刷新授权目录并重新选择当前定义；未保存草稿仍保留，不会自动换用新版本。</StatusMessage>}
    {page && !error && !changed && <>
      <Field label="查看 Agent 历史版本"><select disabled={disabled || busy} value={detail?.version ?? ''} onChange={event => void loadVersion(page.items.find(item => item.version === Number(event.target.value)))}>
        <option value="">选择历史版本</option>{page.items.map(item => <option key={item.version} value={item.version}>v{item.version} · {item.title} · {item.updated_at}</option>)}
      </select></Field>
      {page.next_before_version !== null && <Button disabled={disabled || busy} onClick={() => void loadPage(page.next_before_version!)}>读取更早定义历史</Button>}
    </>}
    {detail && comparison && !error && !changed && <>
      <p>历史 v{detail.version} → 已保存 v{saved.version}：{comparison.changed ? '以下为变化片段，可能包含未改变的行。' : '定义内容相同。'}</p>
      {comparison.changed && <><Details label="历史定义变化片段" value={comparison.removed} open /><Details label="已保存定义变化片段" value={comparison.added} open /></>}
      {comparison.truncated && <StatusMessage tone="warning">比较每侧最多显示 100 行；完整历史定义见下方。此比较不是语义差异判断。</StatusMessage>}
      <Details label="完整历史声明式定义" value={detail.definition} />
      {dirty && <><StatusMessage tone="warning">表单有未保存编辑。请先保存，或明确放弃这些编辑，再填入历史定义。</StatusMessage><Button disabled={disabled || busy} onClick={onDiscard}>放弃未保存的 Agent 定义编辑</Button></>}
      <Button disabled={disabled || busy || dirty} onClick={() => onFill(JSON.parse(JSON.stringify(detail.definition)) as AuthoredWorkflow)}>将历史定义填入表单</Button>
    </>}
  </section>;
}
