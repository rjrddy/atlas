# Atlas salvage

The older Mini vector search engine's `src/ivf.cpp` supplied the deterministic centroid/Lloyd/posting-list baseline and the idea of checking full probes against exact search. Atlas rewrites that baseline into an owned C++20 object, with bounded training sample, SIMD distance calls, heap top-k, metadata filters, immutable serving, persistence and native tests. No pybind module or old measured number was copied as current evidence.

The old harness's same-vectors/same-thread FAISS comparison inspired the new harness; the new benchmark reruns on actual public SIFT1M and GloVe rather than reusing the older digits fixture. Memory scopes and query-boundary costs are stated explicitly.

Finance Q&A's structured-fact retrieval was inspected during the migration audit but not incorporated: its TF-IDF/SEC structured-fact validation does not supply this engine's ANN core or a valid vector benchmark. That source remains available for Docket. HNSW, SIMD, complete snapshots, filtering, gRPC, Python SDK, React explorer, API tests and measurements are new work. Old repositories and remote GitHub repositories remain untouched.
