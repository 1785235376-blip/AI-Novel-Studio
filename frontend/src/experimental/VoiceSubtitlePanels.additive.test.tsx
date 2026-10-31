// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { SubtitleTimelinePanel } from './SubtitleTimelinePanel';
import { experimentalClient } from './api';
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
const client=(nid='novel')=>experimentalClient(nid,{sessionToken:'trusted',scope:{branchId:'branch'} as any});
const track={id:'track',version:1,title:'Synthetic captions',status:'DRAFT',stale:false,asset_id:'audio',timebase:{numerator:1000,denominator:1},media:{duration_seconds:{numerator:2,denominator:1},waveform:{status:'UNAVAILABLE'}},cues:[{id:'cue',start_tick:0,end_tick:1000,text:'你好🌙',segment_id:null,overlap_reason:''}],speakers:{},warnings:[]};
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

it('reviews actionable caption transfer issues locally, focuses cues and preserves unsaved input',async()=>{
 const fetch=vi.fn(async(url:string)=>response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[track]}));vi.stubGlobal('fetch',fetch);
 render(<SubtitleTimelinePanel client={client()}/>);await screen.findByLabelText('字幕 1 文本');
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'Keep {literal} 🌙'}});
 fireEvent.change(screen.getByLabelText('字幕 1 结束 tick'),{target:{value:'3000'}});
 fireEvent.click(screen.getByRole('button',{name:'检查字幕交付兼容性'}));
 expect(screen.getByText(/当前未保存输入/)).toBeTruthy();expect(screen.getByText(/超过绑定媒体/)).toBeTruthy();
 fireEvent.click(screen.getAllByRole('button',{name:'定位字幕 1'})[0]);expect(document.activeElement).toBe(screen.getByLabelText('字幕 1 文本'));
 expect(fetch).toHaveBeenCalledTimes(2);expect((screen.getByRole('button',{name:'下载 SRT'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('字幕 1 文本'),{target:{value:'你好🌙'}});fireEvent.change(screen.getByLabelText('字幕 1 结束 tick'),{target:{value:'1000'}});
 expect(screen.getByText(/本地时间与纯文字检查通过/)).toBeTruthy();expect(screen.getByText(/原说话人 ID、重叠说明/)).toBeTruthy();
});
it('hides compatibility review while source refresh fails and resets on owner replacement',async()=>{
 let failing=false;const fetch=vi.fn(async(url:string)=>failing?response({detail:{code:'UNAVAILABLE'}},503):response(url.endsWith('/catalog')?{assets:[],plans:[]}:{items:[track]}));vi.stubGlobal('fetch',fetch);
 const view=render(<SubtitleTimelinePanel client={client()}/>);await screen.findByLabelText('字幕 1 文本');fireEvent.click(screen.getByRole('button',{name:'检查字幕交付兼容性'}));
 expect(screen.getByRole('region',{name:'字幕交付兼容性检查'})).toBeTruthy();failing=true;fireEvent.click(screen.getByRole('button',{name:'刷新字幕来源与记录'}));
 await screen.findAllByText(/UNAVAILABLE/);expect(screen.queryByRole('region',{name:'字幕交付兼容性检查'})).toBeNull();
 view.rerender(<SubtitleTimelinePanel client={client('other')}/>);expect(screen.queryByText('本地字幕交付检查')).toBeNull();
});
