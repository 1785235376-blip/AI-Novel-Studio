import { useLayoutEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import { resourceBodyText, type ResourceDetailPin } from './pluginResourceDetailContract';

type Props = { pin: ResourceDetailPin; name: string; ownerKey: string };
type Read = { owner: object; loading: boolean; text?: string; failed?: boolean };
export function PluginResourceDetail({ pin, name, ownerKey }: Props) {
  const identity = JSON.stringify([ownerKey, pin]);
  const owner = useRef({ identity, token: {} });
  if (owner.current.identity !== identity) owner.current = { identity, token: {} };
  const token = owner.current.token;
  const alive = useRef(true), running = useRef<{ owner: object }>();
  const [read, setRead] = useState<Read>();
  const current = read?.owner === token ? read : undefined;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; running.current = undefined; }; }, []);
  async function inspect() {
    if (!alive.current || owner.current.token !== token || running.current?.owner === token) return;
    const ticket = { owner: token };
    running.current = ticket;
    const valid = () => alive.current && owner.current.token === token && running.current === ticket;
    setRead({ owner: token, loading: true });
    try {
      const value: unknown = await api.pluginResource(pin.pluginId, pin.resourceId);
      if (valid()) setRead({ owner: token, loading: false, text: resourceBodyText(value, pin) });
    } catch {
      if (valid()) setRead({ owner: token, loading: false, failed: true });
    } finally { if (valid()) running.current = undefined; }
  }
  return <section className="plugin-resource-detail" aria-label={`${name} 只读资源详情`}>
    <Button variant="ghost" loading={current?.loading} aria-label={`读取 ${name} 的资源正文`} onClick={() => void inspect()}>
      {current ? '重新校验并读取正文' : '读取资源正文'}
    </Button>
    {current && <Button variant="ghost" onClick={() => { running.current = undefined; setRead(undefined); }}>收起正文</Button>}
    {current?.loading && <StatusMessage>正在重新校验资源正文…</StatusMessage>}
    {current?.failed && <StatusMessage tone="error">正文读取失败、不可用或已变更。未保留旧正文；请重新校验资源摘要后再试。</StatusMessage>}
    {current?.text !== undefined && <>
      <p className="novel-help">以下仅为声明式 JSON 正文，可选择文本供人工查看；不会应用预设、执行工作流或导出。发布者仍未经验证。</p>
      <pre tabIndex={0} aria-label={`${name} 的资源正文`}>{current.text}</pre>
    </>}
  </section>;
}
