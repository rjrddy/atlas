# Atlas interview kit

## Two-minute pitch

Atlas is a vector search engine whose difficult part is balancing recall, search work and memory with an index I can explain. I wrote the C++ HNSW graph, IVF-flat baseline, SIMD kernels, filtered search and complete snapshot format. A Python gRPC service calls that core through pybind11; a React chart instrument shows live synthetic neighbors and recorded public SIFT/GloVe comparisons with FAISS.

The story is the measurement contract, not a claim that my engine beats FAISS. Each run names the base corpus and query sample, recomputes exact truth, records every timing trial and distinguishes native capacities from serialized bytes. Full-probe IVF matches exact search; approximate settings may miss neighbors. A filtered HNSW query uses an explicitly labeled exact fallback to preserve eligible top-k. The caught corruption test proves the snapshot loader rejects damaged files; it does not prove cryptographic authenticity. See README and raw JSON for the measured results rather than memorizing a speed claim out of context.

## Ten-minute walkthrough

Start at `src/index.hpp`: one object owns vectors, tags, graph layers, centers and lists. Explain why immutable ownership makes concurrent serving simple and why dynamic insert/delete are excluded. Walk through `Index::Index`, the level distribution, upper greedy search, bounded candidate beam, diversity selection and reciprocal pruning. Compare `search`'s exact heap, HNSW beam and IVF probe paths. Explain the intentionally linear filtered fallback.

Then read `l2`: architecture-guarded NEON/SSE2, unaligned loads, scalar tail, no fused contraction and tolerance-based parity. Show `save/load`, portable words, checksum, bounds and adjacency validation; explain why an attacker can forge the checksum and why files must be trusted local artifacts.

Follow `scripts/server.py` through synthetic seed, snapshot startup, HTTP validation, gRPC bearer check and GIL release. Use `sdk/client.py` against a real local socket. Open the explorer: two-dimensional projection is labeled, ranking uses the entire vector, each result states its path, and public evidence is separate from live synthetic measurements.

Finish in `scripts/bench.py` and the raw result JSON. Compare a similar-recall setting rather than announcing a winner at equal ef. Explain differences in training initialization, combined versus separate build scopes, binding overhead and the laptop's noisy trials. Show `tests/core.cpp`, socket/property tests, ASan/TSan evidence and the corrupted-snapshot failure. End with the remaining operational scope in `docs/QUALITY.md`.

## Five tradeoffs

- Immutable deployment snapshots simplify readers and reproducibility; updates require rebuilding and replacement rather than mutation.
- Filtered HNSW falls back to exact eligible search for completeness, sacrificing approximate-search latency.
- A vector-of-vectors graph is inspectable; allocator overhead and locality are worse than a compact arena layout.
- The Python gRPC boundary avoids a complex native RPC dependency build; serialization and Python scheduling remain part of service overhead.
- Portable checksummed snapshots are straightforward; they are not authenticated, mmap-based or crash-durable index publication.

## Five failures and handling

- Corrupt/truncated snapshot: checksum/shape/edge/EOF validation rejects load and demo startup fails closed. Actual corruption rejection is saved in `docs/results/core-tests.log`.
- Sparse eligible filter: HNSW exact fallback returns all eligible top-k without graph-disconnection loss. IVF may underfill because partial lists are approximate.
- Nonfinite or malformed query: API/native checks reject it; socket and browser tests exercise the boundary.
- Concurrent readers: no mutation, per-thread epoch marks; native multithread tests and TSan exercise scratch isolation. This is finite testing, not a formal proof.
- Wrong credentials or lost connection: auth error displayed; reconnect clears errors and issues a new request. No stale result is displayed as a newly completed query.

## Fifteen likely questions

1. Why hierarchy? Sparse upper layers provide a cheap route toward a useful bottom-layer start; the bottom beam handles local exploration.
2. What does ef bound? Retained best candidates, not total visited nodes, latency or a recall guarantee.
3. Why diversity selection? Keeping only nearest neighbors can cluster links locally; the heuristic favors neighbors that add directions.
4. Does graph pruning preserve connectivity? No guarantee. Compare recall with exact truth; larger ef cannot recover a truly disconnected component.
5. Why L2 for cosine? Unit-normalized vectors give squared L2 equal to twice one minus cosine; zero vectors require care. Public data is checked by the actual harness behavior.
6. Is exact scan really exact? It evaluates every eligible vector with the configured floating-point kernel and stable distance/ID ordering. Mathematical real-number and different-kernel ties may differ.
7. What does a missing filtered result mean? Exact fallback can return fewer than k only if fewer eligible vectors exist; partial-probe IVF can also miss eligible lists.
8. How does thread-local scratch scale? One visited-mark array per active thread, reused by epoch; it is outside persistent-index capacity totals.
9. Can one thread search several indexes? Each traversal advances the thread-local epoch; marks from earlier calls cannot leak into a later index. Reentrant nested callbacks are not part of the API.
10. Why not AVX-only? Portable SSE2 and NEON cover the tested architectures without assuming unsupported CPU instructions. Wider dispatch is future work.
11. Are save operations atomic? The core save truncates its target; the demo writes a sibling temp and renames. No fsync/power-loss guarantee.
12. Is FNV secure? No. It detects accidental corruption in these tests; use signatures/MACs and stronger format hardening for untrusted distribution.
13. Is the benchmark apples-to-apples? Same corpus/queries/metric/thread budget and comparable settings; training, implementation, binding costs and memory scopes differ and are disclosed.
14. Can a canceled RPC stop C++ search? Not currently; deadlines stop waiting but do not preempt bounded native computation. Production cancellation needs an explicit cooperative budget.
15. What do sanitizer passes establish? No detected violations on the exercised native paths and concurrent histories. They do not prove safety for every input or hardware/compiler.

## Three more months

Compact graph arenas and measured allocator/RSS accounting; stronger authenticated snapshot publication with streaming bounds validation; larger randomized query samples on multiple machines; isolated timing trials; filtered ANN policies with exact fallback thresholds; native cooperative cancellation; TLS/multi-tenant authorization and per-client resource quotas; update/rebuild lifecycle and deployment testing. Prioritize improvements only after measuring whether they move the recall/latency/memory tradeoff.
