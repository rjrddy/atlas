"""Browser proof: real queries, full-coordinate edits, sweeps, auth and narrow screens."""

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/results/browser"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    receipts, errors = [], []
    with tempfile.TemporaryDirectory() as temp:
        logpath = Path(temp) / "server.log"
        with logpath.open("w") as log:
            process = subprocess.Popen(
                [str(ROOT / ".venv/bin/python"), "scripts/server.py"],
                cwd=ROOT,
                env={
                    **os.environ,
                    "PYTHONPATH": "build:sdk",
                    "PORT": "18095",
                    "ATLAS_GRPC_PORT": "50073",
                    "ATLAS_SNAPSHOT": str(Path(temp) / "demo.atlas"),
                },
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:18095/health", timeout=1).close()
                        break
                    except OSError:
                        if process.poll() is not None:
                            raise RuntimeError(logpath.read_text()) from None
                        time.sleep(0.1)
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=p.chromium.executable_path)
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1100},
                        **(
                            {
                                "record_video_dir": temp,
                                "record_video_size": {"width": 1440, "height": 1100},
                            }
                            if args.record
                            else {}
                        ),
                    )
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto("http://127.0.0.1:18095")
                    expect(page.get_by_text("INDEX ON STATION", exact=False)).to_be_visible()
                    started = time.monotonic()

                    def query():
                        with page.expect_response(
                            lambda r: r.url.endswith("/api/query") and r.request.method == "POST"
                        ) as response:
                            page.get_by_role("button", name="Locate neighbors").click()
                        data = response.value.json()
                        assert response.value.ok, data
                        expect(page.get_by_label("Neighbor results")).to_be_visible()
                        assert len(data["neighbors"]) == 10
                        receipts.append(
                            {
                                "kind": "query",
                                "path": data["path"],
                                "recall": data["recall"],
                                "neighbors": data["neighbors"],
                                "elapsed_ms": data["elapsed_ms"],
                            }
                        )
                        return data

                    result = query()
                    assert result["neighbors"][0]["id"] == 17
                    page.screenshot(path=str(OUT / "desktop.png"), full_page=True)
                    for algorithm, effort in [
                        ("ivf", "1"),
                        ("ivf", "32"),
                        ("exact", "1"),
                        ("hnsw", "64"),
                    ]:
                        page.get_by_label("Index", exact=True).select_option(algorithm)
                        page.get_by_label("Effort", exact=True).fill(effort)
                        result = query()
                        if algorithm == "exact" or effort == "32":
                            assert result["recall"] == 1
                    for tag in ["0", "3", "7"]:
                        page.get_by_label("Eligible group").select_option(tag)
                        result = query()
                        assert result["path"] == "exact-filtered"
                        assert all(n["tag"] == int(tag) for n in result["neighbors"])
                    page.get_by_label("Eligible group").select_option("-1")
                    page.get_by_label("Query source").select_option("manual")
                    page.get_by_label("24 float coordinates").fill("[1, 2]")
                    page.get_by_role("button", name="Locate neighbors").click()
                    expect(page.get_by_role("alert")).to_contain_text("24 finite")
                    receipts.append(
                        {
                            "kind": "caught-invalid-dimension",
                            "text": page.get_by_role("alert").inner_text(),
                        }
                    )
                    page.get_by_label("24 float coordinates").fill(json.dumps([0.25] * 24))
                    query()
                    page.get_by_label("Query source").select_option("anchor")
                    with page.expect_response(lambda r: r.url.endswith("/api/sweep")) as response:
                        page.get_by_role("button", name="Measure a sweep").click()
                    data = response.value.json()
                    assert len(data["rows"]) == 8
                    expect(
                        page.get_by_role("img", name="Recall at ten versus queries per second")
                    ).to_be_visible()
                    receipts.append({"kind": "live-sweep", **data})
                    page.locator("summary").click()
                    page.get_by_label("Bearer token").fill("invalid-token")
                    page.get_by_role("button", name="Reconnect", exact=True).click()
                    expect(page.get_by_role("alert")).to_contain_text("bearer required")
                    page.get_by_label("Bearer token").fill("local-demo")
                    page.get_by_role("button", name="Reconnect", exact=True).click()
                    expect(page.get_by_role("alert")).to_have_count(0)
                    query()
                    page.get_by_role("button", name="Public-data expeditions").click()
                    expect(
                        page.get_by_role("heading", name="Hold every claim against the evidence.")
                    ).to_be_visible()
                    page.screenshot(path=str(OUT / "evidence.png"), full_page=True)
                    page.get_by_role("button", name="Search field").click()
                    for width in [390, 768, 1024, 1440]:
                        page.set_viewport_size({"width": width, "height": 1100})
                        page.evaluate("window.scrollTo(0,0)")
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        ), width
                        expect(page.get_by_role("button", name="Locate neighbors")).to_be_visible()
                        if width == 390:
                            page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
                        receipts.append({"kind": "responsive", "width": width, "no_overflow": True})
                    # Record actual varied query lifecycles, not a padded static screenshot.
                    iteration = 0
                    while args.record and time.monotonic() - started < 92:
                        page.get_by_label("Vector ID").fill(str((17 + 73 * iteration) % 2048))
                        page.get_by_label("Eligible group").select_option(
                            str(iteration % 8) if iteration % 2 else "-1"
                        )
                        query()
                        page.wait_for_timeout(1300)
                        iteration += 1
                    page.get_by_role("button", name="Locate neighbors").focus()
                    expect(page.get_by_role("button", name="Locate neighbors")).to_be_focused()
                    assert not errors, errors
                    elapsed = time.monotonic() - started
                    video = page.video
                    context.close()
                    if video:
                        video.save_as(str(OUT / "atlas-demo.webm"))
                    browser.close()
                    (OUT / "review.json").write_text(
                        json.dumps(
                            {
                                "elapsed_seconds": elapsed,
                                "page_errors": errors,
                                "receipts": receipts,
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                    print(
                        json.dumps(
                            {
                                "elapsed_seconds": elapsed,
                                "receipts": len(receipts),
                                "page_errors": errors,
                            }
                        )
                    )
            finally:
                process.terminate()
                process.wait(timeout=10)
                (OUT / "server.log").write_text(logpath.read_text())


if __name__ == "__main__":
    main()
