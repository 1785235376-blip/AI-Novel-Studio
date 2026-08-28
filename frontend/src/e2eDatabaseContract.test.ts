import {describe, expect, it} from 'vitest';

import {
  buildBackendEnvironment,
  buildFixtureEnvironment,
  resolveE2EDatabaseContract,
  type E2EEnvironment,
} from './e2eDatabaseContract';

const safeUrl = 'postgresql+psycopg://e2e-user:TEST_ONLY_PASSWORD@127.0.0.1:5432/ai_novel_studio_e2e_run_42?sslmode=require';
const safeName = 'ai_novel_studio_e2e_run_42';

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

  it('builds isolated child environments without mutating the parent', () => {
    const parent: E2EEnvironment = {E2E_DATABASE_URL: safeUrl, E2E_DATABASE_CONFIRM_DROP: safeName, DATABASE_URL: 'DO_NOT_USE', KEEP: 'yes'};
    const snapshot = {...parent};
    const contract = resolveE2EDatabaseContract(parent);
    const fixture = buildFixtureEnvironment(parent, contract);
    const backend = buildBackendEnvironment(parent, contract);
    expect(parent).toEqual(snapshot);
    expect(contract.databaseUrl).toMatch(/^postgresql:\/\//);
    expect(fixture.DATABASE_URL).toBeUndefined();
    expect(fixture.E2E_DATABASE_URL).toBe(contract.databaseUrl);
    expect(fixture.E2E_DATABASE_CONFIRM_DROP).toBe(safeName);
    expect(backend.DATABASE_URL).toBe(contract.databaseUrl);
    expect(backend.DATABASE_URL).not.toBe('DO_NOT_USE');
  });

  it('leaves the independent visual Playwright configuration loadable without E2E variables', async () => {
    const visualConfigPath = '../playwright.visual.config';
    const visual = await import(/* @vite-ignore */ visualConfigPath);
    expect(visual.default.testDir?.replaceAll('\\', '/')).toContain('tests/visual');
  });
});
