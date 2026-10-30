/** [HERMIA-FE-20261031 VERA-EN] 默认标题「新生成图片」等在 en 下不显示中文；zh-CN 原样。 */
import { describe, expect, it } from 'vitest';
import { DEFAULT_TITLE_EN, displayNodeTitle } from './defaultNodeTitle';
import { NODE_TYPES } from '../rebuild/canvas/RebuildCanvas';

describe('displayNodeTitle', () => {
  it('translates every default 新<label> title in en', () => {
    expect(displayNodeTitle('en', '新生成图片')).toBe('New generated image');
    expect(displayNodeTitle('en', '新生成视频')).toBe('New generated video');
    for (const kind of ['image', 'video'] as const) for (const n of NODE_TYPES[kind]) {
      const out = displayNodeTitle('en', `新${n.label}`);
      expect(/[\u4e00-\u9fff]/.test(out), `${n.label} -> ${out}`).toBe(false);
    }
  });
  it('keeps zh-CN and user titles untouched', () => {
    expect(displayNodeTitle('zh-CN', '新生成图片')).toBe('新生成图片');
    expect(displayNodeTitle('en', 'My lighthouse')).toBe('My lighthouse');
  });
  it('does not translate user titles that merely hit the dictionary', () => {
    for (const s of ['风格', '生成图片', '重新读取配置', '新灯塔']) expect(displayNodeTitle('en', s)).toBe(s);
  });
});

describe('DEFAULT_TITLE_EN', () => {
  it('covers exactly the NODE_TYPES labels', () => {
    const labels = new Set([...NODE_TYPES.image, ...NODE_TYPES.video].map(x => x.label));
    expect(new Set(Object.keys(DEFAULT_TITLE_EN))).toEqual(labels);
  });
});
