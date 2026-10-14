import {
  PRODUCTION_WORKFLOW_ASSET_KINDS, PRODUCTION_WORKFLOW_ASSET_KIND_LABELS,
  type ProductionWorkflowAssetOverview as AssetOverview,
} from './productionWorkflowTypes';

export type ProductionAssetOverviewProps = { overview: AssetOverview };

/** Measured counts only. Nothing here imports, exports, reviews or deletes an asset. */
export function ProductionAssetOverview({ overview }: ProductionAssetOverviewProps) {
  return <section className="production-asset-overview" aria-label="素材概览">
    <header><h3>素材概览</h3>
      <p>共 {overview.total} 项 · 待审核私有候选 {overview.private_pending_review} · 已审核 {overview.reviewed}</p>
    </header>
    <dl>
      {PRODUCTION_WORKFLOW_ASSET_KINDS.map(kind => <div key={kind}>
        <dt>{PRODUCTION_WORKFLOW_ASSET_KIND_LABELS[kind]}</dt><dd>{overview.by_kind[kind]}</dd>
      </div>)}
    </dl>
  </section>;
}
