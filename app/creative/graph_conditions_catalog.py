"""Explicit read-only discovery for the existing gated schema7 owner."""
from copy import deepcopy
from .graph_local_conditions import CONTRACT, CACHE_MODE, NODE_IDS, require_conditions
from .graph_models import (definition_for, MAX_NODES, MAX_EDGES, MAX_DEFINITION_BYTES, MAX_OUTPUT_BYTES,
    MAX_GRAPHS, MAX_RUNS, MAX_HISTORY, RUN_TIMEOUT_SECONDS, NODE_TIMEOUT_SECONDS)

def catalog(guard):
    def current():
        guard();require_conditions()
    current();definitions=[]
    for key in sorted(NODE_IDS):
        value=definition_for(key,schema_version=7)
        definitions.append({'id':key,'version':1,'inputs':deepcopy(value['inputs']),'outputs':deepcopy(value['outputs']),
            'parameters_schema':value['parameters'].model_json_schema(),
            'default_parameters':{'predicate':{'kind':'boolean','value':True}} if key=='local_condition' else value['parameters']().model_dump(),
            'executable':True,'model_called':False,'blockers':[]})
    result={'definitions':definitions,'limits':{'nodes':MAX_NODES,'edges':MAX_EDGES,'definition_bytes':MAX_DEFINITION_BYTES,
        'output_bytes':MAX_OUTPUT_BYTES,'graphs':MAX_GRAPHS,'runs':MAX_RUNS,'history':MAX_HISTORY,
        'runtime_timeout_seconds':RUN_TIMEOUT_SECONDS,'node_timeout_seconds':NODE_TIMEOUT_SECONDS},
        'capabilities':{'local_execution':True,'chapter_required':False,'model_execution':False,'external_reference_execution':False,
            'external_reference_detach':False,'binary_cache':False,'parallel_execution':False,'automatic_retry':False,
            'actor_private':True,'cache_mode':CACHE_MODE,'local_conditions_contract':CONTRACT,'local_conditions_schema_version':7,
            'local_conditions_frontend_entry':True,'whole_graph_required':True,'condition_kinds':['boolean','enum']}}
    current();return result
