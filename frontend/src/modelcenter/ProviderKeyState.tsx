import { Badge, StatusMessage } from '../ui/primitives';
import { secretState } from './modelCenterOps';
import type { ModelCenterCredentialState, SecretStateView } from './modelCenterTypes';

/**
 * Provider 密钥状态：**只显示"存在/不存在/过期/未知"**。
 *
 * 这个组件拿到的永远是 `SecretStateView`，它的 `secret_value` 字段类型是字面量
 * `null`——也就是说，"渲染密钥值"在这份代码里没有可写的类型。
 * 后端越权回传 `secret` / `api_key` 之类的键名时，解码器会让整次读取失败
 * （`MODEL_CENTER_SECRET_VALUE_REJECTED`），因此也不存在"渲染了一个值"的路径。
 */
export function ProviderKeyState({ credentials, providers }: {
  credentials: readonly ModelCenterCredentialState[];
  /** 需要显示但原 owner 未回传状态的 provider；保持"未知"。 */
  providers?: readonly string[];
}) {
  const views: SecretStateView[] = (providers && providers.length ? providers : credentials.map(item => item.provider))
    .map(provider => secretState(credentials.find(item => item.provider === provider)));
  return (
    <section className="ui-panel model-center__keys" aria-label="Provider 密钥状态（只显示是否存在）">
      <header><h2>Provider 密钥状态</h2></header>
      <p className="model-center__hint">
        本面板只报告密钥是否存在、是否过期，以及凭据库是否降级。
        密钥值既不读取、也不渲染、也不进入任何查询缓存；原 owner 的
        <code> CredentialVault.status()</code> 里 <code>secret</code> 恒为 <code>null</code>，
        一旦响应里出现密钥字段，整次读取会被拒绝。
      </p>
      {!views.length
        ? <StatusMessage tone="warning">没有任何需要凭据的 provider，或原 owner 未回传凭据状态：一律显示"未知"，不猜测为"已配置"。</StatusMessage>
        : (
          <ul className="model-center__key-list">
            {views.map(view => (
              <li key={view.provider}>
                <span className="model-center__owner-fact">{view.provider}</span>
                <Badge tone={view.state === 'PRESENT' ? 'success' : view.state === 'ABSENT' ? 'neutral' : view.state === 'EXPIRED' ? 'error' : 'warning'}>
                  {view.label}
                </Badge>
                {view.backend && <span>后端：{view.backend}{view.persistent === false ? '（仅当前进程，不持久）' : view.persistent === true ? '（持久）' : ''}</span>}
                {view.degraded && <span>凭据库降级{view.degraded_reason ? `：${view.degraded_reason}` : ''}</span>}
                <span className="model-center__hint">密钥值：不显示（本模块的类型里没有可放的字段）</span>
              </li>
            ))}
          </ul>
        )}
    </section>
  );
}
