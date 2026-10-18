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
from .canvas_view_models import CANVAS_VIEWS, CanvasViewDefinition, CanvasViewCreate, CanvasViewSave


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
        definition=deepcopy(row['definition']);unavailable={item['card_id'] for item in states if item['state']=='UNAVAILABLE'}
        for card in definition['cards']:
            if card['id'] in unavailable:card.pop('asset')
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
        incarnation,current=self.graph._context(nid,scope,actor,guard)
        definition=body.definition.model_dump();request_digest=digest(body.model_dump())
        with self.graph.asset_inputs.transaction(nid,scope,actor,current) as state:
            if any(item['state']!='CURRENT_METADATA' for item in self._states(nid,scope,actor,definition,current)):
                raise StaleSourceError('CREATIVE_CANVAS_SOURCE_CHANGED')
            rows=state['collections'].setdefault(CANVAS_VIEWS,{})
            found=next((row for row in rows.values() if row.get('created_by')==actor and row.get('request_id')==body.request_id),None)
            if found:
                if found.get('request_digest')!=request_digest:raise ValueError('CREATIVE_CANVAS_REQUEST_ID_REUSED')
                row=self._owned(nid,scope,actor,found['id'],state)
            else:
                row=new_row(nid,scope,actor,{BINDING:incarnation,'definition':definition,
                    'definition_digest':digest(definition),'request_id':body.request_id,'request_digest':request_digest})
                rows[row['id']]=row
            self.graph._capacity(state);current();saved_id=row['id']
        return self.get(nid,scope,actor,saved_id,current)

    def save(self,nid,scope,actor,rid,value,guard=lambda:None):
        body=CanvasViewSave.model_validate(value)
        _,current=self.graph._context(nid,scope,actor,guard)
        definition=body.definition.model_dump()
        with self.graph.asset_inputs.transaction(nid,scope,actor,current) as state:
            row=self._owned(nid,scope,actor,rid,state);check_version(row,body.expected_version)
            if any(item['state']!='CURRENT_METADATA' for item in self._states(nid,scope,actor,definition,current)):
                raise StaleSourceError('CREATIVE_CANVAS_SOURCE_CHANGED')
            change_row(row,actor,body.expected_version,lambda target:target.update(definition=deepcopy(definition),definition_digest=digest(definition)))
            self.graph._capacity(state);current()
        return self.get(nid,scope,actor,rid,current)
