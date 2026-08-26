// @vitest-environment jsdom
import {render,screen,waitFor,cleanup} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {api,type CredentialStatus} from '../api';
import {AiControlCenter} from './AiControlCenter';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

it('distinguishes persistent credentials from a degraded process-only vault',async()=>{
  vi.spyOn(api,'credentialStatus').mockImplementation(async provider=>({provider,configured:provider==='deepseek',backend:'memory',persistent:false,degraded:true,degraded_reason:'KEYRING_BACKEND_UNUSABLE',secret:null}) as CredentialStatus);
  vi.spyOn(api,'textModels').mockResolvedValue([]);
  vi.spyOn(api,'multimodalHealth').mockResolvedValue({});
  vi.spyOn(api,'userPreferences').mockResolvedValue({enabled:true,share_enabled:false,harness_enabled:false,items:[]});
  vi.spyOn(api,'harnessStatus').mockResolvedValue({configured:false,reachable:false});
  vi.spyOn(api,'harnessProcess').mockResolvedValue({running:false,pid:null});
  vi.spyOn(api,'harnessAccessAudit').mockResolvedValue({items:[]});
  vi.spyOn(api,'releaseReadiness').mockResolvedValue({status:'DEGRADED',profile:'local',checks:{vault:{status:'DEGRADED',backend:'memory',persistent:false,degraded:true,degraded_reason:'KEYRING_BACKEND_UNUSABLE'},session_boundary:{status:'PASS',mode:'loopback_only',detail:'Local only'},providers:{status:'DEGRADED',text:{configured:true,reachable:true},image:{registered:0,configured:0},speech:{configured:false},vision:{configured:false}},packaged:{status:'SKIP',bootstrap:false,memory_fallback_allowed:true},plugin_runtime:{status:'DEFERRED',execution_supported:false,isolation:'DENY_ALL'}},blockers:[],warnings:['VAULT_MEMORY_BACKEND'],docs:{env:[]}});
  render(<AiControlCenter/>);
  await waitFor(()=>expect(screen.getByText('仅当前进程')).toBeTruthy());
  expect(screen.getAllByText(/KEYRING_BACKEND_UNUSABLE/).length).toBeGreaterThan(0);
  expect(screen.getByText('开发可用，尚未达到发布标准')).toBeTruthy();
  expect(screen.getByText('VAULT_MEMORY_BACKEND')).toBeTruthy();
});
