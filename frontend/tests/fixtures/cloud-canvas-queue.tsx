import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ImageRebuild, type ImageView} from '../../src/rebuild/image/ImageRebuild';
import '../../src/style.css';
import '../../src/ui/tokens.css';
import '../../src/ui/ui.css';
import '../../src/rebuild/rebuild.css';

// Actual production components; HTTP is intercepted only by the Playwright test.
// This fixture does not stand in for a File backend, provider execution or media review.
function CloudCanvasQueueFixture() {
  const [view, setView] = useState<ImageView>('dual');
  return <div className="app-shell" data-module="IMAGE" style={{gridTemplateRows: 'auto minmax(0, 1fr)'}}>
    <header data-testid="frontend-fixture-banner" style={{padding: 'var(--space-2) var(--space-3)', borderBottom: 'var(--border-default)'}}>
      仅前端模拟接口验证 · 真实图片组件 · 未连接 File 后端、生成 Provider 或媒体执行
    </header>
    <div style={{display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0}}>
      <ImageRebuild novelId="fixture-project" view={view} onViewChange={setView} shellMode="pro" />
    </div>
  </div>;
}

createRoot(document.getElementById('root')!).render(<CloudCanvasQueueFixture />);
