# Run and record Atlas

Prerequisites: Python with venv and headers, C++20 compiler, CMake, Node/npm. On Debian/Ubuntu install `build-essential cmake python3-dev python3-venv nodejs npm` first. Network is needed once for pinned Python/npm packages. Public dataset downloads are separate and are not needed for the synthetic demo.

```
make demo
```

Open http://127.0.0.1:8094 . The default `local-demo` bearer works only on loopback. Choose a seed ID, locate neighbors, switch HNSW/IVF/exact, vary effort, filter a group, and run a live sweep. Custom input accepts a full finite coordinate array; selecting a seed query prepopulates it after a successful query. The map displays only two coordinates and is not an embedding or a faithful distance map.

The Public-data expeditions tab reads recorded raw JSON shipped with the repo. It is not a live public-corpus service. Live queries use seeded synthetic data. The field counters reset on restart; the immutable seed snapshot reloads from `.cache/demo.atlas`. Stop with Ctrl-C.

## gRPC SDK

The server also listens on loopback port 50071. With the server running:

```
PYTHONPATH=build:sdk .venv/bin/python -c 'from client import Client; c=Client("127.0.0.1:50071","local-demo",secure=False); print(c.query([0.25]*24)); c.close()'
```

The SDK defaults to TLS. The explicit insecure override above is only for the local demo. HTTP/gRPC bearer failure returns an error. There is no hosted endpoint.

## Exact ninety-second recording steps

Start screen capture before the sequence; record actual behavior rather than padding:

- 0–15s: show map, choose a seed, query and inspect returned native timing/path/recall.
- 15–30s: set IVF effort to a small probe count, then all lists; compare results with exact.
- 30–45s: choose a group; show `exact-filtered` HNSW and eligible returned tags.
- 45–60s: enter an invalid short vector, show rejection, restore a complete vector and query.
- 60–75s: run a sweep and inspect recall/QPS chart and raw settings table.
- 75–90s: open public SIFT1M/GloVe evidence, distinguish public corpus/queries/timing/memory scopes; narrow the screen and repeat a query.

Optional automated proof: install `requirements-browser.txt` in the local venv, then `.venv/bin/python -m playwright install chromium ffmpeg`. Run `PYTHONPATH=build:sdk .venv/bin/python scripts/review.py --record`. The recorder owns/stops its server and repeatedly executes real changed queries to complete the recording. Verify video duration with `ffprobe docs/results/browser/atlas-demo.webm`; do not pad short footage. `PLAYWRIGHT_BROWSERS_PATH` may point to an already installed matching browser cache.

## Benchmarks

Download public files with `.venv/bin/python scripts/data.py`, then run `make bench` for a subset smoke comparison. Full corpus: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=build .venv/bin/python scripts/bench.py --limit 2000000 --queries 200`. This is long-running; files live in ignored `.cache/data`. JSON names state the actual corpus size. `make test` contains the snapshot-corruption caught-failure gate; `make asan tsan` runs native sanitizer tests.

## Deployment preparation

`Dockerfile` and `render.yaml` are prepared only. No account, service or deployment created. Render free-service docs: https://render.com/docs/free . Free storage is ephemeral; the synthetic immutable demo may rebuild its seed snapshot, and no hosted durable-index guarantee follows. Set a private `ATLAS_TOKEN`; HTTPS must terminate at the proxy. Open connection settings in the UI and enter that token. gRPC remains loopback-only. A production remote gRPC service needs TLS, auth policy, rollout and resource-budget work first.
