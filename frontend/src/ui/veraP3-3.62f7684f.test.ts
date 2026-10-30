// [HERMIA-FE-20261031 VERA-P3-3] Vera 62f7684f 复审 P3-3：IMAGE/VIDEO 剩余英文词条
import {describe, expect, it} from 'vitest';
import {translateZh} from '../i18n';

describe('EN entries for remaining IMAGE/VIDEO copy (P3-3)', () => {
  it('translates every string', () => {
    for (const s of ['图片生成', '这里排镜头和画面关系；剪成片在剪辑页。', '卡片 · 参考素材 · 连线', '节点 · 素材引用 · 关系边', '三层工作区', '① 镜头脚本', '② 无限画布', '③ 内置导演台']) {
      const out = translateZh('en', s);
      expect(/[\u4e00-\u9fff]/.test(out), `${s} -> ${out}`).toBe(false);
    }
  });
});
