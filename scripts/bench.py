"""Single-thread, single-query end-to-end native binding comparison, public data."""

import argparse
import gc
import hashlib
import json
import os
import platform
import resource
import time
from pathlib import Path

import atlas_native
import faiss
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(dataset: str, limit: int, queries: int) -> dict:
    faiss.omp_set_num_threads(1)
    file = ROOT / ".cache/data" / f"{dataset}.hdf5"
    with h5py.File(file) as h:
        total = len(h["train"])
        base = np.array(h["train"][: min(limit, total)], dtype="float32")
        query = np.array(h["test"][:queries], dtype="float32")
    if dataset.startswith("glove"):
        faiss.normalize_L2(base)
        faiss.normalize_L2(query)
    n, d = base.shape
    started = time.perf_counter()
    truth = faiss.IndexFlatL2(d)
    truth.add(base)
    expected = truth.search(query, 10)[1]
    truth_s = time.perf_counter() - started
    del truth
    qlists = query.tolist()
    qarrays = [q.reshape(1, -1) for q in query]
    tags = [i % 8 for i in range(n)]
    rows = []
    builds = []
    for engine in ["atlas", "faiss-hnsw", "faiss-ivf"]:
        started = time.perf_counter()
        if engine == "atlas":
            index = atlas_native.Index(base, tags, 12, 80, 32, 42)
        elif engine == "faiss-hnsw":
            index = faiss.IndexHNSWFlat(d, 12)
            index.hnsw.efConstruction = 80
            index.add(base)
        else:
            index = faiss.IndexIVFFlat(faiss.IndexFlatL2(d), d, 32)
            index.cp.seed = 42
            index.cp.niter = 8
            index.train(base)
            index.add(base)
        build_s = time.perf_counter() - started
        if engine == "atlas":
            memory = index.allocated_bytes
            memory_kind = (
                "C++ capacities incl both indexes, vectors once; excludes allocator/scratch/Python"
            )
            index.save(str(ROOT / ".cache" / f"{dataset}.atlas"))
            disk = (ROOT / ".cache" / f"{dataset}.atlas").stat().st_size
            settings = [("hnsw", e) for e in [10, 32, 80, 200]] + [
                ("ivf", e) for e in [1, 4, 16, 32]
            ]
        else:
            memory = len(faiss.serialize_index(index))
            memory_kind = "FAISS serialized bytes, not heap/RSS; separate index"
            disk = memory
            settings = [
                (engine.removeprefix("faiss-"), e)
                for e in ([10, 32, 80, 200] if engine.endswith("hnsw") else [1, 4, 16, 32])
            ]
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        builds.append(
            {
                "engine": engine,
                "seconds": build_s,
                "bytes": memory,
                "bytes_per_vector": memory / n,
                "memory_kind": memory_kind,
                "serialized_bytes": disk,
                "process_highwater_bytes_so_far": peak
                if platform.system() == "Darwin"
                else peak * 1024,
            }
        )
        for algorithm, effort in settings:
            if engine == "faiss-hnsw":
                index.hnsw.efSearch = effort
            elif engine == "faiss-ivf":
                index.nprobe = effort

            def search(
                j: int, index=index, engine=engine, effort=effort, algorithm=algorithm
            ) -> list[int]:
                if engine == "atlas":
                    return [hit[1] for hit in index.search(qlists[j], 10, effort, algorithm)]
                return index.search(qarrays[j], 10)[1][0].tolist()

            for j in range(min(20, len(query))):
                search(j)
            trials = []
            latencies = []
            actual = []
            for _ in range(3):
                result = []
                start = time.perf_counter()
                for j in range(len(query)):
                    stamp = time.perf_counter_ns()
                    result.append(search(j))
                    latencies.append((time.perf_counter_ns() - stamp) / 1e6)
                trials.append(len(query) / (time.perf_counter() - start))
                actual = result
            recall = float(
                np.mean([len(set(a) & set(b)) / 10 for a, b in zip(actual, expected, strict=True)])
            )
            row = {
                "engine": engine,
                "algorithm": algorithm,
                "effort": effort,
                "recall_at_10": recall,
                "qps_trials": trials,
                "qps_median": float(np.median(trials)),
                "p50_ms": float(np.percentile(latencies, 50)),
                "p99_ms": float(np.percentile(latencies, 99)),
            }
            rows.append(row)
            print(json.dumps({"dataset": dataset, **row}), flush=True)
        del search
        del index
        gc.collect()
    result = {
        "dataset": dataset,
        "available_base": total,
        "base_vectors": n,
        "dimensions": d,
        "query_count": len(query),
        "query_selection": "first test rows; full base up to --limit",
        "metric": "squared L2"
        if dataset.startswith("sift")
        else "squared L2 on unit vectors (cosine ranking)",
        "seed": 42,
        "threads": 1,
        "kernel": atlas_native.kernel(),
        "ground_truth_seconds": truth_s,
        "builds": builds,
        "rows": rows,
    }
    out = ROOT / "docs/results" / f"{dataset}-{n}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=20000)
    p.add_argument("--queries", type=int, default=200)
    p.add_argument(
        "--dataset", choices=["all", "sift-128-euclidean", "glove-100-angular"], default="all"
    )
    args = p.parse_args()
    env = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "faiss": faiss.__version__,
        "numpy": np.__version__,
        "thread_env": {k: os.environ.get(k) for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"]},
        "timing": "single query calls, preconverted input; Python binding/result conversion included; three warm trials; no network; same process sequential builds, not isolated RSS",
    }
    (ROOT / "docs/results/environment.json").write_text(json.dumps(env, indent=2) + "\n")
    for dataset in (
        ["sift-128-euclidean", "glove-100-angular"] if args.dataset == "all" else [args.dataset]
    ):
        file = ROOT / ".cache/data" / f"{dataset}.hdf5"
        if not file.exists():
            raise SystemExit(f"Missing {file}; run scripts/data.py first")
        digest = hashlib.file_digest(file.open("rb"), "sha256").hexdigest()
        print(json.dumps({"dataset": dataset, "sha256": digest}), flush=True)
        run(dataset, args.limit, args.queries)


if __name__ == "__main__":
    main()
