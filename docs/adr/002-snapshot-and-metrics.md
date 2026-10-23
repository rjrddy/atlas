# Portable snapshots and honest memory

Versioned little-endian words store the complete graph and IVF state. FNV-1a detects accidental corruption; it is not a cryptographic signature. Loader verifies checksum, dimensions, parameter bounds, finite coordinates, graph edges/levels/degrees, unique complete IVF assignments, and exact EOF. Treat files as trusted local artifacts: bounded loading can still consume substantial RAM and checksum forgery is trivial.

The demo writes a sibling temporary snapshot and renames it. There is no fsync durability promise and the low-level save method itself is not atomic. A corrupt snapshot fails startup; no silent rebuild.

Atlas memory counts vector capacities plus container objects for BOTH native indexes and one shared vector matrix. FAISS reports serialized index bytes separately. These are different measures and cannot prove a memory winner. Whole-process peak RSS is cumulative and includes Python/data/previous engines; it is labeled accordingly. Allocator metadata and per-thread visited scratch are excluded from capacity accounting.
