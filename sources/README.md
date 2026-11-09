The editable letter paths are in `paths.py`.
The `ufo/` directories are generated Unified Font Object sources with glyph outlines, metrics, and OpenType features.
Edit `paths.py` for lasting changes because each build replaces the UFO files.
Install the pinned packages in `requirements.txt`, then run `bash sources/build.sh` from the repository root to regenerate the UFO, TTF, and WOFF2 files.
