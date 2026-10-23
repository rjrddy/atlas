"""Independent clone/setup/gates plus actual make demo, without ignored source artifacts."""

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/results/fresh-clone"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="atlas-fresh-") as temp:
        clone = Path(temp) / "atlas"
        subprocess.run(
            ["git", "clone", "--no-hardlinks", str(ROOT), str(clone)],
            check=True,
            capture_output=True,
        )
        with (OUT / "checks.log").open("w") as log:
            subprocess.run(
                ["make", "setup", "lint", "test", "bench", "web"],
                cwd=clone,
                stdout=log,
                stderr=log,
                check=True,
            )
        for file in (clone / "docs/results").glob("*-20000.json"):
            (OUT / file.name).write_bytes(file.read_bytes())
        env = dict(os.environ, PORT="18097", ATLAS_GRPC_PORT="50074")
        with (OUT / "demo.log").open("w") as log:
            child = subprocess.Popen(
                ["make", "demo"], cwd=clone, env=env, stdout=log, stderr=log, start_new_session=True
            )
            try:
                for _ in range(600):
                    if child.poll() is not None:
                        raise RuntimeError((OUT / "demo.log").read_text())
                    try:
                        with urllib.request.urlopen(
                            "http://127.0.0.1:18097/", timeout=1
                        ) as response:
                            assert b"Atlas" in response.read()
                        break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("demo startup timeout")
                request = urllib.request.Request(
                    "http://127.0.0.1:18097/api/query",
                    data=b'{"anchor":17,"tag":3}',
                    headers={
                        "Authorization": "Bearer local-demo",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    result = json.load(response)
                assert result["path"] == "exact-filtered" and result["recall"] == 1
                assert len(result["neighbors"]) == 10
                assert all(n["tag"] == 3 for n in result["neighbors"])
                (OUT / "verification.json").write_text(
                    json.dumps(
                        {
                            "head": head,
                            "commands": [
                                "git clone --no-hardlinks",
                                "make setup lint test bench web",
                                "make demo",
                            ],
                            "ignored_artifacts_copied": False,
                            "data": "downloaded from public source by make bench",
                            "http_query": result,
                            "passed": True,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                print(json.dumps({"head": head, "fresh_clone": "pass", "make_demo": "pass"}))
            finally:
                import signal

                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=10)


if __name__ == "__main__":
    main()
