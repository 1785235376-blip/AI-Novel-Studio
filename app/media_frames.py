"""Resolve local storyboard/shot frames without inventing image assets."""
import base64
import ipaddress
from urllib.parse import urlsplit
from .media_files import inspect_image, media_destination
from .privacy import normalize_privacy


def resolve_motion_frame(value,screenplay,novel_id,provider,assets,seen=None):
    value=str(value or '').strip();seen=set(seen or ())
    if value in seen or len(seen)>8:raise ValueError('cyclic frame reference')
    seen.add(value)
    if value.startswith(('http://','https://')):
        parsed=urlsplit(value)
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:raise ValueError('invalid frame URL')
        try:ip=ipaddress.ip_address(parsed.hostname)
        except ValueError:ip=None
        if ip is not None or parsed.hostname.lower()=='localhost':
            media_destination(value,getattr(provider,'endpoint',None))
        return value,{'kind':'REMOTE_REFERENCE','content_verified':False}
    if value.startswith(('shot:','storyboard:')):
        kind,identifier=value.split(':',1)
        rows=screenplay.get('shots' if kind=='shot' else 'storyboard',[])
        item=next((row for row in rows if row.get('id')==identifier or row.get('shot_id')==identifier),None)
        if item is None:raise ValueError('frame reference not found in this screenplay')
        asset_id=item.get('frame_asset_id') or item.get('asset_id')
        if not asset_id:raise ValueError('frame reference has no rendered image asset')
        return resolve_motion_frame(str(asset_id) if str(asset_id).startswith('asset:') else 'asset:'+str(asset_id),screenplay,novel_id,provider,assets,seen)
    if not value.startswith('asset:') or assets is None:raise ValueError('local frame asset resolver is unavailable')
    asset_id=value.split(':',1)[1];asset=assets.get(asset_id,branch_id=screenplay.get('branch_id'))
    if asset.get('novel_id')!=novel_id or not asset.get('media_type','').startswith('image/'):raise ValueError('frame asset must be an image in this project and branch')
    parsed=urlsplit(getattr(provider,'endpoint',''))
    try:ip=ipaddress.ip_address(parsed.hostname or '')
    except ValueError:ip=None
    local=provider_is_local(provider)
    if not local and normalize_privacy(asset.get('privacy_level'))!='CLOUD_ALLOWED':raise ValueError('FRAME_CLOUD_PRIVACY_REVIEW_REQUIRED')
    data=assets.content(asset_id,branch_id=screenplay.get('branch_id'));measured=inspect_image(data)
    return f"data:{measured['media_type']};base64,"+base64.b64encode(data).decode(),{'kind':'ASSET','asset_id':asset_id,'asset_sha256':asset['sha256'],'asset_version':asset.get('version',1),'content_verified':True}


def provider_is_local(provider):
    parsed=urlsplit(getattr(provider,'endpoint',''))
    try:address=ipaddress.ip_address(parsed.hostname or '')
    except ValueError:return parsed.hostname=='localhost'
    address=getattr(address,'ipv4_mapped',None) or address
    return (address.is_loopback or address.is_private) and not address.is_link_local and not address.is_unspecified and (not address.is_reserved or address.is_loopback)
