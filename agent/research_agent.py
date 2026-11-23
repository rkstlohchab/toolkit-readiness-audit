"""Headless research agent: one app in, one evidence-backed JSON record out.

  Model   : Claude Opus 5.5 (adaptive thinking, high effort, server-side refusal fallback)
  Search  : --engine claude   -> Anthropic server tools web_search_20260209 + web_fetch_20260209
            --engine composio -> Composio session tools (COMPOSIO_SEARCH + FIRECRAWL toolkits) via composio_anthropic
  Checks  : the deterministic verification loops are also exposed to the agent as tools, so it applies the
            lessons learned while researching: check_mcp_registry, check_connector_directories, fetch_page.

usage:
  export ANTHROPIC_API_KEY=...            (+ COMPOSIO_API_KEY for --engine composio)
  python -m agent.research_agent --ids 15,60,85 --engine claude      -> data/agent_runs/<id>.json
  python -m agent.research_agent --all --engine composio

Then run the verification loops on the output (see README / run_pipeline.sh).
"""
import argparse, asyncio, csv, json, pathlib, sys

import anthropic

from agent import schema
from agent.mcp_registry import run as registry_run, VENDOR
from agent.directories import run as directories_run
from agent.fetch_evidence import run as fetch_run, CACHE

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = "claude-opus-5-5"
SYSTEM = (ROOT / "agent/prompts/research.md").read_text()

RECORD_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["what", "auth", "auth_d", "access", "access_d", "api", "breadth", "api_d", "mcp", "mcp_d",
                 "verdict", "blocker", "ev", "quotes", "conf"],
    "properties": {
        "what": {"type": "string"},
        "auth": {"type": "array", "items": {"type": "string", "enum": schema.AUTH}},
        "auth_d": {"type": "string"},
        "access": {"type": "string", "enum": list(schema.ACCESS)},
        "access_d": {"type": "string"},
        "api": {"type": "array", "items": {"type": "string", "enum": schema.API}},
        "breadth": {"type": "string", "enum": schema.BREADTH},
        "api_d": {"type": "string"},
        "mcp": {"type": "string", "enum": schema.MCP},
        "mcp_d": {"type": "string"},
        "verdict": {"type": "string", "enum": list(schema.VERDICT)},
        "blocker": {"type": "string"},
        "ev": {"type": "object", "additionalProperties": False, "required": ["auth", "access", "api", "mcp"],
               "properties": {k: {"type": "string"} for k in ["auth", "access", "api", "mcp"]}},
        "quotes": {"type": "object", "additionalProperties": False, "required": ["auth", "access", "api", "mcp"],
                   "properties": {k: {"type": "string"} for k in ["auth", "access", "api", "mcp"]}},
        "conf": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}

# ---------------------------------------------------------------- client-side tools (our verification loops)
LOCAL_TOOLS = [
    {"name": "check_mcp_registry", "strict": True,
     "description": "Search the official MCP Registry for servers whose verified namespace belongs to this app's vendor. "
                    "Positive evidence only: absence does not prove there is no MCP.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["app_id"],
                      "properties": {"app_id": {"type": "integer"}}}},
    {"name": "check_connector_directories", "strict": True,
     "description": "Check claude.com/connectors and openai.com/business/plugins for a vendor-built connector for this app.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["app"],
                      "properties": {"app": {"type": "string"}}}},
    {"name": "fetch_page", "strict": True,
     "description": "Fetch a URL and return its visible text. Falls back to a real headless Chrome for client-rendered docs.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["url"],
                      "properties": {"url": {"type": "string"}}}},
]


def run_local_tool(name, args):
    if name == "check_mcp_registry":
        i = args["app_id"]
        return asyncio.run(registry_run([i]))[i] if i in VENDOR else {"error": "unknown app id"}
    if name == "check_connector_directories":
        return asyncio.run(directories_run([args["app"]]))[args["app"]]
    if name == "fetch_page":
        m = asyncio.run(fetch_run([args["url"]]))[args["url"]]
        return {"status": m["status"], "state": m["state"], "text": (CACHE / m["cache"]).read_text()[:20000]}
    return {"error": f"unknown tool {name}"}


def search_tools(engine):
    if engine == "claude":
        return [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12},
                {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 12}], None, None
    from composio import Composio, SESSION_PRESET_DIRECT_TOOLS   # pip install composio composio_anthropic
    from composio_anthropic import AnthropicProvider
    provider = AnthropicProvider()
    composio = Composio(provider=provider)
    session = composio.create(user_id="toolkit-research-agent", toolkits=["composio_search", "firecrawl"],
                              session_preset=SESSION_PRESET_DIRECT_TOOLS)
    return list(session.tools()), provider, session


def research(client, app, engine):
    tools, provider, session = search_tools(engine)
    composio_names = {t["name"] for t in tools if "type" not in t} if engine == "composio" else set()
    messages = [{"role": "user", "content": f"App #{app['id']}: {app['app']} (category: {app['category']}; hint: {app['hint']})."}]
    for _ in range(40):
        resp = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, messages=messages, tools=tools + LOCAL_TOOLS,
            thinking={"type": "adaptive"}, output_config={"effort": "high", "format": {"type": "json_schema", "schema": RECORD_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"refused: {resp.stop_details}")
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "pause_turn":            # server tool loop hit its limit; let it continue
            continue
        if resp.stop_reason != "tool_use":
            text = next(b.text for b in resp.content if b.type == "text")
            return json.loads(text)
        uses = [b for b in resp.content if b.type == "tool_use"]
        results = []
        for u in uses:                                   # all results go back in ONE user message
            if u.name in composio_names:                 # Composio tool: execute through the session by slug
                r = session.execute(u.name, arguments=u.input)
                out = {"result_type": r.result_type, "data": r.data, "error": r.error}
            else:
                out = run_local_tool(u.name, u.input)
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(out, default=str)[:30000]})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("agent did not finish in 40 turns")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=""); ap.add_argument("--all", action="store_true")
    ap.add_argument("--engine", choices=["claude", "composio"], default="claude")
    a = ap.parse_args()
    apps = list(csv.DictReader((ROOT / "apps.csv").open()))
    for x in apps:
        x["id"] = int(x["id"])
    ids = {int(i) for i in a.ids.split(",") if i} if not a.all else {x["id"] for x in apps}
    out_dir = ROOT / "data/agent_runs"; out_dir.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    for app in (x for x in apps if x["id"] in ids):
        try:
            rec = research(client, app, a.engine)
        except anthropic.RateLimitError as e:
            print(f"#{app['id']} rate limited (retry-after {e.response.headers.get('retry-after')}s)", file=sys.stderr); continue
        except anthropic.APIStatusError as e:
            print(f"#{app['id']} API error {e.status_code}: {e.message}", file=sys.stderr); continue
        except anthropic.APIConnectionError:
            print(f"#{app['id']} network error", file=sys.stderr); continue
        rec = {"id": app["id"], "app": app["app"], "cat": app["category"], **rec}
        (out_dir / f"{app['id']:03d}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        print(f"#{app['id']:<3} {app['app']:24} {rec['access']:8} mcp={rec['mcp']:9} {rec['verdict']}  ({rec['conf']})")


if __name__ == "__main__":
    main()
