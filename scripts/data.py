"""Download hash-pinned public ANN-Benchmarks files, separately from make demo."""

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cache = root / ".cache/data"
cache.mkdir(parents=True, exist_ok=True)
expected = {
    "sift-128-euclidean": "dd6f0a6ed6b7ebb8934680f861a33ed01ff33991eaee4fd60914d854a0ca5984",
    "glove-100-angular": "544af1d5e84e112cd4749571dcfd8ca109818a572f850af75a3a09e093a953c4",
}
rows = []
for name, pinned in expected.items():
    url = f"https://ann-benchmarks.com/{name}.hdf5"
    dest = cache / f"{name}.hdf5"
    temporary = dest.with_suffix(".download")
    candidate = dest if dest.exists() else temporary
    if not dest.exists():
        request = urllib.request.Request(
            url, headers={"User-Agent": "AtlasResearch/0.1 (+https://github.com/rjrddy/atlas)"}
        )
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
    with candidate.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != pinned:
        raise RuntimeError(f"dataset checksum mismatch: {name}; refusing unverified input")
    if candidate != dest:
        candidate.replace(dest)
    rows.append({"dataset": name, "url": url, "sha256": digest, "bytes": dest.stat().st_size})
(root / "docs/results/datasets.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
