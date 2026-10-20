import { useLayoutEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../../ui/primitives';
import { canonicalExecutionImpact, executionImpactSnapshot, fingerprintExecutionImpact,
  type ExecutionImpactConfirmation, type ExecutionImpactInput, type ExecutionImpactSnapshot } from './executionImpact';

export type ExecutionImpactPanelProps = {
  input: ExecutionImpactInput;
  /** Stable original-owner identity; replace it when its authority changes. */
  owner: object;
  current: boolean;
  canConfirm: boolean;
  busy?: boolean;
  isCurrent: () => boolean;
  onConfirm: (confirmation: ExecutionImpactConfirmation) => void;
};
type Fingerprint = { token: object; value: string };

/** Advisory input review only. No transport, persistence, execution or template mutation. */
export function ExecutionImpactPanel(props: ExecutionImpactPanelProps) {
  let snapshot: ExecutionImpactSnapshot | undefined, error = '';
  try { snapshot = executionImpactSnapshot(props.input); } catch (reason) { error = reason instanceof Error ? reason.message : '无法完整核对输入。'; }
  const alive = useRef(true), live = useRef(props); live.current = props;
  const values = [snapshot?.canonical ?? error, props.owner, props.current, props.canConfirm];
  const fence = useRef({ values, token: {}, retired: false });
  if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {}, retired: false };
  const generation = fence.current, token = generation.token, capturedGuard = props.isCurrent, canonical = snapshot?.canonical;
  const [fingerprint, setFingerprint] = useState<Fingerprint>(), [failure, setFailure] = useState<Fingerprint>();
  const [acknowledgement, setAcknowledgement] = useState<Fingerprint>(), [issued, setIssued] = useState<object>();
  const acknowledgementRef = useRef(acknowledgement); acknowledgementRef.current = acknowledgement;
  const fingerprintRef = useRef(fingerprint); fingerprintRef.current = fingerprint;
  const issuedRef = useRef(issued); issuedRef.current = issued;
  function current() {
    if (generation.retired) return false;
    try {
      const valid = alive.current && fence.current.token === token && live.current.current && live.current.canConfirm
        && capturedGuard() && live.current.isCurrent() && !!canonical && canonicalExecutionImpact(live.current.input) === canonical;
      // An observed mismatch retires every receipt of this generation permanently.
      if (!valid) generation.retired = true;
      return valid;
    } catch { generation.retired = true; return false; }
  }
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => {
    if (!snapshot) return;
    void fingerprintExecutionImpact(snapshot).then(value => {
      if (alive.current && fence.current.token === token) setFingerprint({ token, value });
    }, () => { if (alive.current && fence.current.token === token) setFailure({ token, value: '输入指纹核对失败，请重新读取；不能确认本次输入。' }); });
  }, [token]);
  const visible = fingerprint?.token === token ? fingerprint : undefined;
  const acknowledged = acknowledgement?.token === token && acknowledgement.value === visible?.value;
  const canAcknowledge = !!snapshot?.taskOnly && !!visible && current() && !props.busy;
  function confirm() {
    if (!canAcknowledge || !current() || live.current.busy || !visible || fingerprintRef.current !== visible
      || acknowledgementRef.current?.token !== token || acknowledgementRef.current.value !== visible.value || issuedRef.current === token) return;
    issuedRef.current = token; setIssued(token);
    props.onConfirm(Object.freeze({ contract: 'studio-execution-impact-confirmation/1', inputFingerprint: visible.value, scope: 'TASK', isCurrent: current }));
  }
  if (!props.current) return <Panel title="本次任务修改影响"><StatusMessage tone="warning">原输入范围已失效，请从原任务入口重新读取。旧确认不会复用。</StatusMessage></Panel>;
  return <Panel title="本次任务修改影响" aria-label="本次任务修改影响">
    <p><Badge>{snapshot?.taskOnly ? '仅本次任务' : '共享模板不可确认'}</Badge> 参数核对不会自动派发、采用结果或扩大批量。</p>
    <p>本组件不修改共享工作流模板。执行与费用许可、来源授权、原预览和 Job 版本检查仍由原 owner 分别确认。</p>
    <StatusMessage tone="warning">费用、运行时长和资源用量：当前合同未提供可核对估算，均为未知。</StatusMessage>
    {error ? <StatusMessage tone="error">{error}</StatusMessage> : snapshot && <>
      {!snapshot.previousCommandAvailable && <p>原任务未提供参数快照，不能判断是否发生变化；下列本次输入仅供核对。</p>}
      {!snapshot.recipeAvailable && <p>本次真实配方未提供，内部步骤未知。后续配方一旦变化，本次确认即失效。</p>}
      {!snapshot.taskOnly && <StatusMessage tone="warning">此入口不支持确认共享模板修改，请返回原模板管理入口。</StatusMessage>}
      <p>已提供快照中的变化 {snapshot.differences.filter(row => row.changed === true).length} 项；缺少对照 {snapshot.differences.filter(row => row.changed === null).length} 项。</p>
      <div style={{ maxWidth: '100%', overflowX: 'auto' }}><table style={{ width: '100%', tableLayout: 'fixed', overflowWrap: 'anywhere' }}>
        <caption>真实命令与配方的前后核对</caption><thead><tr><th scope="col">字段</th><th scope="col">原任务</th><th scope="col">本次输入</th></tr></thead>
        <tbody>{snapshot.differences.slice(0, 50).map(row => <tr key={row.path}><th scope="row"><code>{row.path}</code></th><td style={{ whiteSpace: 'pre-wrap' }}>{row.before}</td><td style={{ whiteSpace: 'pre-wrap' }}>{row.after}</td></tr>)}</tbody>
      </table></div>
      {!snapshot.differences.length && <p>已提供的命令与配方中未发现变化；这不代表执行能力、费用或可用性已经验证。</p>}
      {snapshot.differences.length > 50 && <p>当前列出前 50 项，共 {snapshot.differences.length} 项；输入指纹包含全部字段。</p>}
    </>}
    {failure?.token === token && <StatusMessage tone="error">{failure.value}</StatusMessage>}
    {snapshot && !visible && failure?.token !== token && <p role="status">正在核对完整输入指纹。</p>}
    <label><input type="checkbox" checked={!!acknowledged} disabled={!canAcknowledge || issued === token}
      onChange={event => { if (canAcknowledge && current()) { const value = event.target.checked ? visible : undefined; acknowledgementRef.current = value; setAcknowledgement(value); } }}/>
      已核对本次输入变化与影响范围</label>
    <Button disabled={!canAcknowledge || !acknowledged || issued === token} onClick={confirm}>确认本次输入核对</Button>
    {issued === token && <StatusMessage>当前输入已核对；这只是本地核对凭据，不是执行或费用许可。下一步仍使用原预览、执行与审核入口。</StatusMessage>}
  </Panel>;
}
