import { Badge, EmptyState, StatusMessage } from '../ui/primitives';
import { DELIVERY_ITEM_KIND_LABELS, DELIVERY_NOTICES, type HandoverManifest } from './deliveryTypes';
import './deliveryCenter.css';

/**
 * 工程交接包清单：显示**只有**被显式勾选、且身份有权导出的对象（各带版本与摘要），
 * 以及每一条被排斥对象的原因。
 *
 * 这里的四条 `contains_*` 是清单类型里的常量 `false`：模型、依赖目录、凭据/密钥与
 * 他项目对象在这个结构里**装不进去**（排斥判据见 `deliveryOps.ts::handoverManifest`）。
 * 本面板只呈现，不组装、不新增协议。
 */
export type HandoverManifestPanelProps = {
  manifest: HandoverManifest;
  selectionCount: number;
};

function masked(digest: string): string {
  return `${digest.slice(0, 12)}…${digest.slice(-6)}`;
}

export function HandoverManifestPanel(props: HandoverManifestPanelProps) {
  const { manifest } = props;
  return <section className="delivery-manifest" aria-label="工程交接包清单">
    <header className="delivery-manifest__head">
      <h3>工程交接包清单</h3>
      <Badge tone={manifest.entries.length ? 'success' : 'neutral'}>{manifest.entries.length} 项</Badge>
    </header>
    <p className="delivery-center__help">{DELIVERY_NOTICES.singleItemIndependent}</p>
    <dl className="delivery-center__counts">
      <div><dt>项目</dt><dd>{manifest.project_id}</dd></div>
      <div><dt>身份</dt><dd>{manifest.identity}</dd></div>
      <div><dt>来源</dt><dd>{manifest.generated_from === 'SELECTION' ? '显式勾选' : manifest.generated_from}</dd></div>
      <div><dt>已选</dt><dd>{props.selectionCount} 项</dd></div>
      <div><dt>已进入清单</dt><dd>{manifest.entries.length} 项</dd></div>
      <div><dt>被排斥</dt><dd>{manifest.excluded.length} 项</dd></div>
      <div><dt>已核对字节</dt><dd>{manifest.total_bytes === null ? '无法核对' : `${manifest.total_bytes} B`}</dd></div>
    </dl>
    <ul className="delivery-center__counts delivery-manifest__flags" aria-label="交接包结构保证">
      <li>包含模型：{manifest.contains_models ? '是' : '否（结构上不可能）'}</li>
      <li>包含依赖目录：{manifest.contains_dependencies ? '是' : '否（结构上不可能）'}</li>
      <li>包含凭据/密钥：{manifest.contains_credentials ? '是' : '否（结构上不可能）'}</li>
      <li>包含他项目对象：{manifest.contains_foreign_project_objects ? '是' : '否（结构上不可能）'}</li>
    </ul>

    {!manifest.entries.length
      ? <EmptyState title="交接包当前为空" detail="只有被显式勾选且当前身份有权导出的对象才会进入清单；被排斥的对象列在下方并说明原因。" />
      : <ul className="delivery-manifest__list">
        {manifest.entries.map(entry => <li key={entry.id} className="delivery-manifest__row">
          <strong>{entry.id}</strong>
          <span>{DELIVERY_ITEM_KIND_LABELS[entry.kind]}</span>
          <span>v{entry.version}</span>
          <span className="delivery-center__digest" title={entry.digest}>{masked(entry.digest)}</span>
          <span>{entry.size_bytes} B</span>
          <span>{entry.media_type ?? '未声明媒体类型'}</span>
          <span>{entry.path ?? '未披露路径'}</span>
        </li>)}
      </ul>}

    {!!manifest.excluded.length && <div className="delivery-manifest__excluded">
      <h4>被排斥的对象（默认拒绝）</h4>
      <ul>
        {manifest.excluded.map((row, index) => <li key={`${row.id ?? 'unknown'}:${row.reason}:${index}`}>
          <code>{row.reason}</code> · {row.id ?? '（无标识）'} · {row.message}
        </li>)}
      </ul>
      <p className="delivery-center__help">排斥是默认结果：模型权重、依赖/构建目录、凭据与密钥、他项目对象、
        以及无法核对版本或摘要的对象都不会进入交接包。</p>
    </div>}
    {manifest.total_bytes === null && <StatusMessage tone="warning">
      有对象因超出整包上限而被排斥，因此这里不给出"已核对字节"合计，也不会为了凑数而丢弃对象后仍声称完整。
    </StatusMessage>}
  </section>;
}
