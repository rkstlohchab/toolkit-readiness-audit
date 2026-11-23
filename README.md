# Toolkit Readiness Audit: 100 apps

**Live case study:** https://rkstlohchab.github.io/toolkit-readiness-audit/

An AI research agent checked whether each of 100 apps can become an agent toolkit. For every app it records the
login method, whether a developer can get API access on their own, the API surface, whether an official MCP server
exists, a verdict and the main blocker. Each answer links to the vendor page it came from. Verification loops, a
blind audit and a held-out test then measured how accurate the agent was.

| Measure | Value |
| --- | --- |
| Build now / with caveats / needs outreach | **64 / 25 / 11** |
| Self-serve apps | 73 |
| Apps offering OAuth 2.0 | 66 |
| Apps with an official MCP server | 84 (the agent's first draft guessed 48) |
| Accuracy on 10 held-out apps | **81.7% → 91.7%** (first draft → final) |
| Accuracy on the 30-app audit sample | 83.9% → 92.2% from the automated loops alone |

## How it works

| Step | What happens | Code |
|---|---|---|
| 1. First draft | The agent fills all 100 records from what it knows and proposes a source for every claim. Frozen and sha256-hashed before any check. | `data/pass1/`, `agent/freeze.py` |
| 2. Link check | Every source is fetched over HTTP, falling back to headless Chrome for JavaScript-built docs. Catches dead links, soft 404s and redirects to a homepage. | `agent/fetch_evidence.py` |
| 3. Claim check | Does the cited page actually contain the claimed login method, access gate, API style or MCP? Also flags contradictions. | `agent/verify.py` |
| 4. MCP Registry | A domain-verified namespace in registry.modelcontextprotocol.io proves an MCP server is the vendor's own. | `agent/mcp_registry.py` |
| 5. Re-research | The agent re-reads vendor docs only for flagged apps. Every change is an append-only patch with source and quote. | `agent/patch.py`, `data/patches_pass2.jsonl` |
| 6. Blind audit | 30 apps (drawn before any check) graded on 6 fields from primary docs against a written rubric. | `verification/audit.json`, `verification/RUBRIC.md` |
| 7. Learned rule | Error types found by the audit are re-checked across all 100 apps (connector directories, vendor docs). | `agent/directories.py`, `data/patches_final.jsonl` |
| 8. Held-out test | 10 new apps drawn after all fixes, graded the same way, against the data as it stood when they were drawn. | `verification/holdout.json`, `agent/score.py` |
| 9. Human sign-off | 12 consequential or uncertain answers queued for a person, each with its source. | `verification/human_review.csv` |

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium   # skip if Google Chrome is installed
./run_pipeline.sh                                 # every check, the scores, the patterns and the page (docs/)
```

The same pipeline runs in GitHub Actions on every push (`.github/workflows/verify.yml`).

Research one app with the agent:

```bash
# Claude Code (how this run was done): uses .claude/commands/research-app.md
claude "/research-app 15"

# Headless agent: Claude Opus 5.5 with Anthropic web search/fetch; the check loops are exposed to it as tools
export ANTHROPIC_API_KEY=...
.venv/bin/python -m agent.research_agent --ids 15,60

# Headless agent with Composio's composio_search + firecrawl toolkits
export COMPOSIO_API_KEY=...
.venv/bin/python -m agent.research_agent --ids 15 --engine composio
```

Records land in `data/agent_runs/`. Feed them through the checks and re-research only what gets flagged:
`.venv/bin/python -m agent.tools_cli flagged pass1`.

## Honest notes

- In this run, Claude Code (Opus 5.5) did the research steps as the agent, following `agent/prompts/research.md`.
  `agent/research_agent.py` is the headless version. It is checked against `anthropic==2.12.0` and
  `composio==0.34.0` but was not run end to end, because no API keys were available.
- The automated checks alone caught 55% of first-draft errors at 88% precision. They are a cheap filter in front of
  the agent. The blind audit caught the rest (mostly MCP servers and subtle access gates) and became rules.
- "Paygent Connect" defeated the agent: two different companies match the name and the NMI link could not be found.
- "On Composio" probes `composio.dev/toolkits/<slug>`. A miss is a strong hint, not proof.
- To record the human sign-off, fill the last two columns of `verification/human_review.csv` and run
  `.venv/bin/python -m agent.build_page`.

## Layout

```text
apps.csv            the 100 apps
agent/              schema, research agent + prompt, check loops, scoring, analysis, page builder
data/               pass1 / pass2 / final records; patches_*.jsonl = every change with its reason and source
verification/       link results, flags, MCP Registry, directories, audit truth, scores, patterns, human review
docs/               the published case study (GitHub Pages) + data.json, data.csv, llms.txt
```
