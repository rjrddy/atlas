# Atlas quality report

Scope: an immutable local vector engine, inspectable API/SDK and seeded React explorer. No hosted service, dynamic update/delete API, production remote gRPC or tenant isolation is claimed.

| Gate | Local evidence | Verdict |
|---|---|---|
| Owned hard core and guarantees explained | C++ HNSW/IVF/SIMD/snapshots; DESIGN and ADRs | PASS |
| One-command fresh clone | fresh-clone/verification.json and actual make demo log; genuine package/public data downloads | PASS |
| Viewer shows live behavior | browser/review.json, screenshots, actual WebM and ffprobe duration | PASS |
| Unit/integration/randomized/concurrency tests | core-tests.log, checks.log, final-gates.log; real HTTP/gRPC SDK and native reference properties | PASS |
| Measured public benchmark | full-benchmark.log; full base SIFT1M and GloVe JSON; fixed test-query sample; subset smoke recorded separately | PASS |
| Demonstrated caught failure | core corruption rejection; caught download 403, browser label ambiguity, and container harness ownership/stderr failures | PASS |
| ADRs | immutable filtering, persistence/memory, chart/evidence decisions | PASS |
| Interview kit | INTERVIEW.md and DRILL.md | PASS |
| ASan / TSan | asan.log / tsan.log plus Linux matrix jobs | PASS locally; exact-head CI link maintained by coordinator |
| Dependency scan | dependency-scan.log includes runtime/build/browser/plot Python tooling and npm | PASS |
| No unmeasured performance claims | README generated from raw JSON; benchmark commentary discloses trial spread and unmatched memory scopes | PASS within stated scopes |

CI is independent Linux evidence: its exact-head result is verified in the coordinator's ATLAS_CI_VERIFICATION.json. The container tests execute the actual nonroot image, query the native index, kill/restart, compare neighbors, and require corrupt-snapshot startup rejection. Early failures were proof-harness bugs: attempting host write access to a container-owned file, then ignoring stderr where the expected rejection was printed. Both original failure logs are retained. They are not described as application bugs.

## Limits and unmeasured items

- The complete public base corpora were used; only the fixed leading test-query sample was measured. This does not establish general workload performance or a speed advantage. Development work ran in the background; CPU pinning, stable power state and isolated runs are unfinished.
- SIMD correctness is checked against scalar kernels. A scalar-versus-SIMD throughput speedup is **not measured**.
- Capacity accounting and serialized sizes differ. Isolated per-engine heap/RSS, allocator fragmentation and concurrent-search memory curves are **not measured**. Cumulative RSS is retained only as process context.
- Filtered HNSW is an exact fallback; filtered ANN acceleration is unfinished. Dynamic updates, multi-tenant auth, gRPC TLS exposure and cooperative cancellation/preemption are future scope.
- Snapshot corruption detection is accidental-integrity checking. Malicious tamper authentication and power-loss durability are **not measured or guaranteed**.
- HTTP/gRPC service throughput and remote network latency are **not measured**. No account or deployment created. Docker/Render configuration is prepared only.

Raw source files are under docs/results/ relative to this repository. No previous project result was reused as an Atlas measurement. Previous repositories remain preserved; no integration or deletion was performed.
