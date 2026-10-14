/**
 * UX-08 项目提示助手控制器。
 *
 * 它**只消费调用方已经加载好的 owner 数据**（props 里传进来的投影），自己
 * 不发起任何读取：没有 `fetch`、没有客户端参数、没有轮询、没有定时器。
 * 唯一的工作是解码 + 推导 + 暴露显式状态。
 *
 * 状态语义（与 `taskcenter` / `assetbrowser` 同一套）：
 * - `IDLE`：视口不可见，或调用方尚未传入任何事实。
 * - `LOADING`：调用方声明正在读这些事实（`pending`）。
 * - `READY`：至少读到一个来源，且存在可展示的提示。
 * - `EMPTY`：读成功、且**确实没有任何**需要处理的条目（不是被拒绝）。
 * - `DENIED`：调用方声明事实读取被拒绝 —— 永远不是"空项目"。
 * - `FAILED`：声明的输入形状不合法，或一个来源都读不到（含事实不可读）。
 */
import { useMemo, useRef } from 'react';
import { decodeProjectGuideInput, type GuideInput } from './projectGuideFacts';
import { nextSteps, noFabrication, unreadableFactsRefusal, staticFallback } from './projectGuideOps';
import {
  GUIDE_BOUNDS, GUIDE_CODES, GUIDE_NOTICES, GUIDE_VIEW_NAMES,
  type GuideHint, type GuideProjection, type GuideRefusal, type GuideSurfaceState, type GuideViewName,
} from './projectGuideTypes';
import { QINGJIAN_EXTENSION } from './qingjianExtension';

export type UseProjectGuideProps = {
  projectId: string;
  /** 稳定的工作区 / 分支身份；变化会重新推导全部提示（不会丢弃任何 owner 数据）。 */
  identity: string;
  /** 视图在屏幕上。关闭的视图不推导、不显示。 */
  active: boolean;
  /** 调用方声明的事实读取被拒绝（401/403）。 */
  denied: boolean;
  /** 调用方是否仍在读取这些事实（`true` 时状态是 `LOADING`）。 */
  pending?: boolean;
  /**
   * 已解码的事实包。除分镜回执外，其余事实一律由**具名投影**传入，
   * 因此这个字段今天只承载挂载方整体传进来的形状（见 `readFactsEnvelope`）。
   */
  facts?: unknown;
  workflow?: unknown;
  tasks?: unknown;
  inbox?: unknown;
  assets?: unknown;
  graph?: unknown;
  timeline?: unknown;
  storyboard?: unknown;
  onNavigate?: (target: GuideViewName) => void;
  onUnavailable?: () => void;
};

/** 控制器对外暴露的一切：状态 + 已解码事实 + 可展示提示 + 拒绝原因。 */
export type ProjectGuideController = {
  state: GuideSurfaceState;
  /** 与 `state` 一致的中文说明；`READY` 时为空串。 */
  notice: string;
  /** 解码结果；形状层失败时为 `null`。 */
  projection: GuideProjection | null;
  /** 通过 `noFabrication()` 的提示（有序、去重、有界）。 */
  hints: readonly GuideHint[];
  /** 状态需要解释时的拒绝（事实不可读 / 输入不合法 / 空项目 / 被拒绝）。 */
  refusal: GuideRefusal | null;
  /** 至少读到一个来源；只有它为真时提示才有意义。 */
  hasFacts: boolean;
  /** 逐来源可读性（缺失的来源一律是 `false`，绝不当作"没有问题"）。 */
  sourcesReadable: Readonly<Record<string, boolean>>;
  /** 不可读来源的稳定标识列表。 */
  unreadableSources: readonly string[];
  /** 引导到既有工作区视图；控制器自己不导航。 */
  navigate: (target: GuideViewName) => boolean;
  /** 青简扩展点始终不可用：暴露出来是为了让"未连接"可验证。 */
  mentor: typeof QINGJIAN_EXTENSION;
};

const noticeRefusal = (code: string, message: string, reason: string): GuideRefusal =>
  Object.freeze({ ok: false as const, code, message, reason });

const sourcesOf = (projection: GuideProjection): string[] =>
  Object.entries(projection.sources_readable).filter(([, ok]) => !ok).map(([source]) => source);

/**
 * 控制器：**不做 I/O**。输入是 props 里已有的投影，输出是显式状态与提示。
 */
export function useProjectGuide(props: UseProjectGuideProps): ProjectGuideController {
  const latest = useRef(props);
  latest.current = props;

  const derived = useMemo(() => {
    // 被声明的具名投影必须是一个对象：不是对象就是形状不合法（fail-closed），
    // 绝不静默忽略 —— 忽略一个坏输入会让状态看起来像"没问题"。
    const named: Array<[string, unknown]> = [
      ['workflow', props.workflow], ['tasks', props.tasks], ['inbox', props.inbox], ['assets', props.assets],
      ['graph', props.graph], ['timeline', props.timeline], ['storyboard', props.storyboard],
    ];
    const malformed = named.find(([, value]) => value !== undefined && (value === null || typeof value !== 'object'));
    if (malformed) {
      return {
        projection: null, shapeRejected: true,
        refusal: noticeRefusal(GUIDE_CODES.factsInvalid,
          `项目提示事实不可用：${malformed[0]} 不是一个对象。`, `输入形状不合法：${malformed[0]}`),
      };
    }
    const input: GuideInput = {
      projectId: props.projectId, identity: props.identity, documentId: props.identity,
      ...(props.workflow === undefined ? {} : { workflow: props.workflow }),
      ...(props.tasks === undefined ? {} : { tasks: props.tasks }),
      ...(props.inbox === undefined ? {} : { inbox: props.inbox }),
      ...(props.assets === undefined ? {} : { assets: props.assets }),
      ...(props.graph === undefined ? {} : { graph: props.graph }),
      ...(props.timeline === undefined ? {} : { timeline: props.timeline }),
      ...(props.storyboard === undefined ? {} : { storyboard: props.storyboard }),
    };
    // `facts` 是冻结 props 里的整体入口：它必须是一个对象，否则 fail-closed。
    // 挂载入口把它里面的分镜回执解出来，作为具名 `storyboard` 传进来。
    if (props.facts !== undefined && (props.facts === null || typeof props.facts !== 'object')) {
      return {
        projection: null, shapeRejected: true,
        refusal: noticeRefusal(GUIDE_CODES.factsInvalid,
          GUIDE_NOTICES.unreadable, '输入形状不合法：facts 不是一个对象'),
      };
    }
    const decoded = decodeProjectGuideInput(input);
    if ('ok' in decoded && decoded.ok === false) {
      return {
        projection: null, shapeRejected: true,
        refusal: noticeRefusal(decoded.code, decoded.message, decoded.reason),
      };
    }
    return { projection: decoded as GuideProjection, refusal: null, shapeRejected: false };
  }, [props.projectId, props.identity, props.facts, props.workflow, props.tasks, props.inbox,
    props.assets, props.graph, props.timeline, props.storyboard]);

  const projection = derived.projection;
  const visible = props.active && !props.denied;
  const hints: readonly GuideHint[] = useMemo(() => {
    if (!visible || props.pending === true || !projection || projection.sources_read_count === 0) return [];
    return nextSteps(projection).filter(entry => noFabrication(entry) === null).slice(0, GUIDE_BOUNDS.hints);
  }, [visible, props.pending, projection]);

  let state: GuideSurfaceState;
  let refusal: GuideRefusal | null = null;
  let notice = '';
  if (props.denied) {
    // 被拒绝绝不是空项目：先清空一切，再说明原因。
    state = 'DENIED';
    notice = GUIDE_NOTICES.deniedIsNotUnknownProject;
    refusal = noticeRefusal(GUIDE_CODES.factsUnreadable, notice, '调用方声明事实读取被拒绝');
  } else if (!props.active) {
    state = 'IDLE';
    notice = '提示助手只在这个视图可见时推导；它不读取、不轮询。';
  } else if (derived.shapeRejected) {
    state = 'FAILED';
    refusal = derived.refusal ?? staticFallback();
    notice = refusal.message;
  } else if (props.pending === true) {
    state = 'LOADING';
    notice = '正在等待调用方读取项目事实；提示助手自己不会发起读取。';
  } else if (!projection || projection.sources_read_count === 0) {
    state = 'FAILED';
    refusal = projection ? unreadableFactsRefusal(projection) : staticFallback();
    notice = GUIDE_NOTICES.unreadable;
  } else if (hints.length === 0) {
    // EMPTY = 读成功且确实没有任何需要处理的条目。它**不是**一种拒绝：
    // 这里只说明状态，不生成"为什么没有建议"的警告块（那会和空状态重复一遍）。
    state = 'EMPTY';
    notice = GUIDE_NOTICES.emptyIsNotDenied;
  } else {
    state = 'READY';
  }

  return {
    state,
    notice,
    projection,
    hints,
    refusal,
    hasFacts: !!projection && projection.sources_read_count > 0,
    sourcesReadable: projection ? projection.sources_readable : Object.freeze({}),
    unreadableSources: projection ? sourcesOf(projection) : [],
    navigate: (target: GuideViewName) => {
      // 导航只发出既有视图名，由调用方决定是否真的跳转；这里从不自己改地址。
      // 目标必须在既有视图词表里：运行时的意外取值会被拒绝，而不是被转发。
      const handler = latest.current.onNavigate;
      if (typeof handler !== 'function'
        || !(GUIDE_VIEW_NAMES as readonly string[]).includes(target as string)) return false;
      handler(target);
      return true;
    },
    mentor: QINGJIAN_EXTENSION,
  };
}
