// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {api} from '../api';
import {AudioGenerationPanel} from './AudioGenerationPanel';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

it('exposes non-TTS audio capabilities and submits with project scope',async()=>{
  vi.spyOn(api,'audioProviders').mockResolvedValue({domain:'AUDIO',routing_policy:'LOCAL_FIRST',items:[{provider_id:'stable-audio-local',display_name:'Stable Audio（本地）',endpoint:'http://127.0.0.1:8002/v1',default_model:'stable-audio',local:true,requires_credential:false,capabilities:['SFX','FOLEY','MUSIC','AUDIO_EDIT']}]});
  const generate=vi.spyOn(api,'audioGenerate').mockResolvedValue({domain:'AUDIO',kind:'SFX',provider_id:'stable-audio-local',model_id:'stable-audio',audio_uri:'https://example.test/result.mp3',status:'SUCCEEDED'});
  render(<AudioGenerationPanel novelId="novel-1"/>);
  expect(await screen.findByRole('option',{name:'音效'})).toBeTruthy();
  expect(screen.getByRole('option',{name:'拟音 / Foley'})).toBeTruthy();
  expect(screen.getByRole('option',{name:'音乐'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'生成音频'}));
  await waitFor(()=>expect(generate).toHaveBeenCalledWith(expect.objectContaining({provider_id:'auto',capability:'SFX',novel_id:'novel-1'})));
  expect(await screen.findByLabelText('音频制作结果')).toBeTruthy();
});

it('requires a safe source for audio editing',async()=>{
  vi.spyOn(api,'audioProviders').mockResolvedValue({domain:'AUDIO',routing_policy:'LOCAL_FIRST',items:[]});
  render(<AudioGenerationPanel novelId="novel-1"/>);
  fireEvent.change(screen.getByLabelText('音频制作类型'),{target:{value:'AUDIO_EDIT'}});
  expect((screen.getByRole('button',{name:'生成音频'}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText('来源必须使用 http(s)、data:audio 或 data:video 地址。')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('源音频地址'),{target:{value:'https://example.test/source.wav'}});
  expect((screen.getByRole('button',{name:'生成音频'}) as HTMLButtonElement).disabled).toBe(false);
});
