// @vitest-environment jsdom
// [HERMIA-FE-20261024 M6] TaskCenter error alerts: human text, no raw code visible.
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { TaskCenter } from './TaskCenter';
import { problemText, TASK_CENTER_PROBLEM_FALLBACK } from './problemText';

afterEach(cleanup);

describe('[HERMIA-FE-20261024 M6] problemText', () => {
  it('keeps a human message and never returns the raw code', () => {
    expect(problemText({ code: 'STUDIO_REQUEST_FAILED', message: '原记录或功能当前不可用。' })).toBe('原记录或功能当前不可用。');
    expect(problemText({ code: 'STUDIO_REQUEST_FAILED', message: 'STUDIO_REQUEST_FAILED' })).toBe(TASK_CENTER_PROBLEM_FALLBACK);
    expect(problemText({ code: 'X', message: 'SOME_RAW_CODE' })).toBe(TASK_CENTER_PROBLEM_FALLBACK);
    expect(problemText({ code: 'X', message: '  ' })).toBe(TASK_CENTER_PROBLEM_FALLBACK);
    expect(problemText(undefined)).toBe(TASK_CENTER_PROBLEM_FALLBACK);
  });
});
