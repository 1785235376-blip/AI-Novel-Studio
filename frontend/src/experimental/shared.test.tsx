// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Field } from './shared';
afterEach(cleanup);
describe('experimental field accessible associations', () => {
  it('labels a native select with only the field name, excluding its option text', () => {
    render(<Field label="规划模板"><select defaultValue="three-act"><option value="three-act">Three acts (optional)</option><option value="multiple-endings">Alternative endings</option></select></Field>);
    const control = screen.getByRole('combobox', { name: '规划模板' }) as HTMLSelectElement;
    expect(screen.getByLabelText('规划模板', { exact: true })).toBe(control);
    expect(control.id).toBeTruthy(); expect(control.labels).toHaveLength(1);
    expect(control.labels![0].htmlFor).toBe(control.id);
    expect(control.labels![0].textContent).toBe('规划模板');
    expect(control.labels![0].contains(control)).toBe(false);
    fireEvent.change(control, { target: { value: 'multiple-endings' } });
    expect(control.value).toBe('multiple-endings');
  });
  it('uses unique explicit IDs and preserves supplied control IDs', () => {
    render(<><Field label="标题"><input /></Field><Field label="说明"><textarea /></Field><Field label="审核领域"><select id="domain-filter"><option>world</option></select></Field></>);
    const title = screen.getByLabelText('标题') as HTMLInputElement;
    const description = screen.getByLabelText('说明') as HTMLTextAreaElement;
    const domain = screen.getByRole('combobox', { name: '审核领域' }) as HTMLSelectElement;
    expect(title.id).not.toBe(description.id); expect(domain.id).toBe('domain-filter');
    expect(domain.labels![0].htmlFor).toBe('domain-filter');
  });
});
