// [HERMIA-FE-20261031 DUALCANVAS-COMFY VERA-3 OBS] VIDEO 种子节点「镜头 n · 内容」：en 只翻译 UI 模板前缀；内容是剧本数据，原样保留；存储值不变。
import {describe, it, expect} from 'vitest';
import {displayNodeTitle} from './defaultNodeTitle';

describe('shot seed title display', () => {
  it('en translates the 镜头 n · prefix only', () => {
    expect(displayNodeTitle('en', '镜头 1 · 雾港码头')).toBe('Shot 1 · 雾港码头');
    expect(displayNodeTitle('en', '镜头 12 · Harbor')).toBe('Shot 12 · Harbor');
    expect(displayNodeTitle('en', '镜头 3 · 镜头 3')).toBe('Shot 3 · Shot 3');
  });
  it('zh-CN and non-matching titles are untouched', () => {
    expect(displayNodeTitle('zh-CN', '镜头 1 · 雾港码头')).toBe('镜头 1 · 雾港码头');
    expect(displayNodeTitle('en', '镜头一 雾港')).toBe('镜头一 雾港');
    expect(displayNodeTitle('en', '我的镜头 1 · x')).toBe('我的镜头 1 · x');
  });
});
