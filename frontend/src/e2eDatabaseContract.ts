export type E2EEnvironment = Readonly<Record<string, string | undefined>>;

export interface E2EDatabaseContract {
  databaseName: string;
  databaseUrl: string;
  confirmation: string;
}

const PREFIX = 'ai_novel_studio_e2e_';
const DATABASE_NAME = /^ai_novel_studio_e2e_[a-z0-9_-]{1,42}$/;

function contractError(code: string): never {
  throw new Error(code);
}

export function resolveE2EDatabaseContract(env: E2EEnvironment): E2EDatabaseContract {
  const raw = env.E2E_DATABASE_URL;
  if (!raw) contractError('E2E_DATABASE_URL_REQUIRED');
  if (!env.E2E_DATABASE_CONFIRM_DROP) contractError('E2E_DATABASE_CONFIRM_REQUIRED');

  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    contractError('E2E_DATABASE_URL_INVALID');
  }
  if (!['postgresql:', 'postgresql+psycopg:'].includes(parsed.protocol)) {
    contractError('E2E_DATABASE_SCHEME_UNSUPPORTED');
  }
  if (!parsed.hostname || parsed.hash || !parsed.pathname.startsWith('/') || parsed.pathname.slice(1).includes('/')) {
    contractError('E2E_DATABASE_URL_INVALID');
  }
  const encodedName = parsed.pathname.slice(1);
  if (!encodedName || encodedName.includes('%')) contractError('E2E_DATABASE_NAME_UNSAFE');
  const databaseName = encodedName;
  if (!DATABASE_NAME.test(databaseName) || databaseName === PREFIX.slice(0, -1)) {
    contractError('E2E_DATABASE_NAME_UNSAFE');
  }
  if (env.E2E_DATABASE_CONFIRM_DROP !== databaseName) {
    contractError('E2E_DATABASE_CONFIRM_MISMATCH');
  }
  parsed.protocol = 'postgresql:';
  return {databaseName, databaseUrl: parsed.toString(), confirmation: databaseName};
}

function withoutGenericDatabaseUrl(env: E2EEnvironment): Record<string, string | undefined> {
  const copy = {...env};
  delete copy.DATABASE_URL;
  return copy;
}

export function buildFixtureEnvironment(
  env: E2EEnvironment,
  contract: E2EDatabaseContract,
): Record<string, string | undefined> {
  return {
    ...withoutGenericDatabaseUrl(env),
    E2E_DATABASE_URL: contract.databaseUrl,
    E2E_DATABASE_CONFIRM_DROP: contract.confirmation,
  };
}

export function buildBackendEnvironment(
  env: E2EEnvironment,
  contract: E2EDatabaseContract,
): Record<string, string | undefined> {
  return {
    ...buildFixtureEnvironment(env, contract),
    DATABASE_URL: contract.databaseUrl,
  };
}
