// @vitest-environment node
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Fountain} from 'fountain-js';
import {describe,expect,it} from 'vitest';

const root=fileURLToPath(new URL('../../../',import.meta.url));
function exportScript(character:string,action='THE DOOR\nIt opens slowly.',dialogue='First paragraph.\n\nSecond paragraph.'){
  const screenplay={title:'Synthetic screenplay',scenes:[{id:'scene',location:'ROOM',time:'DAY',action,dialogue:[{character,text:dialogue}]}]};
  const program='import json,sys; from app.industry_export_formats import screenplay_to_fountain; print(screenplay_to_fountain(json.load(sys.stdin),snapshot_id="snapshot-original"),end="")';
  return execFileSync(process.env.PYTHON||'python3',['-c',program],{cwd:root,input:JSON.stringify(screenplay),encoding:'utf8',stdio:['pipe','pipe','pipe']});
}

describe('complete independent fountain-js 1.2.4 parser',()=>{
  it.each(['ALICE','小明','小明Alex','007','McCLANE','Саша','R2D2','ALICE (V.O.)'])('retains %s as a character and paragraphs as dialogue',character=>{
    const parsed=new Fountain().parse(exportScript(character),true);
    expect(parsed.tokens?.filter(token=>token.type==='character').map(token=>token.text)).toEqual([character]);
    expect(parsed.tokens?.filter(token=>token.type==='dialogue').map(token=>token.text)).toEqual(['First paragraph.\n\nSecond paragraph.']);
    expect(parsed.tokens?.filter(token=>token.type==='action').map(token=>token.text)).toEqual(['THE DOOR\nIt opens slowly.']);
    expect(parsed.html.script).not.toContain('Source-Versions');
    expect(parsed.html.title_page).toContain('snapshot-original');
  });
  it.each(['INT. FAKE - NIGHT','# Not a section','= Not a synopsis','===','@NotACharacter','~Not lyrics','>Not a transition','> CENTERED <','CUT TO:','> CUT TO:'])('preserves syntax-looking action %s',action=>{
    const parsed=new Fountain().parse(exportScript('007',action),true);
    expect(parsed.tokens?.filter(token=>token.type==='action').map(token=>token.text?.trimEnd())).toEqual([action]);
    expect(parsed.tokens?.filter(token=>token.type==='scene_heading')).toHaveLength(1);
    expect(parsed.tokens?.filter(token=>['transition','section','synopsis','lyrics','centered','page_break'].includes(token.type))).toHaveLength(0);
  });
  it('retains repeated paragraphs and literal inline emphasis/boneyards',()=>{
    const action='THE DOOR\nIt opens.\n\nINT. THE SIGN - DAY\n\nLiteral /* text */ and _underscores_ and *stars*.';
    const parsed=new Fountain().parse(exportScript('小明Alex',action,'One.\n\n\nFour.'),true);
    expect(parsed.tokens?.filter(token=>token.type==='action')).toHaveLength(3);
    expect(parsed.html.script).toContain('Literal /* text */ and _underscores_ and *stars*.');
    expect(parsed.tokens?.filter(token=>token.type==='dialogue').map(token=>token.text)).toEqual(['One.\n\n\nFour.']);
  });
  it('rejects ambiguous literal note delimiters instead of hiding authored prose',()=>{
    expect(()=>exportScript('ALICE','[[this must never disappear]]')).toThrow();
  });
  it('rejects multiline or dual-dialogue cue injection',()=>{
    expect(()=>exportScript('ALICE\nBOB')).toThrow();
    expect(()=>exportScript('ALICE ^')).toThrow();
  });
});
