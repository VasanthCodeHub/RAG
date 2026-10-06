"""Single entry point: starts the FastAPI backend and the React frontend.

    python run.py              # backend :8000 + frontend :5173
    python run.py --no-frontend

The MCP server is not started here on purpose: the backend launches it on
demand over stdio (see mcp_server/client.py), exactly how an MCP host would.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-frontend", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    procs: list[subprocess.Popen] = []
    try:
        print(f"[run] backend  -> http://localhost:{args.port}  (docs: /docs)")
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(args.port)], cwd=ROOT
            )
        )
        if not args.no_frontend:
            npm = shutil.which("npm")
            if not npm:
                print("[run] npm not found -- install Node.js 18+ or pass --no-frontend")
                return 1
            if not (FRONTEND / "node_modules").exists():
                print("[run] installing frontend dependencies (first run)...")
                subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
            print("[run] frontend -> http://localhost:5173")
            procs.append(subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND, env={**os.environ}))
        print("[run] Ctrl+C to stop.")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    sys.exit(main())
