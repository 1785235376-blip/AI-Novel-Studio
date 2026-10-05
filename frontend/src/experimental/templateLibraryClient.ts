import type { ExperimentalClient } from './api';
export type TemplatePackage = { schema_version: 1; manifest: { id: string; version: string; type: string; title: string; description: string; author: string; license: string; dependencies: string[]; provenance: string }; content: Record<string, any> };
export type CatalogEntry = { id: string; package: TemplatePackage; digest: string; builtin: boolean; installed: boolean; version: number; favorite: boolean; favorite_version: number; missing_dependencies: string[] };
export type TemplateInstance = { id: string; version: number; package_id: string; package_version: string; manifest: TemplatePackage['manifest']; content: Record<string, any>; edited: boolean; linked_target: { id: string; feature: string; version: number } | null };
export type TemplateDiff = { lines: string[]; truncated: boolean };
export type TemplatePreview = { package: TemplatePackage; expected_version: number; preview_digest: string; diff: TemplateDiff; missing_dependencies: string[] };
export type TemplateComparison = { preview_digest: string; expected_version: number; package_id: string; from_version: string; to_version: string; edited: boolean; diff: TemplateDiff; linked_target_will_change: false };
export function templateLibraryClient(client: ExperimentalClient) {
  const base = '/template-library'; const segment = encodeURIComponent;
  return {
    catalog: (signal?: AbortSignal) => client.get<{ items: CatalogEntry[]; types: string[]; remote_sync: string }>(base, signal),
    preview: (text: string) => client.post<TemplatePreview>(base + '/preview', { package: text }),
    install: (text: string, preview: TemplatePreview) => client.post(base + '/install', { package: text, expected_version: preview.expected_version, preview_digest: preview.preview_digest }),
    favorite: (entry: CatalogEntry) => client.post(base + '/packages/' + segment(entry.id) + '/favorite', { expected_version: entry.favorite_version, favorite: !entry.favorite }),
    uninstall: (entry: CatalogEntry) => client.post(base + '/packages/' + segment(entry.id) + '/uninstall', { expected_version: entry.version }),
    instances: (signal?: AbortSignal) => client.get<{ items: TemplateInstance[] }>(base + '/instances', signal),
    copy: (entry: CatalogEntry, requestId: string) => client.post<TemplateInstance>(base + '/instances', { package_id: entry.id, package_digest: entry.digest, request_id: requestId }),
    edit: (row: TemplateInstance, content: Record<string, any>) => client.put<TemplateInstance>(base + '/instances/' + segment(row.id), { expected_version: row.version, content }),
    compare: (row: TemplateInstance) => client.post<TemplateComparison>(base + '/instances/' + segment(row.id) + '/compare', { expected_version: row.version, package_id: row.package_id }),
    update: (row: TemplateInstance, comparison: TemplateComparison, overwrite: boolean) => client.post<TemplateInstance>(base + '/instances/' + segment(row.id) + '/update', { expected_version: row.version, package_id: row.package_id, preview_digest: comparison.preview_digest, overwrite_edited_copy: overwrite }),
    history: (id: string) => client.get<{ items: { version: number; package_version: string; content: unknown }[] }>(base + '/instances/' + segment(id) + '/history'),
    revert: (row: TemplateInstance, version: number) => client.post<TemplateInstance>(base + '/instances/' + segment(row.id) + '/revert', { expected_version: row.version, restore_version: version }),
  };
}
