"""Package a validated tagged font release."""

from pathlib import Path
from sys import argv
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fontTools.ttLib import TTFont
from build import FONT_VERSION, VERSION


ROOT = Path(__file__).resolve().parents[1]

if len(argv) != 2 or argv[1] != f"v{VERSION}":
    raise SystemExit("Usage: python3 tools/package.py vX.Y.Z")

tag = argv[1]
fonts = sorted((ROOT / "fonts" / "ttf").glob("*.ttf"))
expected = f"Version {FONT_VERSION}"
if not fonts or any(TTFont(path)["name"].getDebugName(5) != expected for path in fonts):
    raise SystemExit(f"Font versions must match {tag}")

webfonts = [ROOT / "fonts" / "webfonts" / f"{path.stem}.woff2" for path in fonts]
assets = [ROOT / "OFL.txt", ROOT / "AUTHORS.txt", ROOT / "CONTRIBUTORS.txt", *fonts, *webfonts]
if len(assets) != 3 + 2 * len(fonts) or any(not path.is_file() for path in webfonts):
    raise SystemExit("Every TTF must have a WOFF2 export")
output = ROOT / "dist"
output.mkdir(exist_ok=True)
archive = output / f"Darn-{tag}.zip"
with ZipFile(archive, "w") as package:
    for asset in assets:
        entry = ZipInfo(asset.name, (1980, 1, 1, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        entry.external_attr = 0o644 << 16
        package.writestr(entry, asset.read_bytes())

checksums = [f"{sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in [archive, *assets[3:]]]
(output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
