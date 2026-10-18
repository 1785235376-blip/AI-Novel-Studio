"""B06 reviewed comic layouts over screenplay IDs and the original asset library.

The only renderer produces bounded PNGs. The preview and export call the same
composition function, with no HTML, SVG, remote URLs, or executable content.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import math
import zipfile
from contextlib import contextmanager, ExitStack, nullcontext
from typing import Literal
from pydantic import Field, model_serializer, model_validator
from .comic_collections import ComicCollectionsMixin
from .comic_publication_budget import source_read_limit, segment_buffer, lineage_read_work, publication_active
from .comic_layers import ComicLayerStack, validate_references, iter_layer_images, composite_layer, MAX_LAYER_SOURCE_PIXELS, MAX_LAYER_PIXELS, ora_decode_budget, consume_decode_pixels
from .common import DomainService, StaleSourceError, check_version, now, new_row, change_row
from .director import DirectorService
from .media import StrictModel, digest
from ..source_privacy import source_privacy_status
from ..repositories.file.mutation_coordinator import workspace_mutation

MAX_PIXELS = 16_000_000
MAX_IMAGE_PIXELS = 20_000_000
MAX_OUTPUT = 64 * 1024 * 1024
PRESETS = {'PAGE': {'width': 800, 'height': 1120, 'safe_area': 24, 'segment_height': 1120},
           'WEBTOON': {'width': 800, 'height': 2400, 'safe_area': 24, 'segment_height': 1200}}


class Rect(StrictModel):
    x: int = Field(ge=0, le=12000, strict=True)
    y: int = Field(ge=0, le=12000, strict=True)
    width: int = Field(ge=16, le=1600, strict=True)
    height: int = Field(ge=16, le=12000, strict=True)


class Bubble(Rect):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    kind: Literal['DIALOGUE', 'NARRATION'] = 'DIALOGUE'
    text: str = Field(min_length=1, max_length=1000)
    character_id: str | None = Field(default=None, max_length=240)
    font_size: int = Field(default=28, ge=14, le=96, strict=True)

    @model_validator(mode='after')
    def plain(self):
        if any(ord(c) < 32 and c != '\n' or 0xD800 <= ord(c) <= 0xDFFF for c in self.text):
            raise ValueError('COMIC_PLAIN_TEXT_REQUIRED')
        return self


class AppearanceReference(StrictModel):
    character_id: str = Field(min_length=1, max_length=240)
    asset_id: str = Field(min_length=1, max_length=240)
    expected_asset_version: int = Field(ge=1, strict=True)
    note: str = Field(default='', max_length=2000)


class ComicPanel(Rect):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    shot_id: str | None = Field(default=None, min_length=1, max_length=240)
    artwork_mode: Literal['IMAGE', 'BLANK'] = 'IMAGE'
    order: int = Field(ge=1, le=24, strict=True)
    character_ids: list[str] = Field(default_factory=list, max_length=20)
    asset_id: str | None = Field(default=None, min_length=1, max_length=240)
    expected_asset_version: int | None = Field(default=None, ge=1, strict=True)
    fit: Literal['CONTAIN', 'COVER'] = 'CONTAIN'
    cover_x_percent: int = Field(default=50, ge=0, le=100, strict=True)
    cover_y_percent: int = Field(default=50, ge=0, le=100, strict=True)
    bubbles: list[Bubble] = Field(default_factory=list, max_length=12)
    image_brief: str = Field(default='', max_length=8000)
    appearance_references: list[AppearanceReference] = Field(default_factory=list, max_length=20)

    @model_serializer(mode='wrap')
    def preserve_legacy_framing(self, handler):
        # Omission survives API normalization and history restore. Never migrate
        # existing approval-bound documents merely by reading or saving them.
        document = handler(self)
        for field in ('cover_x_percent', 'cover_y_percent', 'artwork_mode'):
            if field not in self.model_fields_set:
                document.pop(field, None)
        return document

    @model_validator(mode='after')
    def references(self):
        if self.artwork_mode == 'BLANK' and (self.asset_id is not None or self.expected_asset_version is not None):
            raise ValueError('COMIC_BLANK_PANEL_HAS_IMAGE')
        ids = [ref.character_id for ref in self.appearance_references]
        if len(set(ids)) != len(ids): raise ValueError('COMIC_DUPLICATE_APPEARANCE_CHARACTER')
        if set(ids) - set(self.character_ids): raise ValueError('COMIC_APPEARANCE_CHARACTER_NOT_IN_PANEL')
        if any(ord(c) < 32 and c not in '\n\t' or 0xD800 <= ord(c) <= 0xDFFF for c in self.image_brief):
            raise ValueError('COMIC_PLAIN_TEXT_REQUIRED')
        return self


class LayoutIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    source_mode: Literal['SCREENPLAY', 'INDEPENDENT'] = 'SCREENPLAY'
    screenplay_id: str | None = Field(default=None, min_length=1, max_length=240)
    expected_screenplay_version: int | None = Field(default=None, ge=1, strict=True)
    preset: Literal['PAGE', 'WEBTOON'] = 'PAGE'
    font_family: Literal['NOTO_SANS_SC_OFL'] = 'NOTO_SANS_SC_OFL'
    width: int = Field(default=800, ge=320, le=1600, strict=True)
    height: int = Field(default=1120, ge=320, le=12000, strict=True)
    safe_area: int = Field(default=24, ge=0, le=128, strict=True)
    segment_height: int = Field(default=1120, ge=320, le=2400, strict=True)
    panels: list[ComicPanel] = Field(max_length=24)
    layer_stack: ComicLayerStack | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy_source_mode(self, handler):
        document = handler(self)
        for field in ('source_mode', 'layer_stack'):
            if field not in self.model_fields_set:
                document.pop(field, None)
        return document

    @model_validator(mode='after')
    def bounded(self):
        if 'layer_stack' in self.model_fields_set:
            if self.layer_stack is None:
                raise ValueError('COMIC_LAYER_STACK_REQUIRED')
            if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in self.title):
                raise ValueError('COMIC_LAYER_TITLE_INVALID')
            validate_references(self.layer_stack, self.panels)
            if self.source_mode != 'INDEPENDENT' and any(i.kind == 'RASTER' for i in self.layer_stack.items):
                raise ValueError('COMIC_RASTER_INDEPENDENT_ONLY')
        if self.source_mode == 'INDEPENDENT':
            if self.screenplay_id is not None or self.expected_screenplay_version is not None or any(p.shot_id is not None for p in self.panels):
                raise ValueError('COMIC_INDEPENDENT_SOURCE_CONFLICT')
        elif self.screenplay_id is None or self.expected_screenplay_version is None or not self.panels or any(p.shot_id is None for p in self.panels):
            raise ValueError('COMIC_SCREENPLAY_SOURCE_REQUIRED')
        if self.width * self.height > MAX_PIXELS:
            raise ValueError('COMIC_PIXEL_LIMIT_16000000')
        if len({p.id for p in self.panels}) != len(self.panels):
            raise ValueError('COMIC_DUPLICATE_PANEL_ID')
        bubbles = [b for p in self.panels for b in p.bubbles]
        if len(bubbles) > 80 or sum(len(b.text) for b in bubbles) > 10000:
            raise ValueError('COMIC_TEXT_LIMIT')
        if len({b.id for b in bubbles}) != len(bubbles):
            raise ValueError('COMIC_DUPLICATE_BUBBLE_ID')
        return self


class LayoutEdit(LayoutIn):
    expected_version: int = Field(ge=1, strict=True)


def renderer_status():
    try:
        import PIL
        if PIL.__version__ != '12.3.0':
            return {'available': False, 'code': 'COMIC_PINNED_PILLOW_REQUIRED'}
        from PIL import features
        return {'available': True, 'version': PIL.__version__, 'freetype_version': features.version_module('freetype2'),
                'jpeg_version': features.version_codec('jpg'), 'webp_version': features.version('webp'),
                'format': 'PNG', 'model_called': False}
    except ImportError:
        return {'available': False, 'code': 'COMIC_RENDERER_UNAVAILABLE'}


def licensed_font():
    """Reuse verified build fonts, including the packaged fixed regular face."""
    from ..pdf_export import _font_candidates
    # Existing prepare_pdf_font.py upstream pin and Windows package regular-face
    # pin (derived by pinned fonttools 4.59.1, weight 400, no subsetting).
    font_pins = {'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da',
                 'eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461'}
    license_pin = '1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9'
    for configured in _font_candidates():
        for candidate in (configured, configured.parent / 'NotoSansSC-Variable.ttf'):
            license_file = candidate.parent / 'OFL.txt'
            try:
                if any(p.is_symlink() or p.stat().st_size > 24 * 1024 * 1024 for p in (candidate, license_file)):
                    continue
                data, license_data = candidate.read_bytes(), license_file.read_bytes()
                if hashlib.sha256(data).hexdigest() not in font_pins or hashlib.sha256(license_data).hexdigest() != license_pin:
                    continue
                from fontTools.ttLib import TTFont
                with TTFont(io.BytesIO(data)) as font:
                    coverage = frozenset(font.getBestCmap())
                return data, license_data, coverage
            except (OSError, ValueError, ImportError):
                continue
    raise ValueError('COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE')


def font_status():
    try:
        data, _, _ = licensed_font()
        return {'available': True, 'family': 'Noto Sans SC', 'license': 'SIL OFL 1.1', 'sha256': hashlib.sha256(data).hexdigest(), 'embedded': False, 'rendered_into_pixels': True}
    except ValueError as error:
        return {'available': False, 'code': str(error)}


def _image(data, *, pixel_budget=None):
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('COMIC_STATIC_RASTER_LIMIT')
            if pixel_budget is not None:
                pixels = image.width * image.height
                if pixels > pixel_budget[0]:
                    raise ValueError('COMIC_LAYER_SOURCE_PIXEL_LIMIT_64000000')
                pixel_budget[0] -= pixels
            from .comic_publication_budget import source_work
            source_work(len(data), image.width * image.height)
            consume_decode_pixels(image.width * image.height)
            image.load()
            # Explicit EXIF orientation normalization for both preview/export.
            from PIL import ImageOps
            result = ImageOps.exif_transpose(image).convert('RGBA')
            result.info.clear()
            return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('COMIC_INVALID_RASTER') from None


def _inside(inner, outer, padding=0):
    return (inner['x'] >= outer['x'] + padding and inner['y'] >= outer['y'] + padding and
            inner['x'] + inner['width'] <= outer['x'] + outer['width'] - padding and
            inner['y'] + inner['height'] <= outer['y'] + outer['height'] - padding)


def _overlap(a, b):
    return max(a['x'], b['x']) < min(a['x'] + a['width'], b['x'] + b['width']) and max(a['y'], b['y']) < min(a['y'] + a['height'], b['y'] + b['height'])


def _text_layout(bubble, font_data, coverage):
    from PIL import ImageFont
    if any(ord(c) not in coverage for c in bubble['text'] if c != '\n'):
        raise ValueError('COMIC_FONT_MISSING_GLYPH')
    font = ImageFont.truetype(io.BytesIO(font_data), bubble['font_size'])
    if hashlib.sha256(font_data).hexdigest() == 'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da':
        font.set_variation_by_axes([400])
    available = bubble['width'] - 24
    lines = []
    for paragraph in bubble['text'].split('\n'):
        line = ''
        for char in paragraph:
            if font.getlength(char) > available:
                raise ValueError('COMIC_TEXT_OVERFLOW')
            if line and font.getlength(line + char) > available:
                # Bounded CJK punctuation rule: do not strand a closing mark
                # at the next line start or an opening mark at the line end.
                if char in '，。！？；：、）】》」』〉〕％,.!?;:%)]}' or line[-1] in '（【《「『〈〔([{':
                    tail = line[-1] + char
                    if len(line) < 2 or font.getlength(tail) > available:
                        raise ValueError('COMIC_TEXT_OVERFLOW')
                    lines.append(line[:-1]); line = tail
                else:
                    lines.append(line); line = char
            else:
                line += char
        lines.append(line)
    line_height = math.ceil(bubble['font_size'] * 1.5)
    if len(lines) * line_height > bubble['height'] - 24:
        raise ValueError('COMIC_TEXT_OVERFLOW')
    for index, line in enumerate(lines):
        left, top, right, bottom = font.getbbox(line, anchor='lt')
        if left < -12 or right > bubble['width'] - 12 or index * line_height + bottom > bubble['height'] - 24:
            raise ValueError('COMIC_TEXT_OVERFLOW')
    return font, lines, line_height


def compose(document, images, *, render=False):
    """One geometry/text engine for preflight, preview and exported segment bytes."""
    issues = []
    def issue(code, target, severity='BLOCKER'):
        issues.append({'code': code, 'target': target, 'severity': severity})
    ready = renderer_status()
    if not ready['available']:
        issue(ready['code'], 'renderer')
    font_data = coverage = None
    text_present = any(p['bubbles'] for p in document['panels'])
    if text_present:
        try: font_data, _, coverage = licensed_font()
        except ValueError as error: issue(str(error), 'font')
    frame = {'x': 0, 'y': 0, 'width': document['width'], 'height': document['height']}
    panels = document['panels']; text = {}; placements = {}
    pixel_budget = [MAX_LAYER_SOURCE_PIXELS] if 'layer_stack' in document else None
    if sorted(p['order'] for p in panels) != list(range(1, len(panels) + 1)):
        issue('COMIC_READING_ORDER_CONFLICT', 'panels')
    if [p['id'] for p in sorted(panels, key=lambda p: (p['y'], p['x']))] != [p['id'] for p in sorted(panels, key=lambda p: p['order'])]:
        issue('COMIC_SPATIAL_ORDER_CONFLICT', 'panels')
    for index, panel in enumerate(panels):
        pid = panel['id']
        if not _inside(panel, frame, document['safe_area']): issue('COMIC_PANEL_OUTSIDE_SAFE_AREA', pid)
        if any(_overlap(panel, p) for p in panels[:index]): issue('COMIC_PANEL_OVERLAP', pid)
        source = images.get(panel.get('asset_id'))
        blank = panel.get('artwork_mode', 'IMAGE') == 'BLANK'
        if source is None and not blank: issue('COMIC_MISSING_APPROVED_IMAGE', pid)
        elif source is not None and ready['available']:
            image = _image(source, pixel_budget=pixel_budget)
            scale = (max if panel['fit'] == 'COVER' else min)(panel['width'] / image.width, panel['height'] / image.height)
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            offset = ((panel['width'] - size[0]) // 2, (panel['height'] - size[1]) // 2)
            center_offset = offset
            if panel['fit'] == 'COVER':
                # Align over the available crop travel, preserving Python's
                # negative floor rounding exactly at the legacy center (50).
                offset = ((panel['width'] - size[0]) * panel.get('cover_x_percent', 50) // 100,
                          (panel['height'] - size[1]) * panel.get('cover_y_percent', 50) // 100)
            placements[pid] = {'size': size, 'offset': offset}
            if size[0] * size[1] > MAX_IMAGE_PIXELS: issue('COMIC_IMAGE_RESAMPLE_LIMIT', pid)
            if size[0] > panel['width'] or size[1] > panel['height']:
                issue('COMIC_CENTER_CROP' if offset == center_offset else 'COMIC_POSITIONED_CROP', pid, 'WARNING')
        for bi, bubble in enumerate(panel['bubbles']):
            bid = bubble['id']
            if not _inside(bubble, panel, 8): issue('COMIC_BUBBLE_OUTSIDE_PANEL_SAFE_AREA', bid)
            if any(_overlap(bubble, b) for b in panel['bubbles'][:bi]): issue('COMIC_BUBBLE_OVERLAP', bid)
            if any(bubble['y'] < cut < bubble['y'] + bubble['height'] for cut in range(document['segment_height'], document['height'], document['segment_height'])):
                issue('COMIC_SEGMENT_CUTS_BUBBLE', bid, 'WARNING')
            if bubble['font_size'] * 320 / document['width'] < 12: issue('COMIC_SMALL_TEXT_AT_320PX', bid, 'WARNING')
            if font_data is not None and ready['available']:
                try: text[bid] = _text_layout(bubble, font_data, coverage)
                except ValueError as error: issue(str(error), bid)
    for item in document.get('layer_stack', {}).get('items', []):
        if item['kind'] != 'RASTER': continue
        source = images.get(item['target_id'])
        if source is None: issue('COMIC_MISSING_REVIEWED_RASTER', item['id'])
        elif ready['available']:
            image = _image(source, pixel_budget=pixel_budget)
            if image.size != (item['width'], item['height']): issue('COMIC_RASTER_DIMENSIONS_CHANGED', item['id'])
            image.close()
    segments = [{'index': i, 'y': y, 'width': document['width'], 'height': min(document['segment_height'], document['height'] - y)}
                for i, y in enumerate(range(0, document['height'], document['segment_height']))]
    result = {'issues': issues, 'segments': segments, 'placements': placements, 'can_render': not any(i['severity'] == 'BLOCKER' for i in issues), 'geometry': 'INTEGER_PAGE_PIXELS_V1'}
    if 'layer_stack' in document:
        result['layer_profile'] = 'NATIVE_REFERENCE_LAYERS_V1'
        if sum(p['size'][0] * p['size'][1] for p in placements.values()) > MAX_LAYER_PIXELS:
            issue('COMIC_LAYER_RESAMPLE_PIXEL_LIMIT_64000000', 'layers')
            result['can_render'] = False
    if not render or not result['can_render']: return result, []
    from PIL import Image, ImageDraw
    if 'layer_stack' in document:
        canvas = Image.new('RGBA', (document['width'], document['height']), 'white')
        for item, x, y, surface in iter_layer_images(document, images, placements, text):
            composite_layer(canvas, item, x, y, surface)
        canvas = canvas.convert('RGB')
    else:
        canvas = Image.new('RGB', (document['width'], document['height']), 'white')
        draw = ImageDraw.Draw(canvas)
        for panel in sorted(panels, key=lambda p: p['order']):
            if panel.get('artwork_mode', 'IMAGE') != 'BLANK':
                placement = placements[panel['id']]; source = _image(images[panel['asset_id']])
                resized = source.resize(placement['size'], Image.Resampling.LANCZOS)
                panel_image = Image.new('RGBA', (panel['width'], panel['height']), 'white')
                panel_image.alpha_composite(resized, placement['offset'])
                canvas.paste(panel_image.convert('RGB'), (panel['x'], panel['y']))
            draw.rectangle((panel['x'], panel['y'], panel['x'] + panel['width'] - 1, panel['y'] + panel['height'] - 1), outline='black', width=2)
            for bubble in panel['bubbles']:
                box = (bubble['x'], bubble['y'], bubble['x'] + bubble['width'] - 1, bubble['y'] + bubble['height'] - 1)
                draw.rounded_rectangle(box, radius=16 if bubble['kind'] == 'DIALOGUE' else 0, fill='white', outline='black', width=2)
                font, lines, line_height = text[bubble['id']]
                for i, line in enumerate(lines): draw.text((bubble['x'] + 12, bubble['y'] + 12 + i * line_height), line, font=font, fill='black', anchor='lt')
    output = []
    for segment in segments:
        stream = segment_buffer(); canvas.crop((0, segment['y'], document['width'], segment['y'] + segment['height'])).save(stream, format='PNG', compress_level=9)
        data = stream.getvalue()
        with Image.open(io.BytesIO(data)) as check:
            check.verify()
        output.append(data)
    if sum(map(len, output)) > MAX_OUTPUT: raise ValueError('COMIC_EXPORT_SIZE_LIMIT')
    return result, output


class ComicLayoutsService(ComicCollectionsMixin, DomainService):
    RECORDS = 'comic_layouts_v2'

    def __init__(self, store, novels, chapters, screenplays, assets, *, lineage=None, independent_store=None):
        super().__init__(store, novels, chapters)
        self.screenplays, self.assets, self.lineage = screenplays, assets, lineage
        self.independent_store = independent_store

    @staticmethod
    def _independent(row):
        return row['document'].get('source_mode', 'SCREENPLAY') == 'INDEPENDENT'

    def _independent_owner(self):
        owner = self.independent_store
        if owner is None or owner.store is not self.store:
            raise ValueError('COMIC_ORIGINAL_PROJECT_OWNER_UNAVAILABLE')
        return owner

    def _independent_identity(self, nid):
        # Reads and existing mutations must never initialize a missing marker.
        self.novels.get(nid)
        owner = self._independent_owner()
        with owner.existing_owner_only():
            return owner.incarnation(nid)

    def _check_independent_identity(self, nid, row):
        if self._independent(row) and (not row.get('project_incarnation')
                or row['project_incarnation'] != self._independent_identity(nid)):
            raise FileNotFoundError('comic owner unavailable')

    @contextmanager
    def _independent_transaction(self, nid, scope, *, create=False):
        self.novels.get(nid)
        owner = self._independent_owner()
        # Original scope -> original project lease. The project lease outlives
        # the raw scope commit; no copied store, registry widening or lock namespace.
        with (nullcontext() if create else owner.existing_owner_only()):
            with ExitStack() as lifecycle:
                with self.store.transaction(nid, scope) as state:
                    # Asset content rechecks below use the original asset lock.
                    # Acquire it before the project lease, matching asset -> project
                    # writers and avoiding an inversion during review/save.
                    lifecycle.enter_context(self.assets._lock)
                    lifecycle.enter_context(workspace_mutation(self.assets.root, 'asset-library'))
                    lifecycle.enter_context(owner.owner_lease(nid))
                    self.novels.get(nid)
                    yield state

    def mutate(self, nid, scope, actor, collection, rid, expected_version, callback):
        original = self._row(nid, scope, actor, rid)
        if not self._independent(original):
            return super().mutate(nid, scope, actor, collection, rid, expected_version, callback)
        with self._independent_transaction(nid, scope) as state:
            row = state['collections'].get(collection, {}).get(rid)
            if row is None or row.get('novel_id') != nid or row.get('scope') != scope or row.get('created_by') != actor:
                raise FileNotFoundError(rid)
            self._check_independent_identity(nid, row)
            change_row(row, actor, expected_version, callback)
            return copy.deepcopy(row)

    def _director(self): return DirectorService(self.store, self.novels, self.chapters, self.screenplays)

    @contextmanager
    def _studio_asset_scope(self, nid, scope):
        owner = self._independent_owner()
        with owner.existing_owner_only():
            expected = {'novel_id': nid, 'branch_id': scope.get('branch_id'),
                'scope_key': self.store.key(nid, scope), 'incarnation': self._independent_identity(nid)}
            active = getattr(self.assets._scope, 'binding', None)
            if active is not None and active != expected:
                raise FileNotFoundError('comic asset owner unavailable')
            with (nullcontext() if active is not None else self.assets.project_scope(nid, scope.get('branch_id'),
                    lambda: owner.owner_lease(nid), scope_key=expected['scope_key'])):
                yield

    @staticmethod
    def _studio_image_review(asset):
        from ..creative.workspace import IndependentWorkspaceService
        origin, proof = asset.get('_studio_result_origin'), asset.get('_origin_provenance')
        if not isinstance(origin, dict) or not isinstance(proof, dict):
            raise ValueError('COMIC_USE_ORIGINAL_GENERATION_REVIEW')
        IndependentWorkspaceService._production_asset_ids(origin)
        from ..creative.production_contracts import ProductionSourceSnapshot
        for source in origin['sources']:
            ProductionSourceSnapshot.model_validate(source)
        receipt = {key: value for key, value in proof.items() if key not in {'receipt_digest', 'human_review', 'review_actor'}}
        if (asset.get('_owner_actor_id') is not None or not asset.get('approved_at')
                or proof.get('contract') != 'studio-image-execution/1' or proof.get('human_review') != 'EXPLICIT_APPROVAL'
                or proof.get('review_actor') != origin.get('actor') or proof.get('job_id') != origin.get('job_id')
                or not str(origin.get('operation_id', '')).startswith('m5.image.')
                or asset.get('source_job_id') != origin.get('job_id')
                or any(proof.get(key) != origin.get(key) or asset.get(key) != origin.get(key) for key in ('provider_id', 'model_id'))
                or proof.get('request_digest') != origin.get('request_digest')
                or proof.get('source_snapshots') != origin.get('sources')
                or proof.get('candidate_asset_id') != asset['id'] or proof.get('output_digest') != asset['sha256']
                or type(proof.get('candidate_asset_version')) is not int
                or asset.get('version') != proof['candidate_asset_version'] + 1
                or proof.get('receipt_digest') != digest(receipt)):
            raise ValueError('COMIC_USE_ORIGINAL_GENERATION_REVIEW')

    def _asset(self, nid, scope, actor, aid, *, approved=True, pixel_budget=None):
        # Original unbound uploads retain their namespace. A second read uses
        # only the actual current project owner; no asset self-declaration can
        # select an incarnation, and private candidates never enter Comic.
        active = getattr(self.assets._scope, 'binding', None)
        if active is not None:
            with self._studio_asset_scope(nid, scope):
                asset = self.assets.get(aid, branch_id=scope.get('branch_id'), actor_id=actor)
                self._studio_image_review(asset)
                return self._read_asset(nid, scope, actor, aid, approved=approved, pixel_budget=pixel_budget)
        try:
            return self._read_asset(nid, scope, actor, aid, approved=approved, pixel_budget=pixel_budget)
        except FileNotFoundError:
            if self.independent_store is None:
                raise
        with self._studio_asset_scope(nid, scope):
            asset = self.assets.get(aid, branch_id=scope.get('branch_id'), actor_id=actor)
            self._studio_image_review(asset)
            return self._read_asset(nid, scope, actor, aid, approved=approved, pixel_budget=pixel_budget)

    def _read_asset(self, nid, scope, actor, aid, *, approved=True, pixel_budget=None):
        asset = self.assets.get(aid, branch_id=scope.get('branch_id'), actor_id=actor)
        if asset.get('novel_id') != nid or asset.get('branch_id') != scope.get('branch_id'): raise FileNotFoundError(aid)
        if asset['media_type'] not in {'image/png', 'image/jpeg', 'image/webp'}: raise ValueError('COMIC_STATIC_RASTER_REQUIRED')
        if approved and not asset.get('approved_at'): raise ValueError('COMIC_ASSET_REVIEW_REQUIRED')
        if self.lineage is not None:
            lineage_read_work(asset)
            if self.lineage.asset(nid, scope, aid, include_impact=not publication_active())['stale']:
                raise StaleSourceError('COMIC_ASSET_LINEAGE_CHANGED')
        # Bind privacy decisions across recorded lineage, not only content bytes.
        privacy, seen, frontier = {}, set(), [asset]
        while frontier:
            parent = frontier.pop()
            if parent['id'] in seen: continue
            seen.add(parent['id'])
            if len(seen) > 100: raise ValueError('COMIC_ASSET_LINEAGE_LIMIT')
            for cid in parent.get('parameters', {}).get('asset_lineage_v2', {}).get('sources', {}):
                chapter = self.chapters_for(scope).get(cid)
                if chapter.get('novel_id') != nid or chapter.get('branch_id') != scope.get('branch_id'): raise FileNotFoundError(cid)
                privacy[cid] = source_privacy_status(chapter, scope.get('branch_id'), self.store.root)
            for pid in parent.get('source_asset_ids', []):
                parent_row = self.assets.get(pid, branch_id=scope.get('branch_id'), actor_id=actor)
                if parent_row.get('novel_id') != nid or parent_row.get('branch_id') != scope.get('branch_id'): raise FileNotFoundError(pid)
                frontier.append(parent_row)
        asset['_comic_source_privacy'] = privacy
        content = self.assets.content(aid, branch_id=scope.get('branch_id'), actor_id=actor, max_bytes=source_read_limit(asset))
        if renderer_status()['available']: _image(content, pixel_budget=pixel_budget)
        return asset, content

    def _raster_asset(self, nid, scope, actor, item, *, pixel_budget=None):
        """Only reviewed ORA pins enter the bound reader; legacy _asset is untouched."""
        from ..services.comic_ora_origin import record, reviewed
        owner = self._independent_owner()
        expected_binding = {'novel_id': nid, 'branch_id': scope.get('branch_id'),
                            'scope_key': self.store.key(nid, scope), 'incarnation': self._independent_identity(nid)}
        active = getattr(self.assets._scope, 'binding', None)
        if active is not None and active != expected_binding: raise FileNotFoundError(item['target_id'])
        lease = nullcontext() if active is not None else self.assets.project_scope(nid, scope.get('branch_id'),
            lambda: owner.owner_lease(nid), scope_key=expected_binding['scope_key'])
        with owner.existing_owner_only(), lease:
            asset = self.assets.get(item['target_id'], branch_id=scope.get('branch_id'), actor_id=actor)
            origin = record(asset); proof = reviewed(asset.get('_comic_ora_review'), origin)
            pin = item['pin']
            if (origin['actor'] != actor or asset.get('novel_id') != nid
                    or asset.get('_project_binding') != expected_binding
                    or (asset['version'], asset['sha256'], proof['review_digest']) !=
                       (pin['version'], pin['sha256'], pin['review_digest'])):
                raise StaleSourceError('COMIC_RASTER_REVIEW_CHANGED')
            data = self.assets.content(asset['id'], branch_id=scope.get('branch_id'), actor_id=actor,
                                       max_bytes=source_read_limit(asset, self.assets.MAX_BYTES))
            image = _image(data, pixel_budget=pixel_budget)
            if image.size != (item['width'], item['height']):
                image.close(); raise StaleSourceError('COMIC_RASTER_DIMENSIONS_CHANGED')
            image.close()
            return asset, data

    def _binding(self, asset):
        return {'version': asset['version'], 'sha256': asset['sha256'], 'approved_at': asset.get('approved_at'), 'metadata_digest': digest(asset)}

    @staticmethod
    def _manual(asset):
        return not any(asset.get(key) for key in ('source_job_id', 'provider_id', 'model_id', 'source_asset_ids', '_origin_provenance', '_required_features'))

    def approve_image(self, nid, scope, actor, aid, expected_version, guard=lambda: None):
        # Original upload review only. Never approve a model proposal here.
        with self.assets._lock, workspace_mutation(self.assets.root, 'asset-library'):
            asset, _ = self._asset(nid, scope, actor, aid, approved=False)
            if not self._manual(asset): raise ValueError('COMIC_USE_ORIGINAL_GENERATION_REVIEW')
            if not renderer_status()['available']: raise ValueError('COMIC_RENDERER_UNAVAILABLE')
            check_version(asset, expected_version); guard()
            result = self.assets.update_metadata(aid, {'approved_at': now()}, branch_id=scope.get('branch_id'), actor_id=actor, expected_version=expected_version)
            guard()
            return {'id': result['id'], 'version': result['version'], 'approved': True}

    def image_preview(self, nid, scope, actor, aid):
        _, data = self._asset(nid, scope, actor, aid, approved=False)
        if not renderer_status()['available']: raise ValueError('COMIC_RENDERER_UNAVAILABLE')
        image = _image(data); image.thumbnail((800, 800)); stream = io.BytesIO(); image.save(stream, format='PNG')
        return stream.getvalue()

    def catalog(self, nid, scope, actor):
        base = self._director().catalog(nid, scope, actor); assets = []
        candidates = self.assets.list(nid, branch_id=scope.get('branch_id'), actor_id=actor)
        if self.independent_store is not None:
            try:
                with self._studio_asset_scope(nid, scope):
                    for asset in self.assets.list(nid, branch_id=scope.get('branch_id'), actor_id=actor):
                        try: self._studio_image_review(asset)
                        except ValueError: continue
                        candidates.append(asset)
            except FileNotFoundError:
                pass
        for asset in candidates:
            try: row, _ = self._asset(nid, scope, actor, asset['id'], approved=False)
            except (FileNotFoundError, ValueError): continue
            assets.append({k: row[k] for k in ('id', 'filename', 'version')} | {'approved': bool(row.get('approved_at')), 'manual_review_available': self._manual(row)})
        return {'screenplays': base['screenplays'], 'characters': base['characters'], 'assets': assets,
                'presets': PRESETS, 'renderer': renderer_status(), 'font': font_status(), 'privacy_level': 'LOCAL_ONLY', 'automatic_generation': False,
                'appearance_reference_policy': 'ORIGINAL_APPROVED_ASSET_VERSION_PINNED',
                'image_brief_policy': 'HUMAN_AUTHORED_DECLARATION_NO_GENERATION'}

    def _payload(self, nid, scope, actor, value, *, bind_independent=True):
        body = LayoutIn.model_validate(value); document = body.model_dump(); director = self._director()
        self.novels.get(nid)
        independent = body.source_mode == 'INDEPENDENT'
        source = None if independent else director.screenplay(nid, scope, body.screenplay_id)
        if source is not None and source['edit_version'] != body.expected_screenplay_version: raise StaleSourceError('COMIC_SCREENPLAY_CHANGED')
        shots = {shot['id']: shot for shot in source.get('shots', [])} if source is not None else {}
        if not independent and any(p.shot_id not in shots for p in body.panels): raise ValueError('COMIC_UNKNOWN_SHOT')
        characters = {cid for p in body.panels for cid in p.character_ids} | {b.character_id for p in body.panels for b in p.bubbles if b.character_id}
        character_sources = director._character_sources(nid, scope, characters)
        assets = {}
        pixel_budget = [MAX_LAYER_SOURCE_PIXELS] if body.layer_stack is not None else None
        def bind(aid, version, code):
            # Legacy validation order stays unchanged. Opted-in reference layers
            # bound each distinct source before decoding; repeated pins reuse it.
            if pixel_budget is None or aid not in assets:
                asset, _ = self._asset(nid, scope, actor, aid, pixel_budget=pixel_budget)
                assets[aid] = self._binding(asset)
            if version != assets[aid]['version']: raise StaleSourceError(code)
        for panel in body.panels:
            if panel.asset_id:
                bind(panel.asset_id, panel.expected_asset_version, 'COMIC_ASSET_VERSION_CHANGED')
            for reference in panel.appearance_references:
                bind(reference.asset_id, reference.expected_asset_version, 'COMIC_APPEARANCE_ASSET_VERSION_CHANGED')
        for item in document.get('layer_stack', {}).get('items', []):
            if item['kind'] == 'RASTER':
                asset, _ = self._raster_asset(nid, scope, actor, item, pixel_budget=pixel_budget)
                binding = {**self._binding(asset), 'origin_kind': 'REVIEWED_ORA_RASTER'}
                if item['target_id'] in assets and assets[item['target_id']] != binding:
                    raise ValueError('COMIC_RASTER_BINDING_CONFLICT')
                assets[item['target_id']] = binding
        return {**({'project_incarnation': self._independent_identity(nid)} if independent and bind_independent else {}), 'document': document, 'screenplay_version': source['edit_version'] if source is not None else None, 'source_evidence': director.evidence(nid, scope, source) if source is not None else {'sources': {}, 'privacy': {}},
                'character_sources': character_sources, 'asset_sources': assets,
                'scene_ids': {p.id: shots[p.shot_id].get('scene_id') if p.shot_id in shots else None for p in body.panels}, 'status': 'DRAFT', 'approval': None}

    def _current(self, nid, scope, actor, row):
        self.novels.get(nid)
        self._check_independent_identity(nid, row)
        director = self._director()
        if row['document'].get('source_mode', 'SCREENPLAY') != 'INDEPENDENT':
            source = director.screenplay(nid, scope, row['document']['screenplay_id'])
            if source['edit_version'] != row['screenplay_version'] or director.evidence(nid, scope, source) != row['source_evidence']:
                raise StaleSourceError('COMIC_SOURCE_CHANGED')
        elif (row['document'].get('screenplay_id') is not None or row['document'].get('expected_screenplay_version') is not None
              or row['screenplay_version'] is not None or row['source_evidence'] != {'sources': {}, 'privacy': {}}
              or any(p.get('shot_id') is not None for p in row['document']['panels'])):
            raise StaleSourceError('COMIC_INDEPENDENT_SOURCE_CONFLICT')
        if director._character_sources(nid, scope, row['character_sources']) != row['character_sources']:
            raise StaleSourceError('COMIC_SOURCE_CHANGED')
        images = {}
        pixel_budget = [MAX_LAYER_SOURCE_PIXELS] if 'layer_stack' in row['document'] else None
        for aid, binding in row['asset_sources'].items():
            if binding.get('origin_kind') == 'REVIEWED_ORA_RASTER':
                refs = [i for i in row['document'].get('layer_stack', {}).get('items', [])
                        if i['kind'] == 'RASTER' and i['target_id'] == aid]
                if not refs: raise StaleSourceError('COMIC_RASTER_REFERENCE_MISSING')
                asset, data = self._raster_asset(nid, scope, actor, refs[0], pixel_budget=pixel_budget)
                if any(i['pin'] != refs[0]['pin'] or (i['width'], i['height']) != (refs[0]['width'], refs[0]['height']) for i in refs):
                    raise StaleSourceError('COMIC_RASTER_REFERENCE_CONFLICT')
                current_binding = {**self._binding(asset), 'origin_kind': 'REVIEWED_ORA_RASTER'}
            else:
                asset, data = self._asset(nid, scope, actor, aid, pixel_budget=pixel_budget)
                current_binding = self._binding(asset)
            if current_binding != binding: raise StaleSourceError('COMIC_ASSET_CHANGED')
            images[aid] = data
            if sum(map(len, images.values())) > MAX_OUTPUT: raise ValueError('COMIC_SOURCE_BYTES_LIMIT')
        return images

    def _row(self, nid, scope, actor, rid):
        row = self.get(nid, scope, self.RECORDS, rid)
        if row['created_by'] != actor: raise FileNotFoundError(rid)
        self._check_independent_identity(nid, row)
        return row

    def _view(self, nid, scope, actor, row):
        safe = {k: row[k] for k in ('id', 'version', 'status')}
        try: self._current(nid, scope, actor, row)
        except (FileNotFoundError, ValueError): return {**safe, 'stale': True, 'privacy_level': 'LOCAL_ONLY'}
        return {**safe, 'stale': False, 'privacy_level': 'LOCAL_ONLY', 'document': row['document'], 'scene_ids': row['scene_ids'],
                'history_versions': [h['version'] for h in row['history']], 'automatic_promotion': False}

    def records(self, nid, scope, actor):
        items = []
        for row in self.list(nid, scope, self.RECORDS):
            if row['created_by'] != actor: continue
            try: self._check_independent_identity(nid, row)
            except (FileNotFoundError, ValueError): continue
            items.append(self._view(nid, scope, actor, row))
        return {'items': items}

    def save(self, nid, scope, actor, value, guard=lambda: None, rid=None, expected_version=None):
        body = LayoutIn.model_validate(value)
        if rid:
            original = self._row(nid, scope, actor, rid)
            if self._independent(original) != (body.source_mode == 'INDEPENDENT'):
                raise ValueError('COMIC_SOURCE_MODE_IMMUTABLE_CREATE_NEW_LAYOUT')
        if body.source_mode == 'INDEPENDENT':
            # Only a valid explicit create may establish the original project epoch.
            payload = self._payload(nid, scope, actor, body, bind_independent=False)
            guard()
            with self._independent_transaction(nid, scope, create=rid is None) as state:
                guard()
                if rid:
                    current = state['collections'].get(self.RECORDS, {}).get(rid)
                    if current is None or current.get('novel_id') != nid or current.get('scope') != scope or current.get('created_by') != actor:
                        raise FileNotFoundError(rid)
                    self._check_independent_identity(nid, current)
                    check_version(current, expected_version)
                    if len(current['history']) >= 100: raise ValueError('COMIC_REVISION_LIMIT_CREATE_NEW_LAYOUT')
                payload['project_incarnation'] = self._independent_identity(nid)
                guard(); self._current(nid, scope, actor, payload)
                if rid:
                    saved = change_row(current, actor, expected_version, lambda row: row.update(payload))
                else:
                    saved = new_row(nid, scope, actor, payload)
                    state['collections'].setdefault(self.RECORDS, {})[saved['id']] = saved
                guard()
                saved = copy.deepcopy(saved)
            return self._view(nid, scope, actor, saved)
        payload = self._payload(nid, scope, actor, body)
        if rid:
            def update(row):
                if row['created_by'] != actor: raise FileNotFoundError(rid)
                if len(row['history']) >= 100: raise ValueError('COMIC_REVISION_LIMIT_CREATE_NEW_LAYOUT')
                guard(); self._current(nid, scope, actor, payload); row.update(payload)
            saved = self.mutate(nid, scope, actor, self.RECORDS, rid, expected_version, update)
        else:
            with self.store.transaction(nid, scope) as state:
                guard(); self._current(nid, scope, actor, payload)
                saved = new_row(nid, scope, actor, payload)
                state['collections'].setdefault(self.RECORDS, {})[saved['id']] = saved
                guard()
            saved = copy.deepcopy(saved)
        return self._view(nid, scope, actor, saved)

    def adopt_generated_image(self, nid, scope, actor, rid, panel_id, expected_version, approved_asset, guard):
        """Private adapter entry: only an already approved original job result.

        The callback checks the immutable original Image approval under this
        owner transaction. It never promotes, dispatches, or changes job state.
        """
        with self._independent_transaction(nid, scope) as state:
            row = state['collections'].get(self.RECORDS, {}).get(rid)
            if row is None or row.get('created_by') != actor or row.get('novel_id') != nid or row.get('scope') != scope:
                raise FileNotFoundError(rid)
            check_version(row, expected_version)
            if len(row['history']) >= 100: raise ValueError('COMIC_REVISION_LIMIT_CREATE_NEW_LAYOUT')
            self._current(nid, scope, actor, row)
            asset = approved_asset()
            document = copy.deepcopy(row['document'])
            panel = next((p for p in document['panels'] if p['id'] == panel_id), None)
            if panel is None: raise FileNotFoundError(panel_id)
            panel['asset_id'], panel['expected_asset_version'] = asset['id'], asset['version']
            payload = self._payload(nid, scope, actor, document)
            self._current(nid, scope, actor, payload)
            approved_asset(); guard()
            saved = change_row(row, actor, expected_version, lambda current: current.update(payload))
            guard()
            saved = copy.deepcopy(saved)
        return self._view(nid, scope, actor, saved)

    def restore(self, nid, scope, actor, rid, expected_version, target_version, guard=lambda: None):
        original = self._row(nid, scope, actor, rid); check_version(original, expected_version)
        target = next((h for h in original['history'] if h['version'] == target_version), None)
        if target is None: raise FileNotFoundError('layout revision')
        self._current(nid, scope, actor, target)
        return self.save(nid, scope, actor, target['document'], guard, rid, expected_version)

    def preflight(self, nid, scope, actor, rid, expected_version):
        row = self._row(nid, scope, actor, rid); check_version(row, expected_version)
        images = self._current(nid, scope, actor, row)
        report, _ = compose(row['document'], images)
        binding = {'layout_id': rid, 'actor': actor, 'scope': scope, 'document': row['document'], 'source_evidence': row['source_evidence'],
                   'character_sources': row['character_sources'], 'asset_sources': row['asset_sources'], 'font': font_status(), 'renderer': renderer_status(), 'report': report}
        if self._independent(row): binding['project_incarnation'] = row['project_incarnation']
        return {**report, 'review_digest': digest(binding), 'version': row['version'], 'status': row['status'], 'draft': row['status'] != 'APPROVED', 'font': binding['font']}

    def approve(self, nid, scope, actor, rid, expected_version, review_digest, acknowledge_warnings, guard=lambda: None):
        def update(row):
            if row['created_by'] != actor: raise FileNotFoundError(rid)
            if row['status'] != 'DRAFT': raise ValueError('COMIC_DRAFT_REVIEW_REQUIRED')
            if len(row['history']) >= 100: raise ValueError('COMIC_REVISION_LIMIT_CREATE_NEW_LAYOUT')
            guard(); report = self.preflight(nid, scope, actor, rid, expected_version)
            if not report['can_render']: raise ValueError('COMIC_PREFLIGHT_BLOCKED')
            if report['review_digest'] != review_digest: raise StaleSourceError('COMIC_REVIEW_CHANGED')
            if report['issues'] and not acknowledge_warnings: raise ValueError('COMIC_WARNINGS_REQUIRE_REVIEW')
            guard(); self._current(nid, scope, actor, row)
            row.update(status='APPROVED', approval={'digest': review_digest, 'actor': actor, 'at': now()})
        saved = self.mutate(nid, scope, actor, self.RECORDS, rid, expected_version, update)
        return self._view(nid, scope, actor, saved)

    def _render(self, nid, scope, actor, rid, expected_version, *, approved=False, guard=lambda: None):
        row = self._row(nid, scope, actor, rid); report = self.preflight(nid, scope, actor, rid, expected_version)
        if approved and (row['status'] != 'APPROVED' or (row.get('approval') or {}).get('digest') != report['review_digest']):
            raise ValueError('COMIC_CURRENT_EXPLICIT_APPROVAL_REQUIRED')
        if not report['can_render']: raise ValueError('COMIC_PREFLIGHT_BLOCKED')
        images = self._current(nid, scope, actor, row); _, output = compose(row['document'], images, render=True)
        guard(); latest = self._row(nid, scope, actor, rid); check_version(latest, expected_version); self._current(nid, scope, actor, latest)
        if self.preflight(nid, scope, actor, rid, expected_version)['review_digest'] != report['review_digest']: raise StaleSourceError('COMIC_RENDER_SOURCE_CHANGED')
        return report, output

    def preview(self, nid, scope, actor, rid, expected_version, index, guard=lambda: None):
        report, output = self._render(nid, scope, actor, rid, expected_version, guard=guard)
        if not 0 <= index < len(output): raise FileNotFoundError('segment')
        return output[index]

    def export(self, nid, scope, actor, rid, expected_version, guard=lambda: None):
        report, output = self._render(nid, scope, actor, rid, expected_version, approved=True, guard=guard)
        row = self._row(nid, scope, actor, rid)
        panel_sources = [{'panel_id': panel['id'], 'shot_id': panel['shot_id'], 'scene_id': row['scene_ids'].get(panel['id']),
            'image_brief': panel.get('image_brief', ''), 'asset_id': panel.get('asset_id'),
            'appearance_references': panel.get('appearance_references', [])} for panel in row['document']['panels']]
        stream = io.BytesIO(); manifest = {'format': 'comic-png-segments-v1', 'layout_version': expected_version, 'review_digest': report['review_digest'],
                                          'status': 'APPROVED_LAYOUT_EXPORT_COPY', 'automatic_publication': False, 'segments': [],
                                          'panel_sources': panel_sources, 'asset_bindings': row['asset_sources'], 'privacy_level': 'LOCAL_ONLY'}
        def put(archive, name, data):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_STORED; archive.writestr(info, data)
        with zipfile.ZipFile(stream, 'w') as archive:
            for segment, data in zip(report['segments'], output):
                name = f"segment-{segment['index'] + 1:03}.png"; put(archive, name, data)
                manifest['segments'].append({**segment, 'filename': name, 'sha256': hashlib.sha256(data).hexdigest()})
            put(archive, 'manifest.json', json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
            if any(p['bubbles'] for p in self._row(nid, scope, actor, rid)['document']['panels']): put(archive, 'OFL.txt', licensed_font()[1])
        guard(); check_version(self._row(nid, scope, actor, rid), expected_version)
        if self.preflight(nid, scope, actor, rid, expected_version)['review_digest'] != report['review_digest']: raise StaleSourceError('COMIC_EXPORT_SOURCE_CHANGED')
        if len(stream.getvalue()) > MAX_OUTPUT: raise ValueError('COMIC_EXPORT_SIZE_LIMIT')
        return stream.getvalue()

    def export_ora(self, nid, scope, actor, rid, expected_version, guard=lambda: None):
        with ora_decode_budget():
            return self._export_ora(nid, scope, actor, rid, expected_version, guard)

    def _export_ora(self, nid, scope, actor, rid, expected_version, guard):
        from .comic_ora import encode_ora
        row = self._row(nid, scope, actor, rid); check_version(row, expected_version)
        if 'layer_stack' not in row['document']:
            raise ValueError('COMIC_EXPLICIT_LAYER_STACK_REQUIRED')
        report = self.preflight(nid, scope, actor, rid, expected_version)
        if row['status'] != 'APPROVED' or (row.get('approval') or {}).get('digest') != report['review_digest']:
            raise ValueError('COMIC_CURRENT_EXPLICIT_APPROVAL_REQUIRED')
        if not report['can_render']: raise ValueError('COMIC_PREFLIGHT_BLOCKED')
        guard(); images = self._current(nid, scope, actor, row)
        result = encode_ora(row['document'], images, report, expected_version)
        guard(); latest = self._row(nid, scope, actor, rid); check_version(latest, expected_version)
        self._current(nid, scope, actor, latest)
        if self.preflight(nid, scope, actor, rid, expected_version)['review_digest'] != report['review_digest']:
            raise StaleSourceError('COMIC_EXPORT_SOURCE_CHANGED')
        return result
