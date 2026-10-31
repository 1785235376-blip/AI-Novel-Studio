import { useEffect } from 'react';
import { Badge, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import {
  GUIDE_HINT_SEVERITY_TONES, GUIDE_NOTICES, GUIDE_HINT_OWNER_LABELS, GUIDE_BOUNDS,
  type GuideHint,
} from './projectGuideTypes';
import { citeSources } from './projectGuideOps';
import { readFactsEnvelope } from './projectGuideFacts';
import { useProjectGuide, type ProjectGuideController } from './useProjectGuide';
import { qingjianMentorAvailable, registerQingjianAdapter } from './qingjianExtension';
import { BlockedStateNotice } from './BlockedStateNotice';
import { HintDetail } from './HintDetail';
import { HintList } from './HintList';
import './projectGuide.css';

/** 来源标签：既显示精确到字段的引用，也显示它属于哪个原 owner。 */
export function sourceLabel(hint: GuideHint): string {
  const owner = GUIDE_HINT_OWNER_LABELS[hint.owner] ?? hint.owner;
  const codes = citeSources(hint);
  return `${owner} · ${codes.length ? codes.join('、') : '（无来源）'}`;
}

/**
 * 提示助手视图：组合列表 + 详情 + 阻塞说明。
 *
 * 它**只呈现控制器算出来的东西**：没有任何 `useEffect`、没有 fetch、没有定时器，
 * 因此挂载一个面板不可能产生网络请求。每条提示都强制显示它引用的 owner 字段。
 */
export function ProjectGuidePanelView({ controller }: { controller: ProjectGuideController }) {
  const { state, hints, refusal } = controller;
  return <Panel title="项目提示助手" className="project-guide" aria-label="项目提示助手"
    data-guide-state={state} data-guide-hints={String(hints.length)}>
    <p>提示助手只读原 owner 已经给到的项目状态：它不调用模型、不发起网络请求、不改变任何项目数据，也不代表产品验收通过。</p>
    {state === 'LOADING' && <StatusMessage>正在等待调用方读取项目事实…</StatusMessage>}
    {state === 'IDLE' && <EmptyState title="尚未打开提示视图" detail="只有这个视图可见时才推导提示；关闭时既不读取也不轮询。"/>}
    {state === 'DENIED' && <BlockedStateNotice state={state} refusal={refusal}
      title="当前会话无权读取这个项目的提示事实"
      detail="被拒绝不是「空项目」：这里没有任何项目内容可判断，重新核对身份与项目范围后再打开。"/>}
    {state === 'FAILED' && <BlockedStateNotice state={state} refusal={refusal}
      title="项目事实不可读，因此没有建议" detail={GUIDE_NOTICES.unreadable}/>}
    {state === 'EMPTY' && <EmptyState title="没有需要处理的项目条目" detail={GUIDE_NOTICES.emptyIsNotDenied}/>}
    {(state === 'READY' || state === 'EMPTY') && controller.unreadableSources.length > 0 &&
      <StatusMessage tone="warning">{GUIDE_NOTICES.partialUnreadable}不可读：{controller.unreadableSources.join('、')}</StatusMessage>}
    {hints.length > 0 && <>
      <HintList hints={hints}/>
      <HintDetail hints={hints} onNavigate={controller.navigate}/>
    </>}
    <section className="project-guide__boundary" aria-label="提示助手的边界">
      <header><h3>边界</h3>
        <Badge tone="neutral">只读</Badge>
        <Badge tone="neutral">无模型调用</Badge>
        <Badge tone="neutral">{`最多 ${GUIDE_BOUNDS.hints} 条`}</Badge>
      </header>
      <p>{GUIDE_NOTICES.everyHintCitesOwner}</p>
      <p>{GUIDE_NOTICES.capabilityBoundary}</p>
      {/* 青简扩展点：隐藏、禁用。**不渲染任何内容**、不报告任何连接状态，
          因此这里没有任何 DOM 节点，界面不可能显示"已连接青简"或导师建议。 */}
    </section>
  </Panel>;
}

/** 单条提示的徽标语气（纯呈现映射，不改变 owner 状态）。 */
export const severityTone = (hint: GuideHint) => GUIDE_HINT_SEVERITY_TONES[hint.severity];

/**
 * **冻结的挂载 props**（工作包逐字要求，不得增删字段）。
 *
 * 每一个输入都被当作不可信数据：控制器解码后才使用。`facts` 与具名投影同义
 * （见 `useProjectGuide`），`onNavigate` 只接受既有工作区视图名，
 * `onUnavailable` 用于调用方在被拒绝时撤销自己的视图。
 */
export type ProjectGuidePanelProps = {
  projectId: string;
  identity: string;
  active: boolean;
  denied: boolean;
  facts?: unknown;
  workflow?: unknown;
  tasks?: unknown;
  inbox?: unknown;
  assets?: unknown;
  graph?: unknown;
  timeline?: unknown;
  onNavigate?: (target: 'START' | 'ASSETS' | 'GRAPH' | 'PRODUCTION' | 'TASKS' | 'STORYBOARD') => void;
  onUnavailable?: () => void;
};

/**
 * 自包含挂载入口。
 *
 * 它**不做任何读取**：所有事实都由调用方通过 props 传入（调用方用既有的
 * `useProductionWorkflow` / `useTaskCenter` / `useAssetBrowser` 等控制器加载）。
 * 因此挂载这个面板不会产生任何网络请求、模型调用或定时器。
 *
 * 青简扩展点在挂载时被显式尝试注册一次，并且**永远被拒绝**：既没有适配器，
 * 也没有连接状态，也不渲染任何导师内容。
 */
export function ProjectGuidePanel(props: ProjectGuidePanelProps) {
  // `facts` 是冻结 props 里唯一的整体入口：今天它只承载分镜回执，其余事实一律
  // 走具名投影。信封形状不合法时**如实**传给控制器（`FAILED`），绝不静默忽略成
  // "没有分镜"；信封合法时把它里面的分镜回执作为具名 `storyboard` 传入。
  const envelope = (() => {
    if (props.facts === undefined || props.facts === null || typeof props.facts !== 'object') return null;
    try {
      return readFactsEnvelope(props.facts);
    } catch {
      return null;
    }
  })();
  const factsRejected = props.facts !== undefined
    && (props.facts === null || typeof props.facts !== 'object' || envelope === null);
  const controller = useProjectGuide({
    projectId: props.projectId,
    identity: props.identity,
    active: props.active,
    denied: props.denied,
    ...(factsRejected ? { facts: 'not-a-facts-envelope' } : {}),
    ...(props.workflow === undefined ? {} : { workflow: props.workflow }),
    ...(props.tasks === undefined ? {} : { tasks: props.tasks }),
    ...(props.inbox === undefined ? {} : { inbox: props.inbox }),
    ...(props.assets === undefined ? {} : { assets: props.assets }),
    ...(props.graph === undefined ? {} : { graph: props.graph }),
    ...(props.timeline === undefined ? {} : { timeline: props.timeline }),
    ...(envelope === null || envelope.storyboard === undefined ? {} : { storyboard: envelope.storyboard }),
    ...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate }),
    ...(props.onUnavailable === undefined ? {} : { onUnavailable: props.onUnavailable }),
  });

  useEffect(() => {
    // 没有注册表、没有端点：这一行永远是拒绝，且不影响任何状态。
    const registration = registerQingjianAdapter({ adapter_id: 'none', advisory_only: true });
    if (registration.registered || qingjianMentorAvailable()) return;
  }, []);

  return <ProjectGuidePanelView controller={controller}/>;
}
