import { formatNumber, t as i18nT } from '../i18n'; // [HERMIA-FE-20261025 I18N P1] shared formatters
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { MODEL_CENTER_CODES, type OrphanReport, type StorageReport } from './modelCenterTypes';
import type { ModelCenterSourceStatus } from './modelCenterClient';

type ModelCenterSourceState = ModelCenterSourceStatus['state'];

export type StoragePanelProps = {
  report: StorageReport;
  orphans: OrphanReport;
  /** 是否真的读取到了项目存储投影；未读取到时不把用量显示成 0。 */
  loaded: boolean;
  loading?: boolean;
  /** 存储来源自身的结论（READY / DENIED / FAILED / UNAVAILABLE）。 */
  sourceState?: ModelCenterSourceState;
  sourceCode?: string;
  onReRead?: () => void;
  canReRead?: boolean;
};

const bytes = (value: number | null): string => value === null ? '未知' : i18nT('fmt.bytes', { n: formatNumber(value) });

/**
 * 存储面板：用量 / 配额 / 冷存储 / 孤儿报告。**只读**，并对"不可逆动作"说实话：
 * `physical_delete` 恒为 false，界面没有任何清理、迁移或删除按钮。
 */
export function StoragePanel({ report, orphans, loaded, loading = false, sourceState, sourceCode, onReRead, canReRead }: StoragePanelProps) {
  return (
    <section className="ui-panel model-center__storage" aria-label="项目存储与冷存储" data-storage-state={sourceState}>
      <header>
        <h2>项目存储与冷存储</h2>
        <Button variant="ghost" disabled={!canReRead} onClick={onReRead}>重新读取存储事实</Button>
      </header>
      {!loading && <StorageSourceNotice state={sourceState} code={sourceCode} retained={loaded} />}
      {!loading && loaded && (sourceState === 'FAILED' || sourceState === 'UNAVAILABLE') && <StatusMessage tone="warning">保留上一次成功读取的存储事实供对照；本次刷新未完成，当前用量可能已变化。</StatusMessage>}
      {!loaded && !loading
        ? <StatusMessage tone="warning">没有读取到项目存储投影：用量与可用空间保持未知，不显示为 0。{MODEL_CENTER_CODES.readFailed.message}</StatusMessage>
        : null}
      <dl className="model-center__facts" aria-label="用量与配额">
        {loaded ? (
          <>
            <div><dt>活动资产</dt><dd>{report.used_count} 项 · {bytes(report.used_bytes)}</dd></div>
            <div><dt>回收站（软删除）</dt><dd>{report.trash_count} 项 · {bytes(report.trash_bytes)}</dd></div>
            <div><dt>项目字节配额</dt><dd>{bytes(report.quota_bytes)}</dd></div>
            <div><dt>项目条目配额</dt><dd>{report.quota_items} 项</dd></div>
          </>
        ) : (
          <>
            <div><dt>活动资产</dt><dd>未知（没有读取到存储投影，不显示为 0）</dd></div>
            <div><dt>回收站（软删除）</dt><dd>未知（没有读取到存储投影，不显示为 0）</dd></div>
            <div><dt>项目字节配额</dt><dd>未知（没有读取到存储投影，不显示为 0）</dd></div>
            <div><dt>项目条目配额</dt><dd>未知（没有读取到存储投影，不显示为 0）</dd></div>
          </>
        )}
        <div><dt>准入可用字节</dt><dd>{report.free_bytes === null ? '未知（不可与 0 互换）' : bytes(report.free_bytes)}</dd></div>
        <div><dt>准入状态</dt><dd>{report.free_state ?? '原 owner 未回传 admission'}</dd></div>
      </dl>
      <section aria-label="不可逆动作说明">
        <h3>不可逆动作：本界面一个都不提供</h3>
        <p>
          <Badge tone="warning">physical_delete = {String(report.physical_delete)}</Badge>
          <span>（抄自 `physical_cleanup_available: false`）</span>
        </p>
        <ul>
          <li>清理"会触及"的所有者标签：{report.cleanup_would_touch.join('、') || '无'}。这些目录由各自原 owner 持有，本面板只有标签，没有路径。</li>
          <li>模型目录只被引用（MODEL_CENTER_REFERENCES_ONLY）：不扫描、不统计、不移动。</li>
          <li>需要用户显式确认之后才可能发生的动作：{report.requires_explicit_user_confirmation.length ? report.requires_explicit_user_confirmation.join('、') : '当前没有（原 owner 未提供任何清理端点）'}。</li>
          <li>automatic_cleanup = {String(report.automatic_cleanup)}；automatic_migration = {String(report.automatic_migration)}；external_model_scan = {String(report.external_model_scan)}。</li>
          <li>本界面可触发的磁盘动作：{report.disk_actions_available ? '有' : '没有'}。</li>
        </ul>
        {!loading && report.notices.map(notice => <p className="model-center__hint" key={notice}>{notice}</p>)}
      </section>
      <section aria-label="冷存储与孤儿候选（只读报告）">
        <h3>冷存储与孤儿候选（只读报告）</h3>
        <p>{orphans.detail}</p>
        <p>
          <Badge tone="neutral">mutates = {String(orphans.mutates)}</Badge>
          <Badge tone="neutral">physical_delete = {String(orphans.physical_delete)}</Badge>
          <span>候选合计：{orphans.total_bytes === null ? '未知' : bytes(orphans.total_bytes)}</span>
        </p>
        {orphans.candidates.length ? (
          <ul className="model-center__blockers">
            {orphans.candidates.map(item => (
              <li key={`${item.reason_code}:${item.asset_id ?? item.label}`}>
                <Badge tone="warning">{item.reason_code}</Badge>
                <span className="model-center__owner-fact">{item.asset_id ?? '身份未知（原 owner 未提供）'}</span>
                <span>{item.label} · {item.bytes === null ? '字节数未知' : bytes(item.bytes)}</span>
                <span>{item.reason}</span>
              </li>
            ))}
          </ul>
        ) : <p className="model-center__hint">没有候选。候选只是报告，从来不等于可以删除。</p>}
      </section>
      <p className="model-center__hint">
        本面板只读取事实：没有清理、迁移或删除按钮，也没有"腾出空间"这类会改动磁盘的动作。
      </p>
    </section>
  );
}

export function StorageSourceNotice({ state, code, retained = false }: { state?: ModelCenterSourceState; code?: string; retained?: boolean }) {
  if (!state) return null;
  if (state === 'DENIED') return <StatusMessage tone="error">存储读取被拒绝（DENIED）：不显示为"没有资产"。</StatusMessage>;
  if (state === 'FAILED') return <StatusMessage tone="error">存储读取失败（FAILED）。{code ? `（${code}）` : ''}</StatusMessage>;
  if (state === 'UNAVAILABLE') return <StatusMessage tone="warning">当前服务未提供项目存储读取{code ? `（${code}）` : ''}：{retained ? '当前用量未知，所列旧值仅供对照。' : '用量保持未知。'}</StatusMessage>;
  return null;
}
