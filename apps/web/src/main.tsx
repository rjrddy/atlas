import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Point = { id: number; x: number; y: number; tag: number };
type State = {
  points: Point[];
  vectors: number;
  dimensions: number;
  bytes: number;
  kernel: string;
  requests: number;
};
type Result = {
  neighbors: { id: number; squared_l2: number; tag: number }[];
  elapsed_ms: number;
  recall: number;
  path: string;
  query: number[];
};
type Sweep = {
  rows: {
    algorithm: string;
    effort: number;
    recall: number;
    p50_ms: number;
    qps: number;
    path: string;
  }[];
  scope: string;
  queries_per_setting: number;
};
type EvidenceRow = {
  engine: string;
  algorithm: string;
  effort: number;
  recall_at_10: number;
  qps_median: number;
};
type Evidence = {
  dataset: string;
  base_vectors: number;
  available_base: number;
  query_count: number;
  metric: string;
  rows: EvidenceRow[];
  builds: {
    engine: string;
    seconds: number;
    bytes_per_vector: number;
    memory_kind: string;
  }[];
};
const colors = [
  "#5ec7bd",
  "#f4b578",
  "#9da0e8",
  "#c7d78a",
  "#e49db0",
  "#8ac2e8",
  "#e0cf9b",
  "#b0c5ba",
];
const fmt = (n: number, d = 2) =>
  n.toLocaleString(undefined, { maximumFractionDigits: d });
function App() {
  const [token, setToken] = useState("local-demo");
  const [state, setState] = useState<State | null>(null);
  const [anchor, setAnchor] = useState(17);
  const [tag, setTag] = useState(-1);
  const [algorithm, setAlgorithm] = useState("hnsw");
  const [effort, setEffort] = useState(64);
  const [result, setResult] = useState<Result | null>(null);
  const [sweep, setSweep] = useState<Sweep | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [view, setView] = useState("field");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [vector, setVector] = useState("");
  const [manual, setManual] = useState(false);
  async function api<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`/api/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json = await response.json();
    if (!response.ok) throw new Error(json.error || `HTTP ${response.status}`);
    return json;
  }
  async function connect() {
    setBusy(true);
    setError("");
    try {
      setState(await api<State>("state"));
      setEvidence((await api<{ runs: Evidence[] }>("evidence")).runs);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void connect();
  }, []);
  async function query() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const input = manual ? { vector: JSON.parse(vector) } : { anchor };
      const data = await api<Result>("query", {
        ...input,
        tag,
        algorithm,
        effort,
        k: 10,
      });
      setResult(data);
      if (!manual) setVector(JSON.stringify(data.query));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function runSweep() {
    setBusy(true);
    setError("");
    setSweep(null);
    try {
      setSweep(await api<Sweep>("sweep", { anchor, tag }));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const selected = new Set(result?.neighbors.map((n) => n.id));
  const point = state?.points[anchor];
  const px = (x: number) => 50 + ((x + 14) / 28) * 800;
  const py = (y: number) => 540 - ((y + 14) / 28) * 480;
  const queryPoint = result
    ? { x: result.query[0], y: result.query[1] }
    : point;
  return (
    <main>
      <header>
        <a className="wordmark" href="/" aria-label="Atlas home">
          <span className="compass">✳</span> ATLAS
          <span className="edition">SEARCH FIELD STATION</span>
        </a>
        <div className="system">
          <span className={state ? "signal" : "signal off"} />
          {state ? "INDEX ON STATION" : "AWAITING CONNECTION"}
          <small>LOCAL INSTRUMENT / PUBLIC EVIDENCE</small>
        </div>
      </header>
      <section className="intro">
        <div>
          <div className="eyebrow">AN EXPLORATION OF NEAREST NEIGHBORS</div>
          <h1>
            Find your bearings.
            <br />
            <em>Then measure the distance.</em>
          </h1>
        </div>
        <p>
          A vector search engine, written in C++.
          <br />
          Trace a query through the field. Trade search
          <br className="desktop" /> effort for recall. Keep the evidence in
          sight.
        </p>
      </section>
      <nav aria-label="Explorer views">
        <button
          aria-current={view === "field" ? "page" : undefined}
          onClick={() => setView("field")}
        >
          <b>01</b> Search field
        </button>
        <button
          aria-current={view === "evidence" ? "page" : undefined}
          onClick={() => setView("evidence")}
        >
          <b>02</b> Public-data expeditions
        </button>
        <span>HNSW · IVF-FLAT · SQUARED L2</span>
      </nav>
      {error && (
        <div className="error" role="alert">
          CONNECTION / INPUT REJECTED — {error}
        </div>
      )}
      {view === "field" ? (
        <>
          <section className="instrument">
            <aside className="controls">
              <div className="section-label">
                QUERY MANIFEST <span>A—01</span>
              </div>
              <h2>Set a course</h2>
              <p>
                Seeded synthetic vectors.
                <br />
                Select a point or enter a query.
              </p>
              <label>
                Query source
                <select
                  aria-label="Query source"
                  value={manual ? "manual" : "anchor"}
                  disabled={busy}
                  onChange={(e) => setManual(e.target.value === "manual")}
                >
                  <option value="anchor">Seed vector ID</option>
                  <option value="manual">Custom vector</option>
                </select>
              </label>
              {manual ? (
                <label>
                  24 float coordinates
                  <textarea
                    value={vector}
                    disabled={busy}
                    onChange={(e) => setVector(e.target.value)}
                    placeholder="[0.1, 0.2, …]"
                  />
                </label>
              ) : (
                <label>
                  Vector ID
                  <input
                    type="number"
                    min="0"
                    max="2047"
                    disabled={busy}
                    value={anchor}
                    onChange={(e) => {
                      setAnchor(Number(e.target.value));
                      setResult(null);
                    }}
                  />
                </label>
              )}
              <div className="control-pair">
                <label>
                  Index
                  <select
                    aria-label="Index"
                    value={algorithm}
                    disabled={busy}
                    onChange={(e) => {
                      setAlgorithm(e.target.value);
                      setResult(null);
                    }}
                  >
                    <option value="hnsw">HNSW</option>
                    <option value="ivf">IVF-flat</option>
                    <option value="exact">Exact</option>
                  </select>
                </label>
                <label>
                  Effort
                  <input
                    type="number"
                    min="1"
                    max="4096"
                    disabled={busy}
                    value={effort}
                    onChange={(e) => {
                      setEffort(Number(e.target.value));
                      setResult(null);
                    }}
                  />
                </label>
              </div>
              <label>
                Eligible group
                <select
                  aria-label="Eligible group"
                  value={tag}
                  disabled={busy}
                  onChange={(e) => {
                    setTag(Number(e.target.value));
                    setResult(null);
                    setSweep(null);
                  }}
                >
                  <option value="-1">All groups</option>
                  {colors.map((_, i) => (
                    <option key={i} value={i}>
                      Group {i}
                    </option>
                  ))}
                </select>
              </label>
              <p className="note">
                {tag >= 0 && algorithm === "hnsw"
                  ? "Filtered HNSW uses an exact eligible scan. Complete results, higher cost."
                  : algorithm === "ivf"
                    ? "Effort = lists probed (max 32). A partial probe may miss neighbors."
                    : "HNSW effort = candidate beam width. Exact mode ignores effort."}
              </p>
              <button
                className="primary"
                disabled={busy || !state}
                onClick={() => void query()}
              >
                {busy ? "SEARCHING…" : "Locate neighbors"}
                <span>↗</span>
              </button>
              <details>
                <summary>Connection settings</summary>
                <label>
                  Bearer token
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                  />
                </label>
                <button disabled={busy} onClick={() => void connect()}>
                  Reconnect
                </button>
                <p className="note">
                  local-demo is for loopback only. No token is stored.
                </p>
              </details>
            </aside>
            <div className="map-panel">
              <div className="map-heading">
                <span>THE SEARCH FIELD</span>
                <span>PROJECTION: DIMENSIONS 1 × 2</span>
              </div>
              <svg
                className="map"
                viewBox="0 0 900 600"
                role="img"
                aria-label="Synthetic vector field with query and nearest neighbors"
              >
                <defs>
                  <pattern
                    id="grid"
                    width="50"
                    height="50"
                    patternUnits="userSpaceOnUse"
                  >
                    <path
                      d="M 50 0 L 0 0 0 50"
                      fill="none"
                      stroke="#335063"
                      strokeWidth=".5"
                    />
                  </pattern>
                </defs>
                <rect x="0" y="0" width="900" height="600" fill="url(#grid)" />
                {[100, 200, 300].map((r) => (
                  <ellipse
                    key={r}
                    cx="450"
                    cy="300"
                    rx={r * 1.3}
                    ry={r * 0.7}
                    className="contour"
                  />
                ))}
                <text x="25" y="30" className="map-annotation">
                  N ↑ / SYNTHETIC TERRAIN
                </text>
                <text x="25" y="580" className="map-annotation">
                  2D PROJECTION DOES NOT PRESERVE 24D DISTANCES
                </text>
                {state?.points.map((p) => (
                  <circle
                    key={p.id}
                    cx={px(p.x)}
                    cy={py(p.y)}
                    r={selected.has(p.id) ? 5 : 2.1}
                    fill={colors[p.tag]}
                    opacity={
                      tag < 0 || tag === p.tag
                        ? selected.has(p.id)
                          ? 1
                          : 0.65
                        : 0.12
                    }
                    className="vector-point"
                    onClick={() => {
                      if (!busy) {
                        setAnchor(p.id);
                        setManual(false);
                        setResult(null);
                      }
                    }}
                  >
                    <title>
                      Vector {p.id}, group {p.tag}
                    </title>
                  </circle>
                ))}
                {queryPoint && (
                  <g>
                    {result?.neighbors.map((n) => {
                      const p = state?.points[n.id];
                      return p ? (
                        <line
                          key={n.id}
                          x1={px(queryPoint.x)}
                          y1={py(queryPoint.y)}
                          x2={px(p.x)}
                          y2={py(p.y)}
                          className="neighbor-line"
                        />
                      ) : null;
                    })}
                    <circle
                      cx={px(queryPoint.x)}
                      cy={py(queryPoint.y)}
                      r="13"
                      className="query-ring"
                    />
                    <path
                      d={`M${px(queryPoint.x) - 20},${py(queryPoint.y)}h40 M${px(queryPoint.x)},${py(queryPoint.y) - 20}v40`}
                      className="crosshair"
                    />
                    <text
                      x={px(queryPoint.x) + 18}
                      y={py(queryPoint.y) - 15}
                      className="query-label"
                    >
                      {manual ? "CUSTOM" : `Q / ${anchor}`}
                    </text>
                  </g>
                )}
              </svg>
              <div className="map-legend">
                <span>
                  <i className="ring-icon" /> Query
                </span>
                <span>— Nearest-neighbor connection</span>
                <span>
                  {state
                    ? `${fmt(state.vectors)} vectors · ${state.dimensions}D · ${state.kernel}`
                    : "Connecting…"}
                </span>
              </div>
            </div>
          </section>
          <section className="findings">
            <div className="result-title">
              <div className="eyebrow">RETURNED TO STATION</div>
              <h2>Field notes</h2>
              <p aria-live="polite">
                {result
                  ? `${result.neighbors.length} neighbors / ${result.path}`
                  : "Run a query to collect live results."}
              </p>
            </div>
            <div className="reading">
              <span>NATIVE SEARCH</span>
              <strong>
                {result ? fmt(result.elapsed_ms, 3) : "—"}
                <small> ms</small>
              </strong>
              <p>Binding + search; excludes HTTP and exact check.</p>
            </div>
            <div className="reading">
              <span>RECALL @ 10</span>
              <strong>
                {result ? fmt(result.recall * 100, 1) : "—"}
                <small> %</small>
              </strong>
              <p>Against exact eligible neighbors for this query.</p>
            </div>
            <div className="reading">
              <span>OWNED ALLOCATIONS</span>
              <strong>
                {state ? fmt(state.bytes / state.vectors, 1) : "—"}
                <small> B/vector</small>
              </strong>
              <p>Both indexes + vectors. Excludes allocator & scratch.</p>
            </div>
          </section>
          {result && (
            <div className="neighbors" aria-label="Neighbor results">
              {result.neighbors.map((n, i) => (
                <button
                  disabled={busy}
                  key={n.id}
                  onClick={() => {
                    setAnchor(n.id);
                    setManual(false);
                    setResult(null);
                  }}
                >
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <b>V{n.id}</b>
                  <small>
                    G{n.tag} / L² {fmt(n.squared_l2, 3)}
                  </small>
                </button>
              ))}
            </div>
          )}
          <section className="sweep-section">
            <div>
              <div className="eyebrow">THE COST OF EXPLORATION</div>
              <h2>Widen the search.</h2>
              <p>
                Run a live sweep over 16 seed queries per setting.
                <br />
                The field changes with effort. The truth does not.
              </p>
              <button
                className="outline"
                disabled={busy || !state}
                onClick={() => void runSweep()}
              >
                {busy ? "MEASURING…" : "Measure a sweep →"}
              </button>
            </div>
            <div className="sweep-data">
              {sweep ? (
                <>
                  <Chart
                    rows={sweep.rows.map((r) => ({
                      x: r.qps,
                      y: r.recall,
                      label: `${r.algorithm} ${r.effort}`,
                      group: r.algorithm,
                    }))}
                  />
                  <p className="note">{sweep.scope}</p>
                  <table>
                    <thead>
                      <tr>
                        <th>Index / effort</th>
                        <th>Recall@10</th>
                        <th>QPS</th>
                        <th>p50 ms</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sweep.rows.map((r) => (
                        <tr key={r.algorithm + r.effort}>
                          <td>
                            {r.path} / {r.effort}
                          </td>
                          <td>{fmt(r.recall * 100, 1)}%</td>
                          <td>{fmt(r.qps, 0)}</td>
                          <td>{fmt(r.p50_ms, 3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="empty-chart">
                  <span>↗</span>
                  <p>
                    Recall versus speed.
                    <br />A curve you measure here, now.
                  </p>
                  <small>No prefilled performance numbers.</small>
                </div>
              )}
            </div>
          </section>
        </>
      ) : (
        <section className="evidence">
          <div className="eyebrow">
            RECORDED EXPEDITIONS / NOT LIVE REQUESTS
          </div>
          <h2>
            Hold every claim
            <br />
            <em>against the evidence.</em>
          </h2>
          <p>
            Same public vectors, one search thread, exact ground truth. Atlas
            owns both indexes; FAISS provides the comparison. Single-query calls
            include binding/result conversion. Three warm timing trials, median
            QPS.
          </p>
          {evidence.length ? (
            evidence.map((run) => (
              <article key={run.dataset + run.base_vectors}>
                <h3>
                  {run.dataset.startsWith("sift") ? "SIFT1M" : "GloVe"}{" "}
                  <small>
                    {fmt(run.base_vectors)} / {fmt(run.available_base)} base
                    vectors
                  </small>
                </h3>
                <p>
                  {run.metric} · {run.query_count} public test queries ·{" "}
                  {run.base_vectors === run.available_base
                    ? "Full base corpus"
                    : "Subset — not a full-corpus claim"}
                </p>
                <Chart
                  rows={run.rows.map((r) => ({
                    x: r.qps_median,
                    y: r.recall_at_10,
                    label: `${r.engine} ${r.algorithm} ${r.effort}`,
                    group: `${r.engine}-${r.algorithm}`,
                  }))}
                />
                <table>
                  <thead>
                    <tr>
                      <th>Engine / algorithm / effort</th>
                      <th>Recall@10</th>
                      <th>Median QPS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.rows.map((r) => (
                      <tr key={r.engine + r.algorithm + r.effort}>
                        <td>
                          {r.engine} / {r.algorithm} / {r.effort}
                        </td>
                        <td>{fmt(r.recall_at_10 * 100, 1)}%</td>
                        <td>{fmt(r.qps_median, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h4>Build & memory accounting</h4>
                {run.builds.map((b) => (
                  <p className="memory-note" key={b.engine}>
                    <b>{b.engine}</b> / {fmt(b.seconds)} s /{" "}
                    {fmt(b.bytes_per_vector, 1)} B per vector
                    <br />
                    <small>{b.memory_kind}</small>
                  </p>
                ))}
              </article>
            ))
          ) : (
            <p className="empty-chart">
              No recorded public benchmark found. Run scripts/data.py, then make
              bench.
            </p>
          )}
          <p className="note">
            These runs measure search, not service throughput. FAISS
            serialization and Atlas allocated capacities are different memory
            measures. Neither is process RSS. Do not infer a general winner from
            one machine and a fixed query sample.
          </p>
        </section>
      )}
      <footer>
        <div className="wordmark">✳ ATLAS</div>
        <p>
          BUILT TO BE INSPECTED.
          <br />
          PUBLIC + SYNTHETIC DATA ONLY.
        </p>
        <a
          href="https://github.com/rjrddy/atlas"
          target="_blank"
          rel="noreferrer"
        >
          Source & raw measurements ↗
        </a>
      </footer>
    </main>
  );
}
function Chart({
  rows,
}: {
  rows: { x: number; y: number; label: string; group: string }[];
}) {
  const max = Math.max(...rows.map((r) => r.x), 1);
  const groups = [...new Set(rows.map((r) => r.group))];
  return (
    <div className="chart">
      <svg
        viewBox="0 0 650 280"
        role="img"
        aria-label="Recall at ten versus queries per second"
      >
        <path d="M55 20V235H620" className="axis" />
        {[0, 0.5, 1].map((y) => (
          <g key={y}>
            <line
              x1="55"
              x2="620"
              y1={235 - y * 210}
              y2={235 - y * 210}
              className="chart-grid"
            />
            <text x="15" y={240 - y * 210}>
              {y * 100}%
            </text>
          </g>
        ))}
        {groups.map((g, i) => {
          const points = rows.filter((r) => r.group === g);
          return (
            <g key={g} stroke={colors[i % colors.length]}>
              <polyline
                fill="none"
                strokeWidth="2"
                points={points
                  .map((r) => `${55 + (r.x / max) * 550},${235 - r.y * 210}`)
                  .join(" ")}
              />
              {points.map((r) => (
                <circle
                  key={r.label}
                  cx={55 + (r.x / max) * 550}
                  cy={235 - r.y * 210}
                  r="5"
                  fill={colors[i % colors.length]}
                >
                  <title>
                    {r.label}: recall {fmt(r.y * 100)}%, {fmt(r.x, 0)} QPS
                  </title>
                </circle>
              ))}
            </g>
          );
        })}
        <text x="55" y="263">
          0 QPS
        </text>
        <text x="510" y="263">
          {fmt(max, 0)} QPS →
        </text>
      </svg>
      <div className="chart-legend">
        {groups.map((g, i) => (
          <span key={g}>
            <i className={`swatch color-${i % 8}`} />
            {g}
          </span>
        ))}
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
