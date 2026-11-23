---
description: Research one app for toolkit buildability (auth, access, API, MCP, verdict) with cited evidence
argument-hint: <app id from apps.csv>
---
Research app #$ARGUMENTS from `apps.csv` and write `data/agent_runs/<id 3-digit>.json`.

Follow the protocol in `agent/prompts/research.md` exactly, using the schema enums in `agent/schema.py`.
Tools:
- WebSearch / WebFetch for vendor docs.
- `.venv/bin/python -m agent.tools_cli registry $ARGUMENTS`: official MCP Registry check (always run).
- `.venv/bin/python -m agent.tools_cli directories "<App>"`: Claude/OpenAI connector directories (always run).
- `.venv/bin/python -m agent.tools_cli fetch <url>`: read client-rendered docs in headless Chrome.

The output record has the same keys as rows in `data/final.json`, plus a `quotes` object with the sentence that
supports each of auth/access/api/mcp. If the product can't be identified, say so (conf "low", verdict
"needs-outreach"). Then run the automated loops on it:
`.venv/bin/python -m agent.fetch_evidence data/agent_runs/<id>.json /tmp/links.json && .venv/bin/python -m agent.verify data/agent_runs/<id>.json /tmp/links.json single`
and fix anything flagged before you finish.
