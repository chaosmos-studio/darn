"""Package a validated tagged font release."""

from pathlib import Path
from sys import argv
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fontTools.ttLib import TTFont
from build import VERSION


ROOT = Path(__file__).resolve().parents[1]

if len(argv) != 2 or argv[1] != f"v{VERSION}":
    raise SystemExit("Usage: python3 tools/package.py vX.Y.Z")

tag = argv[1]
fonts = sorted((ROOT / "fonts").glob("*.ttf"))
expected = f"Version {tag[1:]}"
if not fonts or any(TTFont(path)["name"].getDebugName(5) != expected for path in fonts):
    raise SystemExit(f"Font versions must match {tag}")

assets = [ROOT / "OFL.txt", *sorted((ROOT / "fonts").glob("*.ttf")),
          *sorted((ROOT / "fonts").glob("*.woff2"))]
if len(assets) != 1 + 2 * len(fonts) or any(not path.with_suffix(".woff2").is_file() for path in fonts):
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

checksums = [f"{sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in [archive, *assets[1:]]]
(output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
