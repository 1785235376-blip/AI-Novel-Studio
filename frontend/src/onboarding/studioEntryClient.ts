import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { STUDIO_INTENTS } from '../creative/studioWorkspacePreferences';
import {
  studioEntryProjects, studioIntentRequest, studioIntentState, studioProjectCreation,
} from './studioEntryContract';
import {
  STUDIO_ENTRY_CONTRACT, STUDIO_ENTRY_ERROR_CODES, STUDIO_INTENT_CATALOG, STUDIO_INTENT_IDS,
  type ProductionWorkflowIntentValueInput, type ProductionWorkflowPreset, type StudioEntryClient,
  type StudioEntryIntent, type StudioEntryProject, type StudioIntentDraft,
} from './studioEntryTypes';

/**
 * The saved preference owner's own GET/PUT projection of a project's intent
 * (`app/creative/workspace_models.py::WorkspacePreferences`). Only these keys are read.
 */
const PREFERENCE_KEYS = ['version', 'intents', 'preset', 'custom_intent'] as const;

/** Bounded, user-facing text per original owner error code. Unknown codes keep the transport text. */
const INTENT_FAILURES: Record<string, string> = {
  [STUDIO_ENTRY_ERROR_CODES.conflict]: '创作意图已被其他会话更新。当前输入仍保留，请核对最新版本后重新提交。',
  [STUDIO_ENTRY_ERROR_CODES.invalid]: '服务端未接受这次创作意图。当前输入仍保留，请核对意图标识与自定义名称。',
  [STUDIO_ENTRY_ERROR_CODES.authorityInvalid]: '当前会话无权修改创作意图。请重新核对身份与项目范围。',
  [STUDIO_ENTRY_ERROR_CODES.authorityChanged]: '身份或项目范围已变化，创作意图未保存。请重新打开工作区。',
};

function invalid(): never {
  throw new ApiError({ status: 200, code: STUDIO_ENTRY_ERROR_CODES.responseInvalid, message: STUDIO_ENTRY_CONTRACT.messages.response_invalid });
}
function refusal(reason: unknown, fallback: string): never {
  if (!(reason instanceof ApiError)) {
    throw new ApiError({ status: 0, code: STUDIO_ENTRY_ERROR_CODES.readFailed, message: fallback });
  }
  const problem = reason.problem;
  if (problem.code === STUDIO_ENTRY_ERROR_CODES.responseInvalid) throw reason;
  if (reason.status === 404) {
    throw new ApiError({ ...problem, code: STUDIO_ENTRY_ERROR_CODES.projectMissing, message: STUDIO_ENTRY_CONTRACT.messages.project_missing });
  }
  if (reason.status === 401) {
    throw new ApiError({ ...problem, message: STUDIO_ENTRY_CONTRACT.messages.denied });
  }
  if (reason.status === 403) {
    const message = INTENT_FAILURES[problem.code];
    throw message ? new ApiError({ ...problem, message }) : reason;
  }
  const message = INTENT_FAILURES[problem.code];
  throw message ? new ApiError({ ...problem, message }) : reason;
}

/**
 * Map the saved preference projection onto the Phase 7 `creative_intent` shape without
 * inventing anything: the vocabulary comes from the existing label catalog, a saved
 * literal selects its own entry, and only the author's own `custom_intent` provides the
 * custom label. A label the owner did not save stays the catalog's default text.
 */
export function studioIntentFromPreferences(value: unknown): StudioEntryIntent {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !(PREFERENCE_KEYS as readonly string[]).includes(key))) invalid();
  const { version, intents, preset, custom_intent: customIntent } = row;
  if (typeof version !== 'number' || !Number.isSafeInteger(version) || version < 0) invalid();
  if (!Array.isArray(intents) || intents.length > STUDIO_INTENTS.length
    || intents.some(item => typeof item !== 'string' || !STUDIO_INTENTS.some(([id]) => id === item))
    || new Set(intents).size !== intents.length) invalid();
  if (typeof preset !== 'string' || !/^[A-Z][A-Z0-9_]{0,31}$/.test(preset)) invalid();
  if (customIntent !== undefined && customIntent !== null && typeof customIntent !== 'string') invalid();
  const custom = typeof customIntent === 'string' ? customIntent.replace(/[\u0000-\u001f\u007f]/g, '').trim() : '';
  const saved = intents as string[];
  return {
    version,
    preset: preset as ProductionWorkflowPreset | null,
    values: STUDIO_INTENT_CATALOG.map(entry => ({
      intent_id: entry.intent_id, label: entry.custom && custom ? custom.slice(0, STUDIO_ENTRY_CONTRACT.bounds.label) : entry.label,
      selected: saved.includes(entry.intent_id.toUpperCase()), custom: entry.custom,
    })),
    editable: true, history_retained: true,
  };
}

/** The owner's `{expected_version, intents[], custom_intent}` replacement, rebuilt explicitly. */
export function studioPreferencesFromIntent(value: unknown): {
  expected_version: number; intents: string[]; custom_intent: string;
} {
  const draft = studioIntentRequest(value);
  const selected = draft.values.filter(item => item.selected);
  const custom = selected.find(item => item.intent_id === STUDIO_INTENT_CATALOG.find(entry => entry.custom)?.intent_id);
  return {
    expected_version: draft.expected_version,
    intents: selected.map(item => item.intent_id.toUpperCase()),
    custom_intent: custom?.label ?? '',
  };
}

/**
 * Inject the original studio transport. This client exposes one project list, one blank
 * project creation, one intent read and one versioned intent replacement — it never looks
 * up credentials, never invents a second project store and never dispatches work.
 */
export function createStudioEntryClient(transport: StudioGraphTransport, scopeProjectId?: string | null): StudioEntryClient {
  const captured = scopeProjectId ?? null;
  const foreign = (projectId: string) => captured !== null && captured !== '' && captured !== projectId;
  const mismatched = (): never => {
    throw new ApiError({ status: 403, code: STUDIO_ENTRY_ERROR_CODES.scopeMismatch, message: STUDIO_ENTRY_CONTRACT.messages.scope_mismatch });
  };
  const base = (projectId: string) => STUDIO_ENTRY_CONTRACT.paths.preferences(projectId);
  return {
    listProjects: async (signal?: AbortSignal): Promise<StudioEntryProject[]> => {
      try {
        return studioEntryProjects(await transport.json<unknown>(STUDIO_ENTRY_CONTRACT.paths.projects, 'GET', undefined, signal));
      } catch (reason) { refusal(reason, STUDIO_ENTRY_CONTRACT.messages.read_failed); }
    },
    createBlankProject: async (input, signal?: AbortSignal): Promise<ReturnType<typeof studioProjectCreation>> => {
      const title = typeof input?.title === 'string' ? input.title.trim() : '';
      if (!title || title.length > STUDIO_ENTRY_CONTRACT.bounds.title || /[\u0000-\u001f\u007f]/.test(title)) {
        throw new ApiError({ status: 200, code: STUDIO_ENTRY_ERROR_CODES.localInvalid, message: '项目名称需要 1–200 个字符。' });
      }
      const body: { title: string; id?: string } = { title };
      if (input.id !== undefined && input.id !== null && input.id !== '') {
        if (typeof input.id !== 'string' || input.id.length > STUDIO_ENTRY_CONTRACT.bounds.project_id || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(input.id)) {
          throw new ApiError({ status: 200, code: STUDIO_ENTRY_ERROR_CODES.localInvalid, message: '项目编号不可用，请检查后重试。' });
        }
        body.id = input.id;
      }
      try {
        return studioProjectCreation(await transport.json<unknown>(STUDIO_ENTRY_CONTRACT.paths.blank_project, 'POST', body, signal));
      } catch (reason) { refusal(reason, STUDIO_ENTRY_CONTRACT.messages.create_failed); }
    },
    readIntent: async (projectId: string, signal?: AbortSignal): Promise<StudioEntryIntent> => {
      if (typeof projectId !== 'string' || !projectId || foreign(projectId)) mismatched();
      try {
        const value = await transport.json<unknown>(base(projectId), 'GET', undefined, signal);
        return studioIntentState(studioIntentFromPreferences(value), projectId, { project_id: captured });
      } catch (reason) { refusal(reason, STUDIO_ENTRY_CONTRACT.messages.read_failed); }
    },
    saveIntent: async (projectId: string, draft: StudioIntentDraft, signal?: AbortSignal): Promise<StudioEntryIntent> => {
      if (typeof projectId !== 'string' || !projectId || foreign(projectId)) mismatched();
      // The request is validated before it leaves this client: an unknown key such as the
      // GET-only `custom` marker, or an unbounded label, is refused locally.
      const body = studioPreferencesFromIntent({
        expected_version: draft.expected_version, values: draft.values, ...(draft.preset === undefined ? {} : { preset: draft.preset }),
      });
      try {
        const value = await transport.json<unknown>(base(projectId), 'PUT', body, signal);
        return studioIntentState(studioIntentFromPreferences(value), projectId, { project_id: captured });
      } catch (reason) { refusal(reason, STUDIO_ENTRY_CONTRACT.messages.save_failed); }
    },
  };
}

/** One locally built entry: the catalog's own label, used when a new project has nothing saved yet. */
export function studioBlankIntentValues(): ProductionWorkflowIntentValueInput[] {
  return STUDIO_INTENT_CATALOG.map(entry => ({ intent_id: entry.intent_id, label: entry.label, selected: false }));
}

export function studioIntentIsSavable(values: ProductionWorkflowIntentValueInput[], customId: string | null): boolean {
  if (!values.some(item => item.selected)) return false;
  const custom = values.find(item => item.intent_id === customId);
  if (custom?.selected && !custom.label.trim()) return false;
  return values.every(item => STUDIO_INTENT_IDS.includes(item.intent_id) && !!item.label.trim() && item.label.length <= STUDIO_ENTRY_CONTRACT.bounds.label);
}
