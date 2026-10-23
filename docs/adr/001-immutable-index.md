# Immutable ownership and filtering

The C++ object owns vectors, tags, graph levels, centroids and posting lists. Construction is single-threaded; serving only const methods permits concurrent readers without locks. Search scratch is thread-local. A new index replaces the old deployment as a whole; no in-place insertion/deletion API is promised.

Filtered HNSW deliberately scans eligible records exactly. Filtering graph traversal can disconnect otherwise reachable candidates; accepting only eligible HNSW hits can silently underfill. The fallback guarantees eligible top-k (up to eligible cardinality), but its latency is linear in the eligible corpus. IVF still filters candidates within probed lists and remains approximate unless all lists are probed. API returns the executed path.

Python implements the gRPC/HTTP boundary and calls owned C++ through pybind11 with the GIL released. This is a Python gRPC service over a C++ index, not a native C++ gRPC server.
