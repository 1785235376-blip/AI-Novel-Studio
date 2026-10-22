// @vitest-environment jsdom
// [HERMIA-FE-20261022 R5] 剪辑页按原型重做：上下两段、一页一主「导出成片…」、媒体池手递、本地编排诚实、导出未接通置灰。
import {afterEach, describe, expect, it, vi} from 'vitest';
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {EditRebuild, placeClip, fmtTc} from './EditRebuild';
import type {EditHandoffItem} from '../../ui/editHandoff';

let host: HTMLDivElement; let root: Root;
const h = (source: EditHandoffItem['source'], label: string): EditHandoffItem => ({id: `eh-${source}-${label}`, source, label, novelId: 'n1', at: 1});
function mount(handoffs: EditHandoffItem[] = [], onBackToVideo = vi.fn(), shellMode: 'basic' | 'pro' = 'basic') {
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  act(() => root.render(<EditRebuild novelId="n1" shellMode={shellMode} editable={false} handoffs={handoffs} onBackToVideo={onBackToVideo} />));
  return onBackToVideo;
}
const q = (s: string) => host.querySelector(s) as HTMLElement | null;
const btn = (t: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.trim() === t) as HTMLButtonElement | undefined;
afterEach(() => { act(() => root?.unmount()); host?.remove(); vi.restoreAllMocks(); });

describe('EditRebuild', () => {
  it('top/bottom split, only primary is 导出成片…, empty timeline has 3 tracks + honest copy', () => {
    const back = mount();
    expect(q('.nle-upper #nleBin')).toBeTruthy(); expect(q('.nle-upper .nle-mons [data-monitor="program"]')).toBeTruthy(); expect(q('.nle-upper .nle-insp')).toBeTruthy();
    expect(q('.nle-tl[data-timeline-hero="true"]')).toBeTruthy();
    const prim = [...host.querySelectorAll('.nle-top .nv-btn--primary')]; expect(prim.map(b => b.textContent)).toEqual(['导出成片…']);
    expect([...host.querySelectorAll('.nle-row')].map(r => r.getAttribute('data-track'))).toEqual(['V1', 'A1', 'S1']);
    expect(host.textContent).toContain('把镜头或声音拖到这里开始剪');
    expect(host.textContent).toContain('还没有可用素材');
    expect(host.textContent).toContain('点一个片段看它的入出点。'); // [HERMIA-FE-20261022 U5] 普通模式不提音量
    expect(host.textContent).not.toContain('入出点和音量');
    expect(q('[data-writable="false"]')).toBeTruthy();
    act(() => btn('回视频改镜头')!.click()); expect(back).toHaveBeenCalled();
  });
  it('handoff appears in pool; 放到时间线 places a local clip and selects it; cut splits at playhead', () => {
    mount([h('VIDEO', '镜头一'), h('AUDIO', '配音一')]);
    expect(q('[data-edit-handoff="received"]')).toBeTruthy();
    expect(q('[data-handoff-source="VIDEO"]')).toBeTruthy();
    act(() => q('[data-handoff-source="VIDEO"]')!.click());
    act(() => q('[data-bin-place="true"]')!.click());
    expect(host.querySelectorAll('.clip').length).toBe(1);
    expect(host.textContent).toContain('片段检视');
    expect(host.querySelectorAll('.nle-row').length).toBe(3); // [U4] 普通只三条基础轨
    act(() => (q('[data-bintab="audio"]') as HTMLButtonElement).click());
    expect(q('[data-handoff-source="AUDIO"]')).toBeTruthy();
  });
  it('export subview: MP4 disabled with reason; no internal ids on screen', () => {
    mount([h('ASSETS', '雾港远景')]);
    act(() => q('[data-edit-primary="export"]')!.click());
    const dis = q('[data-export-disabled="true"]') as HTMLButtonElement; expect(dis.disabled).toBe(true);
    expect(host.textContent).toContain('导出功能还没接好，现在点了不会生成文件。');
    expect(host.textContent).not.toMatch(/eh-|ClipInspector|NLE|edit_tl|W-UX/);
  });
  it('placeClip appends on track end; fmtTc', () => {
    const a = placeClip([], h('VIDEO', 'x')); expect(a).toMatchObject({track: 'V1', start: 0, dur: 5});
    expect(placeClip([a], h('IMAGE', 'y')).start).toBe(5);
    expect(placeClip([a], h('AUDIO', 'z')).track).toBe('A1');
    expect(fmtTc(65.5)).toBe('01:05.50');
  });
  it('[U4] mode gating: normal = V1/A1/字幕, no params/shortcuts; pro = 6 tracks + params + shortcut hints', () => {
    for (const mode of ['basic', 'pro'] as const) {
      mount([h('VIDEO', '镜头一')], vi.fn(), mode);
      act(() => q('[data-handoff-source="VIDEO"]')!.click()); act(() => q('[data-bin-place="true"]')!.click());
      const tracks = [...host.querySelectorAll('.nle-row')].map(r => r.getAttribute('data-track'));
      if (mode === 'basic') { expect(tracks).toEqual(['V1', 'A1', 'S1']); expect(q('[data-pro-only]')).toBeNull(); expect(host.textContent).not.toContain('透明度'); }
      else { expect(tracks).toEqual(['V1', 'V2', 'V3', 'A1', 'A2', 'S1']); expect(q('[data-pro-only="shortcuts"]')).toBeTruthy(); expect(host.textContent).toContain('透明度'); }
      expect(q('[data-writable="false"]')).toBeTruthy();
      act(() => root.unmount()); host.remove();
    }
  });
});
