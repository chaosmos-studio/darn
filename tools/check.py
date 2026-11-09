"""Check exports, coverage, metrics, outlines, and WOFF2 round trips."""

from pathlib import Path

from fontTools.ttLib import TTFont

from build import (BLANK_ADVANCES, FAMILIES, FONT_VERSION, STYLES, WEIGHTS, ensure_brotli,
                   filename, wanted_characters)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {32, *(ord(char) for char in wanted_characters())}
PROOF_TEXT = "PLAY LEVELS SETTINGS SHIFT The First Stitch 0123456789 A small shift can change a whole world. Il1 O0 Café forêt naïve Ångström"


def check(style, weight):
    stem = filename(style, weight)
    path = ROOT / "fonts" / "ttf" / f"{stem}.ttf"
    woff_path = ROOT / "fonts" / "webfonts" / f"{stem}.woff2"
    assert (ROOT / "sources" / "ufo" / f"{stem}.ufo").is_dir()
    font = TTFont(path)
    webfont = TTFont(woff_path)
    cmap = font.getBestCmap()
    assert set(cmap) == EXPECTED, style
    assert webfont.getBestCmap() == cmap, style
    assert set(webfont.keys()) == set(font.keys()), style
    for table in font.keys():
        if table not in ("GlyphOrder", "head"):
            assert webfont.getTableData(table) == font.getTableData(table), (style, table)
    assert set(map(ord, PROOF_TEXT)) <= set(cmap), style
    assert font["head"].unitsPerEm == 1000, style
    assert font["OS/2"].fsType == 0, style
    assert font["OS/2"].fsSelection & 0x80, style
    assert font["OS/2"].usWeightClass == {"Regular": 400, "Bold": 700, "ExtraBold": 800}[weight]
    assert font["OS/2"].ulCodePageRange1 & 1
    assert font["OS/2"].usWinAscent >= font["head"].yMax, style
    assert font["OS/2"].usWinDescent >= -font["head"].yMin, style
    assert "GPOS" in font, style
    assert "GSUB" in font, style
    expected_family = f"{FAMILIES[style]} ExtraBold" if weight == "ExtraBold" else FAMILIES[style]
    assert font["name"].getDebugName(1) == expected_family, style
    assert font["name"].getDebugName(2) == ("Bold" if weight == "Bold" else "Regular"), style
    assert font["name"].getDebugName(4) == f"{FAMILIES[style]} {weight}", style
    assert font["name"].getDebugName(5) == f"Version {FONT_VERSION}", style
    assert font["name"].getDebugName(0) == "; ".join((ROOT / "OFL.txt").read_text().split("\n\n", 1)[0].splitlines()), style
    assert font["head"].fontRevision == 1.0
    assert font["gasp"].gaspRange == {65535: 0x000F}
    assert webfont.flavor == "woff2", style
    for codepoint, name in cmap.items():
        if codepoint == 32 or chr(codepoint) in BLANK_ADVANCES:
            continue
        glyph = font["glyf"][name]
        assert glyph.numberOfContours > 0, (style, codepoint)
        assert font["hmtx"][name][1] == glyph.xMin, (style, codepoint)
    tabular_widths = {font["hmtx"][f"uni{ord(char):04X}.tnum"][0] for char in "0123456789"}
    assert len(tabular_widths) == 1
    print(f"{FAMILIES[style]} {weight}: {len(cmap)} mapped characters, TTF and WOFF2 pass")


if __name__ == "__main__":
    ensure_brotli()
    for variant in STYLES:
        for font_weight in WEIGHTS[variant]:
            check(variant, font_weight)
