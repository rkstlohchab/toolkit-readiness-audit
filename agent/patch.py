"""Record a correction produced by a verification loop (append-only audit trail).

Every change to a record goes through here so the page can show exactly what each loop changed and why.

usage:
  python -m agent.patch <stage> <id> '<json fields>' --loop L1|L2|L2b|L3|L5|human --why "..." --src URL [--quote "..."]
  python -m agent.patch apply <stage> <in.json> <out.json>     # materialize a pass from its patches

stage = pass2 (automated loops + agent re-research) | final (blind audit + propagated rules + human)
"""
import json, pathlib, sys, argparse, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]


def log_path(stage):
    return ROOT / f"data/patches_{stage}.jsonl"


def add(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage"); ap.add_argument("id", type=int); ap.add_argument("fields")
    ap.add_argument("--loop", required=True); ap.add_argument("--why", required=True)
    ap.add_argument("--src", action="append", default=[]); ap.add_argument("--quote", default="")
    a = ap.parse_args(argv)
    fields = json.loads(a.fields)
    entry = {"id": a.id, "fields": fields, "loop": a.loop, "why": a.why, "src": a.src, "quote": a.quote,
             "at": datetime.datetime.now().isoformat(timespec="seconds")}
    with log_path(a.stage).open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"patched #{a.id} {list(fields)} ({a.loop})")


def apply(stage, src, dst):
    rows = {r["id"]: r for r in json.loads(pathlib.Path(src).read_text())}
    changes = []
    for line in log_path(stage).read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        r = rows[e["id"]]
        for k, v in e["fields"].items():
            if k == "ev":                       # evidence is merged per field
                before = dict(r["ev"]); r["ev"].update(v)
                changed = before != r["ev"]
            else:
                before = r.get(k); r[k] = v
                changed = before != v
            if changed and k not in ("auth_d", "access_d", "api_d", "mcp_d", "what", "conf", "ev", "blocker"):
                changes.append({"id": e["id"], "app": r["app"], "field": k, "from": before, "to": v,
                                "loop": e["loop"], "why": e["why"], "src": e["src"], "quote": e["quote"]})
    pathlib.Path(dst).write_text(json.dumps(sorted(rows.values(), key=lambda r: r["id"]), indent=1, ensure_ascii=False))
    pathlib.Path(ROOT / f"data/changes_{stage}.json").write_text(json.dumps(changes, indent=1, ensure_ascii=False))
    print(f"{stage}: {len(changes)} substantive field changes across {len({c['id'] for c in changes})} apps -> {dst}")


if __name__ == "__main__":
    if sys.argv[1] == "apply":
        apply(*sys.argv[2:5])
    else:
        add(sys.argv[1:])
