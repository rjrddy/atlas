# Atlas: the hard part

Approximate neighbors trade graph exploration, centroid probes, memory and construction work against missed true neighbors. A fast query is meaningless without a clearly specified metric, eligible corpus and exact reference.

## Owned core

`src/index.cpp` implements the graph and IVF; FAISS is never called by production search. Read the HNSW paper's hierarchical descent, candidate beam and diversity-selection algorithms: https://arxiv.org/abs/1603.09320 . This is an original compact implementation, not a reproduction of every optimization or guarantee in that paper.

Construction inserts vectors in stable input order. A seeded geometric level distribution gives sparse upper layers. Greedy descent traverses upper levels; a distance-ordered beam explores each insertion layer; a diversity heuristic rejects neighbors closer to a selected neighbor than to the query. Reciprocal edges are pruned at bounded degree. Search repeats greedy upper descent and an ef-sized bottom beam. Connectivity and perfect recall are not guaranteed. Stable `(squared distance, ID)` ordering breaks distance ties.

IVF adapts the older mini-vector-search baseline: deterministic evenly spaced initial centers, bounded Lloyd iterations, empty centers retained, then all records assigned. Training uses a deterministic bounded sample, unlike FAISS's own training strategy. Probing all lists is an exact eligible scan; fewer probes may underfill. HNSW filtered queries deliberately take the exact eligible path. No tenant-isolation or authorization claim follows from a demo tag.

NEON on aarch64 and SSE2 on x86-64 process unaligned four-float blocks and scalar tails. A scalar implementation is the reference. Fused multiply/add contraction is disabled; lane reduction still changes rounding, so kernel parity uses tolerance. Persisting and reloading on one architecture preserves results; cross-architecture bit identity is not promised.

## Guarantees and boundaries

- Immutable indexes permit concurrent reads; no concurrent build/mutation API. Scratch marks are thread-local with wraparound clearing. Serving memory scales with worker count because each worker may own a visited array.
- Input vectors/queries must have valid bounded dimensions, finite bounded coordinates, and nonnegative tags. API has tighter fixed demo limits. Native callers are trusted; native resource limits are not a hardened hostile-input sandbox.
- Snapshot load verifies checksum and structural invariants before returning. A corrupt demo snapshot aborts startup. FNV is an accidental-corruption checksum, not tamper evidence. No fsync or power-loss guarantee.
- Python service terminates HTTP and gRPC and releases the GIL during native search. Bearer comparison uses constant-time comparison. HTTP bodies and workers are bounded; gRPC has message/concurrency limits. The demo gRPC port is loopback-only and plaintext. Exposing it requires TLS implementation first.
- The public `local-demo` token is accepted only with loopback HTTP binding. External HTTP requires an explicit longer token and a TLS reverse proxy. Render config is preparation only. No credentials are committed.
- HTTP request timeout and bounded concurrent worker admission are coarse demo protection. There is no per-user fair rate limiter. gRPC deadlines do not preempt an already-running native query; work is bounded by demo input size.
- Structured HTTP/ready logs omit vectors and credentials. State returns process-local query/error counters; no distributed metrics or traces are claimed.

## Benchmark protocol

Public ANN-Benchmarks SIFT1M uses squared L2. GloVe is normalized and searched with squared L2, preserving cosine ranking (for finite nonzero vectors). The harness recomputes exact top-ten truth with FAISS FlatL2 for the selected base and queries; it does not reuse full-corpus truth for a subset. Duplicate/equal-distance ties can cause set recall differences. Public test rows are deterministic, not a random or production workload.

Same vector order, degree, efConstruction and nominal search settings for the two HNSW implementations. Same centroid count and nominal iterations for IVF, but sampling/initialization differ. Atlas build time includes BOTH indexes; FAISS builds are separate. Scalar single-query Python calls include binding/result conversion, exclude network, preconvert queries, warm up, then retain every repeated timing trial. This is not a pure distance-kernel microbenchmark or service QPS. Core methods are single-threaded; FAISS OMP threads are set to one. The laptop remains an uncontrolled development machine; background compilation/browser work and CPU power state can perturb measurements. Large trial spread is evidence of that limitation, not hidden.

Atlas memory reports container objects and allocated vector capacities for both indexes with one shared matrix. FAISS reports serialized bytes per separate index. Cumulative process high-water RSS is also retained, not attributed to a specific index. These scopes differ; no memory-efficiency winner is claimed. Per-thread scratch and allocator overhead are excluded from native capacity totals.

See raw JSON, environment, dataset hashes and every trial in `docs/results/`. Live UI sweeps are smaller synthetic single-run measurements and are not substituted for the recorded public-data evidence.

## Sources

- Original HNSW algorithm: https://arxiv.org/abs/1603.09320
- FAISS million-vector benchmark protocol and metrics: https://github.com/facebookresearch/faiss/wiki/Indexing-1M-vectors
- Public distributions/provenance: https://github.com/erikbern/ann-benchmarks (SIFT1M from INRIA; GloVe from Stanford). SIFT descriptors/embedding matrices only, no source images, private records or text corpus are ingested.
- gRPC Python service pattern: https://grpc.io/docs/languages/python/basics/
- Map visual conventions, original implementation: https://www.ordnancesurvey.co.uk/mapzone/map-skills/map-symbols
