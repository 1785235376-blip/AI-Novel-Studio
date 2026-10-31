import { Badge, StatusMessage } from '../ui/primitives';
import { CAMERA_FIELD_LABELS } from './CameraLanguageControl';
import type {
  CameraLanguageUsage, DirectorIntentProjection, DirectorIntentRecord, SimpleUsage,
} from './directorWorkspaceTypes';

/**
 * 导演意图面板：显示 `DIRECTOR_INTENT_FIELDS` 里的全部七个维度。
 *
 * 面板最重要的职责是**不把测量说成决定**：
 *  - `DOCUMENT_AUTHORED` 的维度显示原文档里已经 authoring 的值；
 *  - `PER_SHOT_MEASURED` 的维度没有文档级归属，只能显示"逐镜头统计"，并明确
 *    标注"这不是文档级决定"。少了这句话，界面就等于在替导演宣布一个他没做过的决定。
 *
 * 项目自己的题材是**继承来的上下文**，与导演 authoring 的题材分开显示，永不写回。
 */

const NOT_PROVIDED = '原文档未提供';

function usageSummary(record: DirectorIntentRecord): string {
  const usage = record.usage;
  if (!usage) return NOT_PROVIDED;
  const rows = usage.measured_over_rows;
  if (rows === 0) return '原文档还没有可统计的镜头或导演备注';
  const authoredRows = 'authored_rows' in usage ? usage.authored_rows : 0;
  return `逐镜头统计：${authoredRows} / ${rows} 条已填写`;
}

function SimpleUsageTable({ usage }: { usage: SimpleUsage }) {
  return <table className="director-intent__usage">
    <caption>逐镜头统计（不是文档级决定）</caption>
    <thead><tr><th scope="col">字段</th><th scope="col">已填写</th><th scope="col">取值</th></tr></thead>
    <tbody>{Object.entries(usage.dimensions).map(([field, entry]) => <tr key={field}>
      <th scope="row">{CAMERA_FIELD_LABELS[field] ?? field}</th>
      <td>{entry.authored_rows} / {entry.rows}</td>
      <td>{entry.values.length === 0 ? NOT_PROVIDED
        : entry.values.map(item => `${item.value}（${item.count}）`).join('、')}</td>
    </tr>)}</tbody>
  </table>;
}

function CameraUsageTable({ usage }: { usage: CameraLanguageUsage }) {
  return <table className="director-intent__usage">
    <caption>镜头语言逐镜头统计（不是文档级决定）</caption>
    <thead><tr><th scope="col">字段</th><th scope="col">已填写</th><th scope="col">取值（规范 / 旧写法）</th></tr></thead>
    <tbody>{Object.entries(usage.dimensions).map(([field, entry]) => <tr key={field}>
      <th scope="row">{CAMERA_FIELD_LABELS[field] ?? field}</th>
      <td>{entry.authored_rows} / {entry.rows}</td>
      <td>{entry.values.length === 0 ? NOT_PROVIDED : entry.values.map(item =>
        <span key={`${item.value}-${item.code}`} className="director-intent__usage-value">
          {item.value}
          <Badge tone={item.code === 'CANONICAL' ? 'success' : item.code === 'LEGACY_PASSTHROUGH' ? 'warning' : 'neutral'}>
            {item.code === 'CANONICAL' ? '规范' : item.code === 'LEGACY_PASSTHROUGH' ? '旧写法保留' : '未填写'}
          </Badge>
          （{item.count}）
        </span>)}</td>
    </tr>)}</tbody>
  </table>;
}

export function DirectorIntentPanel({ intent, projectContext }: {
  intent: DirectorIntentProjection;
  projectContext: { title: string; genre: string; inherited_not_authored: true };
}) {
  return <section className="director-intent" aria-label="导演意图">
    <p className="director-intent__scope">
      导演意图是原文档里的 authoring 决定。本工作台只读：它不会因为一次读取就改写镜头、
      覆盖已批准结果，也不会把统计结果当成你的决定。
    </p>
    <p className="director-intent__inherited">
      项目题材（继承自项目，不是导演 authoring 的值）：{projectContext.genre || NOT_PROVIDED}
      {projectContext.title && ` · ${projectContext.title}`}
    </p>

    <ul className="director-intent__list">
      {intent.fields.map(record => <li key={record.field} data-field={record.field}
          data-kind={record.kind} className="director-intent__item">
        <div className="director-intent__head">
          <h4>{record.label}</h4>
          <Badge tone={record.kind === 'DOCUMENT_AUTHORED' ? 'info' : 'neutral'}>
            {record.kind === 'DOCUMENT_AUTHORED' ? '文档级 authoring' : '逐镜头统计'}
          </Badge>
          {record.authored ? <Badge tone="success">已填写</Badge> : <Badge tone="neutral">未填写</Badge>}
        </div>
        <p className="director-intent__value">
          {record.kind === 'DOCUMENT_AUTHORED' ? (record.authored ? record.value : NOT_PROVIDED) : usageSummary(record)}
        </p>
        <p className="director-intent__source">来源：<code>{record.source}</code>（owner：<code>{record.owner}</code>）</p>
        {record.detail && <p className="director-intent__detail">
          节奏：{record.detail.rhythm || NOT_PROVIDED} · 参考作品：
          {record.detail.reference_works.join('、') || NOT_PROVIDED}
        </p>}
        {record.usage && record.field === 'camera_language' && <CameraUsageTable usage={record.usage as CameraLanguageUsage} />}
        {record.usage && record.field !== 'camera_language' && <SimpleUsageTable usage={record.usage as SimpleUsage} />}
      </li>)}
    </ul>

    {intent.measured_over === 'NONE' && <StatusMessage tone="info">
      原文档还没有镜头或导演备注，所以逐镜头维度暂时没有任何可统计的 authoring 内容。
    </StatusMessage>}
  </section>;
}
