declare global {
  interface Window { __AI_NOVEL_PACKAGED_HOST__?: boolean; chrome?: { webview?: { postMessage?: (message: unknown) => void } } }
}

/**
 * Provider identifiers accepted by the DesktopHost credential channel.
 * Keep this list aligned with the backend vault and HostControlRuntime allow-list.
 */
export const PACKAGED_CREDENTIAL_PROVIDERS = [
  'deepseek',
  'openai',
  'claude',
  'gemini',
  'ddshub',
  'custom',
] as const;

export type PackagedCredentialProvider = typeof PACKAGED_CREDENTIAL_PROVIDERS[number];

function webViewBridge(): { postMessage: (message: unknown) => void } | undefined {
  const bridge = typeof window !== 'undefined' ? window.chrome?.webview : undefined;
  return bridge && typeof bridge.postMessage === 'function' ? bridge as { postMessage: (message: unknown) => void } : undefined;
}

function supportedProvider(provider: string): provider is PackagedCredentialProvider {
  return (PACKAGED_CREDENTIAL_PROVIDERS as readonly string[]).includes(provider);
}

/**
 * Send a provider credential through the ephemeral DesktopHost channel.
 * The value is deliberately never placed in browser storage or a URL.
 */
export function setProviderSessionCredential(provider: string, credential: string): boolean {
  if (!supportedProvider(provider) || typeof credential !== 'string' || !credential) return false;
  if (new TextEncoder().encode(credential).byteLength > 1024 || /[\0\r\n]/.test(credential)) return false;
  const bridge = webViewBridge();
  if (!bridge) return false;
  bridge.postMessage({
    protocol: 'ai-novel-webview-credential/v1',
    type: 'SET_PROVIDER_CREDENTIAL',
    provider,
    credential,
  });
  return true;
}

/** Clear one provider's ephemeral DesktopHost credential. */
export function clearProviderSessionCredential(provider: string): boolean {
  if (!supportedProvider(provider)) return false;
  const bridge = webViewBridge();
  if (!bridge) return false;
  bridge.postMessage({
    protocol: 'ai-novel-webview-credential/v1',
    type: 'CLEAR_PROVIDER_CREDENTIAL',
    provider,
  });
  return true;
}

export function sendHostPing(): boolean {
  const bridge = webViewBridge();
  if (!bridge) return false;
  bridge.postMessage({protocol: 'ai-novel-webview/v1', type: 'PING'});
  return true;
}

export function setDeepSeekSessionCredential(credential: string): boolean {
  return setProviderSessionCredential('deepseek', credential);
}

export function clearDeepSeekSessionCredential(): boolean {
  return clearProviderSessionCredential('deepseek');
}

export function isPackagedDesktopHost(): boolean {
  return typeof window !== 'undefined' && window.__AI_NOVEL_PACKAGED_HOST__ === true;
}

export function browserPersistenceForMode(packaged: boolean, storage: Storage | undefined): Storage | undefined {
  return packaged ? undefined : storage;
}
