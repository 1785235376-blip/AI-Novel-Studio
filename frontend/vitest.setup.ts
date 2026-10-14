/**
 * Portable test-process environment for the suites that shell out to Python
 * (`src/novel/FountainParser.test.ts` and `src/creative/screenplayFountainParser.test.ts`).
 *
 * Those suites already honour `process.env.PYTHON || 'python3'`, the same
 * convention the repository's Playwright configs use. CI runs the frontend unit
 * suite on ubuntu-24.04, where `python3` exists; this Windows host only provides
 * `python`. Resolving the interpreter here — instead of editing a single test,
 * deleting a case or adding a skip — keeps CI behaviour identical and makes a
 * bare `pnpm test` work locally.
 *
 * `PYTHONUTF8=1` is the repository's established remedy for the Windows GBK
 * console corrupting text piped through a child process (for example `旅人`
 * arriving as `鏃呬汉`); it only affects this test process and its children.
 */
import { existsSync } from 'node:fs';

const configured = process.env.PYTHON?.trim();
const configuredIsMissingPath = !!configured && /[\\/]/.test(configured) && !existsSync(configured);
if (!configured || configuredIsMissingPath) {
  process.env.PYTHON = process.platform === 'win32' ? 'python' : 'python3';
}
process.env.PYTHONUTF8 ??= '1';
