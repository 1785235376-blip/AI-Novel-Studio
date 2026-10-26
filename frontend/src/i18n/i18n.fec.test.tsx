// [HERMIA-FE-20261025 MERGE-FEC i18n] fe-contracts strings exist in zh+en and switch with locale.
import {afterEach,expect,it} from 'vitest';
import {setLocale,t} from './index';
import {zhCN} from './zh-CN';
import {en} from './en';
import {AUDIO_HISTORY_TEXT} from '../workspace/media/audioHistoryText';
afterEach(()=>setLocale('zh-CN'));
const fc=Object.keys(zhCN).filter(k=>k.startsWith('fc.')) as (keyof typeof zhCN)[];
it('every fc.* key has a non-empty, non-Chinese en value',()=>{
  expect(fc.length).toBeGreaterThanOrEqual(25);
  for(const k of fc){expect(en[k],k).toBeTruthy();expect(/[\u4e00-\u9fff]/.test(en[k]),`${k} en has CJK`).toBe(false);}
});
it('zh keeps the fe-contracts wording; en switches',()=>{
  expect(t('fc.prod.loaded',{loaded:3,total:9})).toBe('已加载 3 条 · 本次读取匹配 9 条（只是这次读取的匹配数，不是全部任务总数）');
  expect(t('fc.tc.loadMore')).toBe('加载更多任务');
  expect(AUDIO_HISTORY_TEXT.assetRestore).toBe('撤销删除');
  expect(AUDIO_HISTORY_TEXT.assetHistory).toMatch(/暂不支持/);
  setLocale('en');
  expect(t('fc.prod.loaded',{loaded:3,total:9})).toBe('Loaded 3 · 9 matched in this read (matches for this read only, not the total number of tasks)');
  expect(t('fc.tc.loadMore')).toBe('Load more tasks');
  expect(AUDIO_HISTORY_TEXT.assetRestore).toBe('Undo delete');
  expect(AUDIO_HISTORY_TEXT.assetHistory).toMatch(/not supported/);
});
