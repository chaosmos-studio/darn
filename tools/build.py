"""Build the stitched display and UI fonts from editable centerlines."""

from pathlib import Path
import subprocess
import sys
import types
import unicodedata

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from shapely.affinity import translate
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient
from shapely.ops import substring, unary_union
from ufoLib2 import Font


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
FONT_VERSION = "1.000"
sys.path.insert(0, str(ROOT / "sources"))
from paths import ACCENTS, EXTRA_COMPOSED, GLYPHS, STITCHED_GLYPHS  # noqa: E402

STYLES = ("Stitched", "StitchedUI")
FAMILIES = {"Stitched": "Darn Display", "StitchedUI": "Darn Text"}
WEIGHTS = {"Stitched": ("Regular", "ExtraBold"), "StitchedUI": ("Regular", "Bold")}
FILE_PREFIX = {"Stitched": "DarnDisplay", "StitchedUI": "DarnText"}
BLANK_ADVANCES = {"\u00A0": 320, "\u2028": 0, "\u2029": 0}
MATH_SIGNS = "+=<>×÷−"


def filename(style, weight):
    return f"{FILE_PREFIX[style]}-{weight}"
PAIR_VALUES = {
    "AV": -55, "AW": -35, "AY": -50, "AT": -30, "FA": -30,
    "LT": -30, "LY": -45, "PA": -25, "TA": -45, "Te": -35,
    "Th": -20, "To": -45, "Tu": -25, "VA": -55, "Ve": -30,
    "Vo": -35, "WA": -35, "Wo": -25, "YA": -50, "Ye": -40,
    "Yo": -45, "Wa": -20, "We": -20, "ry": -15,
}


def wanted_characters():
    characters = set(GLYPHS) | set(ACCENTS) | set(EXTRA_COMPOSED) | set(BLANK_ADVANCES)
    for codepoint in list(range(0x00C0, 0x0180)) + [0x1E9E]:
        char = chr(codepoint)
        parts = unicodedata.normalize("NFD", char)
        if len(parts) > 1 and parts[0] in GLYPHS and all(mark in ACCENTS for mark in parts[1:]):
            characters.add(char)
    return characters


def form(strokes, style, char=None):
    regular = style.endswith("Regular")
    design = style.removesuffix("Regular") if regular else style
    pieces = []
    stitched_layers = []
    for points in strokes:
        if design != "Plain":
            points = [(x * 1.12, y) for x, y in points]
        line = LineString(points)
        if line.length < 25:
            dot_radius = 60 if design == "Stitched" else 49 if design == "StitchedUI" else 34
            if regular:
                dot_radius = round(dot_radius * 0.68)
            dot = Point(points[0]).buffer(dot_radius, quad_segs=8)
            if design == "Stitched":
                stitched_layers.append((dot, None))
            else:
                pieces.append(dot)
            continue
        if design == "Stitched":
            intervals = (10, 11, 10, 12, 10, 11, 10)
            distance = 0
            stitch_index = 0
            core_width = {"A": 75, "e": 70, "g": 75, "m": 75, "&": 60, "@": 50}.get(char, 94)
            if regular:
                core_width = round(core_width * 0.63)
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
                half_width = {"A": 80, "e": 72, "g": 80, "m": 82, "&": 68, "@": 55}.get(char, 100) + (stitch_index * 3) % 7
                if regular:
                    half_width = round(half_width * 0.64)
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
                if regular:
                    thickness *= 0.72
                strand_shapes.append(thread.buffer(thickness, cap_style="round", join_style="round", quad_segs=3))
                if 20 < distance < line.length - 20:
                    grooves.append(thread.buffer(1.3 if regular else 1.8, cap_style="round", join_style="round", quad_segs=2))
                distance += intervals[stitch_index % len(intervals)]
                stitch_index += 1
            stroke_shape = unary_union(strand_shapes)
            groove_area = unary_union(grooves).intersection(stroke_shape.buffer(-5)) if grooves else None
            stitched_layers.append((stroke_shape, groove_area))
        else:
            radius = (62 if char == "&" else 72) if design == "StitchedUI" else 36
            if regular:
                radius = round(radius * 0.6)
            pieces.append(line.buffer(radius, cap_style="round", join_style="round", quad_segs=5))
    if design == "Stitched":
        if char == "m":
            shape = unary_union([
                stroke_shape.difference(groove_area) if groove_area is not None else stroke_shape
                for stroke_shape, groove_area in stitched_layers
            ])
        else:
            shape = None
            for stroke_shape, groove_area in stitched_layers:
                shape = stroke_shape if shape is None else shape.union(stroke_shape)
                if groove_area is not None:
                    shape = shape.difference(groove_area)
    else:
        shape = unary_union(pieces)
    return shape.simplify(1.4, preserve_topology=True)


def glyph_geometry(char, style, dotless_i=False):
    if char in ACCENTS:
        shape = form(ACCENTS[char], "Plain")
    elif char in GLYPHS:
        strokes = STITCHED_GLYPHS.get(char, GLYPHS[char])
        shape = form(strokes, style, char)
    else:
        parts = unicodedata.normalize("NFD", char)
        base = "i" if char == "į" and not dotless_i else "ı" if parts[0] == "i" else parts[0]
        base_strokes = STITCHED_GLYPHS.get(base, GLYPHS[base])
        if base == "j":
            base_strokes = base_strokes[:1]
        shape = form(base_strokes, style, base)
        top = shape.bounds[3]
        marks = []
        for mark in parts[1:]:
            mark_shape = form(ACCENTS[mark], "Plain")
            if mark in ("\u0326", "\u0327", "\u0328"):
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


def feature_text(characters, bounds):
    pairs = []
    for pair, value in PAIR_VALUES.items():
        if all(char in characters for char in pair):
            pairs.append(f"    pos uni{ord(pair[0]):04X} uni{ord(pair[1]):04X} {value};")
    bottom_marks = {"\u0326", "\u0327", "\u0328"}
    classes = []
    for mark in ACCENTS:
        left, bottom, right, top = bounds[f"uni{ord(mark):04X}"]
        x = round((left + right) / 2)
        side = "BOTTOM" if mark in bottom_marks else "TOP"
        y = 0 if side == "BOTTOM" else 700
        classes.append(f"markClass uni{ord(mark):04X} <anchor {x} {y}> @{side};")
    base_positions = []
    for char in sorted(characters - set(ACCENTS) - set(BLANK_ADVANCES)):
        left, bottom, right, top = bounds[f"uni{ord(char):04X}"]
        x = round((left + right) / 2)
        base_positions.append(
            f"  pos base uni{ord(char):04X} <anchor {x} {round(top + 35)}> mark @TOP "
            f"<anchor {x} {round(min(bottom, 0) - 25)}> mark @BOTTOM;"
        )
    stacked_positions = []
    for mark in ACCENTS:
        left, bottom, right, top = bounds[f"uni{ord(mark):04X}"]
        x = round((left + right) / 2)
        side = "BOTTOM" if mark in bottom_marks else "TOP"
        y = round(bottom - 25) if side == "BOTTOM" else round(top + 35)
        stacked_positions.append(f"  pos mark uni{ord(mark):04X} <anchor {x} {y}> mark @{side};")
    tabular = " ".join(f"uni{ord(char):04X}" for char in "0123456789")
    tabular_alt = " ".join(f"uni{ord(char):04X}.tnum" for char in "0123456789")
    above = " ".join(f"uni{ord(mark):04X}" for mark in ACCENTS if mark not in bottom_marks)
    return "\n".join([
        f"@above = [{above}];",
        *classes,
        "feature ccmp { sub uni0069' @above by uni0131; sub uni006A' @above by uni0237; sub uni012F' @above by uni012F.dotless; } ccmp;",
        "feature kern {", *pairs, "} kern;",
        "feature mark {", *base_positions, "} mark;",
        "feature mkmk {", *stacked_positions, "} mkmk;",
        f"feature tnum {{ sub [{tabular}] by [{tabular_alt}]; }} tnum;",
    ])


def save_ufo(font, family, weight, style, features, cmap):
    source = Font()
    info = source.info
    info.familyName = family
    info.styleName = weight
    info.unitsPerEm = 1000
    info.ascender = font["hhea"].ascent
    info.descender = font["hhea"].descent
    info.capHeight = 700
    info.xHeight = 490
    info.versionMajor = 1
    info.versionMinor = 0
    info.copyright = font["name"].getDebugName(0)
    info.postscriptFontName = filename(style, weight)
    info.openTypeNameDesigner = "Shravanpuri Goswami"
    info.openTypeNameDesignerURL = "https://github.com/shravanngoswamii"
    info.openTypeNameManufacturer = "Chaosmos Studio"
    info.openTypeNameManufacturerURL = "https://chaosmos.studio"
    info.openTypeNameLicense = font["name"].getDebugName(13)
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeNameUniqueID = f"{FONT_VERSION};Chaosmos Studio;{filename(style, weight)}"
    info.openTypeOS2WeightClass = font["OS/2"].usWeightClass
    info.openTypeOS2Selection = [7, 8]
    info.openTypeOS2Type = []
    info.openTypeOS2VendorID = "CHAO"
    info.openTypeOS2CodePageRanges = [0]
    info.openTypeOS2TypoAscender = font["OS/2"].sTypoAscender
    info.openTypeOS2TypoDescender = font["OS/2"].sTypoDescender
    info.openTypeOS2TypoLineGap = 0
    info.openTypeOS2WinAscent = font["OS/2"].usWinAscent
    info.openTypeOS2WinDescent = font["OS/2"].usWinDescent
    info.openTypeHheaAscender = font["hhea"].ascent
    info.openTypeHheaDescender = font["hhea"].descent
    info.openTypeHheaLineGap = 0
    source.lib["public.glyphOrder"] = font.getGlyphOrder()
    unicodes = {name: codepoint for codepoint, name in cmap.items()}
    for name in font.getGlyphOrder():
        glyph = source.newGlyph(name)
        glyph.width = font["hmtx"][name][0]
        if name in unicodes:
            glyph.unicodes = [unicodes[name]]
        font["glyf"][name].draw(glyph.getPen(), font["glyf"])
    source.features.text = features
    path = ROOT / "sources" / "ufo" / f"{filename(style, weight)}.ufo"
    path.parent.mkdir(parents=True, exist_ok=True)
    source.save(path, overwrite=True)
    return path


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


def save_woff2(source, target):
    ensure_brotli()
    from fontTools.ttLib import woff2

    woff2.compress(str(source), str(target))


def build(style, weight, characters):
    family = FAMILIES[style]
    drawing = f"{style}Regular" if weight == "Regular" else style
    ascent = 1120
    descent = 330
    order = [".notdef", "space"] + [f"uni{ord(char):04X}" for char in sorted(characters)]
    order += [f"uni{ord(char):04X}.tnum" for char in "0123456789"]
    order.append("uni012F.dotless")
    notdef = Point(300, 350).buffer(225).boundary.buffer(28)
    glyphs = {".notdef": to_glyph(notdef), "space": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (600, 47), "space": (320, 0)}
    cmap = {32: "space"}
    for blank, advance in BLANK_ADVANCES.items():
        name = f"uni{ord(blank):04X}"
        glyphs[name] = TTGlyphPen(None).glyph()
        metrics[name] = (advance, 0)
        cmap[ord(blank)] = name
    bounds = {}
    digit_shapes = {}
    math_shapes = {}
    for char in sorted(characters):
        if char in BLANK_ADVANCES:
            continue
        name = f"uni{ord(char):04X}"
        shape = glyph_geometry(char, drawing)
        bounds[name] = shape.bounds
        advance = 0 if char in ACCENTS else round(shape.bounds[2] + 35)
        glyphs[name] = to_glyph(shape)
        metrics[name] = (advance, round(shape.bounds[0]))
        cmap[ord(char)] = name
        if char in "0123456789":
            digit_shapes[char] = shape
        if char in MATH_SIGNS:
            math_shapes[char] = shape
    math_width = max(metrics[f"uni{ord(char):04X}"][0] for char in MATH_SIGNS)
    for char, shape in math_shapes.items():
        name = f"uni{ord(char):04X}"
        centered = translate(shape, xoff=round((math_width - metrics[name][0]) / 2))
        glyphs[name] = to_glyph(centered)
        metrics[name] = (math_width, round(centered.bounds[0]))
        bounds[name] = centered.bounds
    tabular_width = {"Stitched": 800, "StitchedUI": 760}[style]
    for char, shape in digit_shapes.items():
        name = f"uni{ord(char):04X}.tnum"
        width = metrics[f"uni{ord(char):04X}"][0]
        centered = translate(shape, xoff=round((tabular_width - width) / 2))
        glyphs[name] = to_glyph(centered)
        metrics[name] = (tabular_width, round(centered.bounds[0]))
    dotless = glyph_geometry("į", drawing, dotless_i=True)
    glyphs["uni012F.dotless"] = to_glyph(dotless)
    metrics["uni012F.dotless"] = metrics["uni012F"]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    names = {
        "familyName": f"{family} ExtraBold" if weight == "ExtraBold" else family,
        "styleName": "Bold" if weight == "Bold" else "Regular",
        "uniqueFontIdentifier": f"{family} {weight} {FONT_VERSION}",
        "fullName": f"{family} {weight}",
        "psName": filename(style, weight),
        "version": f"Version {FONT_VERSION}",
        "copyright": "; ".join((ROOT / "OFL.txt").read_text().split("\n\n", 1)[0].splitlines()),
        "manufacturer": "Chaosmos Studio",
        "designer": "Shravanpuri Goswami",
        "vendorURL": "https://chaosmos.studio",
        "designerURL": "https://github.com/shravanngoswamii",
        "licenseDescription": "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org",
        "licenseInfoURL": "https://openfontlicense.org",
    }
    if weight == "ExtraBold":
        names["typographicFamily"] = family
        names["typographicSubfamily"] = weight
    builder.setupNameTable(names, mac=False)
    builder.setupOS2(
        version=4,
        sTypoAscender=ascent, sTypoDescender=-descent,
        usWinAscent=ascent, usWinDescent=descent,
        sxHeight=490, sCapHeight=700,
        usWeightClass={"Regular": 400, "Bold": 700, "ExtraBold": 800}[weight],
        fsSelection=0x1A0 if weight == "Bold" else 0x1C0, fsType=0,
        achVendID="CHAO",
        ulCodePageRange1=1, ulCodePageRange2=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    font["head"].fontRevision = 1.0
    if weight == "Bold":
        font["head"].macStyle = 1
    font.recalcTimestamp = False
    font["head"].created = 3876595200
    font["head"].modified = 3876595200
    source = save_ufo(font, family, weight, style, feature_text(characters, bounds), cmap)
    target = ROOT / "fonts" / "ttf" / f"{filename(style, weight)}.ttf"
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "fontmake", "-u", str(source),
                    "-o", "ttf", "--output-path", str(target)],
                   capture_output=True, text=True, check=True)
    compiled = TTFont(target)
    compiled["OS/2"].fsType = 0
    compiled["head"].created = 3876595200
    compiled["head"].modified = 3876595200
    compiled.recalcTimestamp = False
    gasp = newTable("gasp")
    gasp.gaspRange = {65535: 0x000F}
    compiled["gasp"] = gasp
    meta = newTable("meta")
    meta.data = {"dlng": "Latn", "slng": "Latn"}
    compiled["meta"] = meta
    buildStatTable(compiled, [{"tag": "wght", "name": "Weight", "values": [
        {"value": {"Regular": 400, "Bold": 700, "ExtraBold": 800}[weight],
         "name": weight, "flags": 0x2 if weight == "Regular" else 0}
    ]}])
    compiled.save(target)
    web_target = ROOT / "fonts" / "webfonts" / f"{filename(style, weight)}.woff2"
    web_target.parent.mkdir(parents=True, exist_ok=True)
    save_woff2(target, web_target)
    print(f"{family} {weight}: {len(cmap)} characters -> TTF and WOFF2")


if __name__ == "__main__":
    characters = wanted_characters()
    for variant in STYLES:
        for weight in WEIGHTS[variant]:
            build(variant, weight, characters)
