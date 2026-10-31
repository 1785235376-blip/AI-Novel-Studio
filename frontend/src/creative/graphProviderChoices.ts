import type { ProductionProvider } from './studioProductionClient';

/** A saved graph stores only this tuple, so even identical duplicates are ambiguous. */
export function uniqueGraphProviders(values: ProductionProvider[]) {
  const tuple = (row: ProductionProvider) => JSON.stringify([row.operation_id, row.provider_id, row.model_id]);
  const counts = new Map<string, number>();
  values.forEach(row => counts.set(tuple(row), (counts.get(tuple(row)) || 0) + 1));
  return values.filter(row => counts.get(tuple(row)) === 1);
}
