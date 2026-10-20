import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { useAction } from './shared';
import { diagnosticGuidance } from './diagnosticGuidance';
import { type workspaceClient, type DiagnosticOptions, type DiagnosticResult } from './uxClient';

export function WorkspaceDiagnostics({ api }: { api: ReturnType<typeof workspaceClient> }) {
  const alive = useRef(true);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [options, setOptions] = useState<DiagnosticOptions>({ include_environment: true, include_task_states: true, include_error_codes: true });
  const [preview, setPreview] = useState<DiagnosticResult>();
  const action = useAction();
  const select = (key: keyof DiagnosticOptions, checked: boolean) => { setOptions(value => ({ ...value, [key]: checked })); setPreview(undefined); };
  const recheck = () => action.run(async () => {
    // A failed refresh must not leave the older snapshot eligible for export.
    setPreview(undefined);
    const result = await api.preview(options);
    if (alive.current) setPreview(result);
  }, '诊断预览已生成，请检查后导出');
  const download = () => action.run(async () => {
    if (!preview) return;
    let data: DiagnosticResult;
    try {
      data = await api.export(options, preview.preview_digest);
    } catch (error) {
      if (alive.current) setPreview(undefined);
      if (error instanceof ApiError && error.status === 409) {
        throw new ApiError({ ...error.problem, message: '诊断状态已变化，请重新生成预览，再核对导出内容。' });
      }
      throw error;
    }
    if (!alive.current) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = 'workspace-diagnostics.json';
      link.click();
    } finally { URL.revokeObjectURL(url); }
  }, '已请求下载诊断包，未上传');
  return <Panel title="隐私友好诊断包">
    <p>只收集允许的组件信息、任务阶段和已登记错误码。不读取正文、原始提示词、运行日志、路径、密钥、Cookie 或设备标识。不会自动上传。</p>
    {([['include_environment', '组件与存储类型'], ['include_task_states', '任务阶段（不含标题与 ID）'], ['include_error_codes', '安全错误码']] as const).map(([key, label]) => <label className="experimental-check" key={key}><input type="checkbox" checked={options[key]} disabled={action.busy} onChange={e => select(key, e.target.checked)} />{label}</label>)}
    <div className="experimental-actions">
      <Button disabled={action.busy} onClick={recheck}>{preview ? '重新核对诊断预览' : '生成诊断预览'}</Button>
      <Button disabled={!preview || action.busy} onClick={download}>导出已选诊断项</Button>
    </div>
    {preview && <section className="experimental-record" aria-label="诊断预览"><h3>将包含的诊断信息</h3>{preview.sections.environment && <p>组件：{preview.sections.environment.component}；存储：{preview.sections.environment.storage}；范围：{preview.sections.environment.scope_mode}</p>}{preview.sections.task_states && <><h3>任务阶段</h3>{preview.sections.task_states.length ? <ul>{preview.sections.task_states.map((task, index) => <li key={index}>{task.authority} · {task.status} · 费用未知</li>)}</ul> : <p>没有可提供的任务记录。</p>}</>}{preview.sections.error_codes && <p>错误码：{preview.sections.error_codes.join('、') || '没有已报告的错误码'}</p>}{preview.sections.coverage?.truncated && <StatusMessage tone="warning">本次诊断达到读取上限，不是全部任务。更早的记录请在原任务工具核对。</StatusMessage>}
      <p>诊断仅反映原服务本次返回的有界信息；没有错误码不表示全部任务正常，也不证明模型可用。</p>
      {!!preview.sections.error_codes?.length && <section aria-label="错误解释与下一步"><h3>错误解释与下一步</h3><p>以下是确定性操作建议，不是已确认的根因，也不会执行重试。</p><ul>{preview.sections.error_codes.map((code, index) => <li key={index}><strong>{code}</strong>：{diagnosticGuidance(code)}</li>)}</ul></section>}
      <p>原始日志：不包含。上传：否。需要分享时，请先自行核对下载文件及接收方。</p></section>}
    <p>重新核对会撤销旧预览的导出资格；读取失败或导出状态冲突后，请重新生成预览。不会重试原任务。</p>
    {action.feedback}
  </Panel>;
}
