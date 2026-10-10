import { Component, lazy, Suspense, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';
import { MessageCircleQuestion } from 'lucide-react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { localTutorIdentity, type LocalTutorProps } from './identity';
import './entry.css';
export type { EditorSelection, LocalTutorProps } from './identity';
type View = 'ask' | 'settings' | 'diagnostics';
class TutorLoadBoundary extends Component<{ children: ReactNode; retry: () => void; close: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <section aria-label="Tutor 加载失败"><StatusMessage tone="error">Tutor 界面暂时无法加载，Studio 和当前草稿仍可继续使用。重试不会自动连接或共享资料。</StatusMessage><Button onClick={this.props.retry}>重试加载 Tutor</Button><Button onClick={this.props.close}>关闭加载提示</Button></section>;
    return this.props.children;
  }
}
function DeferredLocalTutorDialog(props: LocalTutorProps & { initialView: View; onClose: () => void }) {
  const [attempt, setAttempt] = useState(0);
  const Dialog = useMemo(() => lazy(() => import('./LocalTutorIntegration').then(module => ({ default: module.LocalTutorDialog }))), [attempt]);
  return <TutorLoadBoundary key={attempt} retry={() => setAttempt(value => value + 1)} close={props.onClose}><Suspense fallback={<StatusMessage>正在加载本机 Tutor…<Button onClick={props.onClose}>取消加载 Tutor</Button></StatusMessage>}><Dialog {...props} /></Suspense></TutorLoadBoundary>;
}

/** One consumer of the existing shell slots, no parallel shell or startup discovery. */
export function useLocalTutorIntegration(props: LocalTutorProps) {
  const [opened, setOpened] = useState<{ identity: string; view: View }>();
  const identity = localTutorIdentity(props);
  useLayoutEffect(() => { setOpened(undefined); }, [identity]);
  const show = (view: View) => setOpened({ identity, view });
  return {
    entry: <Button variant="ghost" className="local-tutor-entry" onClick={() => show('ask')}><MessageCircleQuestion aria-hidden="true" />问助手</Button>,
    settings: <Panel title="AI Tutor Integration"><p>本机优先 · 默认关闭 · 正文逐次确认共享</p><Button onClick={() => show('settings')}>本机 Tutor 集成设置</Button></Panel>,
    dialog: opened?.identity === identity ? <DeferredLocalTutorDialog key={identity} {...props} initialView={opened.view} onClose={() => setOpened(undefined)} /> : null,
  };
}
