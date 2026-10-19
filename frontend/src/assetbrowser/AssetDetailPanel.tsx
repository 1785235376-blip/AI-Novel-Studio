import { useMemo, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import {
  ASSET_BROWSER_AUTHOR_DECLARATION, ASSET_BROWSER_IMPACT_GROUP_LABELS, ASSET_BROWSER_INTEGRITY_LABELS,
  ASSET_BROWSER_NOTICES, ASSET_BROWSER_REFERENCE_KIND_LABELS, ASSET_BROWSER_RELATIONSHIP_LABELS,
  ASSET_BROWSER_REVIEW_LABELS, ASSET_BROWSER_SOURCE_STATE_LABELS, ASSET_BROWSER_TAG_LABELS,
  type AssetBrowserAsset, type AssetBrowserDeleteImpact, type AssetBrowserImpact, type AssetBrowserProblem,
  type AssetBrowserRow,
} from './assetBrowserTypes';

function stateTone(state: string): 'neutral' | 'info' | 'success' | 'warning' | 'error' {
  if (state === 'CURRENT' || state === 'VERIFIED' || state === 'APPROVED') return 'success';
  if (state === 'STALE' || state === 'UNAVAILABLE' || state === 'UNVERIFIED' || state === 'CONTENT_UNAVAILABLE') return 'warning';
  if (state === 'DELETED' || state === 'REJECTED') return 'error';
  return 'neutral';
}

function ProvenanceBlock({ asset }: { asset: AssetBrowserAsset }) {
  const provenance = asset.provenance;
  if (!provenance) {
    return <section aria-label="来源与许可">
      <h4>来源与许可</h4>
      <p className="asset-browser__note">原 owner 未披露此素材的来源投影（{ASSET_BROWSER_NOTICES.unverified}）。</p>
    </section>;
  }
  return <section aria-label="来源与许可">
    <h4>来源与许可</h4>
    <dl className="asset-browser__facts">
      <div><dt>来源</dt><dd>{provenance.origin ?? ASSET_BROWSER_NOTICES.unverified}</dd></div>
      <div><dt>提供方记录</dt><dd>{provenance.producer?.provider_id?.trim()
        ? provenance.producer.provider_id : ASSET_BROWSER_NOTICES.unverified}</dd></div>
      <div><dt>模型记录</dt><dd>{provenance.producer?.model_id?.trim()
        ? provenance.producer.model_id : ASSET_BROWSER_NOTICES.unverified}</dd></div>
      <div><dt>完整性</dt><dd>{provenance.integrity === null
        ? ASSET_BROWSER_NOTICES.unverified : ASSET_BROWSER_INTEGRITY_LABELS[provenance.integrity]}</dd></div>
      <div><dt>来源状态</dt><dd>{provenance.stale === null
        ? ASSET_BROWSER_NOTICES.unverified : provenance.stale ? '来源已变化或不可用' : '来源当前'}</dd></div>
      <div><dt>处理操作</dt><dd>{provenance.operation ?? ASSET_BROWSER_NOTICES.unverified}</dd></div>
    </dl>
    <p className="asset-browser__note">提供方与模型为原资产来源记录，当前可用性未核实。</p>
    <p className="asset-browser__note">
      作者许可声明：{provenance.license_label ?? '未声明'}
      {provenance.license_source && ` · 来源：${provenance.license_source}`}。
      {provenance.license_verification === ASSET_BROWSER_AUTHOR_DECLARATION
        ? ' 这是作者声明（AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION）：不是法律核验，也不代表任何云端许可。'
        : ` 原 owner 未给出许可核验标记（${ASSET_BROWSER_NOTICES.unverified}）；界面不会声称存在商用授权。`}
    </p>
    {provenance.declaration_history_versions.length > 0 && <p className="asset-browser__note">
      声明历史版本：{provenance.declaration_history_versions.map(version => `v${version}`).join(' · ')}
    </p>}
    <h4>父资产（{provenance.parents.length}）</h4>
    {provenance.parents.length === 0 && <p className="asset-browser__note">没有父资产记录；这可能是原创输入或未声明来源。</p>}
    <ul className="asset-browser__list">{provenance.parents.map((parent, index) => <li key={`${parent.id ?? 'unknown'}-${index}`}>
      <strong>{parent.label ?? parent.id ?? ASSET_BROWSER_NOTICES.unverified}</strong>
      <span className="asset-browser__meta">
        {parent.version === null ? ASSET_BROWSER_NOTICES.unverified : `v${parent.version}`} ·
        {' '}{parent.digest ?? ASSET_BROWSER_NOTICES.unverified}
      </span>
      <Badge tone={stateTone(parent.state)}>{ASSET_BROWSER_SOURCE_STATE_LABELS[parent.state]}</Badge>
    </li>)}</ul>
    <h4>章节来源（{provenance.sources.length}）</h4>
    {provenance.sources.length === 0 && <p className="asset-browser__note">没有章节来源。</p>}
    <ul className="asset-browser__list">{provenance.sources.map((source, index) => <li key={`${source.id ?? 'unknown'}-${index}`}>
      <strong>{source.id ?? ASSET_BROWSER_NOTICES.unverified}</strong>
      <span className="asset-browser__meta">
        {source.version === null ? ASSET_BROWSER_NOTICES.unverified : `v${source.version}`} ·
        {' '}{source.digest ?? ASSET_BROWSER_NOTICES.unverified}
      </span>
      <Badge tone={stateTone(source.state)}>{ASSET_BROWSER_SOURCE_STATE_LABELS[source.state]}</Badge>
    </li>)}</ul>
  </section>;
}

/** 「被哪些镜头 / 节点 / 时间线使用」——未知关系一律显示未核实，绝不猜。 */
function UsageBlock({ impact, unverified, busy, onLoadReferences }: {
  impact?: AssetBrowserImpact; unverified: boolean; busy: boolean; onLoadReferences: () => void;
}) {
  if (!impact) {
    return <section aria-label="被谁使用">
      <h4>被哪些镜头 / 节点 / 时间线使用</h4>
      <p className="asset-browser__note">尚未读取引用关系（{ASSET_BROWSER_NOTICES.unverified}）。</p>
      <Button type="button" variant="ghost" disabled={busy} onClick={onLoadReferences}>
        {unverified ? '读取引用关系（当前未核实）' : '重新读取引用关系'}
      </Button>
    </section>;
  }
  return <section aria-label="被谁使用">
    <h4>被哪些镜头 / 节点 / 时间线使用（{impact.total}）</h4>
    <p className="asset-browser__note">
      原 owner 的关系投影只声明"谁引用了谁"，不含镜头 / 节点 / 时间线的模块种类，
      因此未核实的分组保持 未核实，不会被当作"没有被使用"。{unverified && ` ${ASSET_BROWSER_NOTICES.relationshipUnreadable}`}
    </p>
    {impact.groups.map(group => <div key={group.group} className="asset-browser__impact-group"
      data-group={group.group} data-empty={group.items.length === 0}>
      <h5>{group.label}（{group.items.length}）{group.unverified > 0 && ` · ${group.unverified} 条${ASSET_BROWSER_NOTICES.unverified}`}</h5>
      {group.items.length === 0
        ? <p className="asset-browser__note">{group.group === 'UNKNOWN'
          ? '没有无法核实的关系记录。' : '当前没有可核实的这一类引用。'}</p>
        : <ul className="asset-browser__list">{group.items.map((entry, index) => <li key={`${entry.id ?? 'unknown'}-${index}`}>
          <strong>{entry.label ?? entry.id ?? ASSET_BROWSER_NOTICES.unverified}</strong>
          <span className="asset-browser__meta">
            {ASSET_BROWSER_RELATIONSHIP_LABELS[entry.relationship]} ·
            {' '}引用方 {ASSET_BROWSER_REFERENCE_KIND_LABELS[entry.kind]} ·
            {' '}{entry.bound_version === null ? `绑定版本 ${ASSET_BROWSER_NOTICES.unverified}` : `绑定 v${entry.bound_version}`}
          </span>
          <Badge tone={stateTone(entry.state)}>{ASSET_BROWSER_SOURCE_STATE_LABELS[entry.state]}</Badge>
          {entry.matches_current === false && <Badge tone="warning">需重新确认</Badge>}
          {entry.matches_current === null && <Badge tone="neutral">{ASSET_BROWSER_NOTICES.unverified}</Badge>}
        </li>)}</ul>}
    </div>)}
    <p className="asset-browser__note">{ASSET_BROWSER_NOTICES.noAutoUpdate}</p>
    <div className="asset-browser__actions">
      <Button type="button" variant="ghost" disabled={busy} onClick={onLoadReferences}>
        {unverified ? '读取引用关系（当前未核实）' : '重新读取引用关系'}
      </Button>
    </div>
  </section>;
}

/**
 * 资产详情。版本、来源、参数（owner 允许披露时）、参考图与被引用位置都在这里；
 * 读取失败时**保持当前选择**并解释原因。
 */
export function AssetDetailPanel({
  row, detail, detailState, detailProblem, impact, referencesUnverified, deleteImpact, comparison,
  onReadDetail, onLoadReferences, onCompare, onSendTo, onDeleteIntent, busy,
}: {
  row?: AssetBrowserRow;
  detail?: AssetBrowserAsset;
  detailState: 'IDLE' | 'LOADING' | 'READY' | 'FAILED';
  detailProblem?: AssetBrowserProblem;
  impact?: AssetBrowserImpact;
  referencesUnverified: boolean;
  deleteImpact?: AssetBrowserDeleteImpact;
  comparison?: { id: string; version: number | null; digest: string } | null;
  onReadDetail: (assetId: string) => void;
  onLoadReferences: () => void;
  onCompare: () => void;
  onSendTo: () => void;
  onDeleteIntent: () => void;
  busy: boolean;
}) {
  const [showParameters, setShowParameters] = useState(false);
  const parameters = detail?.parameters ?? null;
  const parameterKeys = useMemo(() => parameters ? Object.keys(parameters) : [], [parameters]);
  if (!row) {
    return <section className="asset-browser__detail" aria-label="素材详情">
      <EmptyState title="未选择素材" detail="从素材网格或列表选择一项，才会按需读取它的版本、来源与引用。"/>
    </section>;
  }
  return <section className="asset-browser__detail" aria-label="素材详情">
    <header>
      <h3>{row.filename}</h3>
      <p className="asset-browser__meta">
        资产 ID {row.id} · {row.version === null ? `版本 ${ASSET_BROWSER_NOTICES.unverified}` : `v${row.version}`} · {row.digest}
      </p>
      <div className="asset-browser__badges">
        <Badge tone={stateTone(row.review_state)}>{ASSET_BROWSER_REVIEW_LABELS[row.review_state]}</Badge>
        {row.tags.map(tag => <Badge key={tag} tone="neutral">{ASSET_BROWSER_TAG_LABELS[tag]}</Badge>)}
        {row.deleted && <Badge tone="error">已删除（回收站）</Badge>}
      </div>
    </header>

    {detailState === 'FAILED' && <StatusMessage tone="error">
      {detailProblem?.message ?? ASSET_BROWSER_NOTICES.detailFailure}
      {detailProblem?.code && <span> · 代码 {detailProblem.code}</span>}
    </StatusMessage>}
    {detailState === 'LOADING' && <p className="asset-browser__note" role="status">正在读取资产详情…</p>}
    {detailState !== 'READY' && <div className="asset-browser__actions">
      <Button type="button" variant="ghost" disabled={busy || detailState === 'LOADING'}
        onClick={() => onReadDetail(row.id)}>按需读取详情</Button>
    </div>}

    {detail && <ProvenanceBlock asset={detail}/>}

    <section aria-label="参数">
      <h4>参数</h4>
      {parameters === null
        ? <p className="asset-browser__note">
          原 owner 未披露此素材的参数（{ASSET_BROWSER_NOTICES.unverified}）；内部标记与关系元数据不会出现在这里。
        </p>
        : <>
          <Button type="button" variant="ghost" aria-expanded={showParameters}
            onClick={() => setShowParameters(!showParameters)}>
            {showParameters ? '收起参数' : `展开参数（${parameterKeys.length} 项）`}
          </Button>
          {showParameters && <dl className="asset-browser__facts">{parameterKeys.map(key => <div key={key}>
            <dt>{key}</dt>
            <dd><code>{JSON.stringify(parameters[key])?.slice(0, 400) ?? 'null'}</code></dd>
          </div>)}</dl>}
        </>}
    </section>

    <UsageBlock impact={impact} unverified={referencesUnverified} busy={busy}
      onLoadReferences={onLoadReferences}/>

    <section aria-label="版本对比与传参">
      <h4>版本对比与传参</h4>
      <p className="asset-browser__note">
        {comparison
          ? `当前对比目标：${comparison.id} · ${comparison.version === null ? `v${ASSET_BROWSER_NOTICES.unverified}` : `v${comparison.version}`}`
          : '尚未选择对比版本。对比只显示差异，不会更新任何绑定。'}
      </p>
      <div className="asset-browser__actions">
        <Button type="button" variant="ghost" disabled={busy || !detail} onClick={onCompare}>打开版本对比</Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={onSendTo}>传给其他模块…</Button>
      </div>
      {!detail && <p className="asset-browser__note">打开对比前需要先按需读取详情（旧版本信息来自 owner 的来源投影）。</p>}
    </section>

    <section aria-label="删除影响">
      <h4>删除与影响范围</h4>
      <p className="asset-browser__note">{ASSET_BROWSER_NOTICES.noPhysicalDelete}</p>
      {deleteImpact
        ? <>
          <p className="asset-browser__note">{deleteImpact.message}</p>
          <p className="asset-browser__note">
            会影响 {deleteImpact.blocking_total} 处引用（其中 {deleteImpact.unverified_total} 处{ASSET_BROWSER_NOTICES.unverified}）；
            {deleteImpact.refusable_by_owner ? '原 owner 会拒绝这次删除。' : '当前没有阻塞引用。'}
            物理删除：{deleteImpact.physical_delete ? '是' : '否'}。
          </p>
          {deleteImpact.blocking.length > 0 && <ul className="asset-browser__list">
            {deleteImpact.blocking.map((entry, index) => <li key={`${entry.id ?? 'unknown'}-${index}`}>
              <strong>{entry.label ?? entry.id ?? ASSET_BROWSER_NOTICES.unverified}</strong>
              <span className="asset-browser__meta">
                {ASSET_BROWSER_IMPACT_GROUP_LABELS[entry.group]} · {ASSET_BROWSER_RELATIONSHIP_LABELS[entry.relationship]}
              </span>
            </li>)}
          </ul>}
        </>
        : <p className="asset-browser__note">尚未读取引用关系，删除影响范围未知（{ASSET_BROWSER_NOTICES.unverified}）。</p>}
      <Button type="button" variant="ghost" disabled={busy} onClick={onDeleteIntent}>查看可用删除范围</Button>
    </section>
  </section>;
}
