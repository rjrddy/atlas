"""Download public ANN-Benchmarks distributions. Never part of make demo."""

import hashlib
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cache = root / ".cache/data"
cache.mkdir(parents=True, exist_ok=True)
rows = []
for name in ["sift-128-euclidean", "glove-100-angular"]:
    url = f"https://ann-benchmarks.com/{name}.hdf5"
    dest = cache / f"{name}.hdf5"
    if not dest.exists():
        temporary = dest.with_suffix(".download")
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(dest)
    with dest.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    rows.append({"dataset": name, "url": url, "sha256": digest, "bytes": dest.stat().st_size})
(root / "docs/results/datasets.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
