/** Read-only receipt checks over the original catalog API, never execution authority. */
export type ResourceDetailPin = Readonly<{ pluginId: string; resourceId: string; kind: string; sha256: string; schemaVersion: string }>;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const kinds = new Set(['writing_presets', 'workflow_templates', 'export_profiles']);
const MAX_BODY_BYTES = 1024 * 1024; // Original Plugin Contract v1 resource limit.
const invalid = (): never => { throw new Error('PLUGIN_RESOURCE_DETAIL_UNAVAILABLE'); };

export function resourceDetailPin(pluginId: string, catalog: unknown, resource: unknown): ResourceDetailPin | undefined {
  if (!object(catalog) || catalog.plugin_id !== pluginId || catalog.status !== 'MANIFEST_ACTIVE'
    || catalog.visible !== true || catalog.validated !== true || catalog.validation_status !== 'VALIDATED'
    || catalog.execution_supported !== false || catalog.isolation !== 'DENY_ALL' || catalog.error_code
    || catalog.invalid_resource_count !== 0 || !Array.isArray(catalog.items) || catalog.items.length > 100
    || catalog.total !== catalog.items.length || catalog.resource_count !== catalog.items.length) return;
  const ids = catalog.items.map(row => object(row) ? row.resource_id : undefined);
  if (ids.some(id => typeof id !== 'string' || !id) || new Set(ids).size !== ids.length || !object(resource)
    || resource.plugin_id !== pluginId || resource.validated !== true || typeof resource.resource_id !== 'string'
    || typeof resource.kind !== 'string' || !kinds.has(resource.kind) || !digest(resource.sha256) || resource.execution_supported !== false
    || typeof resource.schema_version !== 'string' || resource.schema_version.length > 80) return;
  const row = catalog.items.find(row => object(row) && row.resource_id === resource.resource_id);
  if (!object(row) || row.sha256 !== resource.sha256 || row.kind !== resource.kind || row.schema_version !== resource.schema_version
    || row.validated !== true || row.execution_supported !== false) return;
  return { pluginId, resourceId: resource.resource_id, kind: resource.kind, sha256: resource.sha256, schemaVersion: resource.schema_version };
}

export function resourceBodyText(value: unknown, pin: ResourceDetailPin): string {
  if (!object(value) || value.plugin_id !== pin.pluginId || value.resource_id !== pin.resourceId
    || value.kind !== pin.kind || value.sha256 !== pin.sha256 || value.schema_version !== pin.schemaVersion
    || value.validated !== true || value.execution_supported !== false || value.error_code
    || value.status !== undefined && value.status !== 'MANIFEST_ACTIVE'
    || value.validation_status !== undefined && value.validation_status !== 'VALIDATED'
    || !Object.prototype.hasOwnProperty.call(value, 'data')) invalid();
  const compact = JSON.stringify((value as Record<string, unknown>).data);
  if (typeof compact !== 'string' || new TextEncoder().encode(compact).length > MAX_BODY_BYTES) invalid();
  const pretty = JSON.stringify((value as Record<string, unknown>).data, null, 2);
  // Keep the entire JSON, using compact text when indentation would exceed the
  // original byte budget. No silently truncated or partially accepted body.
  return new TextEncoder().encode(pretty).length <= MAX_BODY_BYTES ? pretty : compact;
}
