"""Cross-platform backend commands; requires Python 3.12+ and uv on PATH."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup-server", "check-server", "run-server"])
    args = parser.parse_args()
    if sys.version_info < (3, 12):  # noqa: UP036 -- launcher may run before setup
        parser.error("Use Python 3.12 or later.")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("Install uv and make it available on PATH; see README.md.")

    commands: list[list[str]]
    if args.command == "setup-server":
        commands = [[uv, "sync", "--locked", "--extra", "dev"]]
    elif args.command == "check-server":
        commands = [
            [uv, "sync", "--locked", "--extra", "dev"],
            [uv, "run", "--locked", "pytest"],
            [uv, "run", "--locked", "ruff", "check", "."],
            [uv, "run", "--locked", "ruff", "format", "--check", "."],
            [uv, "run", "--locked", "mypy", "src"],
        ]
    else:
        commands = [
            [
                uv,
                "run",
                "--locked",
                "uvicorn",
                "one_job.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--workers",
                "1",
                "--ws-max-size",
                "16384",
                "--log-config",
                "logging.json",
            ]
        ]

    try:
        for command in commands:
            print("Running: " + " ".join(command), flush=True)
            result = subprocess.run(command, cwd=SERVER, check=False)
            if result.returncode:
                return result.returncode
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
