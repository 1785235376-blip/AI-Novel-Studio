import { StatusMessage } from '../ui/primitives';
import { staticFallback } from './projectGuideOps';
import type { GuideRefusal, GuideSurfaceState } from './projectGuideTypes';

/**
 * 状态说明块：被拒绝、失败与事实不可读都走这里。
 *
 * 它的作用是让"没有建议"永远有一个**具体**原因（被拒绝 / 不可读 / 输入不合法），
 * 而不是显示成一个空项目或一句"请稍后重试"。
 */
export function BlockedStateNotice({ state, refusal, title, detail }: {
  state: GuideSurfaceState;
  refusal: GuideRefusal | null;
  title: string;
  detail: string;
}) {
  const problem = refusal ?? staticFallback();
  // `detail` 是界面自己写的状态说明；`problem.message` 是这条状态的具体原因。
  // 两者刻意不重复，因此这里不会出现同一句话被渲染两遍。
  return <section className="project-guide-blocked" data-guide-state={state} data-guide-code={problem.code} role="status">
    <header><h3>{title}</h3></header>
    <p>{detail}</p>
    <StatusMessage tone={state === 'DENIED' ? 'error' : 'warning'}>{problem.message}</StatusMessage>
    <dl>
      <div><dt>机器码</dt><dd><code>{problem.code}</code></dd></div>
      <div><dt>原因</dt><dd>{problem.reason}</dd></div>
    </dl>
    <p className="project-guide-blocked__no-retry">这里不会自动重试，也不会代替原 owner 重新读取；请回到对应模块重新核对。</p>
  </section>;
}
