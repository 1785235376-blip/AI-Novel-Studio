"""Bounded logical layer references over the original Comic document.

No text, geometry, assets or persistence are owned here. Items are bottom first;
their referenced panel/bubble remains the single editable source of truth.
"""
from __future__ import annotations

from typing import Literal, Annotated
from contextlib import contextmanager
from contextvars import ContextVar
from pydantic import Field, model_validator, field_validator
from .media import StrictModel

MAX_LAYER_PIXELS = 64_000_000
MAX_LAYER_SOURCE_PIXELS = 64_000_000
MAX_ORA_DECODE_PIXELS = 128_000_000
_ora_decode_remaining = ContextVar('comic_ora_decode_remaining', default=None)


@contextmanager
def ora_decode_budget():
    """Count actual decoder work across every approval/source/export recheck."""
    token = _ora_decode_remaining.set([MAX_ORA_DECODE_PIXELS])
    try:
        yield
    finally:
        _ora_decode_remaining.reset(token)


def consume_decode_pixels(pixels):
    remaining = _ora_decode_remaining.get()
    if remaining is not None:
        if pixels > remaining[0]:
            raise ValueError('COMIC_ORA_DECODE_WORK_LIMIT_128000000')
        remaining[0] -= pixels


class ComicLayer(StrictModel):
    id: str = Field(pattern=r'^layer_[A-Za-z0-9_-]{1,74}$')
    kind: Literal['PANEL_ART', 'PANEL_FRAME', 'BUBBLE_SHAPE', 'BUBBLE_TEXT']
    target_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=120)
    visible: bool = Field(default=True, strict=True)
    opacity_percent: int = Field(default=100, ge=0, le=100, strict=True)

    @model_validator(mode='after')
    def plain_name(self):
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in self.name):
            raise ValueError('COMIC_LAYER_NAME_INVALID')
        return self


class ComicRasterPin(StrictModel):
    version: int = Field(ge=2, strict=True)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    review_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class ComicRasterLayer(ComicLayer):
    kind: Literal['RASTER']
    pin: ComicRasterPin
    x: int = Field(ge=-12000, le=12000, strict=True)
    y: int = Field(ge=-12000, le=12000, strict=True)
    width: int = Field(ge=1, le=16000, strict=True)
    height: int = Field(ge=1, le=16000, strict=True)

    @model_validator(mode='after')
    def bounded_pixels(self):
        if self.width * self.height > 20_000_000:
            raise ValueError('COMIC_RASTER_PIXEL_LIMIT')
        return self


class ComicLayerStack(StrictModel):
    schema_version: Literal[1]
    items: list[Annotated[ComicLayer | ComicRasterLayer, Field(discriminator='kind')]] = Field(max_length=256)

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int:
            raise ValueError('COMIC_LAYER_SCHEMA_INVALID')
        return value

    @model_validator(mode='after')
    def unique(self):
        if len({i.id for i in self.items}) != len(self.items):
            raise ValueError('COMIC_DUPLICATE_LAYER_ID')
        return self


def validate_references(stack, panels):
    expected = {(kind, p.id) for p in panels for kind in ('PANEL_ART', 'PANEL_FRAME')}
    expected |= {(kind, b.id) for p in panels for b in p.bubbles for kind in ('BUBBLE_SHAPE', 'BUBBLE_TEXT')}
    actual = [(i.kind, i.target_id) for i in stack.items if i.kind != 'RASTER']
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('COMIC_LAYER_REFERENCE_COVERAGE_REQUIRED')
    # Count hidden layers too: export preserves their pixels for later editing.
    pixels = 2 * sum(p.width * p.height + sum(b.width * b.height for b in p.bubbles) for p in panels)
    pixels += sum(i.width * i.height for i in stack.items if i.kind == 'RASTER')
    if pixels > MAX_LAYER_PIXELS:
        raise ValueError('COMIC_LAYER_PIXEL_LIMIT_64000000')


def iter_layer_images(document, images, placements, text=None):
    """Yield one cropped transparent RGBA surface at a time, never N full pages."""
    from PIL import Image, ImageDraw
    from .comic_layouts import _image, _text_layout, licensed_font
    panels = {p['id']: p for p in document['panels']}
    bubbles = {b['id']: b for p in document['panels'] for b in p['bubbles']}
    if text is None:
        text = {}
        if bubbles:
            font_data, _, coverage = licensed_font()
            text = {bid: _text_layout(b, font_data, coverage) for bid, b in bubbles.items()}
    pixel_budget = [MAX_LAYER_SOURCE_PIXELS]
    for item in document['layer_stack']['items']:
        kind = item['kind']
        if kind == 'RASTER':
            surface = _image(images[item['target_id']], pixel_budget=pixel_budget)
            if surface.size != (item['width'], item['height']):
                surface.close()
                raise ValueError('COMIC_RASTER_DIMENSIONS_CHANGED')
            yield item, item['x'], item['y'], surface
            continue
        obj = (panels if kind.startswith('PANEL_') else bubbles)[item['target_id']]
        surface = Image.new('RGBA', (obj['width'], obj['height']), (0, 0, 0, 0))
        draw = ImageDraw.Draw(surface)
        box = (0, 0, obj['width'] - 1, obj['height'] - 1)
        if kind == 'PANEL_ART' and obj.get('artwork_mode', 'IMAGE') != 'BLANK':
            placement = placements[obj['id']]
            source = _image(images[obj['asset_id']], pixel_budget=pixel_budget)
            resized = source.resize(placement['size'], Image.Resampling.LANCZOS)
            surface.paste('white', box=(0, 0, obj['width'], obj['height']))
            surface.alpha_composite(resized, placement['offset'])
            source.close(); resized.close()
        elif kind == 'PANEL_FRAME':
            draw.rectangle(box, outline='black', width=2)
        elif kind == 'BUBBLE_SHAPE':
            draw.rounded_rectangle(box, radius=16 if obj['kind'] == 'DIALOGUE' else 0, fill='white', outline='black', width=2)
        elif kind == 'BUBBLE_TEXT':
            font, lines, line_height = text[obj['id']]
            for index, line in enumerate(lines):
                draw.text((12, 12 + index * line_height), line, font=font, fill='black', anchor='lt')
        yield item, obj['x'], obj['y'], surface


def composite_layer(canvas, item, x, y, surface):
    if not item['visible'] or item['opacity_percent'] == 0:
        return
    if item['opacity_percent'] != 100:
        surface = surface.copy()
        percent = item['opacity_percent']
        surface.putalpha(surface.getchannel('A').point(lambda a: (a * percent + 50) // 100))
    canvas.alpha_composite(surface, (x, y))
