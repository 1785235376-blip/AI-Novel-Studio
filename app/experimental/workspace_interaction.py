"""Actor-scoped interaction metadata owned by WorkspaceToolsService.

Only display/keyboard preferences are stored here. No commands execute and no
manuscript, permission, task or model authority is copied into this collection.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator

from .common import change_row, new_row
from .planning import StrictModel, digest
from ..services.v1_capability_service import CapabilityVersionConflict

SECTIONS = ('resume', 'search', 'tasks', 'diagnostics', 'guide')
COMMANDS = (
    {'id': 'open_resume', 'section': 'resume', 'label': '继续工作', 'shortcut': 'Mod+Shift+R'},
    {'id': 'open_search', 'section': 'search', 'label': '搜索与命令', 'shortcut': 'Mod+Shift+F'},
    {'id': 'open_tasks', 'section': 'tasks', 'label': '任务中心', 'shortcut': 'Mod+Shift+J'},
    {'id': 'open_diagnostics', 'section': 'diagnostics', 'label': '诊断包', 'shortcut': 'Mod+Shift+D'},
    {'id': 'open_guide', 'section': 'guide', 'label': '使用指引', 'shortcut': 'Mod+Shift+H'},
)
Command = Literal['open_resume', 'open_search', 'open_tasks', 'open_diagnostics', 'open_guide']
Chord = Literal['Mod+Shift+R', 'Mod+Shift+F', 'Mod+Shift+J', 'Mod+Shift+D', 'Mod+Shift+H']


class InteractionPreferences(StrictModel):
    keyboard_enabled: bool = False
    shortcuts: dict[Command, Chord] = Field(default_factory=lambda: {r['id']: r['shortcut'] for r in COMMANDS})
    announcements: Literal['polite', 'off'] = 'polite'
    reduced_motion: Literal['system', 'reduce'] = 'system'
    confirm_navigation_with_unsaved_input: Literal[True] = True

    @model_validator(mode='after')
    def unique_shortcuts(self):
        if len(set(self.shortcuts.values())) != len(self.shortcuts):
            raise ValueError('WORKSPACE_SHORTCUT_CONFLICT')
        return self


class InteractionIn(StrictModel):
    expected_version: int = Field(ge=0)
    preferences: InteractionPreferences


class InteractionVersionIn(StrictModel):
    expected_version: int = Field(ge=0)


class InteractionRestoreIn(InteractionVersionIn):
    source_version: int = Field(ge=1)


class CommandResolveIn(StrictModel):
    command_id: Command
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class WorkspaceInteractionMixin:
    INTERACTION = 'workspace_interaction_v1'

    def _interaction_row(self, ctx, doc=None):
        self.novels.get(ctx.novel_id)
        doc = doc if doc is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = doc['collections'].get(self.INTERACTION, {}).get(self._owner(ctx.actor))
        if row and (row.get('novel_id') != ctx.novel_id or row.get('scope') != ctx.scope
                    or row.get('created_by') != ctx.actor):
            raise ValueError('WORKSPACE_INTERACTION_OWNER_INVALID')
        return row

    def interaction(self, ctx, reauthorize=lambda: None):
        reauthorize()
        row = self._interaction_row(ctx)
        recovery = False
        try:
            preferences = InteractionPreferences.model_validate(row['preferences'] if row else {}).model_dump()
        except (ValueError, KeyError, TypeError):
            preferences = InteractionPreferences().model_dump()
            recovery = True
        reauthorize()
        return {'schema_version': 1, 'version': row['version'] if row else 0,
                'preferences': preferences, 'state': 'RECOVERY_REQUIRED' if recovery else 'READY' if row else 'EMPTY',
                'recovery_required': recovery, 'history_limit': 20,
                'scope': deepcopy(ctx.scope), 'cancel': 'DISCARD_CLIENT_DRAFT_BEFORE_SAVE',
                'restart': 'DURABLE_SAVED_PREFERENCES_ONLY', 'permission': 'domain.write',
                'ui_contract': {'keyboard_scope': 'ACTIVE_WORKSPACE_ONLY', 'skip_editable': True,
                                'skip_composition': True, 'skip_repeated_key': True,
                                'unsaved_navigation': 'EXPLICIT_CONFIRMATION_REQUIRED',
                                'focus': 'PRESERVE_VISIBLE_FOCUS', 'model_or_task_dispatch': False}}

    def save_interaction(self, ctx, body, reauthorize=lambda: None):
        value = InteractionIn.model_validate(body)
        return self._write_interaction(ctx, value.expected_version, value.preferences.model_dump(), reauthorize)

    def _write_interaction(self, ctx, version, preferences, reauthorize):
        # A synchronous atomic commit has no background replay or hidden retry.
        reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            row = self._interaction_row(ctx, doc)
            reauthorize()
            if row:
                change_row(row, ctx.actor, version, lambda r: r.update(preferences=deepcopy(preferences), status='SAVED'))
                row['history'] = row['history'][-20:]
            else:
                if version != 0:
                    raise CapabilityVersionConflict({'version': 0})
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'preferences': deepcopy(preferences), 'status': 'SAVED'})
                doc['collections'].setdefault(self.INTERACTION, {})[self._owner(ctx.actor)] = row
            reauthorize()
        return self.interaction(ctx, reauthorize)

    def interaction_history(self, ctx, reauthorize=lambda: None):
        reauthorize()
        row = self._interaction_row(ctx)
        items = []
        for old in (row or {}).get('history', [])[-20:]:
            try:
                preferences = InteractionPreferences.model_validate(old['preferences']).model_dump()
            except (ValueError, KeyError, TypeError):
                items.append({'version': old['version'], 'state': 'UNAVAILABLE'})
                continue
            items.append({'version': old['version'], 'state': 'READY', 'preferences': preferences,
                          'updated_at': old.get('updated_at')})
        reauthorize()
        return {'items': items}

    def restore_interaction(self, ctx, body, reauthorize=lambda: None):
        value = InteractionRestoreIn.model_validate(body)
        # Reading and restoring in one transaction prevents a raced history source.
        reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            row = self._interaction_row(ctx, doc)
            if row is None:
                raise FileNotFoundError('interaction')
            if row['version'] != value.expected_version:
                raise CapabilityVersionConflict({'version': row['version']})
            old = next((r for r in row.get('history', []) if r.get('version') == value.source_version), None)
            if old is None:
                raise FileNotFoundError('interaction history')
            preferences = InteractionPreferences.model_validate(old['preferences']).model_dump()
            reauthorize()
            change_row(row, ctx.actor, value.expected_version,
                       lambda r: r.update(preferences=preferences, restored_from=value.source_version, status='SAVED'))
            row['history'] = row['history'][-20:]
            reauthorize()
        return self.interaction(ctx, reauthorize)

    def reset_interaction(self, ctx, expected_version, reauthorize=lambda: None):
        return self._write_interaction(ctx, expected_version, InteractionPreferences().model_dump(), reauthorize)

    def workspace_commands(self, ctx, reauthorize=lambda: None):
        current = self.interaction(ctx, reauthorize)
        enabled = current['preferences']['keyboard_enabled'] and not current['recovery_required']
        result = {'schema_version': 1, 'scope': deepcopy(ctx.scope), 'preferences_version': current['version'],
                  'state': 'RECOVERY_REQUIRED' if current['recovery_required'] else 'READY',
                  'dispatches_tasks': False, 'items': [
                      {**row, 'shortcut': current['preferences']['shortcuts'].get(row['id']) if enabled else None,
                       'action': 'NAVIGATE_WORKSPACE_SECTION', 'permission': 'domain.read',
                       'feature_flag': 'workspace_interaction_v1', 'requires_dirty_guard': True}
                      for row in COMMANDS]}
        # Revision binds to scope, actor and settings, without disclosing actor ID.
        result['revision'] = digest({'projection': result, 'owner': self._owner(ctx.actor)})
        reauthorize()
        return result

    def resolve_workspace_command(self, ctx, body, reauthorize=lambda: None):
        value = CommandResolveIn.model_validate(body)
        current = self.workspace_commands(ctx, reauthorize)
        if current['revision'] != value.expected_revision:
            raise HTTPException(409, {'code': 'WORKSPACE_COMMAND_STALE'})
        if current['state'] != 'READY':
            raise HTTPException(409, {'code': 'WORKSPACE_INTERACTION_RECOVERY_REQUIRED'})
        row = next(r for r in current['items'] if r['id'] == value.command_id)
        reauthorize()
        return {'kind': 'workspace_section', 'section': row['section'], 'command_id': row['id'],
                'revision': current['revision'], 'requires_dirty_guard': True, 'dispatched': False}
