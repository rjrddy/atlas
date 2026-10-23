"""Real nonroot image, HTTP/native query, snapshot restart and corrupt-start rejection."""

import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

NAME = "atlas-smoke"
TOKEN = "container-test-token-only-123456789"


def docker(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True
    ).stdout.strip()


def ready() -> dict:
    for _ in range(100):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:18096/api/query",
                data=b'{"anchor":17}',
                headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=1) as response:
                return json.load(response)
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(docker("logs", NAME, check=False))


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        directory.chmod(0o777)
        try:
            docker(
                "run",
                "-d",
                "--name",
                NAME,
                "-p",
                "127.0.0.1:18096:8094",
                "-e",
                f"ATLAS_TOKEN={TOKEN}",
                "-v",
                f"{temp}:/app/.cache",
                "atlas:test",
            )
            first = ready()
            assert first["neighbors"][0]["id"] == 17
            assert docker("exec", NAME, "id", "-u") == "10001"
            docker("kill", "--signal=KILL", NAME)
            docker("start", NAME)
            second = ready()
            assert first["neighbors"] == second["neighbors"]
            docker("stop", NAME)
            docker("rm", NAME)
            payload = bytearray((directory / "demo.atlas").read_bytes())
            payload[100] ^= 1
            damaged = directory / "damaged.atlas"
            damaged.write_bytes(payload)
            damaged.replace(directory / "demo.atlas")
            docker(
                "run",
                "-d",
                "--name",
                NAME,
                "-e",
                f"ATLAS_TOKEN={TOKEN}",
                "-v",
                f"{temp}:/app/.cache",
                "atlas:test",
            )
            code = docker("wait", NAME)
            log = docker("logs", NAME, check=False)
            assert code != "0" and "checksum mismatch" in log
            print(
                json.dumps(
                    {
                        "nonroot_uid": 10001,
                        "query": "pass",
                        "sigkill_reload": "identical neighbors",
                        "corrupt_start": "rejected",
                        "corrupt_exit": code,
                    }
                )
            )
        finally:
            docker("rm", "-f", NAME, check=False)


if __name__ == "__main__":
    main()
