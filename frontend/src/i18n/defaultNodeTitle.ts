/** [HERMIA-FE-20261031 VERA-EN] 画布新建节点默认标题「新<类型>」只在显示层翻译；存储值与服务端契约保持原中文。
 *  [HERMIA-FE-20261031 VERA-P3] 只翻译由 NODE_TYPES 标签生成的默认标题；用户自填标题（即使命中词典）原样显示。 */
import type { Locale } from './index';

/** NODE_TYPES 标签 → 默认标题英文名词短语（与 RebuildCanvas NODE_TYPES 同步，由测试锁定）。 */
export const DEFAULT_TITLE_EN: Readonly<Record<string, string>> = {
  文本输入: 'text input', 参考图: 'reference image', 资产引用: 'asset reference', 图片提示词: 'image prompt', 风格: 'style',
  生成图片: 'generated image', 放大: 'upscale', 人工审核: 'human review', 分镜规划: 'storyboard plan', 镜头: 'shot',
  镜头提示词: 'shot prompt', 导演备注: 'director note', 生成视频: 'generated video', 素材审核: 'media review', 送剪辑时间线: 'send to edit timeline',
};
export function displayNodeTitle(locale: Locale, title: string): string {
  if (locale === 'zh-CN' || !title || !title.startsWith('新')) return title;
  const en = Object.prototype.hasOwnProperty.call(DEFAULT_TITLE_EN, title.slice(1)) ? DEFAULT_TITLE_EN[title.slice(1)] : '';
  return en ? `New ${en}` : title;
}
