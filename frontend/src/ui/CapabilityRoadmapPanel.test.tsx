// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it} from 'vitest';
import {CapabilityRoadmapPanel} from './CapabilityRoadmapPanel';

afterEach(()=>cleanup());

describe('capability roadmap',()=>{
  it('describes remaining cards honestly instead of as reserved-but-done services',()=>{
    render(<CapabilityRoadmapPanel/>);
    expect(screen.getByText('研究资料')).toBeTruthy();
    expect(screen.getByText('角色成长轨迹')).toBeTruthy();
    expect(screen.getByText(/execution_supported=false/)).toBeTruthy();
    expect(screen.getByText(/VIDEO_PROVIDER_NOT_CONFIGURED/)).toBeTruthy();
    expect(screen.getByText(/不会从正文自动抽取成长/)).toBeTruthy();
    expect(screen.getByText(/没有独立发布窗口/)).toBeTruthy();
    expect(screen.getAllByText('部分接入').length).toBeGreaterThanOrEqual(6);
    expect(screen.getByText('资产派生与记忆')).toBeTruthy();
    expect(screen.getByText('后端预留')).toBeTruthy();
  });
});
