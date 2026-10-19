/**
 * Portable server-command helpers shared by the live browser CI configs.
 *
 * Playwright executes webServer.command through the platform shell: cmd.exe on
 * Windows, /bin/sh elsewhere. A POSIX pipeline such as '2>&1 | tee file' cannot
 * start on Windows ("'tee' is not recognized as an internal or external
 * command"), so the whole browser job fails before its first assertion even
 * though the application itself is healthy. CI must be able to run the real
 * backend/Vite/browser journey on a Windows development host too.
 *
 * - Keep the POSIX tee pipeline where a POSIX shell provides it.
 * - Use cmd.exe redirection on Windows so the same receipt log is still written.
 * - Never default to a POSIX-only virtualenv path on Windows.
 */
export type ShellPlatform = NodeJS.Platform;

/** Append the receipt-log redirection in the syntax of the owning platform shell. */
export function withReceiptLog(
  command: string,
  logPath: string,
  platform: ShellPlatform = process.platform,
): string {
  if (platform === 'win32') return command + ' > "' + logPath + '" 2>&1';
  return command + ' 2>&1 | tee "' + logPath + '"';
}

/** Resolve the interpreter that boots the uvicorn/browser-test server. */
export function serverPython(
  root: string,
  platform: ShellPlatform = process.platform,
  environment: NodeJS.ProcessEnv = process.env,
): string {
  const configured = (environment.V2_PYTHON || environment.LOCAL_CI_PYTHON || '').trim();
  if (configured) return configured;
  if (platform === 'win32') return 'python';
  return String(root).replace(/[\\/]+$/, '') + '/.venv/bin/python';
}
