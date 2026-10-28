"""Asset display persistence using original Graph/scope/asset/project ownership.

Metadata binding is checked without loading image/video/audio payloads. Actual
preview/download remains an original Asset operation. No model, graph run or
binary ownership is introduced. API and UI mounting are a separate gate.
"""
from copy import deepcopy
from hashlib import sha256
from ..experimental.common import StaleSourceError, new_row, change_row, check_version
from ..experimental.store import canonical
from .project_store import BINDING
from .canvas_view_models import (CANVAS_VIEWS, CanvasViewDefinition, CanvasViewCreate, CanvasViewSave,
    CanvasViewRestore, CanvasImageNodeResult, CanvasImageNodeOrigin, CanvasViewResolveCreate, MAX_CANVAS_VIEWS)


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


class CreativeCanvasViews:
    def __init__(self, graph):
        self.graph, self.store, self.workspace = graph, graph.store, graph.workspace

    def _owned(self,nid,scope,actor,rid,state):
        row=self.graph._owned(nid,scope,actor,CANVAS_VIEWS,rid,state)
        definition=CanvasViewDefinition.model_validate(row.get('definition')).model_dump()
        if definition!=row['definition'] or digest(definition)!=row.get('definition_digest'):
            raise ValueError('CREATIVE_CANVAS_RECORD_CORRUPT')
        return row

    def _states(self,nid,scope,actor,definition,guard):
        if not self.graph.asset_inputs.in_phase(nid,scope,actor):
            raise ValueError('CREATIVE_CANVAS_ASSET_PHASE_REQUIRED')
        guard();cache={};states=[]
        for card in definition['cards']:
            reference=card['asset'];key=canonical(reference)
            if key not in cache:
                try:
                    asset=self.workspace._row(nid,scope,reference['asset_id'])
                    if asset.get('_owner_actor_id'):
                        raise FileNotFoundError(reference['asset_id'])
                    current=(asset['version'],asset['sha256'],asset['kind'])==(reference['version'],reference['digest'],reference['kind'])
                    cache[key]={'state':'CURRENT_METADATA' if current else 'STALE'}
                    if current:
                        cache[key]['filename']=asset['filename']
                except (FileNotFoundError,ValueError,KeyError):
                    cache[key]={'state':'UNAVAILABLE'}
            states.append({'card_id':card['id'],**cache[key]})
        guard();return states

    def _view(self,nid,scope,actor,row,guard):
        states=self._states(nid,scope,actor,row['definition'],guard)
        return self._presentation(nid,scope,row,states)

    @staticmethod
    def _presentation(nid,scope,row,states):
        definition=deepcopy(row['definition']);unavailable={item['card_id'] for item in states if item['state']=='UNAVAILABLE'}
        for card in definition['cards']:
            if card['id'] in unavailable:card.pop('asset')
        if definition.get('image_node_origin',{}).get('target',{}).get('node_id') in unavailable:
            definition.pop('image_node_origin',None)
        return {'id':row['id'],'version':row['version'],'definition':definition,
            'definition_digest':row['definition_digest'],'project_id':nid,'scope':deepcopy(scope),
            'created_at':row['created_at'],'updated_at':row['updated_at'],'reference_states':states,
            'execution_authority':False,'binary_content_verified':False,
            'capacity':{'history_used':len(row['history']),'record_bytes':len(canonical(row).encode('utf-8'))}}

    def list(self,nid,scope,actor,guard=lambda:None):
        _,current=self.graph._context(nid,scope,actor,guard)
        state=self.store.read(nid,scope);items=[]
        for rid,value in state['collections'].get(CANVAS_VIEWS,{}).items():
            if value.get('created_by')!=actor:continue
            row=self._owned(nid,scope,actor,rid,state)
            items.append({key:deepcopy(row[key]) for key in ('id','version','definition_digest','created_at','updated_at')}|
                {'title':row['definition']['title'],'card_count':len(row['definition']['cards'])})
        current();return {'items':sorted(items,key=lambda row:(row['created_at'],row['id'])),'execution_authority':False}

    def get(self,nid,scope,actor,rid,guard=lambda:None):
        _,current=self.graph._context(nid,scope,actor,guard)
        with self.graph.asset_inputs.phase(nid,scope,actor,current) as state:
            row=self._owned(nid,scope,actor,rid,state)
            result=self._view(nid,scope,actor,row,current)
            current();return result

    def create(self,nid,scope,actor,value,guard=lambda:None):
        body=CanvasViewCreate.model_validate(value)
        if body.definition.image_node_origin is not None:
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_ORIGINAL_OWNER_REQUIRED')
        incarnation,current=self.graph._context(nid,scope,actor,guard)
        definition=body.definition.model_dump();request_digest=digest(body.model_dump())
        intent=body.image_node_intent
        if intent is not None and (intent.project_id != nid or intent.scope != scope
                or intent.incarnation != incarnation or definition != intent.empty_definition()):
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_INTENT_CHANGED')
        with self.graph.asset_inputs.transaction(nid,scope,actor,current) as state:
            if any(item['state']!='CURRENT_METADATA' for item in self._states(nid,scope,actor,definition,current)):
                raise StaleSourceError('CREATIVE_CANVAS_SOURCE_CHANGED')
            rows=state['collections'].setdefault(CANVAS_VIEWS,{})
            matches=[row for row in rows.values() if row.get('created_by')==actor
                and row.get('novel_id')==nid and row.get('scope')==scope and row.get(BINDING)==incarnation
                and row.get('request_id')==body.request_id]
            if len(matches)>1:
                raise StaleSourceError('CREATIVE_CANVAS_CREATE_AMBIGUOUS')
            found=matches[0] if matches else None
            if found:
                if found.get('request_digest')!=request_digest:raise ValueError('CREATIVE_CANVAS_REQUEST_ID_REUSED')
                row=self._owned(nid,scope,actor,found['id'],state)
                if intent is not None and row.get('image_node_intent') != intent.model_dump():
                    raise StaleSourceError('CREATIVE_CANVAS_CREATE_INTENT_CHANGED')
                if intent is not None and (row['version'] != 1 or row['history']
                        or row['definition'] != definition or row['definition_digest'] != digest(definition)):
                    raise StaleSourceError('CREATIVE_CANVAS_CREATE_CHANGED')
            else:
                row=new_row(nid,scope,actor,{BINDING:incarnation,'definition':definition,
                    'definition_digest':digest(definition),'request_id':body.request_id,'request_digest':request_digest})
                if intent is not None:
                    row['image_node_intent']=intent.model_dump()
                rows[row['id']]=row
            self.graph._capacity(state);current();saved_id=row['id']
        return self.get(nid,scope,actor,saved_id,current)

    def resolve_create(self,nid,scope,actor,value,guard=lambda:None):
        with self.store.existing_owner_only(), self.workspace.store.existing_owner_only():
            return self._resolve_create(nid,scope,actor,value,guard)

    def _resolve_create(self,nid,scope,actor,value,guard):
        """Observe one original creation; absence never authorizes a resend.

        Original store.read supplies a consistent detached scope snapshot. No
        asset phase is needed for a strictly empty definition, and no raw scope
        transaction or project marker can be provisioned by this observation.
        A later queue still checks its original Canvas version and digest.
        """
        body=CanvasViewResolveCreate.model_validate(value)
        incarnation,current=self.graph._context(nid,scope,actor,guard)
        intent=body.image_node_intent
        if (body.expected_incarnation != incarnation or intent.incarnation != incarnation
                or intent.project_id != nid or intent.scope != scope):
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_CONTEXT_CHANGED')
        expected=CanvasViewCreate(request_id=body.request_id,expected_version=0,
            definition=intent.empty_definition(),image_node_intent=intent)
        current();state=self.store.read(nid,scope);current()
        collection=state['collections'].get(CANVAS_VIEWS,{})
        # The original owner permits eight views per scope. Corrupt oversized
        # collections fail before inspecting any record payload.
        if len(collection)>MAX_CANVAS_VIEWS:
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_AMBIGUOUS')
        rows=[row for row in collection.values()
            if row.get('created_by')==actor and row.get('novel_id')==nid
            and row.get('scope')==scope and row.get(BINDING)==incarnation]
        if len(rows)>MAX_CANVAS_VIEWS:
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_AMBIGUOUS')
        matches=[row for row in rows if row.get('request_id')==body.request_id]
        if not matches:
            raise FileNotFoundError(body.request_id)
        if len(matches)!=1:
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_AMBIGUOUS')
        row=self._owned(nid,scope,actor,matches[0]['id'],state)
        if (row.get('request_digest') != digest(expected.model_dump())
                or row.get('image_node_intent') != intent.model_dump()
                or row['version'] != 1 or row['history']
                or row['definition'] != expected.definition.model_dump()
                or row['definition_digest'] != digest(expected.definition.model_dump())):
            raise StaleSourceError('CREATIVE_CANVAS_CREATE_CHANGED')
        result={'contract':'studio-canvas-image-node-resolve/1','request_id':body.request_id,
            'image_node_intent':intent.model_dump(),'incarnation':incarnation,
            'canvas':self._presentation(nid,scope,row,[])}
        current();return result

    def save(self,nid,scope,actor,rid,value,guard=lambda:None):
        body=CanvasViewSave.model_validate(value)
        incarnation,current=self.graph._context(nid,scope,actor,guard)
        if body.expected_incarnation is not None and body.expected_incarnation != incarnation:
            raise StaleSourceError('CREATIVE_CANVAS_SAVE_INCARNATION_CHANGED')
        definition=body.definition.model_dump()
        captured=self._owned(nid,scope,actor,rid,self.store.read(nid,scope))
        check_version(captured,body.expected_version)
        old_origin=captured['definition'].get('image_node_origin')
        if definition.get('image_node_origin') != old_origin:
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_ORIGIN_CHANGED')
        proof=None
        if old_origin is not None:
            from .canvas_image_node import capture
            proof=capture(self,nid,scope,actor,old_origin,current)
        with self.graph.asset_inputs.transaction(nid,scope,actor,current) as state:
            row=self._owned(nid,scope,actor,rid,state);check_version(row,body.expected_version)
            if row['definition'].get('image_node_origin') != old_origin:
                raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_ORIGIN_CHANGED')
            if body.expected_definition_digest is not None and body.expected_definition_digest != row['definition_digest']:
                raise StaleSourceError('CREATIVE_CANVAS_SAVE_DEFINITION_CHANGED')
            if body.expected_card is not None:
                old_card = next((card for card in row['definition']['cards'] if card['id'] == body.expected_card.card_id), None)
                if (old_card is None or old_card['asset'] != body.expected_card.source.model_dump()
                        or self._states(nid,scope,actor,{'cards':[old_card]},current)[0]['state'] != 'CURRENT_METADATA'):
                    raise StaleSourceError('CREATIVE_CANVAS_RETURN_SOURCE_CHANGED')
            if any(item['state']!='CURRENT_METADATA' for item in self._states(nid,scope,actor,definition,current)):
                raise StaleSourceError('CREATIVE_CANVAS_SOURCE_CHANGED')
            if proof is not None:
                from .canvas_image_node import current_asset
                current_asset(self,nid,scope,actor,proof,current)
            change_row(row,actor,body.expected_version,lambda target:target.update(definition=deepcopy(definition),definition_digest=digest(definition)))
            self.graph._capacity(state);current()
        return self.get(nid,scope,actor,rid,current)

    def image_node_result(self,nid,scope,actor,rid,value,guard=lambda:None):
        """Explicitly attach one original formal result; never approve or run it."""
        from .canvas_image_node import capture, current_asset
        body=CanvasImageNodeResult.model_validate(value)
        incarnation,current=self.graph._context(nid,scope,actor,guard)
        if body.expected_incarnation != incarnation:
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_CONTEXT_CHANGED')
        runtime=self.graph.media_runtime
        if runtime is None:
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_OWNER_REQUIRED')
        # Job reads stay outside the original scope/asset transaction. A
        # terminal APPROVED original Job cannot be cancelled or replayed.
        job,context=runtime.production._row(nid,scope,actor,'image',body.job_id,current)
        target=context.get('command',{}).get('canvas_image_node')
        if target is None:
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_SOURCE_CHANGED')
        origin=CanvasImageNodeOrigin.model_validate({'contract':'studio-canvas-image-node-result/1',
            'target':target,'job_id':body.job_id,'job_version':body.job_version,
            'job_request_digest':body.job_request_digest,'asset':body.asset.model_dump()}).model_dump()
        target=origin['target']
        if (target['canvas_id'] != rid or target['canvas_version'] != body.expected_version
                or target['canvas_digest'] != body.expected_definition_digest
                or target['incarnation'] != body.expected_incarnation):
            raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_CONTEXT_CHANGED')
        proof=capture(self,nid,scope,actor,origin,current)
        with self.graph.asset_inputs.transaction(nid,scope,actor,current) as state:
            row=self._owned(nid,scope,actor,rid,state)
            current_asset(self,nid,scope,actor,proof,current)
            existing=row['definition'].get('image_node_origin')
            if existing == origin:
                # Exact explicit replay confirms the original association; it
                # neither moves a subsequently moved card nor appends history.
                pass
            else:
                check_version(row,body.expected_version)
                if (existing is not None or row['definition_digest'] != body.expected_definition_digest
                        or row['definition']['cards']):
                    raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_TARGET_CHANGED')
                definition=deepcopy(row['definition'])
                definition['cards']=[{'id':target['node_id'],'position':deepcopy(target['position']),
                    'asset':deepcopy(origin['asset'])}]
                definition['image_node_origin']=deepcopy(origin)
                definition=CanvasViewDefinition.model_validate(definition).model_dump()
                change_row(row,actor,body.expected_version,lambda item:item.update(
                    definition=definition,definition_digest=digest(definition)))
                self.graph._capacity(state)
            # Original owner writes may reenter this phase on the same thread.
            # Recheck the captured Asset pin after all Canvas mutations, while
            # the existing lease still excludes other-thread/process writers.
            current_asset(self,nid,scope,actor,proof,current)
            current()
        return self.get(nid,scope,actor,rid,current)

    def _history_entries(self, nid, scope, actor, row):
        # Original change_row snapshots are the only history authority. Never
        # trust a client-supplied definition or another record's snapshot.
        entries = [*row['history'], row]
        for version, entry in enumerate(entries, 1):
            if (not isinstance(entry, dict) or type(entry.get('version')) is not int
                    or entry['version'] != version or entry.get('id') != row['id']
                    or entry.get('novel_id') != nid or entry.get('scope') != scope
                    or entry.get('created_by') != actor or entry.get(BINDING) != row[BINDING]):
                raise ValueError('CREATIVE_CANVAS_HISTORY_CORRUPT')
            definition = CanvasViewDefinition.model_validate(entry.get('definition')).model_dump()
            if definition != entry['definition'] or digest(definition) != entry.get('definition_digest'):
                raise ValueError('CREATIVE_CANVAS_HISTORY_CORRUPT')
        if len(entries) != row['version']:
            raise ValueError('CREATIVE_CANVAS_HISTORY_CORRUPT')
        return entries

    def history(self, nid, scope, actor, rid, guard=lambda: None):
        incarnation, current = self.graph._context(nid, scope, actor, guard)
        with self.graph.asset_inputs.phase(nid, scope, actor, current) as state:
            row = self._owned(nid, scope, actor, rid, state)
            items = []
            for entry in self._history_entries(nid, scope, actor, row):
                states = self._states(nid, scope, actor, entry['definition'], current)
                definition = deepcopy(entry['definition'])
                unavailable = {value['card_id'] for value in states if value['state'] == 'UNAVAILABLE'}
                for card in definition['cards']:
                    if card['id'] in unavailable:
                        card.pop('asset')
                if definition.get('image_node_origin',{}).get('target',{}).get('node_id') in unavailable:
                    definition.pop('image_node_origin',None)
                items.append({key: deepcopy(entry[key]) for key in
                    ('version', 'definition_digest', 'created_at', 'updated_at')} |
                    {'definition': definition, 'reference_states': states,
                     'can_restore': entry['version'] < row['version'] and
                         all(value['state'] == 'CURRENT_METADATA' for value in states)})
            current()
            return {'project_id': nid, 'scope': deepcopy(scope), 'id': rid,
                'incarnation': incarnation, 'current_version': row['version'],
                'current_definition_digest': row['definition_digest'], 'items': items,
                'restore_policy': 'CURRENT_METADATA_ONLY', 'execution_authority': False,
                'binary_content_verified': False}

    def restore(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = CanvasViewRestore.model_validate(value)
        incarnation, current = self.graph._context(nid, scope, actor, guard)
        if body.expected_incarnation != incarnation:
            raise StaleSourceError('CREATIVE_CANVAS_RESTORE_CONTEXT_CHANGED')
        captured=self._owned(nid,scope,actor,rid,self.store.read(nid,scope))
        check_version(captured,body.expected_version)
        old_origin=captured['definition'].get('image_node_origin')
        proof=None
        if old_origin is not None:
            from .canvas_image_node import capture
            proof=capture(self,nid,scope,actor,old_origin,current)
        with self.graph.asset_inputs.transaction(nid, scope, actor, current) as state:
            row = self._owned(nid, scope, actor, rid, state)
            check_version(row, body.expected_version)
            if row['definition'].get('image_node_origin') != old_origin:
                raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_ORIGIN_CHANGED')
            if row['definition_digest'] != body.expected_definition_digest:
                raise StaleSourceError('CREATIVE_CANVAS_RESTORE_CONTEXT_CHANGED')
            entries = self._history_entries(nid, scope, actor, row)
            target = next((entry for entry in entries[:-1] if entry['version'] == body.restore_version), None)
            if target is None:
                raise ValueError('CREATIVE_CANVAS_RESTORE_HISTORY_VERSION_REQUIRED')
            if target['definition_digest'] != body.restore_definition_digest:
                raise StaleSourceError('CREATIVE_CANVAS_RESTORE_HISTORY_CHANGED')
            definition = deepcopy(target['definition'])
            if definition.get('image_node_origin') != old_origin:
                raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_ORIGIN_CHANGED')
            if any(item['state'] != 'CURRENT_METADATA' for item in
                    self._states(nid, scope, actor, definition, current)):
                raise StaleSourceError('CREATIVE_CANVAS_RESTORE_SOURCE_UNRESOLVED')
            if proof is not None:
                from .canvas_image_node import current_asset
                current_asset(self,nid,scope,actor,proof,current)
            change_row(row, actor, body.expected_version, lambda value: value.update(
                definition=definition, definition_digest=target['definition_digest']))
            self.graph._capacity(state)
            current()
        return self.get(nid, scope, actor, rid, current)
