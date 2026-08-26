import {Construction,Info} from 'lucide-react';
import {Badge,Panel} from './primitives';

export function CapabilityPlaceholder({title,service,description,apiPrefix}: {title:string;service:string;description:string;apiPrefix:string}){
  return <Panel title={title} actions={<Badge tone="warning">后端预留</Badge>} className="capability-placeholder"><div className="capability-placeholder__icon"><Construction aria-hidden="true"/></div><h3>窗口已准备，服务尚未接入</h3><p>{description}</p><dl><div><dt>服务归属</dt><dd>{service}</dd></div><div><dt>预留 API</dt><dd><code>{apiPrefix}</code></dd></div></dl><p className="novel-help"><Info aria-hidden="true"/> 当前不会伪造结果；后端补齐后可直接接入本窗口。</p></Panel>
}
