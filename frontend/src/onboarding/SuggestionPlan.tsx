import { Badge, Button } from '../ui/primitives';
import {
  PRODUCTION_WORKFLOW_MODULE_LABELS, STUDIO_ENTRY_CONTRACT, STUDIO_INTENT_LABELS,
} from './studioEntryTypes';
import type { StudioEntryController } from './useStudioEntry';
import './studioEntry.css';

const selectionText = (ids: string[]) => ids.map(id => STUDIO_INTENT_LABELS[id] ?? id).join('、') || '未选择（空白起步）';

/**
 * The recommended layout / module / node plan, derived only from the selected intents.
 * Adopting a plan writes the preference; it executes no generation, opens no job and
 * changes no asset.
 */
export function SuggestionPlan({ controller, onAdopt }: { controller: StudioEntryController; onAdopt: (planId: string) => void }) {
  const plans = controller.suggestions;
  return <section className="studio-entry-suggestion" aria-label="推荐方案">
    <header className="studio-entry-suggestion__header">
      <h3>推荐方案</h3>
      <Badge tone="neutral">只影响推荐布局</Badge>
    </header>
    <p className="studio-entry-suggestion__scope">{STUDIO_ENTRY_CONTRACT.notices.adopt_scope}</p>
    <ul className="studio-entry-suggestion__list">
      {plans.map(plan => {
        const adopted = controller.adoptedPlanId === plan.plan_id;
        return <li key={plan.plan_id} className="studio-entry-suggestion__plan">
          <article aria-label={`推荐方案 ${plan.title}`}>
            <header>
              <h4>{plan.title}</h4>
              {adopted && <Badge tone="success">已采用</Badge>}
              <Badge tone="info">{plan.preset}</Badge>
            </header>
            <p>布局：{plan.layout}</p>
            <p>模块：{plan.modules.map(id => PRODUCTION_WORKFLOW_MODULE_LABELS[id]).join('、')}</p>
            <p>节点：{plan.nodes.join(' → ')}</p>
            <p className="studio-entry-suggestion__note">{plan.note}</p>
            <Button
              variant={adopted ? 'secondary' : 'primary'}
              disabled={controller.saving || controller.state === 'denied' || controller.state === 'missing' || adopted}
              onClick={() => { controller.adoptPlan(plan.plan_id); onAdopt(plan.plan_id); }}
            >采用这个推荐方案（只写入偏好）</Button>
          </article>
        </li>;
      })}
    </ul>
    <p className="studio-entry-suggestion__basis">推荐依据：当前选择的创作意图（{selectionText(controller.selectedIntentIds)}）；推荐不限制任何模块或权限，也不代表任何内容已生成。</p>
  </section>;
}
