// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {WorldSummaryEditor} from './StoryDatabase';
afterEach(cleanup);
describe('world summary editor',()=>{
  it('edits and explicitly saves the world setting summary',async()=>{
    const onSave=vi.fn().mockResolvedValue(undefined);render(<WorldSummaryEditor value="旧规则" onSave={onSave}/>);
    fireEvent.change(screen.getByLabelText('核心设定'),{target:{value:' 新世界规则 '}});
    fireEvent.click(screen.getByRole('button',{name:'保存世界观概要'}));
    expect(onSave).toHaveBeenCalledWith('新世界规则');
  });
});
