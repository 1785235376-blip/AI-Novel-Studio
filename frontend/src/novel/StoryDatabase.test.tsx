// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {StoryDatabase} from './StoryDatabase';
afterEach(cleanup);

describe('StoryDatabase',()=>{
  const sections=[{kind:'characters' as const,records:[{id:'hero',title:'林遥',summary:'调查员'}]},{kind:'timeline' as const,records:[],loading:true},{kind:'world' as const,records:[],availability:'unavailable' as const}];
  it('shows passed records and selects without exposing ids',()=>{const select=vi.fn();render(<StoryDatabase sections={sections} activeKind="characters" onSelectKind={vi.fn()} onSelectRecord={select}/>);fireEvent.click(screen.getByText('林遥'));expect(select).toHaveBeenCalledWith('characters','hero');expect(screen.queryByText('hero')).toBeNull()});
  it('renders loading and unavailable states',()=>{const {rerender}=render(<StoryDatabase sections={sections} activeKind="timeline" onSelectKind={vi.fn()}/>);expect(screen.getByRole('status').textContent).toContain('正在加载时间线');rerender(<StoryDatabase sections={sections} activeKind="world" onSelectKind={vi.fn()}/>);expect(screen.getByText('世界观暂未开放')).toBeTruthy()});
});
