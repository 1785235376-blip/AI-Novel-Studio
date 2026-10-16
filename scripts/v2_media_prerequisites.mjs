// Read-only prerequisites for the new synthetic VIDEO journey, not bootstrap.
// Never installs software, changes PATH, or substitutes a media/mock decoder.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execute = promisify(execFile);
export const MEDIA_PROBE_LIMITS = Object.freeze({
  timeout: 5000, maxBuffer: 64 * 1024, killSignal: 'SIGTERM', encoding: 'utf8',
});

export async function verifyInstalledMediaTools() {
  const receipt = { schema_version: 1, mode: 'EXISTING_TOOLS_ONLY', install_attempted: false,
    timeout_ms_per_tool: MEDIA_PROBE_LIMITS.timeout, tools: [], status: 'INCOMPLETE' };
  for (const tool of ['ffmpeg', 'ffprobe']) {
    const started = Date.now();
    try {
      const { stdout, stderr } = await execute(tool, ['-version'], MEDIA_PROBE_LIMITS);
      if (!stdout.startsWith(`${tool} version `)) throw new Error('INVALID_VERSION_RECEIPT');
      receipt.tools.push({ tool, status: 'PASS', elapsed_ms: Date.now() - started,
        version_output: stdout, stderr });
    } catch (cause) {
      receipt.status = 'FAIL';
      receipt.tools.push({ tool, status: 'FAIL', elapsed_ms: Date.now() - started,
        reason: cause?.code === 'ENOENT' ? 'MISSING'
          : cause?.killed || cause?.code === 'ERR_CHILD_PROCESS_STDIO_MAXBUFFER'
            ? 'TIMEOUT_OR_OUTPUT_LIMIT' : 'NONZERO_OR_INVALID_VERSION',
        exit_code: typeof cause?.code === 'number' ? cause.code : null });
      const failure = new Error(`V2_MEDIA_PREREQUISITE_FAILED: ${tool}; no installation or fallback attempted.`, { cause });
      failure.receipt = receipt;
      throw failure;
    }
  }
  receipt.status = 'PASS';
  return receipt;
}
