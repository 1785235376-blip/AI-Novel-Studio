import type { CreativeClient } from './client';
import type { DirectorModelClient } from './directorModelClient';
import { checkedDirectorAdoptionReceipt, type DirectorAdoptionReceipt } from './directorObservationClient';
import { reviewedDirectorSnapshot } from './directorCanvasHandoff';

/** Explicit read-only reopening through the original receipt and export owners.
 * The returned pin is staged data, never permission to insert, save or run Graph.
 */
export async function readVerifiedModelDraft(
  model: Pick<DirectorModelClient, 'readAdoptedDraft'>,
  creative: Pick<CreativeClient, 'export'>,
  expected: DirectorAdoptionReceipt,
  assertCurrent: () => void,
  signal?: AbortSignal,
) {
  const receipt = checkedDirectorAdoptionReceipt(expected, expected.proposal_id);
  const current = () => {
    if (signal?.aborted) throw new DOMException('The read was cancelled.', 'AbortError');
    assertCurrent();
  };
  const verify = (value: DirectorAdoptionReceipt) => {
    const actual = checkedDirectorAdoptionReceipt(value, receipt.proposal_id);
    if (JSON.stringify(actual) !== JSON.stringify(receipt))
      throw new Error('导演采用回执已变化，请重新核对原审核结果。');
  };
  current();
  verify(await model.readAdoptedDraft(receipt.proposal_id, signal));
  current();
  const exported = await creative.export(receipt.document.document_id);
  current();
  // Snapshot before the final await: later transport-object mutation cannot
  // change the document that was checked or the returned handoff.
  const document = structuredClone(exported.document);
  const pin = reviewedDirectorSnapshot(
    { id: receipt.document.document_id, version: receipt.document.version },
    document, exported.document_digest,
    { id: receipt.document.document_id, version: receipt.document.version, digest: receipt.document.digest },
  );
  const source = document.source_documents?.[receipt.source_document_id];
  if (source?.version !== receipt.source_version || source.digest !== receipt.source_digest)
    throw new Error('导演草稿的原分镜来源不匹配，未交给画布。');
  verify(await model.readAdoptedDraft(receipt.proposal_id, signal));
  current();
  return { document, pin, receipt };
}
