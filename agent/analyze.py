"""Cluster the final records into the patterns shown at the top of the case study.

usage: python -m agent.analyze  ->  verification/patterns.json
"""
import json, pathlib, re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATS = ["CRM & Sales", "Support & Helpdesk", "Comms & Messaging", "Marketing, Ads & Social", "Ecommerce",
        "Data, SEO & Scraping", "Dev, Infra & Data", "Productivity & PM", "Finance & Fintech", "AI, Research & Media"]
SELF_SERVE = {"free", "trial", "local"}

BLOCKER_CLUSTERS = [   # first match wins; order = specificity
    ("No public API / unclear product", r"no public api|could not confirm|unclear|no general|mcp-only"),
    ("Customer or partner account", r"customer|realm|tenant|partner approval|business account|technology partner|reseller"),
    ("Sales-gated", r"sales|subscription|license|demo org|contract|enterprise-only"),
    ("Vendor review / approval", r"review|approval|verification|developer token|access application|registration|tech provider|sandbox request|assessment"),
    ("Paid plan to test", r"paid|enterprise plan|lite\+|credits|plan"),
    ("Rate or tier limits", r"tier|rate limit|throttl|quota|connections"),
    ("Per-instance host / self-hosted", r"per-instance|per-store|per-tenant|subdomain|account-specific|multi-dc|multi-site|self-host"),
    ("Request signing / KYC", r"signing|kyc"),
    ("Local tool, needs sandbox", r"sandbox|local|chromium|hosted api"),
    ("Trial-only test account", r"trial"),
]


def cluster(b):
    b = (b or "").lower()
    if b in ("", "none"):
        return "None"
    for name, pat in BLOCKER_CLUSTERS:
        if re.search(pat, b):
            return name
    return "Other"


def main():
    rows = json.loads((ROOT / "data/final.json").read_text())
    p1 = {r["id"]: r for r in json.loads((ROOT / "data/pass1.json").read_text())}
    cat_links = json.loads((ROOT / "verification/links_pass1.json").read_text()).get("composio", {})
    on_composio = {a for a, v in cat_links.items() if v and re.search(r"MCP Server", v["title"]) and "Toolkits -" not in v["title"]}

    auth_any = Counter(m for r in rows for m in r["auth"])
    oauth = sum("OAuth2" in r["auth"] for r in rows)
    key_only = sum(("OAuth2" not in r["auth"] and "OAuth1" not in r["auth"] and r["auth"] != ["None"]) for r in rows)
    access = Counter(r["access"] for r in rows)
    verdict = Counter(r["verdict"] for r in rows)
    blockers = Counter(cluster(r["blocker"]) for r in rows if r["verdict"] != "build-now")
    by_cat = {}
    for c in CATS:
        rs = [r for r in rows if r["cat"] == c]
        by_cat[c] = {"n": len(rs), "self_serve": sum(r["access"] in SELF_SERVE for r in rs),
                     "access": Counter(r["access"] for r in rs), "verdict": Counter(r["verdict"] for r in rs),
                     "oauth": sum("OAuth2" in r["auth"] for r in rs), "mcp_official": sum(r["mcp"] == "official" for r in rs)}
    mcp_final = sum(r["mcp"] == "official" for r in rows)
    mcp_draft = sum(p["mcp"] == "official" for p in p1.values())
    easy = [r for r in rows if r["verdict"] == "build-now" and r["app"] not in on_composio]
    outreach = [r for r in rows if r["verdict"] == "needs-outreach"]
    caveats = [r for r in rows if r["verdict"] == "build-with-caveats"]
    out = {
        "n": len(rows),
        "auth_any": auth_any, "oauth_offered": oauth, "key_only": key_only,
        "access": access, "self_serve": sum(access[k] for k in SELF_SERVE),
        "verdict": verdict, "blockers": blockers, "by_cat": by_cat,
        "mcp": {"official_final": mcp_final, "official_draft": mcp_draft},
        "composio": {"on_composio": len(on_composio), "apps": sorted(on_composio)},
        "easy_wins_not_on_composio": [{"id": r["id"], "app": r["app"], "auth": r["auth"], "mcp": r["mcp"]} for r in easy],
        "outreach": [{"id": r["id"], "app": r["app"], "blocker": r["blocker"]} for r in outreach],
        "caveats": [{"id": r["id"], "app": r["app"], "blocker": r["blocker"], "cluster": cluster(r["blocker"])} for r in caveats],
        "build_now_on_composio": sum(r["verdict"] == "build-now" and r["app"] in on_composio for r in rows),
    }
    (ROOT / "verification/patterns.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ["auth_any", "oauth_offered", "key_only", "access", "self_serve", "verdict", "blockers", "mcp", "build_now_on_composio"]}, indent=0))
    print("composio coverage:", out["composio"]["on_composio"])
    print("easy wins NOT on Composio:", [e["app"] for e in out["easy_wins_not_on_composio"]])
    print("outreach:", [(o["app"], o["blocker"]) for o in out["outreach"]])
    for c, v in by_cat.items():
        print(f'{c:24} self-serve {v["self_serve"]}/{v["n"]}  oauth {v["oauth"]}  mcp {v["mcp_official"]}  {dict(v["verdict"])}')
    print("caveat clusters:", Counter(c["cluster"] for c in out["caveats"]))


if __name__ == "__main__":
    main()
