// [HERMIA-FE-20261022 U5]
import {expect,it} from 'vitest';
import {statusText} from './StoryPlanningWorkspace';
it('translates UNASSIGNED / Draft for display only',()=>{expect(statusText('UNASSIGNED')).toBe('未分配');expect(statusText('Draft')).toBe('草稿');expect(statusText('DRAFT')).toBe('草稿');expect(statusText('')).toBe('未标记');expect(statusText('自定义')).toBe('自定义');});
