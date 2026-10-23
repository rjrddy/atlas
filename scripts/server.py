"""Bounded loopback demo: native immutable index, HTTP explorer and gRPC SDK."""

import hmac
import json
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import atlas_native
import atlas_pb2
import atlas_pb2_grpc
import grpc
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def seed() -> tuple[np.ndarray, list[int]]:
    rng = np.random.default_rng(42)
    centers = rng.normal(0, 4, (8, 24)).astype("float32")
    tags = [i % 8 for i in range(2048)]
    base = centers[tags] + rng.normal(0, 1.2, (2048, 24)).astype("float32")
    return base, tags


def integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"expected integer in [{low}, {high}]")
    return value


class Engine:
    def __init__(self, snapshot: Path) -> None:
        self.base, self.tags = seed()
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            self.index = atlas_native.Index.load(str(snapshot))
        else:
            self.index = atlas_native.Index(self.base, self.tags)
            temporary = snapshot.with_suffix(".tmp")
            self.index.save(str(temporary))
            temporary.replace(snapshot)
        if self.index.size != len(self.base) or self.index.dimensions != 24:
            raise RuntimeError("snapshot does not match demo seed shape")
        self.lock = threading.Lock()
        self.requests = 0
        self.errors = 0

    def query(self, body: dict) -> dict:
        if not isinstance(body, dict):
            raise ValueError("JSON object required")
        k = integer(body.get("k", 10), 1, 100)
        effort = integer(body.get("effort", 64), 1, 4096)
        tag = integer(body.get("tag", -1), -1, 7)
        algorithm = body.get("algorithm", "hnsw")
        if algorithm not in ("hnsw", "ivf", "exact"):
            raise ValueError("unknown algorithm")
        if "vector" in body:
            vector = body["vector"]
            if (
                not isinstance(vector, list)
                or len(vector) != 24
                or any(type(v) not in (float, int) for v in vector)
            ):
                raise ValueError("vector requires 24 finite numeric coordinates")
        else:
            anchor = integer(body.get("anchor", 17), 0, len(self.base) - 1)
            vector = self.base[anchor].tolist()
        started = time.perf_counter_ns()
        hits = self.index.search(vector, k, effort, algorithm, tag)
        elapsed = (time.perf_counter_ns() - started) / 1e6
        expected = self.index.search(vector, k, 1, "exact", tag)
        truth = {hit[1] for hit in expected}
        with self.lock:
            self.requests += 1
        return {
            "neighbors": [{"id": i, "squared_l2": d, "tag": self.tags[i]} for d, i in hits],
            "elapsed_ms": elapsed,
            "recall": len(truth & {h[1] for h in hits}) / len(truth) if truth else 1.0,
            "path": "exact-filtered" if algorithm == "hnsw" and tag >= 0 else algorithm,
            "query": vector,
        }

    def sweep(self, body: dict) -> dict:
        anchor = integer(body.get("anchor", 17), 0, len(self.base) - 1)
        tag = integer(body.get("tag", -1), -1, 7)
        rows = []
        for algorithm, efforts in [("hnsw", [10, 24, 64, 160]), ("ivf", [1, 4, 16, 32])]:
            for effort in efforts:
                results = []
                for j in range(16):
                    results.append(
                        self.query(
                            {
                                "anchor": (anchor + 31 * j) % len(self.base),
                                "tag": tag,
                                "algorithm": algorithm,
                                "effort": effort,
                            }
                        )
                    )
                latencies = [r["elapsed_ms"] for r in results]
                rows.append(
                    {
                        "algorithm": algorithm,
                        "effort": effort,
                        "recall": float(np.mean([r["recall"] for r in results])),
                        "p50_ms": float(np.median(latencies)),
                        "qps": 1000 / float(np.mean(latencies)),
                        "path": results[0]["path"],
                    }
                )
        return {
            "rows": rows,
            "queries_per_setting": 16,
            "scope": "synthetic native search only; exact validation excluded; single warm sweep",
        }


class Service(atlas_pb2_grpc.SearchServicer):
    def __init__(self, engine: Engine, token: str) -> None:
        self.engine, self.token = engine, token

    def Query(self, request, context):
        if not hmac.compare_digest(
            dict(context.invocation_metadata()).get("authorization", ""),
            f"Bearer {self.token}",
        ):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "bearer required")
        try:
            result = self.engine.query(
                {
                    "vector": list(request.vector),
                    "k": request.k,
                    "effort": request.effort,
                    "algorithm": request.algorithm,
                    "tag": request.tag,
                }
            )
        except (ValueError, TypeError) as error:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        return atlas_pb2.QueryResponse(
            neighbors=[
                atlas_pb2.Neighbor(id=n["id"], squared_l2=n["squared_l2"])
                for n in result["neighbors"]
            ],
            elapsed_ms=result["elapsed_ms"],
            path=result["path"],
        )


def handler(engine: Engine, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            print(
                json.dumps({"event": "http", "status": args[1] if len(args) > 1 else "unknown"}),
                flush=True,
            )

        def respond(self, status: int, data: bytes, kind: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def authorized(self) -> bool:
            return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self.respond(200, b'{"status":"ready"}')
                return
            if path.startswith("/api/"):
                if not self.authorized():
                    self.respond(401, b'{"error":"bearer required"}')
                    return
                if path == "/api/state":
                    data = {
                        "points": [
                            {"id": i, "x": float(v[0]), "y": float(v[1]), "tag": engine.tags[i]}
                            for i, v in enumerate(engine.base)
                        ],
                        "vectors": engine.index.size,
                        "dimensions": engine.index.dimensions,
                        "bytes": engine.index.allocated_bytes,
                        "kernel": atlas_native.kernel(),
                        "requests": engine.requests,
                        "errors": engine.errors,
                    }
                elif path == "/api/evidence":
                    data = {
                        "runs": [
                            json.loads(p.read_text())
                            for p in sorted((ROOT / "docs/results").glob("*-angular-*.json"))
                        ]
                        + [
                            json.loads(p.read_text())
                            for p in sorted((ROOT / "docs/results").glob("*-euclidean-*.json"))
                        ]
                    }
                else:
                    self.respond(404, b'{"error":"not found"}')
                    return
                self.respond(200, json.dumps(data, allow_nan=False).encode())
                return
            web = ROOT / "apps/web/dist"
            relative = "index.html" if path == "/" else path.lstrip("/")
            target = (web / relative).resolve()
            if not target.is_relative_to(web.resolve()) or not target.is_file():
                self.respond(404, b'{"error":"not found"}')
                return
            kind = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript",
                ".css": "text/css",
            }.get(target.suffix, "application/octet-stream")
            self.respond(200, target.read_bytes(), kind)

        def do_POST(self) -> None:
            self.connection.settimeout(10)
            if not self.authorized():
                self.respond(401, b'{"error":"bearer required"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("request must be 1..65536 bytes")
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("application/json required")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                if self.path == "/api/query":
                    result = engine.query(body)
                elif self.path == "/api/sweep":
                    result = engine.sweep(body)
                else:
                    self.respond(404, b'{"error":"not found"}')
                    return
                self.respond(200, json.dumps(result, allow_nan=False).encode())
            except (ValueError, TypeError, OverflowError) as error:
                with engine.lock:
                    engine.errors += 1
                self.respond(400, json.dumps({"error": str(error)}).encode())

    return Handler


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler_class):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, handler_class)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main() -> None:
    host = os.environ.get("ATLAS_HOST", "127.0.0.1")
    token = os.environ.get("ATLAS_TOKEN", "local-demo")
    if host not in ("127.0.0.1", "localhost", "::1") and (token == "local-demo" or len(token) < 24):
        raise SystemExit(
            "external binding requires ATLAS_TOKEN of at least 24 characters and TLS at the proxy"
        )
    engine = Engine(Path(os.environ.get("ATLAS_SNAPSHOT", ROOT / ".cache/demo.atlas")))
    grpc_server = grpc.server(
        ThreadPoolExecutor(max_workers=4),
        maximum_concurrent_rpcs=8,
        options=(("grpc.max_receive_message_length", 65536),),
    )
    atlas_pb2_grpc.add_SearchServicer_to_server(Service(engine, token), grpc_server)
    grpc_host = os.environ.get("ATLAS_GRPC_HOST", "127.0.0.1")
    if grpc_host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("demo gRPC is loopback-only; add TLS before exposing it")
    port = int(os.environ.get("ATLAS_GRPC_PORT", "50071"))
    if grpc_server.add_insecure_port(f"{grpc_host}:{port}") == 0:
        raise SystemExit("gRPC bind failed")
    http = BoundedServer((host, int(os.environ.get("PORT", "8094"))), handler(engine, token))
    grpc_server.start()
    stopped = threading.Event()

    def stop(_signum, _frame):
        if not stopped.is_set():
            stopped.set()
            threading.Thread(target=http.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(
        json.dumps(
            {
                "event": "ready",
                "http": f"http://{host}:{http.server_port}",
                "grpc_port": port,
                "vectors": engine.index.size,
            }
        ),
        flush=True,
    )
    try:
        http.serve_forever()
    finally:
        http.server_close()
        grpc_server.stop(2).wait()


if __name__ == "__main__":
    main()
