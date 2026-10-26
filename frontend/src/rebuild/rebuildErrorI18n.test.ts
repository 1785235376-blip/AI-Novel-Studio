// [HERMIA-FE-20261025 VERA-097 P3] 英文界面不混入中文：rbError 固定文案、CJK 透传、模型中心固定文案
import { afterEach, describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import { setLocale, translateZh } from '../i18n';
import { rbError } from './rebuildApi';
import { MODEL_CENTER_CODES } from '../modelcenter/modelCenterTypes';

const CJK = /[\u3400-\u9fff]/;
const err = (status: number, message: string, code = `HTTP_${status}`) => new ApiError({ status, code, message } as any);

afterEach(() => setLocale('zh-CN'));

describe('rbError locale', () => {
  it('zh keeps the exact legacy copy and CJK passthrough', () => {
    setLocale('zh-CN');
    expect(rbError(err(500, 'x'))).toBe('后端返回错误（500）');
    expect(rbError(err(409, '章节已被锁定'))).toBe('章节已被锁定');
    expect(rbError(new Error('boom'))).toBe('后端不可用（无法连接）');
  });
  it('en never returns Chinese, including CJK server messages', () => {
    setLocale('en');
    const cases = [err(500, 'x'), err(409, '章节已被锁定'), err(404, 'nf'), err(401, 'a'), err(403, 'f'),
      err(400, 'x', 'EXPERIMENTAL_FEATURE_DISABLED'), new Error('boom')];
    for (const c of cases) expect(rbError(c)).not.toMatch(CJK);
    expect(rbError(err(409, '章节已被锁定'))).toBe('The backend returned an error (409)');
  });
});

describe('model center fixed copy', () => {
  it('every MODEL_CENTER_CODES message has an English translation via the dictionary', () => {
    for (const { message } of Object.values(MODEL_CENTER_CODES)) {
      const en = translateZh('en', message);
      expect(en, message).not.toMatch(CJK);
      expect(translateZh('zh-CN', message)).toBe(message);
    }
  });
});
