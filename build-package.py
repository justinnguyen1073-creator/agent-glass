#!/usr/bin/env python3
"""Build a self-contained Plasma package using only the standard library."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
target = root / "dist" / "codex-glass.plasmoid"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for name in ("metadata.json", "LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        archive.write(root / name, name)
    for path in sorted((root / "contents").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            archive.write(path, path.relative_to(root))
print(target)
