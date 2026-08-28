export type E2EEnvironment = Readonly<Record<string, string | undefined>>;

export interface E2EDatabaseContract {
  databaseName: string;
  databaseUrl: string;
  confirmation: string;
}

const PREFIX = 'ai_novel_studio_e2e_';
const DATABASE_NAME = /^ai_novel_studio_e2e_[a-z0-9_-]{1,42}$/;
const MALFORMED_PERCENT_ENCODING = /%(?![0-9a-f]{2})/i;
const TARGET_OVERRIDE_QUERY_KEYS = new Set([
  'dbname',
  'database',
  'host',
  'hostaddr',
  'port',
  'user',
  'password',
  'service',
  'servicefile',
]);

function contractError(code: string): never {
  throw new Error(code);
}

function validateQueryEncoding(query: string): void {
  if (MALFORMED_PERCENT_ENCODING.test(query)) contractError('E2E_DATABASE_URL_INVALID');
  try {
    for (const pair of query.replace(/^\?/, '').split('&')) {
      for (const component of pair.split('=', 2)) decodeURIComponent(component.replaceAll('+', ' '));
    }
  } catch {
    contractError('E2E_DATABASE_URL_INVALID');
  }
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
  validateQueryEncoding(parsed.search);
  for (const key of parsed.searchParams.keys()) {
    if (TARGET_OVERRIDE_QUERY_KEYS.has(key.toLowerCase())) {
      contractError('E2E_DATABASE_QUERY_OVERRIDE_FORBIDDEN');
    }
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

function withoutDatabaseVariables(env: E2EEnvironment): Record<string, string | undefined> {
  const copy = {...env};
  delete copy.DATABASE_URL;
  delete copy.E2E_DATABASE_URL;
  delete copy.E2E_DATABASE_CONFIRM_DROP;
  return copy;
}

export function buildFixtureEnvironment(
  env: E2EEnvironment,
  contract: E2EDatabaseContract,
): Record<string, string | undefined> {
  return {
    ...withoutDatabaseVariables(env),
    E2E_DATABASE_URL: contract.databaseUrl,
    E2E_DATABASE_CONFIRM_DROP: contract.confirmation,
  };
}

export function buildBackendEnvironment(
  env: E2EEnvironment,
  contract: E2EDatabaseContract,
): Record<string, string | undefined> {
  return {
    ...withoutDatabaseVariables(env),
    DATABASE_URL: contract.databaseUrl,
  };
}

export function buildFrontendEnvironment(env: E2EEnvironment): Record<string, string | undefined> {
  return withoutDatabaseVariables(env);
}
