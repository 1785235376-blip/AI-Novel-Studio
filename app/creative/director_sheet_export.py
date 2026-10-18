"""Bounded author planning CSV, never an executable workflow or media result."""
import csv
import hashlib
import io
import json
from .models import CreativeProductionDocumentIn

MAX_BYTES = 2_000_000
COLUMNS = ('document_id','document_version','document_digest','document_status','title',
    'scene_id','scene_heading','scene_location','scene_time','note_id','note_number',
    'direction','blocking','shot_size','camera_angle','camera_motion','duration_seconds',
    'emotion','pacing','performance','shot_suggestion','composition','lens','lighting',
    'color_palette','material','transition','character_state','performances','planning')


def cell(value):
    text = '' if value is None else (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)
                                    if isinstance(value,(dict,list)) else str(value))
    if any(ord(c)<32 and c not in '\t\r\n' or 0xD800<=ord(c)<=0xDFFF for c in text):
        raise ValueError('CREATIVE_DIRECTOR_SHEET_TEXT_INVALID')
    # CSV quoting alone does not prevent spreadsheet formula evaluation.
    index = 0
    while index < len(text) and (text[index].isspace() or text[index] in '\ufeff\u200b\u200c\u200d\u2060'):
        index += 1
    if text and (text[0] in '\t\r\n' or text[index:].startswith(('=','+','-','@','＝','＋','－','＠'))):
        text = "'" + text
    return text


def render(row,digest,format):
    if format!='csv':raise ValueError('CREATIVE_DIRECTOR_SHEET_FORMAT_INVALID')
    if row.get('mode')!='DIRECTOR':raise ValueError('CREATIVE_DIRECTOR_SHEET_MODE_REQUIRED')
    value=CreativeProductionDocumentIn.model_validate({k:row[k] for k in CreativeProductionDocumentIn.model_fields if k in row}).model_dump(exclude_none=True)
    scenes={scene['id']:scene for scene in value['scenes']}
    content=bytearray(b'\xef\xbb\xbf')
    def append(values):
        buffer=io.StringIO(newline='');csv.writer(buffer,quoting=csv.QUOTE_ALL,lineterminator='\r\n').writerow([cell(v) for v in values])
        line=buffer.getvalue().encode('utf-8')
        if len(content)+len(line)>MAX_BYTES:raise ValueError('CREATIVE_DIRECTOR_SHEET_CAPACITY')
        content.extend(line)
    append(COLUMNS)
    for note in sorted(value['director_notes'],key=lambda n:n['number']):
        scene=scenes[note['scene_id']]
        entry={**note,'document_id':row['id'],'document_version':row['version'],'document_digest':digest,
            'document_status':row['status'],'title':value['title'],'scene_heading':scene['heading'],
            'scene_location':scene['location'],'scene_time':scene['time'],'note_id':note['id'],
            'note_number':note['number'],'direction':note['note']}
        append(entry.get(key) for key in COLUMNS)
    raw=bytes(content)
    return {'content':raw,'media_type':'text/csv','format':'csv','filename':f'creative-{row["id"]}-v{row["version"]}.csv',
        'document_id':row['id'],'document_version':row['version'],'document_digest':digest,'sha256':hashlib.sha256(raw).hexdigest()}
