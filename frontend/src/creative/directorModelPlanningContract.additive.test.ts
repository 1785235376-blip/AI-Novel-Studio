import { expect, it } from 'vitest';
import captured from './directorModelWire.testFixture.json';
import { documentInput, type CreativeDocument } from './types';
import { checkedPlanningProjection } from './studioProductionGraphContract';

it('accepts the original owner model-reviewed DRAFT planning evidence without dropping it', () => {
  const receipt = captured.adopted.receipt.document;
  const projection = { document_snapshot: { id: receipt.document_id, version: receipt.version, digest: receipt.digest },
    content: documentInput(captured.draft as unknown as CreativeDocument) };
  const result = checkedPlanningProjection(projection, 'DIRECTOR');
  expect(result.content.director_notes[0].planning).toEqual(captured.draft.director_notes[0].planning);
});

it.each(['unknown-claim','missing-rationale','blank-reason','too-many-assumptions','too-many-evidence','invalid-field','invalid-index','no-basis','oversized-excerpt'] as const)('rejects invalid model planning %s without weakening old note fields', change => {
  const content = documentInput(captured.draft as unknown as CreativeDocument), planning: any = content.director_notes[0].planning;
  if (change==='unknown-claim') planning.semantic_verified=true;
  if (change==='missing-rationale') delete planning.rationale;
  if (change==='blank-reason') planning.sequence_reason='   ';
  if (change==='too-many-assumptions') planning.assumptions=Array(13).fill('Assumption');
  if (change==='too-many-evidence') planning.evidence=Array(13).fill(planning.evidence[0]);
  if (change==='invalid-field') planning.evidence[0].field='unknown';
  if (change==='invalid-index') planning.evidence[0].dialogue_index=true;
  if (change==='no-basis') { planning.evidence=[]; planning.assumptions=[]; }
  if (change==='oversized-excerpt') planning.evidence[0].excerpt='x'.repeat(2001);
  const d=captured.adopted.receipt.document;
  expect(()=>checkedPlanningProjection({document_snapshot:{id:d.document_id,version:d.version,digest:d.digest},content},'DIRECTOR')).toThrow();
});

it('preserves the original optional genre without adding it to legacy visual targets', async () => {
  const { checkedVisualTarget } = await import('./studioProductionGraphContract');
  const legacy = { style:'',atmosphere:'',reference_works:[],color:'',rhythm:'' };
  expect(checkedVisualTarget(legacy)).toEqual(legacy);
  expect(Object.hasOwn(checkedVisualTarget(legacy),'genre')).toBe(false);
  expect(checkedVisualTarget({...legacy,genre:'悬疑'}).genre).toBe('悬疑');
  expect(()=>checkedVisualTarget({...legacy,genre:'界'.repeat(2001)})).toThrow();
  expect(()=>checkedVisualTarget({...legacy,execute:true})).toThrow();
});
