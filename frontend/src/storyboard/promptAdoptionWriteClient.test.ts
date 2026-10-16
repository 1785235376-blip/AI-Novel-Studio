import { describe, expect, it, vi } from 'vitest';
import { adoptionRequestBody, checkedAdoptionCapability, checkedAdoptionCommit,
  createPromptAdoptionWriteClient } from './promptAdoptionWriteClient';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

const target = { documentId: 'doc-1', shotId: 'shot-1', version: 2, digest: 'd'.repeat(64) };
const request = { shot_id: 'shot-1', family_id: 'family-1', asset_id: 'asset-1', revision: 1,
  expected_digest: 'a'.repeat(64), expected_version: 2, expected_digest_target: 'd'.repeat(64), request_id: 'request-1' };
const projection = { contract: 'prompt-adoption/1', document_id: 'doc-1', version: 2,
  digest: 'd'.repeat(64), adoptions: [] };
const receipt = () => ({ committed: true, replayed: false, document_id: 'doc-1', shot_id: 'shot-1',
  version: 3, digest: 'e'.repeat(64), adoption: { contract: 'prompt-adoption/1', document_id: 'doc-1',
    ...request, digest: request.expected_digest, target_version: 2, target_digest: target.digest,
    result_version: 3, field: 'frame_prompt', digest_of: 'ORIGINAL_BYTES',
    source_binding_contract: 'prompt-adoption-bindings/1', source_bindings_verified: true } });

describe('Prompt adoption write boundary', () => {
  it.each([undefined, false, true])('only an explicit server true opens capability: %s', enabled => {
    expect(checkedAdoptionCapability({ ...projection, write_enabled: enabled }, 'doc-1').writeEnabled).toBe(enabled === true);
  });
  it.each(['true', 1, null])('refuses malformed capability %s', enabled => {
    expect(() => checkedAdoptionCapability({ ...projection, write_enabled: enabled }, 'doc-1')).toThrow();
  });
  it('refuses a foreign document and malformed digest', () => {
    expect(() => checkedAdoptionCapability(projection, 'foreign')).toThrow();
    expect(() => checkedAdoptionCapability({ ...projection, digest: 'fake' }, 'doc-1')).toThrow();
  });
  it('sends only the original DTO and repeats the identical idempotency key', async () => {
    const calls: unknown[][] = [];
    const transport: StudioGraphTransport = { async json<T>(...args: Parameters<StudioGraphTransport['json']>) {
      calls.push(args); return receipt() as T;
    } };
    const client = createPromptAdoptionWriteClient('p1', transport);
    const injected = { ...request, text: 'never sent', adopted_by: 'forged' };
    await client.adopt(target, injected); await client.adopt(target, injected);
    expect(calls[0]).toEqual(calls[1]);
    expect(calls[0]).toEqual(['/api/projects/p1/studio/documents/doc-1/shots/shot-1/prompt-adoption',
      'POST', request, undefined, 'request-1']);
    expect(adoptionRequestBody(injected)).toEqual(request);
  });
  it('refuses target/body disagreement before transport', async () => {
    const json = vi.fn();
    const client = createPromptAdoptionWriteClient('p1', { json });
    await expect(client.adopt({ ...target, version: 3 }, request)).rejects.toThrow();
    expect(json).not.toHaveBeenCalled();
  });
  it.each(['committed', 'version', 'document_id', 'shot_id', 'digest'])('does not accept a malformed commit %s', field => {
    expect(() => checkedAdoptionCommit({ ...receipt(), [field]: null }, target, request)).toThrow();
  });
  it.each(['family_id', 'asset_id', 'revision', 'request_id', 'digest', 'target_version',
    'target_digest', 'result_version', 'source_bindings_verified', 'source_binding_contract'])('pins proof %s', field => {
    const value = receipt();
    expect(() => checkedAdoptionCommit({ ...value, adoption: { ...value.adoption, [field]: null } }, target, request)).toThrow();
  });
  it('distinguishes replay history from its newer current document version', () => {
    expect(checkedAdoptionCommit({ ...receipt(), replayed: true, version: 7 }, target, request))
      .toMatchObject({ version: 7, resultVersion: 3, replayed: true });
    expect(() => checkedAdoptionCommit({ ...receipt(), version: 7 }, target, request)).toThrow();
  });
});
