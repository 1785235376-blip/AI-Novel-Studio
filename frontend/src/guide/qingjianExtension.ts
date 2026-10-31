/**
 * UX-08 青简（QingJian）导师扩展点 —— **已暂停，且今天什么都不做**。
 *
 * 这个文件存在的唯一理由：让"未来可以接入一个导师适配器"这件事在代码里有据可查，
 * 而不是让某个人偷偷加一条网络接线。它今天：
 *
 * - `available: false`，且**不可在运行时改成 true**（没有 setter、没有全局开关）；
 * - **不注册任何适配器**：`registerQingjianAdapter()` 永远拒绝，并返回稳定机器码；
 * - **不渲染任何东西**：这里没有组件、没有导出任何 JSX；
 * - **不报告任何连接状态**：没有 `connected` / `available` 之类的可显示状态，
 *   因此界面不可能显示"已连接青简"，也不可能伪造导师建议；
 * - **没有任何端点 / 客户端 / fetch**：本模块不 import 任何传输层。
 *
 * 如果将来要真正接入，必须先由青简 owner 提供适配器契约、由 Root/设计系统 owner
 * 批准，并在**新的**工作包里实现；届时这里的 `available` 与拒绝逻辑才允许改变。
 */
import { GUIDE_CODES, GUIDE_NOTICES } from './projectGuideTypes';
export type QingjianMentorAdapter = {
  /** 适配器自己的稳定标识（未来的 owner 决定取值，不是本模块发明的）。 */
  readonly adapter_id: string;
  /** 必须显式声明"只读建议、不执行"；今天的类型里不给任何执行能力。 */
  readonly advisory_only: true;
};

/**
 * 隐藏扩展点的冻结标记。`available` 是字面量 `false`，因此它不可能在运行时为真。
 * 这个模块是唯一接触"青简"这个词的地方；类型模块只是把它再导出一次。
 */
export const QINGJIAN_EXTENSION = Object.freeze({
  available: false as const,
  /** 未来适配器可以注册的位置；今天不注册、不渲染、不报告连接。 */
  slot: 'project-guide-mentor-adapter',
  reason: GUIDE_CODES.qingjianUnavailable,
  message: GUIDE_NOTICES.qingjianDisabled,
});

export type QingjianRegistration =
  | { readonly registered: true; readonly adapter: QingjianMentorAdapter }
  | { readonly registered: false; readonly code: string; readonly message: string };

/** 已注册的适配器数量。恒为 0：这个模块不保存任何注册表。 */
export const qingjianAdapterCount = (): 0 => 0;

/**
 * 尝试注册一个导师适配器。
 *
 * 今天**永远**返回拒绝：`available: false` 意味着没有任何槽位可以被占用，
 * 所以既没有注册、也没有连接、也没有建议。
 */
export function registerQingjianAdapter(_adapter: unknown): QingjianRegistration {
  return Object.freeze({
    registered: false as const,
    code: GUIDE_CODES.qingjianUnavailable,
    message: GUIDE_NOTICES.qingjianRegistrationRefused,
  });
}

/**
 * 提示助手是否有一个可用的导师。恒为 `false`：调用方因此永远不会看到
 * "已连接青简"这类状态，也不会显示任何导师建议。
 */
export const qingjianMentorAvailable = (): false => false;
