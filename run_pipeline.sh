#!/usr/bin/env bash
# Re-runs every deterministic stage of the pipeline from the committed data + patch logs.
# The research / re-research stages are agent work (Claude Code or agent/research_agent.py); their outputs are the
# frozen Pass-1 draft (data/pass1/*.json) and the append-only patch logs (data/patches_*.jsonl).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

$PY -m agent.freeze                                                        # merge + hash Pass 1, draw audit sample
$PY -m agent.fetch_evidence data/pass1.json verification/links_pass1.json --catalog   # L1 liveness + browser loop + Composio catalog
$PY -m agent.mcp_registry   data/pass1.json verification/mcp_registry.json  # L2b official MCP Registry
$PY -m agent.verify         data/pass1.json verification/links_pass1.json pass1       # L1-L3 flags -> re-research queue
echo "re-research queue (flagged ids): $($PY -m agent.tools_cli flagged pass1)"
# Agent step: re-research flagged ids  ->  python -m agent.research_agent --ids <queue>   (or /research-app in Claude Code)
$PY -m agent.patch apply pass2 data/pass1.json data/pass2.json             # Pass 2 = Pass 1 + loop/agent patches
$PY -m agent.fetch_evidence data/pass2.json verification/links_pass2.json  # loop iteration 2
$PY -m agent.verify         data/pass2.json verification/links_pass2.json pass2
$PY -m agent.directories    data/pass2.json verification/directories.json  # L5 learned rule: connector directories
$PY -m agent.patch apply final data/pass2.json data/final.json             # Final = Pass 2 + audit/L5/holdout patches
$PY -m agent.fetch_evidence data/final.json verification/links_final.json
$PY -m agent.verify         data/final.json verification/links_final.json final
$PY -m agent.score                                                          # accuracy per pass (audit + held-out)
$PY -m agent.analyze                                                        # patterns
$PY -m agent.build_page                                                     # docs/ (GitHub Pages) + data exports
