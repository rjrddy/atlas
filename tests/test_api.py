"""Real sockets, SDK, auth and invalid input against an owned child process."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import atlas_native
import grpc
import numpy as np
import pytest
from client import Client

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    directory = tmp_path_factory.mktemp("atlas")
    env = dict(
        os.environ,
        PORT="18094",
        ATLAS_GRPC_PORT="50072",
        ATLAS_SNAPSHOT=str(directory / "index.atlas"),
        ATLAS_TOKEN="integration-test-token",
    )
    log = (directory / "server.log").open("w")
    child = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), "scripts/server.py"],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=log,
    )
    try:
        for _ in range(100):
            if child.poll() is not None:
                raise RuntimeError((directory / "server.log").read_text())
            try:
                with urllib.request.urlopen("http://127.0.0.1:18094/health", timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("server not ready")
        yield child
    finally:
        child.terminate()
        child.wait(timeout=10)
        log.close()


def request(path, body=None, token="integration-test-token"):
    req = urllib.request.Request(
        "http://127.0.0.1:18094" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def test_auth_and_validation(server):
    for path, body, token, expected in [
        ("/api/state", None, "wrong", 401),
        ("/api/query", {"vector": [float("nan")] * 24}, "integration-test-token", 400),
        ("/api/query", {"anchor": True}, "integration-test-token", 400),
        ("/api/query", {"algorithm": "made-up"}, "integration-test-token", 400),
        ("/api/query", {"effort": 0}, "integration-test-token", 400),
        ("/api/query", {"k": 1000000}, "integration-test-token", 400),
    ]:
        with pytest.raises(urllib.error.HTTPError) as error:
            request(path, body, token)
        assert error.value.code == expected


def test_http_filter_and_concurrent_queries(server):
    def query(i):
        result = request("/api/query", {"anchor": i, "tag": 3})
        assert result["path"] == "exact-filtered"
        assert result["recall"] == 1
        assert len(result["neighbors"]) == 10
        assert all(n["tag"] == 3 for n in result["neighbors"])
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len(list(pool.map(query, range(32)))) == 32
    sweep = request("/api/sweep", {"anchor": 17})
    assert len(sweep["rows"]) == 8
    assert all(0 <= row["recall"] <= 1 and row["qps"] > 0 for row in sweep["rows"])


def test_real_grpc_sdk(server):
    vector = request("/api/query", {"anchor": 17})["query"]
    client = Client("127.0.0.1:50072", "integration-test-token", secure=False)
    try:
        hits = client.query(vector)
        assert hits[0].id == 17
        assert hits[0].squared_l2 == 0
        filtered = client.query(vector, tag=5)
        assert all(n.id % 8 == 5 for n in filtered)
        with pytest.raises(grpc.RpcError) as error:
            client.query([1.0])
        assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    finally:
        client.close()
    bad = Client("127.0.0.1:50072", "wrong", secure=False)
    try:
        with pytest.raises(grpc.RpcError) as error:
            bad.query(vector)
        assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED
    finally:
        bad.close()


def test_native_properties_and_persistence(tmp_path):
    rng = np.random.default_rng(123)
    for d in [1, 7, 24, 33]:
        base = rng.normal(size=(100, d)).astype("float32")
        index = atlas_native.Index(base, [i % 3 for i in range(100)], clusters=8)
        path = tmp_path / "index.atlas"
        index.save(str(path))
        loaded = atlas_native.Index.load(str(path))
        for q in rng.normal(size=(20, d)).tolist():
            expected = np.argsort(np.sum((base - np.array(q)) ** 2, axis=1))[:10].tolist()
            for algorithm, effort in [("exact", 1), ("ivf", 8), ("hnsw", 100)]:
                hits = index.search(q, 10, effort, algorithm)
                assert [h[1] for h in hits] == expected
                assert hits == loaded.search(q, 10, effort, algorithm)
        payload = path.read_bytes()
        for offset in [0, 12, 100, len(payload) - 1]:
            damaged = bytearray(payload)
            damaged[offset] ^= 1
            path.write_bytes(damaged)
            with pytest.raises(RuntimeError, match="checksum"):
                atlas_native.Index.load(str(path))
        for cut in [0, 1, 40, len(payload) - 4]:
            path.write_bytes(payload[:cut])
            with pytest.raises(RuntimeError):
                atlas_native.Index.load(str(path))
