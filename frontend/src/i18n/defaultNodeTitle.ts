/** [HERMIA-FE-20261031 VERA-EN] 画布新建节点默认标题「新<类型>」只在显示层翻译；存储值与服务端契约保持原中文。 */
import { translateZh, type Locale } from './index';

const HAN = /[\u4e00-\u9fff]/;
export function displayNodeTitle(locale: Locale, title: string): string {
  if (locale === 'zh-CN' || !title) return title;
  const m = /^新(.+)$/.exec(title);
  if (!m) return translateZh(locale, title);
  const label = translateZh(locale, m[1]);
  return HAN.test(label) ? title : `New ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
}
