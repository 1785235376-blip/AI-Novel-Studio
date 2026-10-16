import { Component, lazy, Suspense, useMemo, useState, type ComponentProps, type ReactNode } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalWorkbench } from './ExperimentalWorkbench';

type Props = ComponentProps<typeof ExperimentalWorkbench>;
class ToolLoadBoundary extends Component<{ children: ReactNode; retry: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <section aria-label="实验工具加载失败"><StatusMessage tone="error">工具暂时无法加载。编辑器和未保存输入仍保留，请先保存或导出草稿。重试只重新加载界面，不会重新提交任务。</StatusMessage><Button onClick={this.props.retry}>重试加载工具</Button></section>;
    return this.props.children;
  }
}

/** Optional tools are loaded only when their actual workbench is opened. */
export function DeferredExperimentalWorkbench(props: Props) {
  if (!Object.values(props.flags?.features || {}).some(value => value === true)) return <EmptyState title="Experimental 未启用" detail="这些功能默认关闭，V1.0 验收模式保持关闭。" />;
  return <LoadedWorkbench {...props} />;
}
function LoadedWorkbench(props: Props) {
  const [attempt, setAttempt] = useState(0);
  const Workbench = useMemo(() => lazy(() => import('./ExperimentalWorkbench').then(module => ({ default: module.ExperimentalWorkbench }))), [attempt]);
  return <ToolLoadBoundary key={attempt} retry={() => setAttempt(value => value + 1)}>
    <Suspense fallback={<StatusMessage>正在加载实验工具；正文编辑仍可使用…</StatusMessage>}><Workbench {...props} /></Suspense>
  </ToolLoadBoundary>;
}
