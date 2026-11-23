"""Loops 1-3: deterministic verification of a records file against the fetched evidence pages.

  L1 liveness   - is each cited URL alive (incl. soft-404s and redirects to a landing page)?
  L2 grounding  - does the cited page's text contain signals that support the claim?
                  (auth keywords for each claimed method, gating/free signals for access, API-style
                  signals, "MCP" on the MCP citation). Also detects CONFLICTS, e.g. access="free" but
                  the access page says "contact sales" and nothing about a free tier.
  L3 rules      - cross-field consistency (verdict vs access, official MCP without a citation, ...)

Every flagged row is routed to re-research (agent loop). Output: verification/verify_<tag>.json

usage: python -m agent.verify data/pass1.json verification/links_pass1.json pass1
"""
import json, pathlib, re, sys
from collections import Counter
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/pages"

AUTH_SIG = {
    "OAuth2": r"oauth ?2|oauth 2\.0|oauth|authorization code|client[_ ]credentials|refresh[_ ]token|/authorize",
    "OAuth1": r"oauth ?1|oauth 1\.0a?|oauth_signature|consumer key",
    "API key": r"api[ _-]?key|x-api-key|apikey|secret key|api token|security[_ ]key|access key",
    "Token": r"access token|bearer|bot token|personal access token|integration token|api token|auth token",
    "Basic": r"basic auth|http basic|authorization: basic|basic authentication|base64",
    "Signature": r"hmac|signature|signed|jwt|json web token|sigv4|private key|key[- ]pair",
}
ACCESS_SIG = {
    "free": r"free (plan|tier|account|forever|developer|sandbox|edition|version|to use|to start)|sandbox|test mode|"
            r"open[- ]source|no credit card|\$0\b|developer edition|demo company|development store",
    "trial": r"free trial|\btrial\b|free credits?|credits? (on|upon) sign|\d+[- ]day",
    "paid": r"paid plan|paid subscription|upgrade|enterprise plan|subscription|per month|/mo\b|plan required|add-on",
    "approval": r"review|approv|apply|application form|verif|developer token|access level|standard access|"
                r"basic access|production access|request access",
    "gated": r"contact (sales|us)|partner|request (a )?demo|talk to (sales|us)|customers? only|existing customers|book a demo",
    "local": r"pip install|npm install|brew install|license|mit\b|open source",
}
API_SIG = {
    "REST": r"\brest\b|endpoint|\bget /|\bpost /|https://api\.|curl ",
    "GraphQL": r"graphql",
    "SOAP": r"\bsoap\b|wsdl",
    "gRPC": r"grpc|protocol buffers?",
    "WebSocket": r"websocket|wss://|gateway|socket mode|event stream",
    "CLI/library": r"\bcli\b|command line|npm install|pip install|usage:",
    "MCP-only": r"\bmcp\b|model context protocol",
}
MCP_SIG = r"\bmcp\b|model context protocol"
STRONG_GATE = (r"app review|requires? (an? )?approval|must be approved|apply for (api )?access|request (api )?access|"
               r"production access|access application|submit (your app )?for review|security review|business verification|"
               r"developer token|standard access|advanced access|partner program|become a partner")
SOFT404 = r"page (not|couldn.t be|could not be) found|\b404\b|doesn.t exist|no longer available|we can.t find|page you requested"


def page(links, url):
    m = links["urls"].get(url)
    if not m:
        return None, ""
    p = CACHE / m["cache"]
    return m, (p.read_text().lower() if p.exists() else "")


def liveness(links, url):
    if not url:
        return "missing"
    m, text = page(links, url)
    if m is None:
        return "missing"
    if m["state"] in ("dead",):
        return "dead"
    if m["state"] == "blocked":
        return "blocked"
    if m["state"] == "thin":
        return "thin"
    if re.search(SOFT404, text[:1500]):
        return "soft404"
    fu = m.get("final_url", url)
    if urlparse(fu).netloc != urlparse(url).netloc and len(urlparse(fu).path.strip("/")) < 3:
        return "redirect-home"
    if len(urlparse(url).path.strip("/")) < 2 and not urlparse(url).query:
        return "homepage"      # alive, but a bare homepage is weak evidence
    return "ok"


def grounded(text, pattern):
    hit = re.search(pattern, text)
    if not hit:
        return None
    s = max(0, hit.start() - 90)
    return text[s:hit.end() + 90].strip()


def check_row(r, links):
    ev = r["ev"]
    app_text = " ".join(page(links, u)[1] for u in set(ev.values()) if u)
    res = {"id": r["id"], "app": r["app"], "flags": [], "fields": {}}

    # ---- L1 liveness per field
    live = {f: liveness(links, ev.get(f, "")) for f in ("auth", "access", "api", "mcp")}
    res["liveness"] = live

    # ---- L2 grounding: auth
    _, t_auth = page(links, ev.get("auth", ""))
    auth = {}
    for m in r["auth"]:
        if m == "None":
            auth[m] = "n/a"
            continue
        if grounded(t_auth, AUTH_SIG[m]):
            auth[m] = "supported"
        elif grounded(app_text, AUTH_SIG[m]):
            auth[m] = "weak"           # only found on another of this app's cited pages
        else:
            auth[m] = "unsupported"
    res["fields"]["auth"] = auth

    # ---- L2 grounding: access (+ conflict detection)
    _, t_acc = page(links, ev.get("access", ""))
    acc = r["access"]
    if acc == "local":
        a_state = "supported" if grounded(app_text, ACCESS_SIG["local"]) else "unsupported"
    else:
        a_state = "supported" if grounded(t_acc, ACCESS_SIG[acc]) else (
            "weak" if grounded(app_text, ACCESS_SIG[acc]) else "unsupported")
    conflict = None
    if acc in ("free", "trial") and grounded(t_acc, ACCESS_SIG["gated"]) and not grounded(t_acc, ACCESS_SIG["free"] + "|" + ACCESS_SIG["trial"]):
        conflict = "claims self-serve, page only shows sales/partner language"
    if acc == "gated" and grounded(t_acc, ACCESS_SIG["free"]) and not grounded(t_acc, ACCESS_SIG["gated"]):
        conflict = "claims gated, page shows free/sandbox language"
    # v1 of this rule matched any "review"/"approv" token and fired on 30+ pricing pages (boilerplate like
    # "customer reviews"). v2 only fires on phrases that actually describe an access gate.
    if acc == "free" and grounded(t_acc, STRONG_GATE) and not re.search(r"approv|review|verif|assess|certif", r["access_d"].lower()):
        conflict = (conflict or "") + " | page describes an approval/review gate not reflected in claim"
    res["fields"]["access"] = {"state": a_state, "conflict": conflict}

    # ---- L2 grounding: API style
    _, t_api = page(links, ev.get("api", ""))
    res["fields"]["api"] = {k: ("supported" if grounded(t_api, API_SIG[k]) else
                                "weak" if grounded(app_text, API_SIG[k]) else "unsupported")
                            for k in r["api"] if k != "None"}

    # ---- L2 grounding: MCP
    if r["mcp"] == "official":
        _, t_mcp = page(links, ev.get("mcp", ""))
        res["fields"]["mcp"] = "supported" if ev.get("mcp") and grounded(t_mcp, MCP_SIG) else "unsupported"
    else:
        res["fields"]["mcp"] = "absence-claim"   # can't prove a negative from a page; search loop handles it

    # ---- flags
    for f, s in live.items():
        if s in ("dead", "soft404", "redirect-home", "missing") and not (f == "mcp" and r["mcp"] != "official"):
            res["flags"].append(f"L1:{f}:{s}")
        elif s in ("thin", "blocked"):
            res["flags"].append(f"L1:{f}:{s}(needs browser/human read)")
        elif s == "homepage":
            res["flags"].append(f"L1:{f}:homepage-citation")
    for m, s in auth.items():
        if s == "unsupported":
            res["flags"].append(f"L2:auth:{m}-not-on-page")
    if a_state == "unsupported":
        res["flags"].append(f"L2:access:{acc}-not-on-page")
    if conflict:
        res["flags"].append(f"L2:access:conflict({conflict.strip(' |')})")
    for k, s in res["fields"]["api"].items():
        if s == "unsupported":
            res["flags"].append(f"L2:api:{k}-not-on-page")
    if res["fields"]["mcp"] == "unsupported":
        res["flags"].append("L2:mcp:official-claim-unsupported")

    # ---- L3 consistency rules
    if r["verdict"] == "build-now" and r["access"] in ("gated", "approval", "paid"):
        res["flags"].append(f"L3:verdict build-now but access={r['access']}")
    if r["verdict"] == "needs-outreach" and r["access"] in ("free", "trial", "local"):
        res["flags"].append(f"L3:verdict needs-outreach but access={r['access']}")
    if "None" in r["api"] and r["verdict"] != "not-viable" and r["verdict"] != "needs-outreach":
        res["flags"].append("L3:no API but buildable verdict")
    if r["mcp"] == "official" and not ev.get("mcp"):
        res["flags"].append("L3:official MCP without citation")
    if r["mcp"] == "none" and r["conf"] != "high":
        res["flags"].append("L3:absence of MCP asserted at <high confidence (search loop)")
    if len({u for u in ev.values() if u}) == 1:
        res["flags"].append("L3:single URL cited for every field")
    if r["conf"] == "low":
        res["flags"].append("L3:agent self-reported low confidence")
    return res


def registry_flags(r, res, registry):
    """Loop 2b: reconcile the MCP claim with the official MCP Registry (positive evidence only)."""
    reg = registry.get(str(r["id"]))
    if not reg:
        return
    res["registry"] = reg["verdict"]
    if reg["verdict"] == "official" and r["mcp"] != "official":
        res["flags"].append(f"L2b:mcp:registry lists vendor-owned server {reg['official'][0]['name']} but claim={r['mcp']}")
    if r["mcp"] == "official" and res["fields"]["mcp"] == "unsupported" and reg["verdict"] != "official":
        res["flags"].append("L2b:mcp:official claim has no grounded citation and no registry entry")
    if r["mcp"] == "official" and reg["verdict"] == "official":
        res["fields"]["mcp"] = "supported"
        res["flags"] = [f for f in res["flags"] if not f.startswith("L2:mcp") and "official MCP without citation" not in f]


def main():
    rows = json.loads(pathlib.Path(sys.argv[1]).read_text())
    links = json.loads(pathlib.Path(sys.argv[2]).read_text())
    tag = sys.argv[3]
    reg_path = ROOT / "verification/mcp_registry.json"
    registry = json.loads(reg_path.read_text()) if reg_path.exists() else {}
    out = []
    for r in rows:
        o = check_row(r, links)
        registry_flags(r, o, registry)
        out.append(o)
    flagged = [o for o in out if o["flags"]]
    by_loop = Counter(f.split(":")[0] for o in out for f in o["flags"])
    by_kind = Counter(":".join(f.split(":")[:2]) for o in out for f in o["flags"])
    summary = {"tag": tag, "rows": len(rows), "rows_flagged": len(flagged),
               "flags_by_loop": by_loop, "flags_by_field": by_kind,
               "claims": {
                   "auth_methods": sum(len(o["fields"]["auth"]) for o in out),
                   "auth_supported": sum(1 for o in out for s in o["fields"]["auth"].values() if s in ("supported", "n/a")),
                   "access_supported": sum(1 for o in out if o["fields"]["access"]["state"] == "supported"),
                   "access_conflicts": sum(1 for o in out if o["fields"]["access"]["conflict"]),
                   "mcp_official_claims": sum(1 for o in out if o["fields"]["mcp"] in ("supported", "unsupported")),
                   "mcp_official_supported": sum(1 for o in out if o["fields"]["mcp"] == "supported"),
                   "links_ok": sum(1 for o in out for s in o["liveness"].values() if s == "ok"),
                   "links_total": sum(1 for o in out for s in o["liveness"].values() if s != "missing"),
               }}
    pathlib.Path(f"{ROOT}/verification/verify_{tag}.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
