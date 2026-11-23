"""CLI access to the agent's verification tools (used by the Claude Code /research-app command).

usage:
  python -m agent.tools_cli registry <app_id>        # official MCP Registry, vendor-verified namespaces
  python -m agent.tools_cli directories "<App name>"  # Claude + OpenAI connector directories
  python -m agent.tools_cli fetch <url>               # visible text, headless-Chrome fallback for SPAs
  python -m agent.tools_cli flagged <tag>             # ids flagged by verification/verify_<tag>.json
"""
import json, pathlib, sys
from agent.research_agent import run_local_tool

ROOT = pathlib.Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "registry":
        print(json.dumps(run_local_tool("check_mcp_registry", {"app_id": int(arg)}), indent=1))
    elif cmd == "directories":
        print(json.dumps(run_local_tool("check_connector_directories", {"app": arg}), indent=1))
    elif cmd == "fetch":
        r = run_local_tool("fetch_page", {"url": arg}); print(r["status"], r["state"]); print(r["text"][:6000])
    elif cmd == "flagged":
        V = json.loads((ROOT / f"verification/verify_{arg}.json").read_text())
        print(",".join(str(o["id"]) for o in V["rows"] if o["flags"]))
