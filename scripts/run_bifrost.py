"""Start a local Bifrost AI gateway for FreshGuard AI.

Reads the project .env, exposes the Groq key to Bifrost as GROQ_API_KEY
(accepting GROQ_API_KEY or LLM_API_KEY), and runs `npx -y @maximhq/bifrost`
with ./bifrost as the app directory (config.json lives there).

Usage:  py -3.13 scripts/run_bifrost.py [--port 8080]
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=os.getenv("BIFROST_PORT", "8080"))
    parser.add_argument("--version", default=os.getenv("BIFROST_VERSION", "v2.5.1"),
                        help="Bifrost release to run (pinned so restarts never re-download).")
    args = parser.parse_args()

    env = os.environ.copy()
    file_vals = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v}
    groq_key = env.get("GROQ_API_KEY") or file_vals.get("GROQ_API_KEY") or file_vals.get("LLM_API_KEY")
    if not groq_key:
        print("GROQ_API_KEY (or LLM_API_KEY) is not set in the environment or .env", file=sys.stderr)
        return 1
    env["GROQ_API_KEY"] = groq_key

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("npx was not found. Install Node.js 18+ to run Bifrost.", file=sys.stderr)
        return 1

    cmd = [npx, "-y", "@maximhq/bifrost", "--transport-version", args.version, "-app-dir", str(ROOT / "bifrost"), "-port", str(args.port), "-host", "127.0.0.1"]
    print(f"Starting Bifrost {args.version} on http://127.0.0.1:{args.port} (app dir: bifrost/)", flush=True)
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
