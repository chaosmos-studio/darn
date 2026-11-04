"""Check exports, coverage, metrics, outlines, and WOFF2 round trips."""

from pathlib import Path

from fontTools.ttLib import TTFont

from build import FAMILIES, FILES, STYLES, VERSION, ensure_brotli, wanted_characters


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {32, *(ord(char) for char in wanted_characters())}
PROOF_TEXT = "PLAY LEVELS SETTINGS SHIFT The First Stitch 0123456789 A small shift can change a whole world. Il1 O0 Café forêt naïve Ångström"


def check(style):
    path = ROOT / "fonts" / f"{FILES[style]}.ttf"
    woff_path = path.with_suffix(".woff2")
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
    assert font["OS/2"].usWinAscent >= font["head"].yMax, style
    assert font["OS/2"].usWinDescent >= -font["head"].yMin, style
    assert "GPOS" in font, style
    assert font["name"].getDebugName(1) == FAMILIES[style], style
    assert font["name"].getDebugName(2) == "Regular", style
    assert font["name"].getDebugName(5) == f"Version {VERSION}", style
    assert font["name"].getDebugName(0).splitlines() == (ROOT / "OFL.txt").read_text().splitlines()[:2], style
    assert webfont.flavor == "woff2", style
    for codepoint, name in cmap.items():
        if codepoint == 32:
            continue
        glyph = font["glyf"][name]
        assert glyph.numberOfContours > 0, (style, codepoint)
        assert font["hmtx"][name][1] == glyph.xMin, (style, codepoint)
    print(f"{style}: {len(cmap)} mapped characters, TTF and WOFF2 pass")


if __name__ == "__main__":
    ensure_brotli()
    for variant in STYLES:
        check(variant)
