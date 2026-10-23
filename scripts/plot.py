"""Export the saved public benchmark curves; no imported speed claims."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
runs = [
    json.loads(p.read_text()) for p in sorted((root / "docs/results").glob("*-1000000.json"))
] + [
    json.loads(p.read_text())
    for p in sorted((root / "docs/results").glob("glove-100-angular-1183514.json"))
]
fig, axes = plt.subplots(1, len(runs), figsize=(7 * len(runs), 4.5), squeeze=False)
for ax, run in zip(axes[0], runs, strict=True):
    groups = list(dict.fromkeys((r["engine"], r["algorithm"]) for r in run["rows"]))
    for engine, algorithm in groups:
        points = [r for r in run["rows"] if r["engine"] == engine and r["algorithm"] == algorithm]
        ax.plot(
            [r["qps_median"] for r in points],
            [r["recall_at_10"] for r in points],
            "o-",
            label=f"{engine} {algorithm}",
        )
    ax.set(
        xscale="log",
        xlabel="Single-query calls / second (median trial)",
        ylabel="Recall@10",
        title=f"{run['dataset']}\n{run['base_vectors']:,} base · {run['query_count']} queries",
        ylim=(0, 1.02),
    )
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(root / "docs/results/recall-qps.svg")
plt.close(fig)
print("Exported recall-qps.svg from saved raw JSON")
