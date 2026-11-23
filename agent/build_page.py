"""Build the case-study page from the data files.

  docs/index.html      the page (served by GitHub Pages)
  docs/data.json, data.csv, scores.json, patterns.json, llms.txt   machine-readable exports
  site/artifact.html   same page body for the claude.ai Artifact (the host adds <html>/<head>)

The whole table is pre-rendered HTML, so the page reads fine with JavaScript off (humans, agents, crawlers);
the script only adds filters, row expansion and chart tooltips.

usage: REPO_URL=https://github.com/<you>/<repo> PAGES_URL=https://<you>.github.io/<repo>/ python -m agent.build_page
"""
import csv, html, io, json, os, pathlib

from agent.analyze import cluster

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"; DOCS.mkdir(exist_ok=True)
SITE = ROOT / "site"; SITE.mkdir(exist_ok=True)
E = html.escape
J = lambda p: json.loads((ROOT / p).read_text())
REPO = os.environ.get("REPO_URL", "https://github.com/rkstlohchab/toolkit-readiness-audit").rstrip("/")
PAGES = os.environ.get("PAGES_URL", "https://rkstlohchab.github.io/toolkit-readiness-audit/")
BLOB = f"{REPO}/blob/main"

rows = J("data/final.json"); p1 = {r["id"]: r for r in J("data/pass1.json")}
S = J("verification/scores.json"); P = J("verification/patterns.json"); A = J("verification/audit.json")
sample = J("verification/sample.json"); hold = J("verification/holdout.json")
V1, VF = J("verification/verify_pass1.json"), J("verification/verify_final.json")
ch = [dict(c, stage="Pass 2") for c in J("data/changes_pass2.json")] + [dict(c, stage="Final") for c in J("data/changes_final.json")]
on_comp = set(P["composio"]["apps"])
human = list(csv.DictReader((ROOT / "verification/human_review.csv").open()))
HV = "human_verdict(✓/✗)"
CATS = list(P["by_cat"])
LOOP = {"L1": "link check", "L2": "claim check", "L2b": "MCP Registry", "L3": "re-research", "L5": "learned rule",
        "audit": "blind audit", "rubric": "rubric review", "rubric-late": "rubric review", "holdout": "held-out check"}
ACCESS = {"free": ("good", "Yes", "free tier / sandbox"), "trial": ("good", "Yes", "trial or free credits"),
          "local": ("good", "Yes", "open source, no keys"), "paid": ("warn", "No", "paid plan needed"),
          "approval": ("warn", "No", "vendor approval"), "gated": ("crit", "No", "sales / partner only")}
VERDICT = {"build-now": ("good", "Build now"), "build-with-caveats": ("warn", "Caveats"), "needs-outreach": ("crit", "Outreach")}
GROUP = {"free": "self", "trial": "self", "local": "self", "paid": "cond", "approval": "cond", "gated": "closed"}

# ------------------------------------------------------------------ records + exports
data = []
for r in rows:
    d = {k: r[k] for k in ["id", "app", "cat", "what", "auth", "auth_d", "access", "access_d", "api", "breadth", "api_d",
                           "mcp", "mcp_d", "verdict", "blocker", "ev", "conf"]}
    d["self_serve"] = GROUP[r["access"]] == "self"
    d["composio"] = r["app"] in on_comp
    d["sample"] = "audit" if r["id"] in sample["ids"] else ("held-out" if r["id"] in hold["ids"] else "")
    d["changes"] = [{"stage": c["stage"], "field": c["field"], "from": c["from"], "to": c["to"],
                     "check": LOOP.get(c["loop"], c["loop"]), "why": c["why"], "src": (c["src"] or [""])[0]}
                    for c in ch if c["id"] == r["id"]]
    data.append(d)
(DOCS / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
buf = io.StringIO(); w = csv.writer(buf)
w.writerow(["id", "app", "category", "what", "auth", "access", "self_serve", "api", "breadth", "mcp", "verdict",
            "blocker", "on_composio", "ev_auth", "ev_access", "ev_api", "ev_mcp", "confidence"])
for d in data:
    w.writerow([d["id"], d["app"], d["cat"], d["what"], "|".join(d["auth"]), d["access"], d["self_serve"], "|".join(d["api"]),
                d["breadth"], d["mcp"], d["verdict"], d["blocker"], d["composio"], *[d["ev"][k] for k in ("auth", "access", "api", "mcp")], d["conf"]])
(DOCS / "data.csv").write_text(buf.getvalue())
(DOCS / "scores.json").write_text(json.dumps(S, indent=1)); (DOCS / "patterns.json").write_text(json.dumps(P, indent=1))
(DOCS / ".nojekyll").write_text("")

# ------------------------------------------------------------------ numbers used in the copy
n = len(rows); V = P["verdict"]
pct = lambda x: f"{x * 100:.1f}%"
a1, a2 = S["passes"]["pass1"]["accuracy"], S["passes"]["pass2"]["accuracy"]
h1, h2, hf = (S["holdout"][p]["accuracy"] for p in ["pass1", "pass2", "final"])
L = S["loops"]
mcp_draft, mcp_final = P["mcp"]["official_draft"], P["mcp"]["official_final"]
gap = [d for d in data if not d["composio"]]
easy = [d for d in gap if d["verdict"] == "build-now"]
outreach = [d for d in data if d["verdict"] == "needs-outreach"]
not_ready = n - V["build-now"]
blk = sorted(((k, v) for k, v in P["blockers"].items() if k != "Other"), key=lambda x: -x[1])
by = P["by_cat"]
full_cats = [c for c in CATS if by[c]["self_serve"] == 10]
low_cat = min(CATS, key=lambda c: by[c]["self_serve"])
dead1 = sum(1 for o in V1["rows"] for s in o["liveness"].values() if s == "dead")
deadF = sum(1 for o in VF["rows"] for s in o["liveness"].values() if s == "dead")
cites1 = sum(1 for r in p1.values() for u in r["ev"].values() if u)
cites = sum(1 for d in data for u in d["ev"].values() if u)
human_done = sum(1 for h in human if h.get(HV, "").strip())
cite_fixed = len({json.loads(l)["id"] for l in (ROOT / "data/patches_pass2.jsonl").read_text().splitlines()
                  if l.strip() and "ev" in json.loads(l)["fields"]})
claim_fixed = len({c["id"] for c in ch if c["stage"] == "Pass 2"})
l5_mcp = sum(1 for c in ch if c["loop"] == "L5" and c["field"] == "mcp")
reg_found = 8
sha = sample["pass1_sha256"]
blk_apps = {}
for d in data:
    if d["verdict"] != "build-now":
        blk_apps.setdefault(cluster(d["blocker"]), []).append(d["app"])

# ------------------------------------------------------------------ small HTML helpers
def chips(ds, cls=""):
    return "".join(f'<a class="chip {cls}" href="#app-{d["id"]}" data-jump="{d["id"]}">{E(d["app"])}</a>' for d in ds)


def pill(v):
    tone, label = VERDICT[v]
    return f'<span class="pill {tone}">{label}</span>'


def access_html(a):
    tone, yes, label = ACCESS[a]
    return f'<span class="acc {tone}"><b>{yes}</b> {label}</span>'


def host(u):
    return u.split("/")[2].removeprefix("www.") if u.startswith("http") else u


# ------------------------------------------------------------------ charts (pre-rendered SVG; hover text in data-tip)
def stacked_by_cat():
    order = sorted(CATS, key=lambda c: (-by[c]["self_serve"], -by[c]["access"].get("free", 0)))
    groups = [("self", "Self-serve", "var(--good)", "#fff"), ("cond", "Paid plan or vendor approval", "var(--warn)", "#111"),
              ("closed", "Sales or partner only", "var(--crit)", "#fff")]
    W, lab, rh, top = 680, 176, 30, 4
    x0, x1 = lab, W - 6; unit = (x1 - x0) / 10
    out = [f'<svg viewBox="0 0 {W} {top + rh * len(order) + 20}" class="chart" role="img" aria-label="Self-serve versus gated apps per category">']
    for t in range(0, 11, 2):
        x = x0 + t * unit
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{top + rh * len(order)}" class="grid"/>'
                   f'<text x="{x:.1f}" y="{top + rh * len(order) + 14}" class="tick" text-anchor="middle">{t}</text>')
    for i, c in enumerate(order):
        y = top + i * rh + 5; h = rh - 10; x = x0
        out.append(f'<text x="{lab - 10}" y="{y + h / 2 + 4}" class="lab" text-anchor="end">{E(c)}</text>')
        parts = []
        for key, name, col, txt in groups:
            ds = [d for d in data if d["cat"] == c and GROUP[d["access"]] == key]
            if ds:
                parts.append((name, col, txt, ds))
        for j, (name, col, txt, ds) in enumerate(parts):
            wd = len(ds) * unit - (2 if j < len(parts) - 1 else 0)
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{wd:.1f}" height="{h}" rx="3" fill="{col}" class="mark" '
                       f'data-tip="{E(c)} · {name}: {len(ds)}&#10;{E(", ".join(d["app"] for d in ds))}"/>')
            if wd > 14:
                out.append(f'<text x="{x + wd / 2:.1f}" y="{y + h / 2 + 4}" class="seg" fill="{txt}" text-anchor="middle">{len(ds)}</text>')
            x += len(ds) * unit
    out.append("</svg>")
    legend = "".join(f'<span><i style="background:{col}"></i>{name}</span>' for _, name, col, _ in groups)
    return f'<div class="legend">{legend}</div>' + "".join(out)


def hbar(items, title, tip):
    W, lab, rh = 520, 176, 26
    mx = max(v for _, v in items); x0, x1 = lab, W - 34
    out = [f'<svg viewBox="0 0 {W} {rh * len(items) + 6}" class="chart" role="img" aria-label="{E(title)}">']
    for i, (k, v) in enumerate(items):
        y = i * rh + 6; h = rh - 10; wd = (x1 - x0) * v / mx
        out.append(f'<text x="{lab - 10}" y="{y + h / 2 + 4}" class="lab" text-anchor="end">{E(k)}</text>'
                   f'<rect x="{x0}" y="{y}" width="{max(wd, 2):.1f}" height="{h}" rx="3" class="mark bar" data-tip="{E(tip(k, v))}"/>'
                   f'<text x="{x0 + wd + 6:.1f}" y="{y + h / 2 + 4}" class="val">{v}</text>')
    out.append("</svg>")
    return "".join(out)


def accuracy_chart():
    rs = [("Audit sample, all fields", a1, a2, None, True)]
    rs += [(f, S["passes"]["pass1"]["per_field"][f], S["passes"]["pass2"]["per_field"][f], None, False)
           for f in ["auth", "access", "api", "mcp", "verdict", "evidence"]]
    rs += [("Held-out, all fields", h1, h2, hf, True)]
    W, lab, rh, top = 640, 176, 27, 8
    lo, hi = 0.5, 1.0
    X = lambda v: lab + (W - lab - 54) * (v - lo) / (hi - lo)
    H = top + rh * len(rs)
    out = [f'<svg viewBox="0 0 {W} {H + 20}" class="chart" role="img" aria-label="Accuracy by field and pass">']
    for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 4}" y2="{H}" class="grid"/>'
                   f'<text x="{X(t):.1f}" y="{H + 15}" class="tick" text-anchor="middle">{int(t * 100)}%</text>')
    for i, (name, a, b, c, strong) in enumerate(rs):
        y = top + i * rh + rh / 2
        label = name if strong else f"· {name}"
        out.append(f'<text x="{lab - 10}" y="{y + 4}" class="lab{" strong" if strong else ""}" text-anchor="end">{E(label)}</text>')
        pts = [v for v in (a, b, c) if v is not None]
        out.append(f'<line x1="{X(min(pts)):.1f}" x2="{X(max(pts)):.1f}" y1="{y}" y2="{y}" class="conn"/>')
        out.append(f'<circle cx="{X(a):.1f}" cy="{y}" r="5" class="mark p1" data-tip="{E(name)} · first draft: {a:.1%}"/>')
        out.append(f'<rect x="{X(b) - 4.5:.1f}" y="{y - 4.5}" width="9" height="9" rx="1.5" class="mark p2" data-tip="{E(name)} · after automated checks: {b:.1%}"/>')
        if c is not None:
            out.append(f'<path d="M{X(c):.1f} {y - 6.5} L{X(c) + 6.5:.1f} {y} L{X(c):.1f} {y + 6.5} L{X(c) - 6.5:.1f} {y} Z" class="mark pf" data-tip="{E(name)} · final: {c:.1%}"/>')
        if strong:
            out.append(f'<text x="{X(max(pts)) + 12:.1f}" y="{y + 4}" class="val">{max(pts):.1%}</text>')
    out.append("</svg>")
    return "".join(out)


AUTH_LABEL = {"OAuth2": "OAuth 2.0", "API key": "API key", "Token": "Personal / bot token", "Basic": "HTTP Basic",
              "Signature": "Signed requests", "OAuth1": "OAuth 1.0a"}
auth_svg = hbar([(AUTH_LABEL[k], v) for k, v in sorted(P["auth_any"].items(), key=lambda x: -x[1]) if k != "None"],
                "Apps supporting each login method", lambda k, v: f"{k}: {v} of 100 apps")
blk_svg = hbar(blk, "Main blocker for apps not ready today", lambda k, v: f"{k}: {v} apps\n" + ", ".join(blk_apps.get(k, [])))

# all 100 at a glance: category rows x verdict columns, app chips
map_rows = []
for c in CATS:
    cells = []
    for v in VERDICT:
        ds = [d for d in data if d["cat"] == c and d["verdict"] == v]
        cells.append(f'<td data-label="{VERDICT[v][1]}">{chips(ds, VERDICT[v][0])}</td>')
    map_rows.append(f'<tr><th scope="row">{E(c)}</th>{"".join(cells)}</tr>')
app_map = ('<table class="map"><thead><tr><th></th>' +
           "".join(f'<th><span class="pill {t}">{l}</span> <span class="n">{V[k]}</span></th>' for k, (t, l) in VERDICT.items()) +
           f'</tr></thead><tbody>{"".join(map_rows)}</tbody></table>')

# ------------------------------------------------------------------ the findings table (pre-rendered)
def change_line(c):
    fr = c["from"] if isinstance(c["from"], str) else ", ".join(c["from"] or [])
    to = c["to"] if isinstance(c["to"], str) else ", ".join(c["to"] or [])
    src = f' <a href="{E(c["src"])}" target="_blank" rel="noopener">source</a>' if c["src"] else ""
    return f'<li><b>{E(c["field"])}</b>: {E(fr)} → {E(to)} <span class="muted">({E(c["check"])}, {E(c["stage"])})</span>. {E(c["why"])}{src}</li>'


trs = []
for d in data:
    ev = "".join(f'<a href="{E(d["ev"][k])}" target="_blank" rel="noopener" title="{E(host(d["ev"][k]))}">{k}</a>'
                 for k in ("auth", "access", "api", "mcp") if d["ev"][k])
    mcp = {"official": '<span class="mcp yes">official MCP</span>', "community": '<span class="mcp">community MCP only</span>',
           "none": '<span class="mcp">no MCP</span>'}[d["mcp"]]
    q = " ".join([d["app"], d["cat"], d["what"], d["blocker"], " ".join(d["auth"]), d["access"], d["mcp"]]).lower()
    oauth = "yes" if "OAuth2" in d["auth"] else "no"
    trs.append(
        f'<tr class="row" id="app-{d["id"]}" tabindex="0" aria-expanded="false" data-verdict="{d["verdict"]}" data-cat="{E(d["cat"])}" '
        f'data-group="{GROUP[d["access"]]}" data-mcp="{d["mcp"]}" data-oauth="{oauth}" data-comp="{"yes" if d["composio"] else "no"}">'
        f'<td data-label="App" class="app"><b>{E(d["app"])}</b><span>{E(d["what"])}</span></td>'
        f'<td data-label="Category">{E(d["cat"])}</td>'
        f'<td data-label="Login">{" ".join(f"<span class=tag>{E(a)}</span>" for a in d["auth"])}</td>'
        f'<td data-label="Self-serve?">{access_html(d["access"])}</td>'
        f'<td data-label="API · MCP"><span class="tag">{E(" + ".join(d["api"]))}</span> <span class="muted">{E(d["breadth"])}</span><br>{mcp}</td>'
        f'<td data-label="Verdict">{pill(d["verdict"])}</td>'
        f'<td data-label="Main blocker">{E(d["blocker"])}</td>'
        f'<td data-label="On Composio">{"yes" if d["composio"] else "<b>no</b>"}</td>'
        f'<td data-label="Sources" class="ev">{ev}</td></tr>'
        f'<tr class="detail" hidden><td colspan="9"><dl class="dl">'
        f'<div><dt>Login</dt><dd>{E(d["auth_d"])}</dd></div><div><dt>Getting access</dt><dd>{E(d["access_d"])}</dd></div>'
        f'<div><dt>API ({E(d["breadth"])})</dt><dd>{E(d["api_d"])}</dd></div><div><dt>MCP</dt><dd>{E(d["mcp_d"])}</dd></div>'
        f'<div><dt>Sources</dt><dd>{"<br>".join(f"{k}: <a href={chr(34)}{E(d[chr(101) + chr(118)][k])}{chr(34)} target=_blank rel=noopener>{E(host(d[chr(101) + chr(118)][k]))}</a>" for k in ("auth", "access", "api", "mcp") if d["ev"][k])}</dd></div>'
        f'<div><dt>Confidence</dt><dd>{d["conf"]}{" · part of the " + d["sample"] + " sample" if d["sample"] else ""}</dd></div>'
        f'<div class="wide"><dt>What the checks changed</dt><dd>{"<ul>" + "".join(change_line(c) for c in d["changes"]) + "</ul>" if d["changes"] else "Nothing. The first draft passed every check."}</dd></div>'
        f'</dl></td></tr>')
apps_table = ('<table class="apps" id="apps"><thead><tr><th>App</th><th>Category</th><th>Login</th><th>Self-serve?</th>'
              '<th>API · MCP</th><th>Verdict</th><th>Main blocker</th><th>On Composio</th><th>Sources</th></tr></thead>'
              f'<tbody>{"".join(trs)}</tbody></table>')

# ------------------------------------------------------------------ verification tables
MISS_NOTE = {
    (3, "mcp"): ("community MCP only", "official MCP (mcp.pipedrive.ai, Jun 2026)"),
    (9, "verdict"): ("caveats", "build now: a no-card trial counts as self-serve"),
    (14, "mcp"): ("community MCP only", "official MCP in beta"),
    (18, "access"): ("free", "trial: the free plan has no API"),
    (18, "mcp"): ("community MCP only", "official MCP (mcp.helpscout.net)"),
    (18, "evidence"): ("pricing page", "page does not support 'API on free plan'"),
    (29, "access"): ("paid", "trial: developer accounts get one"),
    (29, "evidence"): ("partner OAuth tutorial", "does not state the access terms"),
    (30, "evidence"): ("dashboard guide", "never mentions the free signup credit"),
    (35, "mcp"): ("community MCP only", "official Intuit Mailchimp connector"),
    (78, "mcp"): ("community MCP only", "official ChatGPT app by Coda's owner"),
    (86, "access"): ("free", "approval: production keys need an approved App Assessment"),
    (86, "verdict"): ("build now", "caveats (follows from the access miss)"),
    (86, "evidence"): ("go-live page", "contradicts 'free'"),
    (20, "evidence"): ("REST reference", "does not say 'customers only'"),
    (24, "evidence"): ("docs portal", "client-rendered page no tool could read"),
    (34, "access"): ("trial", "free 6-month developer sandboxes"),
    (34, "evidence"): ("empty single-page docs", "nothing readable at the cited URL"),
    (46, "evidence"): ("partner OAuth page", "does not state the plan requirement"),
}
fixed_final = {(m["id"], m["field"]) for m in S["misses"]["final"]}
p2_rows = "".join(
    f'<tr><td>{E(m["app"])}</td><td><code>{m["field"]}</code></td><td>{E(MISS_NOTE.get((m["id"], m["field"]), ("", ""))[0])}</td>'
    f'<td>{E(MISS_NOTE.get((m["id"], m["field"]), ("", ""))[1])}</td><td>{"<span class=ok>fixed by audit</span>" if (m["id"], m["field"]) not in fixed_final else "open"}</td></tr>'
    for m in S["misses"]["pass2"])
final_now = {(d["id"]): d for d in data}
ho_rows = "".join(
    f'<tr><td>{E(m["app"])}</td><td><code>{m["field"]}</code></td><td>{E(MISS_NOTE.get((m["id"], m["field"]), ("", ""))[0])}</td>'
    f'<td>{E(MISS_NOTE.get((m["id"], m["field"]), ("", ""))[1])}</td>'
    f'<td>{"<span class=ok>fixed after measuring</span>" if (m["id"], m["field"]) == (34, "access") else "still open"}</td></tr>'
    for m in S["holdout"]["final"]["misses"])
FIELDS = ["auth", "access", "api", "mcp", "verdict", "evidence"]
miss = {p: {(m["id"], m["field"]) for m in S["misses"][p]} for p in ["pass1", "pass2", "final"]}
grid = "".join(
    f'<tr><th scope="row">{E(final_now[i]["app"])}</th>' + "".join(
        "<td>" + "".join(f'<span class="{"x" if (i, f) in miss[p] else "ok"}" title="{lbl}">{"✗" if (i, f) in miss[p] else "✓"}</span>'
                         for p, lbl in [("pass1", "first draft"), ("pass2", "after checks"), ("final", "final")]) + "</td>"
        for f in FIELDS) + "</tr>" for i in sorted(int(x) for x in A["truth"]))
grid_tbl = f'<table class="hm"><thead><tr><th>App</th>{"".join(f"<th>{f}</th>" for f in FIELDS)}</tr></thead><tbody>{grid}</tbody></table>'
human_rows = "".join(
    f'<tr><td>{E(h["app"])}</td><td><code>{E(h["field"])}</code> = {E(h["pipeline_final_value"])}</td><td>{E(h["why_check"])}</td>'
    f'<td><a href="{E(h["source_url"])}" target="_blank" rel="noopener">source</a></td>'
    f'<td>{E(h[HV]) if h.get(HV, "").strip() else "<span class=muted>pending</span>"}</td></tr>' for h in human)

# ------------------------------------------------------------------ CSS / JS (plain strings, no templating)
CSS = """
:root{--bg:#f5f7f9;--surface:#fff;--sunk:#eef1f4;--ink:#0f1720;--ink2:#455060;--ink3:#687282;--rule:#dde2e8;
--accent:#2a78d6;--accent-ink:#1c5cab;--accent-soft:#e7f0fc;--good:#0ca30c;--warn:#e09a00;--crit:#d03b3b;
--good-soft:#e3f3e3;--warn-soft:#fbf1d9;--crit-soft:#f9e3e3;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;
--display:"Space Grotesk",ui-sans-serif,system-ui,sans-serif;--body:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1116;--surface:#161a21;--sunk:#1d222b;--ink:#e8ebef;--ink2:#b3bbc6;--ink3:#8b94a1;--rule:#2a313c;
--accent:#3987e5;--accent-ink:#86b6ef;--accent-soft:#17263a;--good:#0ca30c;--warn:#fab219;--crit:#e66767;--good-soft:#14291a;--warn-soft:#2d2511;--crit-soft:#321b1c;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e1116;--surface:#161a21;--sunk:#1d222b;--ink:#e8ebef;--ink2:#b3bbc6;--ink3:#8b94a1;--rule:#2a313c;
--accent:#3987e5;--accent-ink:#86b6ef;--accent-soft:#17263a;--good:#0ca30c;--warn:#fab219;--crit:#e66767;--good-soft:#14291a;--warn-soft:#2d2511;--crit-soft:#321b1c;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 56px}
.wrap{max-width:1100px;margin:0 auto}
h1,h2,h3{font-family:var(--display);letter-spacing:-.01em;text-wrap:balance;margin:0}
h2{font-size:1.6rem;font-weight:700}h3{font-size:1.02rem;font-weight:600}
p{margin:0;max-width:72ch}a{color:var(--accent-ink)}code{font:.85em var(--mono)}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,tr:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.eyebrow{font:600 .72rem/1 var(--body);letter-spacing:.09em;text-transform:uppercase;color:var(--ink3)}
.muted{color:var(--ink3)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--bg)}
nav.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);border-bottom:1px solid var(--rule);margin:0 calc(-1*max(16px,env(safe-area-inset-left,0px)));padding:10px max(16px,env(safe-area-inset-left,0px))}
nav.top .wrap{display:flex;gap:16px;align-items:center;overflow-x:auto;white-space:nowrap;font-size:.86rem}
nav.top b{font-family:var(--display);margin-right:6px}nav.top a{color:var(--ink2);text-decoration:none}nav.top a:hover{color:var(--ink)}
.hero{padding-block:40px 8px;display:grid;gap:16px}
.hero h1{font-size:clamp(1.8rem,4.4vw,2.9rem);line-height:1.08;font-weight:700;max-width:24ch}
.hero .lede{font-size:1.06rem;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:14px 16px;display:grid;gap:4px;align-content:start;border-top:4px solid var(--rule)}
.tile.good{border-top-color:var(--good)}.tile.warn{border-top-color:var(--warn)}.tile.crit{border-top-color:var(--crit)}.tile.blue{border-top-color:var(--accent)}
.tile .n{font:700 2.1rem/1 var(--display);font-variant-numeric:tabular-nums}.tile .t{font-weight:600}.tile p{font-size:.84rem;color:var(--ink2)}
.links{display:flex;flex-wrap:wrap;gap:8px}
.btn{display:inline-flex;align-items:center;gap:6px;font-size:.86rem;font-weight:600;padding:7px 12px;border-radius:8px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);text-decoration:none}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
section{padding-block:40px 4px;display:grid;gap:18px;border-top:1px solid var(--rule);margin-top:32px}
section>header{display:grid;gap:6px}
.bottom{font-size:1.05rem;color:var(--ink);background:var(--accent-soft);border-radius:8px;padding:10px 14px;max-width:none}
.brief{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--rule);border-radius:10px;overflow:hidden;font-size:.92rem}
.brief th,.brief td{padding:11px 14px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
.brief thead th{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);background:var(--sunk)}
.brief td:first-child{font-weight:600;white-space:nowrap}.brief tr:last-child td{border-bottom:0}
.brief .check{color:var(--good);font-weight:700;margin-right:6px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:16px 18px;display:grid;gap:8px;align-content:start;min-width:0}
.card .big{font:700 2rem/1 var(--display);color:var(--accent-ink);font-variant-numeric:tabular-nums}
.card p{font-size:.9rem;color:var(--ink2)}.card.span2{grid-column:span 2}.card.span3{grid-column:1/-1}
.chip{display:inline-block;font-size:.79rem;padding:2px 9px;border-radius:999px;background:var(--sunk);border:1px solid var(--rule);color:var(--ink);text-decoration:none;margin:2px 3px 2px 0;white-space:nowrap}
.chip:hover{border-color:var(--ink3)}.chip.good{background:var(--good-soft)}.chip.warn{background:var(--warn-soft)}.chip.crit{background:var(--crit-soft)}
.figs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
figure{margin:0;background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:14px 16px 12px;display:grid;gap:8px;min-width:0}
figure.wide{grid-column:1/-1}figcaption{display:grid;gap:2px}figcaption b{font-family:var(--display);font-weight:600}figcaption span{font-size:.82rem;color:var(--ink3)}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart .grid{stroke:var(--rule)}.chart .tick{fill:var(--ink3);font:11px var(--body)}
.chart .lab{fill:var(--ink2);font:12px var(--body)}.chart .lab.strong{fill:var(--ink);font-weight:600}
.chart .val{fill:var(--ink);font:600 12px var(--body)}.chart .seg{font:600 11px var(--body);pointer-events:none}
.chart .bar{fill:var(--s1)}.chart .mark:hover{opacity:.8}.chart .conn{stroke:var(--ink3);stroke-width:1.5;opacity:.45}
.chart .p1{fill:var(--surface);stroke:var(--s2);stroke-width:2.2}.chart .p2{fill:var(--s3);stroke:var(--surface);stroke-width:1.5}.chart .pf{fill:var(--s1);stroke:var(--surface);stroke-width:1.5}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:.8rem;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}.legend .sym{font-weight:700;margin-right:5px}
.map{width:100%;border-collapse:collapse;font-size:.86rem}
.map th,.map td{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
.map thead th{white-space:nowrap}.map thead .n{font:700 1rem var(--display);margin-left:4px}
.map th[scope=row]{font-weight:600;white-space:nowrap;color:var(--ink2);width:180px}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:.76rem;font-weight:600;padding:2px 9px;border-radius:999px;white-space:nowrap;color:var(--ink)}
.pill::before{content:"";width:8px;height:8px;border-radius:50%}
.pill.good{background:var(--good-soft)}.pill.good::before{background:var(--good)}
.pill.warn{background:var(--warn-soft)}.pill.warn::before{background:var(--warn);border-radius:2px}
.pill.crit{background:var(--crit-soft)}.pill.crit::before{background:var(--crit);border-radius:0;clip-path:polygon(50% 0,100% 100%,0 100%)}
.acc{font-size:.8rem;white-space:nowrap}.acc b{display:inline-block;min-width:2.2em;padding:0 6px;border-radius:4px;margin-right:4px;text-align:center;font-size:.74rem}
.acc.good b{background:var(--good-soft);color:var(--ink)}.acc.warn b{background:var(--warn-soft)}.acc.crit b{background:var(--crit-soft)}
.tag{font:.72rem var(--mono);padding:1px 6px;border-radius:4px;background:var(--sunk);color:var(--ink2);white-space:nowrap;display:inline-block;margin:1px 2px 1px 0}
.mcp{font-size:.76rem;color:var(--ink3)}.mcp.yes{color:var(--ink);font-weight:600}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filters input[type=search],.filters select{font:inherit;font-size:.88rem;padding:7px 10px;border:1px solid var(--rule);border-radius:8px;background:var(--surface);color:var(--ink)}
.filters input[type=search]{flex:1 1 220px;min-width:0}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:8px;overflow:hidden;background:var(--surface)}
.seg button,.tog{font:inherit;font-size:.84rem;padding:6px 11px;border:0;background:transparent;color:var(--ink2);cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}
.seg button[aria-pressed=true]{background:var(--ink);color:var(--bg)}
.tog{border:1px solid var(--rule);border-radius:8px;background:var(--surface)}.tog[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.count{font-size:.84rem;color:var(--ink3)}
.tablebox{background:var(--surface);border:1px solid var(--rule);border-radius:10px;overflow:auto;max-height:78vh}
table.apps{width:100%;border-collapse:collapse;font-size:.86rem}
table.apps th{position:sticky;top:0;z-index:1;background:var(--surface);text-align:left;font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;color:var(--ink3);padding:9px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}
table.apps td{padding:10px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
table.apps tr.row{cursor:pointer}table.apps tr.row:hover td{background:var(--sunk)}
table.apps tr.row[aria-expanded=true] td{background:var(--accent-soft)}
table.apps td.app b{font-weight:600}table.apps td.app span{display:block;color:var(--ink3);font-size:.78rem;max-width:30ch}
table.apps tr.detail>td{background:var(--sunk);padding:14px 16px}
table.apps tr.flash td{animation:flash 1.6s ease}
@keyframes flash{0%,40%{background:var(--warn-soft)}}
.ev a{font-size:.78rem;margin-right:7px;white-space:nowrap}
.dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin:0;font-size:.86rem}
.dl div{min-width:0}.dl .wide{grid-column:1/-1}.dl dt{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3)}
.dl dd{margin:2px 0 0;overflow-wrap:anywhere}.dl ul{margin:4px 0 0;padding-left:1.1em;display:grid;gap:4px}
.flow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.step{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:grid;gap:4px;align-content:start}
.step .k{font:600 .74rem var(--mono);color:var(--accent-ink)}.step p{font-size:.84rem;color:var(--ink2)}
.step .m{font-size:.82rem;font-weight:600;font-variant-numeric:tabular-nums}.step.human{border-style:dashed}
ul.plain{margin:0;padding-left:1.1em;display:grid;gap:7px;font-size:.9rem}ul.plain li{max-width:78ch}
ol.steps{margin:0;padding-left:1.3em;display:grid;gap:6px;font-size:.92rem}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.stat{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:grid;gap:2px}
.stat b{font:700 1.45rem/1.1 var(--display);font-variant-numeric:tabular-nums}.stat span{font-size:.8rem;color:var(--ink2)}
table.small{width:100%;border-collapse:collapse;font-size:.84rem}
table.small th,table.small td{padding:7px 9px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
table.small th{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3)}
.ok{color:var(--good);font-weight:600}
.hm{border-collapse:collapse;width:100%;font-size:.84rem}
.hm th,.hm td{padding:5px 8px;border-bottom:1px solid var(--rule);text-align:center;white-space:nowrap}.hm th[scope=row]{text-align:left;font-weight:500}
.hm thead th{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--ink3)}
.hm span{font-weight:700;margin:0 1px}.hm span.ok{color:var(--good)}.hm span.x{color:var(--crit)}
details{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 16px}
details summary{cursor:pointer;font-weight:600}details[open] summary{margin-bottom:10px}
.scroll{overflow-x:auto;min-width:0}
pre{background:var(--sunk);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;overflow-x:auto;font:12.5px/1.55 var(--mono);margin:0}
#tip{position:fixed;z-index:20;pointer-events:none;background:var(--ink);color:var(--bg);font-size:.78rem;line-height:1.4;padding:7px 10px;border-radius:6px;max-width:300px;white-space:pre-line}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--rule);font-size:.84rem;color:var(--ink3);display:flex;flex-wrap:wrap;gap:6px 16px}
@media (max-width:860px){.tiles,.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.cards,.figs,.flow,.dl{grid-template-columns:minmax(0,1fr)}
.card.span2,.card.span3,figure.wide{grid-column:auto}.brief td:first-child{white-space:normal}}
@media (max-width:700px){
.brief thead{display:none}.brief tr{display:grid;gap:4px;padding:10px 14px;border-bottom:1px solid var(--rule)}.brief tr:last-child{border-bottom:0}
.brief td{display:block;border:0;padding:0}.brief td:first-child{white-space:normal}
.map thead{display:none}.map tr{display:block;padding:8px 0;border-bottom:1px solid var(--rule)}.map th[scope=row]{display:block;border:0;padding:0 0 4px;width:auto}
.map td{display:block;border:0;padding:2px 0}.map td::before{content:attr(data-label) ": ";font-size:.74rem;color:var(--ink3);font-weight:600}
table.apps thead{display:none}table.apps tr.row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:6px 12px;padding:12px;border-bottom:1px solid var(--rule)}
table.apps tr.row td{display:block;border:0;padding:0;min-width:0}table.apps td.app{grid-column:1/-1}
table.apps tr.row td:not(.app)::before{content:attr(data-label);display:block;font-size:.68rem;letter-spacing:.05em;text-transform:uppercase;color:var(--ink3)}
table.apps tr.detail{display:block}table.apps tr.detail[hidden]{display:none}table.apps tr.detail>td{display:block}.tablebox{max-height:none}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation:none!important;transition:none!important}}
"""

JS = r"""
(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const rows = $$('#apps tr.row');
  rows.forEach(r => { r.dataset.q = (r.textContent + ' ' + r.nextElementSibling.textContent).toLowerCase(); });
  const state = { verdict: '', toggles: new Set(), cat: '', q: '' };
  const TOG = { gap: r => r.dataset.comp === 'no', mcp: r => r.dataset.mcp === 'official', nooauth: r => r.dataset.oauth === 'no',
                gated: r => r.dataset.group !== 'self' };
  function apply() {
    let shown = 0;
    for (const r of rows) {
      const ok = (!state.verdict || r.dataset.verdict === state.verdict) && (!state.cat || r.dataset.cat === state.cat) &&
        [...state.toggles].every(t => TOG[t](r)) && (!state.q || r.dataset.q.includes(state.q));
      r.hidden = !ok; const det = r.nextElementSibling;
      if (!ok) { det.hidden = true; r.setAttribute('aria-expanded', 'false'); }
      shown += ok;
    }
    $('#count').textContent = `${shown} of ${rows.length} apps`;
  }
  $$('.seg button').forEach(b => b.addEventListener('click', () => {
    $$('.seg button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    state.verdict = b.dataset.v; apply();
  }));
  $$('.tog').forEach(b => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true'; b.setAttribute('aria-pressed', String(on));
    on ? state.toggles.add(b.dataset.t) : state.toggles.delete(b.dataset.t); apply();
  }));
  $('#fcat').addEventListener('input', e => { state.cat = e.target.value; apply(); });
  $('#q').addEventListener('input', e => { state.q = e.target.value.trim().toLowerCase(); apply(); });
  const toggleRow = (r, open) => {
    const det = r.nextElementSibling, o = open ?? det.hidden;
    det.hidden = !o; r.setAttribute('aria-expanded', String(o));
  };
  $('#apps tbody').addEventListener('click', e => {
    if (e.target.closest('a')) return;
    const r = e.target.closest('tr.row'); if (r) toggleRow(r);
  });
  $('#apps tbody').addEventListener('keydown', e => {
    const r = e.target.closest('tr.row');
    if (r && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleRow(r); }
  });
  // jump from a chip anywhere on the page to the app's row, opened
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-jump]'); if (!a) return;
    e.preventDefault();
    state.verdict = ''; state.cat = ''; state.q = ''; state.toggles.clear();
    $$('.seg button').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.v === '')));
    $$('.tog').forEach(x => x.setAttribute('aria-pressed', 'false')); $('#fcat').value = ''; $('#q').value = '';
    apply();
    const r = document.getElementById('app-' + a.dataset.jump);
    toggleRow(r, true); r.scrollIntoView({ block: 'center' }); r.classList.add('flash'); r.focus({ preventScroll: true });
    setTimeout(() => r.classList.remove('flash'), 1700);
  });
  apply();
  const tip = $('#tip');
  document.addEventListener('mousemove', e => {
    const t = e.target.closest && e.target.closest('[data-tip]');
    if (!t) { tip.hidden = true; return; }
    tip.textContent = t.getAttribute('data-tip'); tip.hidden = false;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
    tip.style.top = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8) + 'px';
  });
})();
"""

# ------------------------------------------------------------------ page
access_counts = P["access"]
page = f"""<title>Toolkit Readiness Audit</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="100 apps researched by an AI agent for agent-toolkit readiness: login method, self-serve access, API, MCP, verdict and blocker, each with a cited source and measured accuracy.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&display=swap">
<style>{CSS}</style>
<nav class="top" aria-label="Sections"><div class="wrap"><b>Toolkit Readiness Audit</b>
<a href="#brief">The brief</a><a href="#patterns">Patterns</a><a href="#apps-section">All 100 apps</a><a href="#agent">The agent</a><a href="#verify">Verification</a><a href="#run">Run it</a></div></nav>
<div class="wrap">

<header class="hero">
  <span class="eyebrow">Take-home case study · 100 apps · November 2026</span>
  <h1>{V["build-now"]} of 100 apps can become agent toolkits today.</h1>
  <p class="lede">An AI research agent checked how each app handles login, how a developer gets API access, what its API covers and whether it has an MCP server, and linked the vendor page behind every answer. Automated checks, a blind audit and a held-out test measured how accurate it is.</p>
  <div class="tiles">
    <div class="tile good"><span class="n">{V["build-now"]}</span><span class="t">Build now</span><p>Public docs, self-serve keys, standard login.</p></div>
    <div class="tile warn"><span class="n">{V["build-with-caveats"]}</span><span class="t">Build with caveats</span><p>Paid tier to test, vendor review, self-hosted stores, rate limits.</p></div>
    <div class="tile crit"><span class="n">{V["needs-outreach"]}</span><span class="t">Need outreach</span><p>Customer-only accounts, partner programs or sales.</p></div>
    <div class="tile blue"><span class="n">{hf * 100:.1f}%</span><span class="t">Accurate</span><p>On 10 apps the checks never saw (first draft: {h1 * 100:.1f}%).</p></div>
  </div>
  <div class="links"><a class="btn primary" href="#apps-section">See all 100 apps</a><a class="btn" href="{REPO}" target="_blank" rel="noopener">Code on GitHub</a>
    <a class="btn" href="{PAGES}data.csv" target="_blank" rel="noopener">Download CSV</a><a class="btn" href="{PAGES}data.json" target="_blank" rel="noopener">JSON for agents</a></div>
</header>

<section id="brief">
  <header><span class="eyebrow">For reviewers</span><h2>What the brief asked, and where it is</h2></header>
  <div class="scroll"><table class="brief"><thead><tr><th>The brief asked for</th><th>Answer in one line</th><th>Where</th></tr></thead><tbody>
    <tr><td><span class="check">✓</span>Patterns, up top</td><td>OAuth 2.0 is the default ({P["oauth_offered"]} apps). {P["self_serve"]} apps are self-serve. The top blocker is waiting on a vendor review. {mcp_final} apps already ship an official MCP server.</td><td><a href="#patterns">Patterns</a></td></tr>
    <tr><td><span class="check">✓</span>Findings for all 100</td><td>Category, one-liner, login method, self-serve vs gated, API and breadth, MCP, verdict, main blocker and a source link for each answer.</td><td><a href="#apps-section">All 100 apps</a></td></tr>
    <tr><td><span class="check">✓</span>Done with an agent</td><td>A Claude Opus 5.5 research agent plus automated check loops. A person made five kinds of calls the agent couldn't.</td><td><a href="#agent">The agent</a></td></tr>
    <tr><td><span class="check">✓</span>Proof you can run</td><td>Public code, a one-command pipeline, a CI run on a clean machine, a Claude Code command and a headless agent with Composio tools.</td><td><a href="#run">Run it</a></td></tr>
    <tr><td><span class="check">✓</span>Verified accuracy</td><td>{pct(h1)} → {pct(hf)} on held-out apps. The automated loops alone took the audit sample from {pct(a1)} to {pct(a2)}. Every miss is listed.</td><td><a href="#verify">Verification</a></td></tr>
  </tbody></table></div>
</section>

<section id="patterns">
  <header><span class="eyebrow">The headline</span><h2>Patterns across the 100 apps</h2></header>
  <p class="bottom"><b>Bottom line:</b> most apps are easy to connect. The hard ones are concentrated in finance, ads and ecommerce, and what blocks them is usually a vendor approval or a customer-only account, not price.</p>
  <div class="cards">
    <div class="card"><span class="big">{P["oauth_offered"]}<small style="font-size:1rem;color:var(--ink3)">/100</small></span><h3>OAuth 2.0 is the default login</h3>
      <p>{P["auth_any"]["API key"]} apps also take API keys and {P["auth_any"]["Token"]} take personal or bot tokens. {P["key_only"]} apps have no OAuth at all, so each user pastes a key instead of clicking Connect.</p></div>
    <div class="card"><span class="big">{P["self_serve"]}<small style="font-size:1rem;color:var(--ink3)">/100</small></span><h3>Most apps are self-serve</h3>
      <p>{" and ".join(full_cats)}: 10 of 10. {low_cat}: {by[low_cat]["self_serve"]} of 10. A developer gets keys alone from a free tier ({access_counts["free"]}), a trial ({access_counts["trial"]}) or open source ({access_counts["local"]}).</p></div>
    <div class="card"><span class="big">{blk[0][1]}<small style="font-size:1rem;color:var(--ink3)"> of {not_ready}</small></span><h3>Top blocker: waiting on a vendor review</h3>
      <p>Developer tokens, app review and production-key approval (Google Ads, Meta, QuickBooks, Amazon). Next: customer or partner accounts ({P["blockers"].get("Customer or partner account", 0)}) and paid plans just to test ({P["blockers"].get("Paid plan to test", 0)}).</p></div>
    <div class="card"><span class="big">{mcp_final}<small style="font-size:1rem;color:var(--ink3)">/100</small></span><h3>Official MCP servers are now normal</h3>
      <p>Many launched in 2026. The agent's first draft, written from memory, guessed {mcp_draft}. So a toolkit's value is managed auth and well-built tools.</p></div>
    <div class="card span2"><span class="big">{len(easy)}</span><h3>Easy wins Composio doesn't cover yet</h3>
      <p>Buildable today, and no Composio toolkit page found:</p><div>{chips(easy, "good")}</div>
      <p style="margin-top:6px"><b>Need outreach first ({len(outreach)}):</b></p><div>{chips(outreach, "crit")}</div></div>
  </div>
  <figure class="wide"><figcaption><b>All 100 apps at a glance</b><span>Click any app to open its row with sources and the checks' history. {P["composio"]["on_composio"]} of the 100 already have a Composio toolkit.</span></figcaption>
    <div class="scroll">{app_map}</div></figure>
  <div class="figs">
    <figure class="wide"><figcaption><b>Self-serve vs gated, by category</b><span>Apps per category (10 each). Hover a segment for the names.</span></figcaption>{stacked_by_cat()}</figure>
    <figure><figcaption><b>Login methods supported</b><span>An app can support several.</span></figcaption>{auth_svg}</figure>
    <figure><figcaption><b>Main blocker, for the {not_ready} apps not ready today</b><span>Hover a bar for the apps.</span></figcaption>{blk_svg}</figure>
  </div>
</section>

<section id="apps-section">
  <header><span class="eyebrow">Findings</span><h2>All 100 apps</h2></header>
  <p class="bottom"><b>How to read it:</b> one row per app. Click a row to see the details, the source for each answer and anything the checks changed.</p>
  <div class="filters">
    <div class="seg" role="group" aria-label="Verdict"><button data-v="" aria-pressed="true">All</button><button data-v="build-now" aria-pressed="false">Build now</button><button data-v="build-with-caveats" aria-pressed="false">Caveats</button><button data-v="needs-outreach" aria-pressed="false">Outreach</button></div>
    <button class="tog" data-t="gated" aria-pressed="false">Not self-serve</button><button class="tog" data-t="nooauth" aria-pressed="false">No OAuth</button>
    <button class="tog" data-t="mcp" aria-pressed="false">Official MCP</button><button class="tog" data-t="gap" aria-pressed="false">Not on Composio</button>
    <select id="fcat" aria-label="Category"><option value="">All categories</option>{"".join(f"<option>{E(c)}</option>" for c in CATS)}</select>
    <input type="search" id="q" placeholder="Search apps, blockers…" aria-label="Search">
    <span class="count" id="count">{n} of {n} apps</span>
  </div>
  <div class="tablebox">{apps_table}</div>
  <p class="count">Self-serve? <b>Yes</b> = a developer can get keys alone (free tier, trial, or open source). <b>No</b> = paid plan, vendor approval, or sales/partner only. “On Composio” = a toolkit page exists at composio.dev/toolkits.</p>
</section>

<section id="agent">
  <header><span class="eyebrow">Process</span><h2>The agent and its checks</h2></header>
  <p class="bottom"><b>Bottom line:</b> write a fast first draft, check it cheaply, and spend real research only where a check fails. Every change is logged with the check that caused it, a source and a quote.</p>
  <div class="flow">
    <div class="step"><span class="k">1 · first draft</span><h3>Agent writes all 100</h3><p>From what it already knows, with a proposed source for every claim. Frozen and hashed before any check.</p><span class="m">{n} apps · {cites1} sources</span></div>
    <div class="step"><span class="k">2 · link check</span><h3>Open every source</h3><p>Plain HTTP first, then a real headless Chrome for pages built in JavaScript or behind bot walls.</p><span class="m">Dead links: {dead1} → {deadF}</span></div>
    <div class="step"><span class="k">3 · claim check</span><h3>Does the page say it?</h3><p>Looks for each claimed login method, access gate, API style and MCP on the cited page, and flags contradictions.</p><span class="m">{V1["summary"]["rows_flagged"]} apps flagged</span></div>
    <div class="step"><span class="k">4 · MCP Registry</span><h3>Vendor-verified MCPs</h3><p>The official MCP Registry only lets a vendor publish under its own domain, so a match proves the server is official.</p><span class="m">+{reg_found} official MCPs found</span></div>
    <div class="step"><span class="k">5 · re-research</span><h3>Fix only what's flagged</h3><p>The agent re-reads the vendor's own docs for flagged apps and logs each change as a patch.</p><span class="m">{claim_fixed} apps corrected · {cite_fixed} sources fixed</span></div>
    <div class="step"><span class="k">6 · blind audit</span><h3>Grade a frozen sample</h3><p>30 apps, picked before any check ran, graded on 6 fields from primary docs.</p><span class="m">{pct(a1)} → {pct(a2)}</span></div>
    <div class="step"><span class="k">7 · learned rule</span><h3>Fix the whole class of error</h3><p>The audit showed MCP answers were weakest, so every non-official MCP claim in all 100 apps was re-checked.</p><span class="m">+{l5_mcp} official MCPs found</span></div>
    <div class="step"><span class="k">8 · held-out test</span><h3>Measure on fresh apps</h3><p>10 new apps drawn after all fixes, graded the same way.</p><span class="m">Final accuracy {pct(hf)}</span></div>
    <div class="step human"><span class="k">9 · human sign-off</span><h3>A person confirms 12 calls</h3><p>The most consequential and least certain answers, each with its source.</p><span class="m">{human_done} of 12 signed off</span></div>
  </div>
  <div class="cards">
    <div class="card"><h3>What the agent uses</h3><ul class="plain">
      <li>Claude Opus 5.5 with web search and web fetch</li><li>Headless Chrome for JavaScript-built docs</li>
      <li>The official MCP Registry API</li><li>Claude and OpenAI connector directories</li>
      <li>Composio's <code>composio_search</code> and <code>firecrawl</code> toolkits (headless mode)</li></ul></div>
    <div class="card"><h3>Where a human was needed</h3><ul class="plain">
      <li><b>Which product?</b> "Paygent Connect" matches two companies. Only the requester can say which.</li>
      <li><b>Rule calls.</b> Docs-only MCPs don't count. Sandbox-only keys count as "approval".</li>
      <li><b>False matches.</b> LinkedIn's ChatGPT app is profile lookup, not Ads.</li>
      <li><b>Unreadable pages.</b> Lark's and HighLevel's docs stay empty even in Chrome.</li>
      <li><b>Customer-only APIs.</b> DealCloud, Gladly and PitchBook can't be tested without a paying account.</li></ul></div>
    <div class="card"><h3>How this run was done</h3><ul class="plain">
      <li>Claude Code (Opus 5.5) did the research steps as the agent, using the prompt and schema in the repo.</li>
      <li>The headless agent (Claude API + Composio tools) is in the repo and checks out against the SDKs. It was not run end to end because no API keys were available.</li>
      <li>All checks are plain Python and re-run in CI on every push.</li></ul></div>
  </div>
</section>

<section id="verify">
  <header><span class="eyebrow">Proof</span><h2>Verification: how accurate is it?</h2></header>
  <p class="bottom"><b>Bottom line:</b> on 10 apps used for nothing else, accuracy went from {pct(h1)} (first draft) to {pct(hf)} (final). Below is how it was measured, and every miss.</p>
  <div class="stats">
    <div class="stat"><b>{pct(a1)} → {pct(a2)}</b><span>30-app audit sample: first draft → after automated checks (180 judgments)</span></div>
    <div class="stat"><b>{pct(h1)} → {pct(hf)}</b><span>10 held-out apps: first draft → final (60 judgments)</span></div>
    <div class="stat"><b>{L["errors_fixed_by_loops"]} of {L["pass1_errors"]}</b><span>first-draft errors fixed by the automated checks alone</span></div>
    <div class="stat"><b>{len(L["regressions_pass1_to_pass2"])}</b><span>new errors the checks introduced in the sample</span></div>
  </div>
  <div class="cards">
    <div class="card span2"><h3>How it was checked</h3><ol class="steps">
      <li>Froze the first draft (sha256 <code>{sha[:12]}…</code>) and drew 30 apps, 3 per category, <b>before</b> running any check.</li>
      <li>Re-read each vendor's own docs for those 30 apps and graded 6 fields (login, access, API, MCP, verdict, sources) against a <a href="{BLOB}/verification/RUBRIC.md" target="_blank" rel="noopener">written rubric</a>. Every truth label stores the quote it rests on.</li>
      <li>After all fixes, drew 10 new apps and graded them the same way. That is the accuracy to expect on the rows nobody audited.</li></ol></div>
    <div class="card"><h3>Mistakes the agent made</h3><ul class="plain">
      <li>Missed new MCP servers (guessed {mcp_draft}, real {mcp_final}).</li>
      <li>Read "has a free plan" as "free API" (Help Scout).</li>
      <li>Called sandbox-only keys "free" (QuickBooks).</li>
      <li>Stale facts: Xero's 2026 pricing tiers, SendGrid's retired free plan.</li>
      <li>{dead1} made-up or moved doc links (now {deadF}).</li></ul></div>
  </div>
  <figure><figcaption><b>Accuracy by field</b><span>The audit fixed the 30 sample apps afterwards, so their final score (100%) is by construction and not shown. The held-out row is the fair number.</span></figcaption>
    <div class="legend"><span><span class="sym" style="color:var(--s2)">○</span>First draft</span><span><span class="sym" style="color:var(--s3)">■</span>After automated checks</span><span><span class="sym" style="color:var(--s1)">◆</span>Final</span></div>
    <div class="scroll">{accuracy_chart()}</div></figure>
  <div class="figs">
    <figure><figcaption><b>Misses left after the automated checks</b><span>Audit sample: {len(S["misses"]["pass2"])} of 180 judgments wrong.</span></figcaption>
      <div class="scroll"><table class="small"><thead><tr><th>App</th><th>Field</th><th>Agent said</th><th>Actually</th><th>Status</th></tr></thead><tbody>{p2_rows}</tbody></table></div></figure>
    <figure><figcaption><b>Misses in the final data</b><span>Held-out sample: {len(S["holdout"]["final"]["misses"])} of 60 judgments wrong.</span></figcaption>
      <div class="scroll"><table class="small"><thead><tr><th>App</th><th>Field</th><th>Cited / said</th><th>Problem</th><th>Status</th></tr></thead><tbody>{ho_rows}</tbody></table></div>
      <p class="count">The automated checks flagged {L["recall"]:.0%} of first-draft errors, and {L["precision"]:.0%} of flagged sample apps really had one. They are a cheap filter. The audit caught the rest.</p></figure>
  </div>
  <details><summary>Show all 180 audit judgments (✓ / ✗ for first draft · after checks · final)</summary><div class="scroll">{grid_tbl}</div>
    <p class="count">Truth labels with quotes: <a href="{BLOB}/verification/audit.json" target="_blank" rel="noopener">verification/audit.json</a>.</p></details>
  <figure><figcaption><b>Human sign-off ({human_done} of 12)</b><span>The calls a person should confirm by hand, each with the source it rests on.</span></figcaption>
    <div class="scroll"><table class="small"><thead><tr><th>App</th><th>Answer</th><th>Why check it</th><th>Source</th><th>Human</th></tr></thead><tbody>{human_rows}</tbody></table></div></figure>
</section>

<section id="run">
  <header><span class="eyebrow">Reproduce</span><h2>Run it yourself</h2></header>
  <div class="cards">
    <div class="card"><h3>Read the code</h3><ul class="plain">
      <li><a href="{REPO}" target="_blank" rel="noopener">Repository</a> and <a href="{BLOB}/README.md" target="_blank" rel="noopener">README</a></li>
      <li><a href="{BLOB}/agent/research_agent.py" target="_blank" rel="noopener">The research agent</a> (Claude + Composio tools)</li>
      <li><a href="{BLOB}/agent/prompts/research.md" target="_blank" rel="noopener">The research prompt</a></li>
      <li><a href="{BLOB}/data/patches_pass2.jsonl" target="_blank" rel="noopener">Every change, with source</a></li>
      <li><a href="{REPO}/actions" target="_blank" rel="noopener">CI runs</a> re-running every check</li></ul></div>
    <div class="card"><h3>Re-run every check</h3>
<pre>git clone {REPO}
cd toolkit-readiness-audit
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run_pipeline.sh</pre></div>
    <div class="card"><h3>Research one app</h3>
<pre># Claude Code
claude "/research-app 15"

# Headless agent
export ANTHROPIC_API_KEY=...
python -m agent.research_agent --ids 15
python -m agent.research_agent --ids 15 \\
  --engine composio  # needs COMPOSIO_API_KEY</pre></div>
  </div>
</section>

<footer><span>Data: <a href="{PAGES}data.csv">CSV</a> · <a href="{PAGES}data.json">JSON</a> · <a href="{PAGES}scores.json">scores</a> · <a href="{PAGES}patterns.json">patterns</a> · <a href="{PAGES}llms.txt">llms.txt</a></span>
<span>First draft sha256 <code>{sha[:16]}…</code></span><span>{n} apps · {cites} sources</span></footer>
</div>
<div id="tip" hidden></div>
<script>{JS}</script>
"""
(SITE / "artifact.html").write_text(page)
cut = page.index("</style>") + len("</style>")
(DOCS / "index.html").write_text('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                                 '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                                 + page[:cut] + "\n</head>\n<body>\n" + page[cut:] + "\n</body>\n</html>\n")
llms = ["# Toolkit Readiness Audit (100 apps)", "",
        "> Agent-researched readiness of 100 SaaS apps to become agent toolkits: login method, self-serve access, API, MCP, verdict and blocker, each with a cited source.",
        f"> Accuracy on held-out apps: first draft {pct(h1)} -> final {pct(hf)}. Audit sample: {pct(a1)} -> {pct(a2)} after automated checks.", "",
        "## Files", f"- {PAGES}data.json: one record per app", f"- {PAGES}data.csv: same, flat", f"- {PAGES}scores.json: accuracy per pass/field and every miss",
        f"- {PAGES}patterns.json: aggregates", f"- {REPO}: code", "", "## Apps"] + [
    f"- {d['app']} ({d['cat']}): {d['verdict']} | access={d['access']} | auth={'/'.join(d['auth'])} | api={'/'.join(d['api'])} | mcp={d['mcp']} | blocker={d['blocker']}"
    for d in data]
(DOCS / "llms.txt").write_text("\n".join(llms) + "\n")
print(f"docs/index.html {len(page) // 1024} KB · data.json · data.csv · scores.json · patterns.json · llms.txt · site/artifact.html")
