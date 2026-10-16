import { FIXTURE_PROJECT } from './taskCenterFixtures';

export const receiptTask = { authority: 'author_generation', id: 'job-1' };
export const receiptScope = { mode: 'local', novel_id: FIXTURE_PROJECT } as const;
/** Fields produced by ModelBrokerService.reserve/finalize; no live provider evidence. */
export function ledgerRow(patch: Record<string, unknown> = {}) {
  return { id: 'reservation-1', job_id: 'job-1', novel_id: FIXTURE_PROJECT, scope: receiptScope,
    created_by: 'local-author', provider_id: 'provider', model_id: 'model', currency: 'USD',
    reserve_microusd: 1200001, actual_microusd: 1000001, dispatched: true,
    status: 'SETTLED', cost_state: 'CALCULATED_FROM_REPORTED_USAGE',
    price: { currency: 'USD', reserve_microusd: 1200001, source: 'Published price fixture', version: 2, applicability: 'per_request' }, ...patch };
}
