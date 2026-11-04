"""Package a validated tagged font release."""

from pathlib import Path
from sys import argv
from zipfile import ZIP_DEFLATED, ZipFile

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]

if len(argv) != 2 or not argv[1].startswith("v"):
    raise SystemExit("Usage: python3 tools/package.py vX.Y.Z")

tag = argv[1]
fonts = sorted((ROOT / "fonts").glob("*.ttf"))
expected = f"Version {tag[1:]}"
if not fonts or any(TTFont(path)["name"].getDebugName(5) != expected for path in fonts):
    raise SystemExit(f"Font versions must match {tag}")

assets = [ROOT / "OFL.txt", *sorted((ROOT / "fonts").glob("*.ttf")),
          *sorted((ROOT / "fonts").glob("*.woff2"))]
output = ROOT / "dist"
output.mkdir(exist_ok=True)
with ZipFile(output / f"Darn-{tag}.zip", "w", ZIP_DEFLATED) as package:
    for asset in assets:
        package.write(asset, asset.name)
