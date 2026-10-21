/** Synthetic browser fixture of the real panel and AppShell. No parent Canvas owner or API. */
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AppShell } from '../../ui/AppShell';
import { CanvasBulkActionsPanel } from './CanvasBulkActionsPanel';
import { input } from './canvasBulkActions.testFixtures';
import '../../ui/ui.css';
import '../../ui/fixture.css';
import '../../ui/desktop-craft.css';
import '../creative.css';

export function mount() {
  const source = input(), ownerToken = {};
  if (new URLSearchParams(location.search).has('capacity')) {
    source.base = undefined; source.definition.groups = undefined;
    source.definition.cards = Array.from({ length: 24 }, (_, index) => ({ id: `Card${index}`, position: { x: index * 20, y: index * 40 },
      asset: { asset_id: `Asset${index}`, kind: 'image', version: 1, digest: 'a'.repeat(64) } }));
    source.selectedIds = source.definition.cards.map(card => card.id);
  }
  function Fixture() {
    const [edits, setEdits] = useState(0);
    return <AppShell module="IMAGE" onModuleChange={() => {}} actor="本地检查"
      scope={{ workspace: '创作工作区', project: '画布逐项确认检查', storyline: '主线', branch: '当前草稿' }}
      sidebar={<p>真实确认面板 · 合成元数据</p>}
      main={<CanvasBulkActionsPanel input={source} ownerToken={ownerToken} current busy={false} canApply isCurrent={() => true}
        onApply={() => { setEdits(count => count + 1); }} />}
      inspector={<p data-testid="draft-edits">父编辑通知：{edits}。此夹具不保存、不执行。</p>} status="本地 metadata 检查" />;
  }
  const host = document.createElement('div'); document.body.replaceChildren(host);
  createRoot(host).render(<Fixture />);
}
