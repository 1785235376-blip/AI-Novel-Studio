"""Unmounted V3 image source foundation over original Asset/project owners.

No proposal, job, model call, persistent image copy or execution capability is
created. Callers must supply a current authorization guard; passive pins cannot
authorize reads. Existing V1/V2 source and terminal contracts are unchanged.
"""
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from typing import Annotated, Literal
import warnings

from pydantic import Field, model_validator

from .director_binding import (_Frozen, Identifier, Digest,
    CreativeDirectorLocalScope, CreativeDirectorCollaborationScope)
from .graph_asset_inputs import GraphAssetInputs

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 4 * 1024 * 1024
MAX_IMAGE_SIDE = 4096


class ImageAssetSelection(_Frozen):
    asset_id: Identifier
    version: int = Field(ge=1, le=2**53 - 1)
    sha256: Digest


class DirectorImageSource(_Frozen):
    contract: Literal['CREATIVE_DIRECTOR_IMAGE_SOURCE_V3'] = 'CREATIVE_DIRECTOR_IMAGE_SOURCE_V3'
    source_kind: Literal['IMAGE'] = 'IMAGE'
    project_id: Identifier
    project_incarnation: Identifier
    actor_id: Identifier
    scope: Annotated[CreativeDirectorLocalScope | CreativeDirectorCollaborationScope,
                     Field(discriminator='mode')]
    asset: ImageAssetSelection
    media_type: Literal['image/png', 'image/jpeg']
    byte_count: int = Field(ge=1, le=MAX_IMAGE_BYTES)
    width: int = Field(ge=1, le=MAX_IMAGE_SIDE)
    height: int = Field(ge=1, le=MAX_IMAGE_SIDE)
    orientation: Literal['IDENTITY_ONLY'] = 'IDENTITY_ONLY'
    transformation: Literal['NONE_EXACT_ASSET_BYTES'] = 'NONE_EXACT_ASSET_BYTES'

    @model_validator(mode='after')
    def identity(self):
        from uuid import UUID
        try:
            backend, value = self.project_incarnation.split(':', 1)
            identity = UUID(value)
            if (backend not in {'file', 'postgres'} or str(identity) != value
                    or (backend == 'file' and identity.version != 4)
                    or self.scope.novel_id != self.project_id
                    or self.width * self.height > MAX_IMAGE_PIXELS):
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError('DIRECTOR_IMAGE_SOURCE_IDENTITY_INVALID') from None
        return self


def decode_image(content, media_type, *, guard):
    """Real bounded Pillow decode, no disk/temp file/network or silent transform.

    Pillow is optional. Missing decoder means unavailable, never header-only
    success. Reject orientation transforms and animation rather than silently
    changing the exact bytes that a future vision adapter would receive.
    """
    if not callable(guard):
        raise ValueError('DIRECTOR_IMAGE_AUTHORITY_REQUIRED')
    guard()
    if (type(content) is not bytes or not 0 < len(content) <= MAX_IMAGE_BYTES
            or media_type not in ('image/png', 'image/jpeg')):
        raise ValueError('DIRECTOR_IMAGE_BYTES_INVALID')
    try:
        from PIL import Image, ImageFile
    except ImportError:
        raise ValueError('DIRECTOR_IMAGE_DECODER_UNAVAILABLE') from None
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError('DIRECTOR_IMAGE_DECODER_POLICY_UNSAFE')
    expected = {'image/png': 'PNG', 'image/jpeg': 'JPEG'}[media_type]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content), formats=[expected]) as image:
                width, height = image.size
                if (image.format != expected or not 0 < width <= MAX_IMAGE_SIDE
                        or not 0 < height <= MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS
                        or getattr(image, 'n_frames', 1) != 1):
                    raise ValueError('invalid image shape')
            with Image.open(BytesIO(content), formats=[expected]) as image:
                image.verify()
            with Image.open(BytesIO(content), formats=[expected]) as image:
                image.load()
                if image.getexif().get(274, 1) != 1:
                    raise ValueError('orientation transform required')
    except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise ValueError('DIRECTOR_IMAGE_DECODE_INVALID') from None
    guard()
    return width, height


class DirectorImageSources:
    """Read-only composition; no canonical store or alternate source authority."""
    def __init__(self, workspace):
        self.workspace = workspace
        self.phase = GraphAssetInputs(SimpleNamespace(store=workspace.store, workspace=workspace))

    @contextmanager
    def read(self, nid, scope, actor, selection, *, guard, expected=None):
        from ..experimental.flags import require_flag
        from ..experimental.common import StaleSourceError
        if not callable(guard):
            raise ValueError('DIRECTOR_IMAGE_AUTHORITY_REQUIRED')
        selection = ImageAssetSelection.model_validate(selection)
        # Validate exact scope/actor syntax before entering any original owner.
        scope_type = CreativeDirectorLocalScope if scope.get('mode') == 'local' else CreativeDirectorCollaborationScope
        checked_scope = scope_type.model_validate(scope)
        if checked_scope.novel_id != nid or not isinstance(actor, str) or not 1 <= len(actor) <= 240:
            raise ValueError('DIRECTOR_IMAGE_AUTHORITY_MISMATCH')
        if expected is not None:
            expected = DirectorImageSource.model_validate(expected)
            if (expected.project_id != nid or expected.scope.model_dump() != scope
                    or expected.actor_id != actor or expected.asset != selection):
                raise ValueError('DIRECTOR_IMAGE_AUTHORITY_MISMATCH')
        def current():
            guard()
            require_flag('narrative_production_v2')
            require_flag('asset_lineage_v2')
        current()
        with self.workspace.store.existing_owner_only():
            with self.phase.phase(nid, scope, actor, current):
                incarnation = self.workspace.store.incarnation(nid)
                if expected is not None and expected.project_incarnation != incarnation:
                    raise StaleSourceError('DIRECTOR_IMAGE_SOURCE_CHANGED')
                row, content = self.workspace.pinned_content(nid, scope, {
                    'id': selection.asset_id, 'version': selection.version,
                    'digest': selection.sha256, 'asset_kind': 'image'},
                    max_bytes=MAX_IMAGE_BYTES, guard=current)
                width, height = decode_image(content, row.get('media_type'), guard=current)
                source = DirectorImageSource(project_id=nid, project_incarnation=incarnation,
                    actor_id=actor, scope=checked_scope, asset=selection, media_type=row['media_type'],
                    byte_count=len(content), width=width, height=height)
                if sha256(content).hexdigest() != selection.sha256 or (expected is not None and expected != source):
                    raise StaleSourceError('DIRECTOR_IMAGE_SOURCE_CHANGED')
                yield source, content
                current()
                # Recheck the actual original pin before returning any projection.
                latest, latest_bytes = self.workspace.pinned_content(nid, scope, {
                    'id': selection.asset_id, 'version': selection.version,
                    'digest': selection.sha256, 'asset_kind': 'image'},
                    max_bytes=MAX_IMAGE_BYTES, guard=current)
                if latest != row or latest_bytes != content:
                    raise StaleSourceError('DIRECTOR_IMAGE_SOURCE_CHANGED')

    def capture(self, nid, scope, actor, selection, *, guard):
        with self.read(nid, scope, actor, selection, guard=guard) as (source, _):
            result = source.model_dump()
        return result
