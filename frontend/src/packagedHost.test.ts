import {afterEach,describe,expect,it,vi} from 'vitest';
import {browserPersistenceForMode,clearProviderSessionCredential,sendHostPing,setProviderSessionCredential} from './packagedHost';

afterEach(()=>{Object.defineProperty(globalThis,'window',{value:undefined,configurable:true});vi.restoreAllMocks()});

describe('packaged desktop session storage boundary',()=>{
  it('returns no browser persistence adapter in packaged mode',()=>{
    const storage={setItem:vi.fn(),getItem:vi.fn(),removeItem:vi.fn()} as unknown as Storage;
    const selected=browserPersistenceForMode(true,storage);
    expect(selected).toBeUndefined();
    expect(storage.setItem).not.toHaveBeenCalled();
  });
  it('preserves the existing development adapter outside packaged mode',()=>{
    const storage={} as Storage;
    expect(browserPersistenceForMode(false,storage)).toBe(storage);
  });
});

describe('narrow WebView host bridge',()=>{
  it('sends fixed ping when available',()=>{ const postMessage=vi.fn(); Object.defineProperty(globalThis,'window',{value:{chrome:{webview:{postMessage}}},configurable:true}); expect(sendHostPing()).toBe(true); expect(postMessage).toHaveBeenCalledWith({protocol:'ai-novel-webview/v1',type:'PING'}); });
  it('fails closed in browser',()=>{ Object.defineProperty(globalThis,'window',{value:{},configurable:true}); expect(sendHostPing()).toBe(false); });
  it('sends an allow-listed provider credential through the ephemeral bridge',()=>{ const postMessage=vi.fn(); Object.defineProperty(globalThis,'window',{value:{chrome:{webview:{postMessage}}},configurable:true}); expect(setProviderSessionCredential('openai','unit-test-secret')).toBe(true); expect(postMessage).toHaveBeenCalledWith({protocol:'ai-novel-webview-credential/v1',type:'SET_PROVIDER_CREDENTIAL',provider:'openai',credential:'unit-test-secret'}); });
  it('rejects unsupported or malformed credentials without messaging the host',()=>{ const postMessage=vi.fn(); Object.defineProperty(globalThis,'window',{value:{chrome:{webview:{postMessage}}},configurable:true}); expect(setProviderSessionCredential('unknown','unit-test-secret')).toBe(false); expect(setProviderSessionCredential('openai','bad\nvalue')).toBe(false); expect(clearProviderSessionCredential('unknown')).toBe(false); expect(postMessage).not.toHaveBeenCalled(); });
  it('clears an allow-listed provider without exposing a value',()=>{ const postMessage=vi.fn(); Object.defineProperty(globalThis,'window',{value:{chrome:{webview:{postMessage}}},configurable:true}); expect(clearProviderSessionCredential('gemini')).toBe(true); expect(postMessage).toHaveBeenCalledWith({protocol:'ai-novel-webview-credential/v1',type:'CLEAR_PROVIDER_CREDENTIAL',provider:'gemini'}); });
});
