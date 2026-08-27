// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from '../api';
import {MediaProviderSettings} from './MediaProviderSettings';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>{vi.restoreAllMocks();host?.remove()});

describe('MediaProviderSettings',()=>{
  function setInput(input:HTMLInputElement,value:string){
    const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!;
    setter.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));
  }
  function providers(){
    vi.spyOn(api,'assetProviders').mockResolvedValue({items:[]} as any);
    vi.spyOn(api,'videoProviders').mockResolvedValue({items:[]} as any);
    vi.spyOn(api,'audioProviders').mockResolvedValue({domain:'AUDIO',routing_policy:'LOCAL_FIRST',items:[]} as any);
  }

  it('rejects non-http endpoints and missing independent credentials',async()=>{
    providers();host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<MediaProviderSettings/>);await Promise.resolve()});
    const endpoint=host.querySelector<HTMLInputElement>('#media-provider-endpoint')!;
    const model=host.querySelector<HTMLInputElement>('#media-provider-model')!;
    await act(async()=>{setInput(endpoint,'file:///tmp/model');setInput(model,'image-v1');host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await Promise.resolve()});
    expect(host.textContent).toContain('服务地址必须以 http:// 或 https:// 开头');
    expect(host.textContent).toContain('需要独立密钥');
    act(()=>root.unmount());
  });

  it('saves a custom provider key separately from its endpoint and model',async()=>{
    providers();const saveCredential=vi.spyOn(api,'saveCredential').mockResolvedValue({} as any);const configure=vi.spyOn(api,'configureAssetProvider').mockResolvedValue({} as any);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<MediaProviderSettings/>);await Promise.resolve()});
    const set=(selector:string,value:string)=>setInput(host.querySelector<HTMLInputElement>(selector)!,value);
    await act(async()=>{set('#media-provider-id','studio_cloud');set('#media-provider-endpoint','https://images.example/v1');set('#media-provider-model','image-pro');set('#media-provider-key','TEST_ONLY_SECRET');host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await Promise.resolve();await Promise.resolve()});
    expect(saveCredential).toHaveBeenCalledWith('studio_cloud','TEST_ONLY_SECRET');
    expect(configure).toHaveBeenCalledWith('studio_cloud',expect.objectContaining({endpoint:'https://images.example/v1',default_model:'image-pro'}));
    act(()=>root.unmount());
  });

  it('exposes audio cloud providers and saves a custom endpoint, capabilities, and vault key',async()=>{
    providers();const saveCredential=vi.spyOn(api,'saveCredential').mockResolvedValue({} as any);const configure=vi.spyOn(api,'configureAudioProvider').mockResolvedValue({} as any);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>{root.render(<MediaProviderSettings/>);await Promise.resolve()});
    await act(async()=>{(host.querySelectorAll('[role="tab"]')[2] as HTMLButtonElement).click();await Promise.resolve()});
    expect(host.textContent).toContain('声音');expect(host.textContent).toContain('语音合成');expect(host.textContent).toContain('视频同步音频');
    const set=(selector:string,value:string)=>setInput(host.querySelector<HTMLInputElement>(selector)!,value);
    await act(async()=>{set('#media-provider-id','custom-audio');set('#media-provider-endpoint','https://audio.example/v1');set('#media-provider-model','audio-pro');set('#media-provider-key','TEST_AUDIO_SECRET');host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await Promise.resolve();await Promise.resolve()});
    expect(saveCredential).toHaveBeenCalledWith('custom-audio','TEST_AUDIO_SECRET');
    expect(configure).toHaveBeenCalledWith('custom-audio',expect.objectContaining({endpoint:'https://audio.example/v1',default_model:'audio-pro',capabilities:['TTS']}));
    act(()=>root.unmount());
  });
});
