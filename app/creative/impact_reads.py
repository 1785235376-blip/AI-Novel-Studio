"""Original-owner, request-local read fences for intent-only DIF observations.

Initial Graph list/get use the existing public projections, including redaction.
Retained guards re-enter the original API authorization and compare owner metadata;
they never reopen an asset phase inside the DIF checkpoint transaction. No request,
credential, permission, or mutable projection is installed as global authority.
"""
from contextlib import contextmanager
from copy import deepcopy

from ..experimental.common import StaleSourceError
from ..experimental.storyboard_impact_adapter import (
    OwnerRead, GraphIdentity, graph_index_projection, graph_projection, storyboard_projection)


def _evidence_read(callback):
    """Sanitize before an inner original invoker maps owner validation errors."""
    try:
        return callback()
    except StaleSourceError:
        raise StaleSourceError('CHANGE_IMPACT_ORIGINAL_OWNER_SOURCE_CHANGED') from None
    except (ValueError, KeyError, TypeError):
        raise ValueError('CHANGE_IMPACT_ORIGINAL_OWNER_EVIDENCE_INVALID') from None


def bind_storyboard_reads(service, call):
    assets = getattr(service.adaptations, 'assets', None)
    impact = getattr(getattr(getattr(assets, 'workspace', None), 'lineage', None), 'change_impact', None)
    if impact is None:
        return  # Stripped owner configurations retain the DIF fail-closed path.

    def factory(request, token, branch):
        @contextmanager
        def read(nid, rid):
            def authorized(actor, scope, guard):
                from .storyboard import storyboard_receipt
                incarnation = service.store.incarnation(nid)

                def projection():
                    # The original controlled reader validates scope, incarnation,
                    # chapter/entity privacy and bounded parent document ancestry.
                    row, fresh = service.story_facts._document(nid, scope, rid)
                    return storyboard_projection(storyboard_receipt(row)), fresh

                value, freshness = _evidence_read(projection)

                def current():
                    guard()
                    if service.store.incarnation(nid) != incarnation or _evidence_read(projection) != (value, freshness):
                        raise StaleSourceError('CHANGE_IMPACT_STORYBOARD_OBSERVATION_CHANGED')
                    guard()

                current()
                return OwnerRead('STORYBOARD', nid, actor, deepcopy(scope), incarnation, value, current)

            # A missing project epoch is unavailable, never implicitly provisioned.
            with service.store.existing_owner_only():
                value = call(request, nid, token, branch, 'domain.read', authorized)
                value.guard()
                yield value
                value.guard()
        return read

    impact._storyboard_reader_factory = factory


def bind_graph_reads(service, invoke):
    impact = getattr(service.workspace.lineage, 'change_impact', None)
    if impact is None:
        return

    def factory(request, token, branch):
        def metadata(nid, scope, actor, rid=None):
            # This is an original Graph-owner metadata fence, under graph_invoke's
            # domain.read/Host guard. Never call this from a bare DIF write scope.
            state = service.store.read(nid, scope)
            if rid is not None:
                row = service._owned(nid, scope, actor, service.GRAPHS, rid, state)
                return {key: row[key] for key in GraphIdentity.model_fields}
            rows = []
            for key, row in state['collections'].get(service.GRAPHS, {}).items():
                if (isinstance(row, dict) and row.get('created_by') == actor
                        and row.get('definition', {}).get('schema_version') not in {6, 7}):
                    owned = service._owned(nid, scope, actor, service.GRAPHS, key, state)
                    rows.append({field: owned[field] for field in GraphIdentity.model_fields})
            return graph_index_projection({'items': sorted(rows, key=lambda item: item['id'])})

        def reader(rid=None):
            @contextmanager
            def read(nid, graph_id=None):
                target_id = graph_id if rid else None
                target = (service.GRAPHS, target_id) if rid else ('list', None)

                def authorized(actor, scope, guard):
                    incarnation, owner_guard = service._context(nid, scope, actor, guard)
                    def project():
                        original = (service.get(nid, scope, actor, target_id, owner_guard) if rid else
                                    service.list(nid, scope, actor, owner_guard))
                        return graph_projection(original) if rid else graph_index_projection(original)
                    value = _evidence_read(project)
                    pin = ({key: value[key] for key in GraphIdentity.model_fields} if rid else
                           {'items': sorted(value['items'], key=lambda item: item['id'])})

                    def current():
                        # Re-enter the SAME original invoker for every boundary,
                        # retaining dynamic Host/schema/feature/epoch admission.
                        def check(current_actor, current_scope, current_guard):
                            owner_guard(); current_guard()
                            if (current_actor, current_scope) != (actor, scope):
                                raise StaleSourceError('CHANGE_IMPACT_GRAPH_AUTHORITY_CHANGED')
                            if _evidence_read(lambda: metadata(nid, scope, actor, target_id)) != pin:
                                raise StaleSourceError('CHANGE_IMPACT_GRAPH_OBSERVATION_CHANGED')
                            owner_guard(); current_guard()
                        invoke(nid, token, branch, 'domain.read', check, request, target=target)

                    current()
                    return OwnerRead('GRAPH' if rid else 'GRAPH_INDEX', nid, actor, deepcopy(scope),
                                     incarnation, value, current)

                with service.store.existing_owner_only():
                    value = invoke(nid, token, branch, 'domain.read', authorized, request, target=target)
                    value.guard()
                    yield value
                    value.guard()
            return read

        return reader(), reader(True)

    impact._graph_reader_factory = factory
