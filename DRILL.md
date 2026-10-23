# Atlas follow-up drill

1. Why no lock on every search? The published object is immutable; only thread-local scratch changes.
2. Why no lock-free label? No shared mutable search structure is being made lock-free; immutable reads are a simpler claim.
3. What happens when an epoch wraps? Clear marks and restart the epoch, preventing an old marker from being mistaken for current visitation.
4. Why does candidate ordering include ID? Deterministic tie-breaking within one floating-point kernel.
5. Can equal-distance ties lower recall? Yes, set overlap can penalize an equally valid alternate tied neighbor; inspect distance ties before attributing all misses to ANN.
6. Is the candidate heap a full Dijkstra search? No; it explores a graph with an ef termination condition and need not visit every vector.
7. Does increasing ef always improve measured QPS? Usually costs more, but timing noise/cache effects can violate monotonic observed speed. Raw trials remain visible.
8. Can all-probe IVF miss a record? The constructed/loaded lists form a complete unique assignment; all probes scan every eligible record. Tests check exact parity.
9. Why keep empty centers? Deterministic simple Lloyd updates; empty lists waste probes and can harm low-probe recall.
10. Why bound training? Construction cost grows with records, clusters and dimensions. A deterministic sample controls training work but may underrepresent the distribution.
11. What is the filtering guarantee? Exact eligible top-k for exact and filtered HNSW; approximate within probed lists for IVF.
12. Is a tag a tenant boundary? No. A query parameter is not an authorization policy.
13. Why separate public and synthetic UI views? They measure different corpora and timing scopes. Showing recorded public QPS as live service capacity would mislead.
14. Why not draw true 24D geometry? A screen cannot preserve all high-dimensional distances in a coordinate projection. The map's warning is part of correctness.
15. Why GIL release? Independent native read searches can execute concurrently; the object remains alive for the method call and vectors are copied before release on construction.
16. What is excluded from bytes/vector? Allocator metadata, Python, thread scratch, fragmentation, code and OS pages. FAISS serialization is another scope entirely.
17. Does the RSS row isolate an engine? No, it is a cumulative process high-water mark after sequential builds; it cannot support an engine-memory comparison.
18. What happens to an acknowledged snapshot on power loss? Unmeasured. No fsync durability guarantee exists; the demo uses rename only.
19. What real negative controls exist? A physical snapshot bit flip is rejected, malformed dimensions/auth fail through real sockets, and small-effort ANN misses are retained in public recall curves.
20. What would change before internet exposure? TLS for gRPC, explicit authorization and quotas, cooperative cancellation, hardened snapshot ingestion, deployment/load/failure tests and operational monitoring. Current deployment files are preparation only.
