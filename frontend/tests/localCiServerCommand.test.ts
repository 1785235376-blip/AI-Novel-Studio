import { describe, expect, it } from 'vitest';
import { serverPython, withReceiptLog } from '../local-ci-server-command';

describe('live browser CI server commands are shell-portable', () => {
  it('never emits the POSIX tee pipeline on Windows cmd.exe', () => {
    const command = withReceiptLog('python -m uvicorn app.main:app --port 8017',
      'C:\\runs\\backend.log', 'win32');
    expect(command).not.toContain('|');
    expect(command).not.toContain('tee');
    expect(command).toContain('> "C:\\runs\\backend.log" 2>&1');
  });

  it('keeps the tee receipt pipeline on POSIX shells', () => {
    const command = withReceiptLog('python -m uvicorn app.main:app --port 8017',
      '/runs/backend.log', 'linux');
    expect(command).toBe('python -m uvicorn app.main:app --port 8017 2>&1 | tee "/runs/backend.log"');
  });

  it('uses the explicitly configured interpreter on every platform', () => {
    expect(serverPython('/repo', 'win32', { V2_PYTHON: 'C:\\venv\\python.exe' }))
      .toBe('C:\\venv\\python.exe');
    expect(serverPython('/repo', 'linux', { LOCAL_CI_PYTHON: '/repo/venv/bin/python' }))
      .toBe('/repo/venv/bin/python');
  });

  it('never defaults to a POSIX-only virtualenv path on Windows', () => {
    expect(serverPython('/repo', 'win32', {})).toBe('python');
    expect(serverPython('/repo/', 'linux', {})).toBe('/repo/.venv/bin/python');
  });
});