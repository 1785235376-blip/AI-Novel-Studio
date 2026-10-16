import { useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import {
  DELIVERY_DECLARED_LIMITS, exportableItem, formatAvailability, formatRefusal, sizeAndLimitsReport,
} from './deliveryOps';
import {
  DELIVERY_FORMAT_KINDS, DELIVERY_ITEM_KIND_LABELS, DELIVERY_NOTICES,
  type DeliveryEntitlements, type DeliveryFormatId, type DeliveryFormatRefusal, type DeliveryItem,
  type DeliveryItemKind, type DeliveryRequest,
} from './deliveryTypes';
import './deliveryCenter.css';

/**
 * 单对象导出面：判定**一个**对象能否独立导出（S11），在格式不被支持时给出明确拒绝，
 * 并把原 owner 声明的限额在撞线之前说清楚。
 *
 * 它**不派发**任何东西：`onRememberDispatch` 是给组合根的回调，用来登记"原 owner 已经
 * 为这个对象创建了任务"这一既成事实，并据此生成恢复计划。本面板没有 dispatch 方法。
 */
export type ItemExportPanelProps = {
  items: DeliveryItem[];
  entitlements: DeliveryEntitlements;
  /** 当前查看的对象种类过滤；空表示全部。 */
  kind: DeliveryItemKind | '';
  onKindChange: (kind: DeliveryItemKind | '') => void;
  selection: string[];
  onToggle: (id: string) => void;
  onRememberDispatch: (request: DeliveryRequest) => void;
};

function maskedDigest(digest: string): string {
  return `${digest.slice(0, 10)}…${digest.slice(-4)}`;
}

export function ItemExportPanel(props: ItemExportPanelProps) {
  const { items, entitlements } = props;
  const visible = items.filter(item => !props.kind || item.kind === props.kind);
  const [format, setFormat] = useState<DeliveryFormatId>(entitlements.formats[0] ?? 'json');
  const [notice, setNotice] = useState('');
  const [refusal, setRefusal] = useState<DeliveryFormatRefusal | null>(null);
  const kindRef = useRef<HTMLSelectElement>(null);
  const selection = items.filter(item => props.selection.includes(item.id));
  const report = sizeAndLimitsReport(selection, entitlements);

  const changeKind = (kind: DeliveryItemKind | ''): void => {
    setNotice('');
    setRefusal(null);
    props.onKindChange(kind);
  };

  const inspect = (item: DeliveryItem): void => {
    // 显式拒绝：格式不被支持时，这里只产出 REFUSED，永远不会产出成功。
    const decision = exportableItem(item, entitlements, format);
    if (decision.state === 'REFUSED') {
      setRefusal({ state: 'REFUSED', code: decision.code, message: decision.message, requested_format: format, available_formats: decision.available_formats });
      setNotice('');
      return;
    }
    setRefusal(null);
    setNotice(`“${item.id}”可以单独导出（${DELIVERY_ITEM_KIND_LABELS[decision.kind]} → ${decision.format}）：它不依赖项目其余部分是否完成。任务仍由原导出服务创建。`);
  };

  return <section className="delivery-item" aria-label="单对象导出">
    <header className="delivery-item__head">
      <h3>单个对象导出</h3>
      <label className="delivery-center__field">
        <span>对象种类</span>
        <select ref={kindRef} aria-label="对象种类过滤" value={props.kind}
          onChange={event => changeKind(event.target.value as DeliveryItemKind | '')}>
          <option value="">全部种类</option>
          {Object.entries(DELIVERY_ITEM_KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label className="delivery-center__field">
        <span>导出格式</span>
        <select aria-label="单对象导出格式" value={format}
          onChange={event => { setFormat(event.target.value as DeliveryFormatId); setRefusal(null); setNotice(''); }}>
          {(entitlements.formats.length ? entitlements.formats : ['json' as DeliveryFormatId])
            .map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </label>
    </header>

    <p className="delivery-center__help">{DELIVERY_NOTICES.singleItemIndependent}{DELIVERY_NOTICES.opOnly}</p>

    {!entitlements.can_export && <StatusMessage tone="warning">当前身份没有被授予导出权利，因此没有任何对象可以导出。</StatusMessage>}
    {!items.length && <EmptyState title="没有可核对的导出对象" detail="本目录只清点父层明确给出的对象；没有给出时不显示任何可导出项，也不会用整个项目冒充。" />}
    {!!items.length && !visible.length && <>
      <EmptyState title="当前种类没有匹配对象" detail="已载入的对象中没有当前种类；可切换对象种类，或显示全部种类。现有交接包选择会保留。" />
      <Button type="button" variant="secondary" onClick={() => { changeKind(''); kindRef.current?.focus(); }}>
        显示全部种类
      </Button>
    </>}

    {!!visible.length && <ul className="delivery-item__list">
      {visible.map(item => {
        const decision = exportableItem(item, entitlements);
        const available = formatAvailability(item, entitlements);
        return <li key={item.id} className="delivery-item__row" data-exportable={decision.state === 'EXPORTABLE'}>
          <div className="delivery-item__facts">
            <strong>{item.id}</strong>
            <span>{item.kind ? DELIVERY_ITEM_KIND_LABELS[item.kind] : '未声明种类'}</span>
            <span>v{item.version ?? '—'}</span>
            <span>{item.digest ? maskedDigest(item.digest) : '无摘要'}</span>
            <span>{item.size_bytes === null ? '字节未知' : `${item.size_bytes} B`}</span>
          </div>
          <div className="delivery-item__actions">
            <Badge tone={decision.state === 'EXPORTABLE' ? 'success' : 'warning'}>
              {decision.state === 'EXPORTABLE' ? '可单独导出' : '不可导出'}
            </Badge>
            <Button type="button" variant="ghost" aria-pressed={props.selection.includes(item.id)}
              onClick={() => props.onToggle(item.id)}>{props.selection.includes(item.id) ? '已选入交接包' : '选入交接包'}</Button>
            <Button type="button" variant="secondary" onClick={() => inspect(item)}>核对这个对象的格式</Button>
          </div>
          {decision.state === 'REFUSED' && <p className="delivery-item__refusal" role="note">
            {decision.message}{decision.available_formats.length
              ? `可用格式：${decision.available_formats.join('、')}。`
              : '当前身份没有任何能写出这类对象的格式。'}
          </p>}
          {decision.state === 'EXPORTABLE' && !available.length && <p className="delivery-center__help">原导出服务当前没有声明能写出这类对象的格式。</p>}
        </li>;
      })}
    </ul>}

    {refusal && <div role="alert"><StatusMessage tone="warning">
      {refusal.message}（机器码：<code>{refusal.code}</code>）可用格式：{refusal.available_formats.length ? refusal.available_formats.join('、') : '无'}。
    </StatusMessage></div>}
    {notice && <StatusMessage>{notice}</StatusMessage>}

    <footer className="delivery-item__limits">
      <h4>限额（原 owner 声明，界面不能上调）</h4>
      <ul className="delivery-center__counts">
        <li>单对象：{DELIVERY_DECLARED_LIMITS.item_bytes} 字节</li>
        <li>整包：{DELIVERY_DECLARED_LIMITS.package_bytes} 字节</li>
        <li>条目：{DELIVERY_DECLARED_LIMITS.items} 条</li>
        <li>本次已选：{report.items} 条</li>
        <li>已核对字节：{report.total_bytes === null ? '无法核对（有对象未报告字节）' : `${report.total_bytes} B`}</li>
        <li>判定：{report.verdict}（无权限时为空包）</li>
        <li>上限是否被上调：{report.limits_raised ? '是' : '否 — 永远不会'}</li>
      </ul>
      {report.verdict !== 'WITHIN_LIMITS' && <p className="delivery-center__help" role="note">
        {report.verdict === 'EXCEEDED'
          ? '本次选择已超出原 owner 的限额，整包被拒绝，也不会为了装下而丢弃对象。'
          : '有对象没有报告字节数，无法核对限额；这里不会把它当成通过。'}
      </p>}
      {!!report.refused_items.length && <p className="delivery-center__help">被拒对象：{report.refused_items.join('、')}</p>}
      <p className="delivery-center__help">
        通用脚本格式（script-txt）由创意面板的原 owner 持有，{Object.keys(DELIVERY_FORMAT_KINDS).length} 个导出格式中当前身份可用 {entitlements.formats.length} 个。
      </p>
      {report.unmeasured.length > 0 && <p className="delivery-center__help">未报告字节：{report.unmeasured.join('、')}（原 owner 未披露字节数，因此无法核对限额。）</p>}
    </footer>
  </section>;
}
