"""Build the stitched display and UI fonts from editable centerlines."""

from pathlib import Path
import subprocess
import sys
import types
import unicodedata

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely.affinity import translate
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient
from shapely.ops import substring, unary_union


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
sys.path.insert(0, str(ROOT / "sources"))
from paths import ACCENTS, GLYPHS, STITCHED_GLYPHS  # noqa: E402

STYLES = ("Stitched", "StitchedUI")
FAMILIES = {"Stitched": "Darn Display", "StitchedUI": "Darn UI"}
FILES = {"Stitched": "Darn-Display", "StitchedUI": "Darn-UI"}
PAIR_VALUES = {
    "AV": -55, "AW": -35, "AY": -50, "AT": -30, "FA": -30,
    "LT": -30, "LY": -45, "PA": -25, "TA": -45, "Te": -35,
    "Th": -20, "To": -45, "Tu": -25, "VA": -55, "Ve": -30,
    "Vo": -35, "WA": -35, "Wo": -25, "YA": -50, "Ye": -40,
    "Yo": -45, "Wa": -20, "We": -20, "ry": -15,
}


def wanted_characters():
    characters = set(GLYPHS)
    for codepoint in list(range(0x00C0, 0x0180)) + [0x1E9E]:
        char = chr(codepoint)
        parts = unicodedata.normalize("NFD", char)
        if len(parts) > 1 and parts[0] in GLYPHS and all(mark in ACCENTS for mark in parts[1:]):
            characters.add(char)
    return characters


def form(strokes, style, char=None):
    pieces = []
    stitched_layers = []
    for points in strokes:
        if style != "Plain":
            points = [(x * 1.12, y) for x, y in points]
        line = LineString(points)
        if line.length < 25:
            dot_radius = 60 if style == "Stitched" else 49 if style == "StitchedUI" else 34
            dot = Point(points[0]).buffer(dot_radius, quad_segs=8)
            if style == "Stitched":
                stitched_layers.append((dot, None))
            else:
                pieces.append(dot)
            continue
        if style == "Stitched":
            intervals = (10, 11, 10, 12, 10, 11, 10)
            distance = 0
            stitch_index = 0
            core_width = 75 if char == "A" else 94
            strand_shapes = [line.buffer(core_width, cap_style="flat",
                                         join_style="bevel" if char == "A" else "round",
                                         quad_segs=5)]
            grooves = []
            apex = line.project(Point(295 * 1.12, 700)) if char == "A" and max(y for _, y in points) > 600 else -100
            while distance <= line.length:
                if abs(distance - apex) < 24:
                    distance += intervals[stitch_index % len(intervals)]
                    stitch_index += 1
                    continue
                center = line.interpolate(distance)
                before = line.interpolate(max(0, distance - 4))
                after = line.interpolate(min(line.length, distance + 4))
                dx, dy = after.x - before.x, after.y - before.y
                length = max((dx * dx + dy * dy) ** 0.5, 1)
                nx, ny = -dy / length, dx / length
                half_width = (80 if char == "A" else 100) + (stitch_index * 3) % 7
                skew = (-3, -1, 1, 2, 3, -2, 0)[stitch_index % 7]
                bend = (-2, 1, 0, 2, -1)[stitch_index % 5]
                thread = LineString([
                    (center.x - nx * half_width - dx / length * skew,
                     center.y - ny * half_width - dy / length * skew),
                    (center.x + dx / length * bend, center.y + dy / length * bend),
                    (center.x + nx * half_width + dx / length * skew,
                     center.y + ny * half_width + dy / length * skew),
                ])
                thickness = (7.2, 7.6, 7.4, 7.8, 7.3)[stitch_index % 5]
                strand_shapes.append(thread.buffer(thickness, cap_style="round", join_style="round", quad_segs=3))
                if 20 < distance < line.length - 20:
                    grooves.append(thread.buffer(1.8, cap_style="round", join_style="round", quad_segs=2))
                distance += intervals[stitch_index % len(intervals)]
                stitch_index += 1
            stroke_shape = unary_union(strand_shapes)
            groove_area = unary_union(grooves).intersection(stroke_shape.buffer(-5)) if grooves else None
            stitched_layers.append((stroke_shape, groove_area))
        else:
            radius = 72 if style == "StitchedUI" else 36
            pieces.append(line.buffer(radius, cap_style="round", join_style="round", quad_segs=5))
    if style == "Stitched":
        shape = None
        for stroke_shape, groove_area in stitched_layers:
            shape = stroke_shape if shape is None else shape.union(stroke_shape)
            if groove_area is not None:
                shape = shape.difference(groove_area)
    else:
        shape = unary_union(pieces)
    return shape.simplify(1.4, preserve_topology=True)


def glyph_geometry(char, style):
    if char in GLYPHS:
        strokes = STITCHED_GLYPHS.get(char, GLYPHS[char])
        shape = form(strokes, style, char)
    else:
        parts = unicodedata.normalize("NFD", char)
        base = "ı" if parts[0] == "i" else parts[0]
        base_strokes = STITCHED_GLYPHS.get(base, GLYPHS[base])
        if base == "j":
            base_strokes = base_strokes[:1]
        shape = form(base_strokes, style, base)
        top = shape.bounds[3]
        marks = []
        for mark in parts[1:]:
            mark_shape = form(ACCENTS[mark], "Plain")
            if mark in ("\u0327", "\u0328"):
                mark_shape = translate(mark_shape, yoff=-25)
            else:
                mark_shape = translate(mark_shape, yoff=top - 700 + 45)
            mark_shape = translate(mark_shape, xoff=36)
            marks.append(mark_shape)
        shape = unary_union([shape, *marks])
    return translate(shape, xoff=35 - shape.bounds[0])


def to_glyph(geometry):
    pen = TTGlyphPen(None)
    if geometry.is_empty:
        return pen.glyph()
    polygons = [geometry] if geometry.geom_type == "Polygon" else [g for g in geometry.geoms if g.geom_type == "Polygon"]
    for polygon in polygons:
        polygon = orient(polygon, sign=-1.0)
        for ring in [polygon.exterior, *polygon.interiors]:
            coordinates = [(round(x), round(y)) for x, y in ring.coords[:-1]]
            if len(set(coordinates)) < 3:
                continue
            pen.moveTo(coordinates[0])
            for coordinate in coordinates[1:]:
                pen.lineTo(coordinate)
            pen.closePath()
    return pen.glyph()


def add_kerning(font, characters):
    pairs = []
    for pair, value in PAIR_VALUES.items():
        if all(char in characters for char in pair):
            pairs.append(f"    pos uni{ord(pair[0]):04X} uni{ord(pair[1]):04X} {value};")
    feature = "feature kern {\n" + "\n".join(pairs) + "\n} kern;"
    addOpenTypeFeaturesFromString(font, feature)


def ensure_brotli():
    try:
        import brotli  # noqa: F401
    except ImportError:
        # FontTools needs the Brotli Python API. The system CLI provides the same stream format.
        shim = types.ModuleType("brotli")
        shim.MODE_FONT = 2
        shim.MODE_TEXT = 1

        def compress(data, mode=None):
            return subprocess.run(["brotli", "--stdout", "--quality=11"], input=data,
                                  capture_output=True, check=True).stdout

        def decompress(data):
            return subprocess.run(["brotli", "--stdout", "--decompress"], input=data,
                                  capture_output=True, check=True).stdout

        shim.compress = compress
        shim.decompress = decompress
        sys.modules["brotli"] = shim


def save_woff2(path):
    ensure_brotli()
    from fontTools.ttLib import woff2

    woff2.compress(str(path.with_suffix(".ttf")), str(path))


def build(style, characters):
    family = FAMILIES[style]
    ascent = 1120
    descent = 330
    order = [".notdef", "space"] + [f"uni{ord(char):04X}" for char in sorted(characters)]
    notdef = Point(300, 350).buffer(225).boundary.buffer(28)
    glyphs = {".notdef": to_glyph(notdef), "space": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (600, 47), "space": (320, 0)}
    cmap = {32: "space"}
    for char in sorted(characters):
        name = f"uni{ord(char):04X}"
        shape = glyph_geometry(char, style)
        advance = round(shape.bounds[2] + 35)
        glyphs[name] = to_glyph(shape)
        metrics[name] = (advance, round(shape.bounds[0]))
        cmap[ord(char)] = name
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{family} {VERSION}",
        "fullName": family,
        "psName": f"{FILES[style].replace('-', '')}-Regular",
        "version": f"Version {VERSION}",
        "copyright": "\n".join((ROOT / "OFL.txt").read_text().splitlines()[:2]),
        "licenseDescription": "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org",
        "licenseInfoURL": "https://openfontlicense.org",
    })
    builder.setupOS2(
        version=4,
        sTypoAscender=ascent, sTypoDescender=-descent,
        usWinAscent=ascent, usWinDescent=descent,
        sxHeight=490, sCapHeight=700,
        usWeightClass=800 if style == "Stitched" else 700,
        fsSelection=0xC0, fsType=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    font.recalcTimestamp = False
    font["head"].created = 3876595200
    font["head"].modified = 3876595200
    add_kerning(font, characters)
    target = ROOT / "fonts" / f"{FILES[style]}.ttf"
    font.save(target)
    save_woff2(target.with_suffix(".woff2"))
    print(f"{family}: {len(cmap)} characters -> TTF and WOFF2")


if __name__ == "__main__":
    characters = wanted_characters()
    for variant in STYLES:
        build(variant, characters)
