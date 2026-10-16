import {useMemo, useState} from 'react';
import type {AIEnvironmentReport, LocalDiscoveryScan, LocalModelRegistration} from '../localAiDiscoveryApi';
import {Badge, Button, StatusMessage} from './primitives';

const PAGE_SIZE = 20;
const ROOT_STATUS: Record<AIEnvironmentReport['roots'][number]['status'], string> = {
  PENDING: '尚未检查', SCANNED: '已检查目录', NOT_FOUND: '本次未找到目录', UNREADABLE: '无法读取',
  REJECTED: '范围被拒绝', BOUNDED: '达到扫描上限', CANCELLED: '检查已取消',
};
const fileSize = (value: number) => {
  if (!Number.isFinite(value) || value < 0) return '未记录';
  const unit = value >= 1024 ** 3 ? ['GiB', 1024 ** 3] as const : value >= 1024 ** 2 ? ['MiB', 1024 ** 2] as const : value >= 1024 ? ['KiB', 1024] as const : undefined;
  return unit ? `${(value / unit[1]).toFixed(1)} ${unit[0]}（${value} bytes）` : `${value} bytes`;
};

/** Display-only projection of the owner's current scan. No discovery, file reads,
 * registration, or routing authority is created by opening or paging this view. */
export function LocalAiModelFiles({scan, registrations, stateUncertain}: {
  scan: LocalDiscoveryScan; registrations: LocalModelRegistration[]; stateUncertain: boolean;
}) {
  const [requestedPage, setPage] = useState(0);
  const files = scan.model_files;
  const pageCount = Math.max(1, Math.ceil((files?.length || 0) / PAGE_SIZE));
  const page = Math.min(requestedPage, pageCount - 1), offset = page * PAGE_SIZE;
  const candidates = useMemo(() => new Map(scan.candidates.map(candidate => [candidate.id, candidate])), [scan.candidates]);
  const registered = useMemo(() => {
    const index = new Map<string, LocalModelRegistration>();
    for (const registration of registrations) {
      // Match the existing registry's first exact id/candidate_id association.
      if (!index.has(registration.id)) index.set(registration.id, registration);
      if (registration.candidate_id && !index.has(registration.candidate_id)) index.set(registration.candidate_id, registration);
    }
    return index;
  }, [registrations]);
  const rootCounts = new Map<string, number>();
  scan.roots?.forEach(root => rootCounts.set(root.status, (rootCounts.get(root.status) || 0) + 1));

  return <section className="local-ai__section" aria-label="本次扫描的文件与索引观察">
    <h3>文件与索引观察{files ? `（${files.length}）` : ''}</h3>
    <p>这些是本次后端主机扫描记录的文件或索引元数据，不代表完整安装、可运行能力或整盘模型清单。这里只显示已有结果，不重新读取文件或加载权重。</p>
    <dl className="local-ai__facts">
      <div><dt>最近扫描开始</dt><dd>{scan.started_at || '未记录'}</dd></div>
      <div><dt>最近扫描结束</dt><dd>{scan.finished_at || '未记录'}</dd></div>
      <div><dt>目录范围</dt><dd>{scan.roots ? `${scan.roots.length} 个目录 · ${scan.roots.filter(root => root.source === 'CONFIGURED').length} 个已配置 · ${scan.roots.filter(root => root.source === 'COMMON').length} 个常用` : '未提供目录范围记录'}</dd></div>
      <div><dt>目录检查结果</dt><dd>{[...rootCounts].map(([status, count]) => `${ROOT_STATUS[status as keyof typeof ROOT_STATUS] || '未知状态'} ${count} 个`).join(' · ') || '没有目录检查结果'}</dd></div>
    </dl>
    <p className="local-ai__muted">范围与深度、文件数、条目数和时间均有限；不代表整盘模型清单，也未按内容去重。目录未找到或 Runtime 绑定未知不能说明主机未安装模型。</p>
    {(scan.status === 'PARTIAL' || scan.status === 'CANCELLED') && <StatusMessage tone="warning">{scan.status === 'PARTIAL' ? '部分检测未完成' : '扫描已取消'}，保留已观察结果；尚未检查的范围仍未知。</StatusMessage>}
    {['QUEUED', 'RUNNING', 'SCANNING', 'CANCELLING'].includes(scan.status) && <p role="status">扫描尚未结束，当前观察仅为部分结果。</p>}
    {scan.roots && scan.roots.length > 0 && <details><summary>高级：查看本次目录路径</summary><ul className="local-ai__notes">{scan.roots.map((root, index) => <li key={index}>{root.source === 'COMMON' ? '常用目录' : '已配置目录'}：{root.path} · {ROOT_STATUS[root.status] || '未知状态'}</li>)}</ul></details>}
    {!files ? <p>本次扫描未提供文件观察数据，不能据此判断是否存在模型文件。</p> : !files.length ? <p>本次有限范围内未观察到模型文件或索引；未检查范围仍未知。</p> : <>
      <div className="local-ai__summary"><span>{offset + 1}–{Math.min(offset + PAGE_SIZE, files.length)} / {files.length} 条观察</span>{pageCount > 1 && <>
        <Button disabled={page === 0} onClick={() => setPage(page - 1)}>上一页文件观察</Button>
        <Button disabled={page === pageCount - 1} onClick={() => setPage(page + 1)}>下一页文件观察</Button>
      </>}</div>
      <div className="local-ai__list">{files.slice(offset, offset + PAGE_SIZE).map(file => {
        // Same-scan IDs are the only evidence of a binding. Names, family,
        // paths, and standalone registrations must never manufacture one.
        const linked = [...new Set(file.candidate_ids)].flatMap(id => candidates.has(id) ? [candidates.get(id)!] : []);
        const missing = file.candidate_ids.some(id => !candidates.has(id));
        return <article key={file.id} aria-label={`${file.name} 文件观察`}>
          <header className="local-ai__actions"><strong>{file.name}</strong><Badge tone="neutral">{file.format === 'DIFFUSERS' ? 'DIFFUSERS · 索引观察' : file.format}</Badge></header>
          <dl className="local-ai__facts">
            <div><dt>{file.format === 'DIFFUSERS' ? '索引大小' : '文件大小'}</dt><dd>{fileSize(file.size_bytes)}</dd></div>
            <div><dt>元数据检查</dt><dd>{file.header_valid ? '有界元数据结构检查通过' : '有界元数据结构未确认'}；未验证权重内容或可运行性</dd></div>
            <div><dt>模型族 / 能力（名称推断提示）</dt><dd>{file.family || 'UNKNOWN'} · {file.declared_capabilities.join(' · ') || 'UNKNOWN'}；仅为名称提示，能力未验证</dd></div>
            <div><dt>文件观察的实际生成验证</dt><dd>NOT_RUN · 文件观察未执行生成测试</dd></div>
          </dl>
          {file.format === 'DIFFUSERS' && <p>路径与大小对应 model_index.json，不代表目录或权重总大小；未验证组件完整性。</p>}
          {!linked.length && <p>Runtime 绑定未知；没有可确认的同次扫描候选关联。</p>}
          {missing && <p>部分候选关联未在本次扫描中找到，对应 Runtime 绑定未知。</p>}
          {linked.length > 0 && <ul className="local-ai__notes" aria-label="同次扫描的 Runtime 关联">{linked.map(candidate => {
            const registration = registered.get(candidate.id), current = registration || candidate;
            return <li key={candidate.id}>{candidate.runtime_type} · {candidate.runtime_id} · {candidate.display_name}
              <div className="local-ai__actions"><Badge tone={stateUncertain ? 'warning' : 'neutral'}>{stateUncertain ? '注册状态待确认' : registration?.enabled ? '已授权路由' : registration ? '已注册 · 未启用' : '候选 · 未注册'}</Badge><span>{stateUncertain ? '关联状态待重新读取；实际生成验证未确认' : current.verified && current.evidence.generation_verified === true ? '关联记录报告实际生成已验证；文件观察本身未执行生成' : '尚未实际生成验证'}</span></div>
            </li>;
          })}</ul>}
          {linked.length > 0 && <p className="local-ai__muted">路由授权与实际生成验证分别记录；启用不会立即加载模型，后续接入仍需原有验证与确认。</p>}
          <details><summary>高级：查看文件路径与身份</summary>
            <dl className="local-ai__facts"><div><dt>{file.format === 'DIFFUSERS' ? '索引路径' : '文件路径'}</dt><dd>{file.path}</dd></div><div><dt>来源目录</dt><dd>{file.source === 'COMMON' ? '常用目录' : '已配置目录'} · {file.root}</dd></div><div><dt>路径身份 ID（非内容哈希）</dt><dd>{file.id}</dd></div></dl>
            {file.notes.length > 0 && <ul className="local-ai__notes">{file.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
          </details>
        </article>;
      })}</div>
    </>}
  </section>;
}
