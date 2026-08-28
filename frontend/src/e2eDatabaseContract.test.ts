import {afterEach, describe, expect, it, vi} from 'vitest';

import {
  buildBackendEnvironment,
  buildFixtureEnvironment,
  buildFrontendEnvironment,
  resolveE2EDatabaseContract,
  type E2EEnvironment,
} from './e2eDatabaseContract';

const safeUrl = 'postgresql+psycopg://e2e-user:TEST_ONLY_PASSWORD@127.0.0.1:5432/ai_novel_studio_e2e_run_42?sslmode=require';
const safeName = 'ai_novel_studio_e2e_run_42';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe('E2E database environment contract', () => {
  it('requires only the explicit E2E URL and destructive confirmation', () => {
    expect(() => resolveE2EDatabaseContract({})).toThrow('E2E_DATABASE_URL_REQUIRED');
    expect(() => resolveE2EDatabaseContract({DATABASE_URL: safeUrl})).toThrow('E2E_DATABASE_URL_REQUIRED');
    expect(() => resolveE2EDatabaseContract({E2E_DATABASE_URL: safeUrl})).toThrow('E2E_DATABASE_CONFIRM_REQUIRED');
  });

  it('rejects unsafe schemes, paths, names and confirmations without disclosing input', () => {
    const invalid = [
      'mysql://user:password@db.example/ai_novel_studio_e2e_run_42',
      'postgresql://user:password@db.example/ai_novel_studio_e2e',
      'postgresql://user:password@db.example/ai_novel_studio_e2e_Upper',
      'postgresql://user:password@db.example/ai_novel_studio_e2e_run/extra',
      'postgresql://user:password@db.example/ai_novel_studio_e2e_%2fescape',
    ];
    for (const value of invalid) {
      try {
        resolveE2EDatabaseContract({E2E_DATABASE_URL: value, E2E_DATABASE_CONFIRM_DROP: safeName});
        throw new Error('unsafe URL accepted');
      } catch (error) {
        const message = String(error);
        expect(message).not.toContain(value);
        expect(message).not.toContain('password');
        expect(message).not.toContain('db.example');
      }
    }
    expect(() => resolveE2EDatabaseContract({E2E_DATABASE_URL: safeUrl, E2E_DATABASE_CONFIRM_DROP: 'wrong'}))
      .toThrow('E2E_DATABASE_CONFIRM_MISMATCH');
  });

  it.each([
    'dbname=production',
    'database=production',
    'host=other-host',
    'hostaddr=10.0.0.1',
    'port=9999',
    'user=other',
    'password=other',
    'service=production',
    'servicefile=production.conf',
    '%64bname=production',
    'DbNaMe=production',
  ])('rejects target-overriding query parameter %s without disclosure', (query) => {
    const url = safeUrl.replace('sslmode=require', query);
    expect(() => resolveE2EDatabaseContract({E2E_DATABASE_URL: url, E2E_DATABASE_CONFIRM_DROP: safeName}))
      .toThrow('E2E_DATABASE_QUERY_OVERRIDE_FORBIDDEN');
    try {
      resolveE2EDatabaseContract({E2E_DATABASE_URL: url, E2E_DATABASE_CONFIRM_DROP: safeName});
    } catch (error) {
      expect(String(error)).not.toContain(query);
      expect(String(error)).not.toContain('TEST_ONLY_PASSWORD');
      expect(String(error)).not.toContain('127.0.0.1');
    }
  });

  it.each(['sslmode=%', 'sslmode=%2', 'sslmode=%GG', 'sslmode=%FF'])('rejects malformed query encoding %s', (query) => {
    const url = safeUrl.replace('sslmode=require', query);
    expect(() => resolveE2EDatabaseContract({E2E_DATABASE_URL: url, E2E_DATABASE_CONFIRM_DROP: safeName}))
      .toThrow('E2E_DATABASE_URL_INVALID');
  });

  it('builds isolated child environments without mutating the parent', () => {
    const parent: E2EEnvironment = {E2E_DATABASE_URL: safeUrl, E2E_DATABASE_CONFIRM_DROP: safeName, DATABASE_URL: 'DO_NOT_USE', KEEP: 'yes'};
    const snapshot = {...parent};
    const contract = resolveE2EDatabaseContract(parent);
    const fixture = buildFixtureEnvironment(parent, contract);
    const backend = buildBackendEnvironment(parent, contract);
    const frontend = buildFrontendEnvironment(parent);
    expect(parent).toEqual(snapshot);
    expect(contract.databaseUrl).toMatch(/^postgresql:\/\//);
    expect(fixture.DATABASE_URL).toBeUndefined();
    expect(fixture.E2E_DATABASE_URL).toBe(contract.databaseUrl);
    expect(fixture.E2E_DATABASE_CONFIRM_DROP).toBe(safeName);
    expect(backend.DATABASE_URL).toBe(contract.databaseUrl);
    expect(backend.DATABASE_URL).not.toBe('DO_NOT_USE');
    expect(backend.E2E_DATABASE_URL).toBeUndefined();
    expect(backend.E2E_DATABASE_CONFIRM_DROP).toBeUndefined();
    expect(frontend.DATABASE_URL).toBeUndefined();
    expect(frontend.E2E_DATABASE_URL).toBeUndefined();
    expect(frontend.E2E_DATABASE_CONFIRM_DROP).toBeUndefined();
    expect(fixture.KEEP).toBe('yes');
    expect(backend.KEEP).toBe('yes');
    expect(frontend.KEEP).toBe('yes');
  });

  it('keeps the DSN out of Playwright commands and scopes each child environment', async () => {
    vi.stubEnv('E2E_DATABASE_URL', safeUrl);
    vi.stubEnv('E2E_DATABASE_CONFIRM_DROP', safeName);
    vi.stubEnv('DATABASE_URL', 'DO_NOT_USE');
    vi.mock('node:child_process', () => ({execFileSync: vi.fn()}));
    const configPath = '../playwright.config?e2e-contract-test';
    const loaded = await import(/* @vite-ignore */ configPath);
    const servers = loaded.default.webServer;
    expect(Array.isArray(servers)).toBe(true);
    expect(servers.map((server: {command: string}) => server.command).join('\n')).not.toContain(safeUrl);
    expect(servers[0].env.DATABASE_URL).toMatch(/^postgresql:\/\//);
    expect(servers[0].env.E2E_DATABASE_URL).toBeUndefined();
    expect(servers[0].env.E2E_DATABASE_CONFIRM_DROP).toBeUndefined();
    expect(servers[1].env.DATABASE_URL).toBeUndefined();
    expect(servers[1].env.E2E_DATABASE_URL).toBeUndefined();
    expect(servers[1].env.E2E_DATABASE_CONFIRM_DROP).toBeUndefined();
  });

  it('leaves the independent visual Playwright configuration loadable without E2E variables', async () => {
    const visualConfigPath = '../playwright.visual.config';
    const visual = await import(/* @vite-ignore */ visualConfigPath);
    expect(visual.default.testDir?.replaceAll('\\', '/')).toContain('tests/visual');
  });
});
