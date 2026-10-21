// @vitest-environment jsdom
import {cleanup,render,screen,within} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import {CanvasAudioTemplateParameterComparison} from './CanvasAudioTemplateParameterComparison';
afterEach(cleanup);
it('shows all explicit source effects and the local values they will replace',()=>{
 render(<CanvasAudioTemplateParameterComparison source={{in_ms:100,out_ms:900,gain_db:-6,fade_in_ms:100,fade_out_ms:200}} current={{in_ms:0,out_ms:1000,gain_db:-3,fade_in_ms:50,fade_out_ms:50}}/>);
 const table=screen.getByRole('table',{name:'模板参数与本次任务对照'});expect(within(table).getAllByRole('row')).toHaveLength(6);
 expect(within(screen.getByRole('row',{name:/增益/})).getByText('-6 dB（本次覆盖）')).toBeTruthy();
 expect(within(screen.getByRole('row',{name:/淡出/})).getByText('50 ms')).toBeTruthy();
});
it('preserves absent effects as absent instead of projecting zero or clearing local settings',()=>{
 render(<CanvasAudioTemplateParameterComparison source={{in_ms:100,out_ms:900}} current={{in_ms:0,out_ms:1000,gain_db:-3,fade_out_ms:50}}/>);
 expect(screen.getAllByText('保留本次设置')).toHaveLength(3);expect(screen.getByText('-3 dB')).toBeTruthy();expect(screen.getByText('50 ms')).toBeTruthy();expect(screen.queryByText('0 dB（本次覆盖）')).toBeNull();
});
it('shows explicitly supplied zero as a real override and avoids guessing missing current values',()=>{
 render(<CanvasAudioTemplateParameterComparison source={{in_ms:0,out_ms:800,gain_db:0,fade_in_ms:0}}/>);
 expect(screen.getByText('0 dB（本次覆盖）')).toBeTruthy();expect(within(screen.getByRole('row',{name:/淡入/})).getByText('0 ms（本次覆盖）')).toBeTruthy();expect(screen.getAllByText('未提供当前值')).toHaveLength(5);
});
it('does not render arbitrary fields or nonnumeric current payloads',()=>{
 render(<CanvasAudioTemplateParameterComparison source={{in_ms:100,out_ms:900}} current={{in_ms:0,out_ms:1000,gain_db:'sk-private-value',token:'secret'} as any}/>);
 expect(screen.queryByText(/sk-private/)).toBeNull();expect(screen.queryByText('secret')).toBeNull();expect(screen.getByText('尚未核对')).toBeTruthy();
});
