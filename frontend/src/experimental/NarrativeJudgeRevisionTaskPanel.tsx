import { useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { ErrorMessage, Field } from './shared';
import type { WorkspaceNavigation } from './uxClient';
import type { RoomTask } from './writerRoomClient';
import { useReviewAction, type JudgeFinding, type JudgeRevisionCatalog, type StyleReviewClient } from './styleReviewClient';

type Props = { api: StyleReviewClient; finding: JudgeFinding; disabled: boolean; onNavigate?: (target: WorkspaceNavigation) => void };
export function NarrativeJudgeRevisionTaskPanel({ api, finding, disabled, onNavigate }: Props) {
  const [catalog, setCatalog] = useState<JudgeRevisionCatalog>();
  const [task, setTask] = useState<RoomTask>();
  const [open, setOpen] = useState(false), [title, setTitle] = useState(`修订：${finding.code}`);
  const [description, setDescription] = useState(finding.suggestion), [assignee, setAssignee] = useState(''), [reviewer, setReviewer] = useState('');
  const action = useReviewAction(), epoch = useRef(0);
  const load = () => action.run(async current => {
    const ticket = ++epoch.current; const result = await api.revisionTaskCatalog(finding.id);
    if (!current() || ticket !== epoch.current) return;
    if (result.finding_id !== finding.id || result.finding_version !== finding.version) throw new Error('审稿线索版本已变化，请刷新后重试。');
    setCatalog(result); setTask(result.existing_task || undefined); setOpen(true);
  });
  const create = () => action.run(async current => {
    const ticket = ++epoch.current;
    const result = await api.createRevisionTask(finding.id, finding.version, { title: title.trim(), description: description.trim(), assignee, reviewer });
    if (current() && ticket === epoch.current) setTask(result.task);
  }, '修订任务已持久化到现有协作室。正文和审稿决定没有改变。');
  const ready = catalog && catalog.finding_version === finding.version;
  return <section aria-label={`修订任务 ${finding.id}`}>
    {!open && <Button disabled={disabled || action.busy || finding.stale} onClick={() => void load()}>准备修订任务</Button>}
    {open && <>
      <Badge>现有协作室任务 · 不调用模型</Badge>
      {task ? <><p>已保存任务：{task.title} · v{task.version} · {task.status}</p><p>任务 ID：{task.id}。重新加载后仍会打开这个任务，不创建副本。</p>{onNavigate && <Button disabled={disabled || action.busy} onClick={() => onNavigate({ kind: 'feature', id: 'writer_room_v2', feature: 'writer_room_v2' })}>打开协作室处理修订</Button>}</> : <>
        <Field label={`修订任务标题 ${finding.id}`}><input maxLength={200} disabled={disabled || action.busy} value={title} onChange={e => setTitle(e.target.value)} /></Field>
        <Field label={`修订任务说明 ${finding.id}`}><textarea maxLength={8000} disabled={disabled || action.busy} value={description} onChange={e => setDescription(e.target.value)} /></Field>
        <Field label={`修订负责人 ${finding.id}`}><select disabled={disabled || action.busy} value={assignee} onChange={e => setAssignee(e.target.value)}><option value="">明确选择负责人</option>{catalog?.members.filter(member => member.can_write).map(member => <option key={member.id} value={member.id}>{member.name}</option>)}</select></Field>
        <Field label={`修订审核人 ${finding.id}`}><select disabled={disabled || action.busy} value={reviewer} onChange={e => setReviewer(e.target.value)}><option value="">明确选择审核人</option>{catalog?.members.filter(member => member.can_review).map(member => <option key={member.id} value={member.id}>{member.name}</option>)}</select></Field>
        <p>任务绑定当前审稿线索 v{finding.version}。后续来源或决定变化时，协作室将提示重新核对；任务不代表正文已修改。</p>
        <Button disabled={disabled || action.busy || !ready || !title.trim() || !description.trim() || !assignee || !reviewer} onClick={() => void create()}>明确创建修订任务</Button>
      </>}
      <Button onClick={() => { epoch.current++; setOpen(false); }}>关闭修订任务准备</Button>
    </>}
    {!!action.error && <><ErrorMessage error={action.error} /><StatusMessage tone="warning">输入保留。请核对协作室开关、权限与审稿来源，重新准备可核对是否已经保存；不会自动重发任务。</StatusMessage></>}
    {action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
  </section>;
}
