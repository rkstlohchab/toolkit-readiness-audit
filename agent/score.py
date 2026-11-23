"""Score every pass against the blind-audit truth (verification/audit.json) using verification/RUBRIC.md.

Also measures the automated verifier itself on the sample:
  recall    = share of Pass-1 errors whose field the automated loops flagged
  precision = share of flagged sample rows that really contained an error

usage: python -m agent.score  ->  verification/scores.json
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIELDS = ["auth", "access", "api", "mcp", "verdict", "evidence"]
FLAG_FIELDS = {  # which graded fields a verifier flag points at
    "auth": ["L1:auth", "L2:auth"], "access": ["L1:access", "L2:access"], "api": ["L1:api", "L2:api"],
    "mcp": ["L1:mcp", "L2:mcp", "L2b:mcp", "L3:absence of MCP", "L3:official MCP"],
    "verdict": ["L3:verdict"], "evidence": ["L1:", "L2:", "L2b:", "L3:official MCP", "L3:single URL"],
}


def grade(rec, t, ev_fail):
    S, T = set(rec["auth"]), set(t["auth"]) | set(t.get("auth_opt", []))
    auth_ok = bool(S) and S <= T and ("OAuth2" not in t["auth"] or "OAuth2" in S)
    api_ok = set(rec["api"]) <= set(t["api"]) and t["api"][0] in rec["api"]
    return {"auth": auth_ok, "access": rec["access"] == t["access"], "api": api_ok,
            "mcp": (rec["mcp"] == "official") == t["mcp"], "verdict": rec["verdict"] == t["verdict"],
            "evidence": str(rec["id"]) not in ev_fail and rec["id"] not in ev_fail}


def main():
    A = json.loads((ROOT / "verification/audit.json").read_text())
    truth = A["truth"]
    passes = {p: {r["id"]: r for r in json.loads((ROOT / f"data/{f}.json").read_text())}
              for p, f in [("pass1", "pass1"), ("pass2", "pass2"), ("final", "final")]}
    out = {"n_apps": len(truth), "n_judgments": len(truth) * len(FIELDS), "passes": {}, "misses": {}}
    grades = {}
    for p, rows in passes.items():
        ev_fail = {int(k) for k in A["evidence_failures"][p]}
        g = {int(i): grade(rows[int(i)], t, ev_fail) for i, t in truth.items()}
        grades[p] = g
        per = {f: sum(g[i][f] for i in g) / len(g) for f in FIELDS}
        tot = sum(g[i][f] for i in g for f in FIELDS)
        out["passes"][p] = {"per_field": per, "correct": tot, "accuracy": tot / out["n_judgments"]}
        out["misses"][p] = [{"id": i, "app": rows[i]["app"], "field": f,
                             "got": (rows[i][f] if f != "evidence" else A["evidence_failures"][p].get(str(i), "")),
                             "truth": (truth[str(i)][f] if f != "evidence" else "live + supporting citations")}
                            for i in sorted(g) for f in FIELDS if not g[i][f]]

    # ---- how good were the automated loops at finding Pass-1 errors?
    V = {o["id"]: o["flags"] for o in json.loads((ROOT / "verification/verify_pass1.json").read_text())["rows"]}
    errs = [(i, f) for i in grades["pass1"] for f in FIELDS if not grades["pass1"][i][f]]
    flagged_field = lambda i, f: any(any(fl.startswith(px) for px in FLAG_FIELDS[f]) or "low confidence" in fl for fl in V[i])
    caught = [(i, f) for i, f in errs if flagged_field(i, f)]
    fixed_by_loops = [(i, f) for i, f in errs if grades["pass2"][i][f]]
    sample_ids = [int(i) for i in truth]
    flagged_rows = [i for i in sample_ids if V[i]]
    err_rows = {i for i, _ in errs}
    regress = [(i, f) for i in grades["pass1"] for f in FIELDS if grades["pass1"][i][f] and not grades["pass2"][i][f]]
    out["loops"] = {
        "pass1_errors": len(errs), "errors_flagged": len(caught), "errors_fixed_by_loops": len(fixed_by_loops),
        "recall": len(caught) / len(errs) if errs else 1.0,
        "flagged_rows": len(flagged_rows), "flagged_rows_with_error": len([i for i in flagged_rows if i in err_rows]),
        "precision": (len([i for i in flagged_rows if i in err_rows]) / len(flagged_rows)) if flagged_rows else 1.0,
        "missed_by_loops": [{"id": i, "app": passes["pass1"][i]["app"], "field": f} for i, f in errs if not flagged_field(i, f)],
        "regressions_pass1_to_pass2": [{"id": i, "field": f} for i, f in regress],
    }
    # ---- held-out check: 10 apps drawn AFTER Final, never audited before (unbiased estimate for unaudited rows).
    # Grade "final" as it stood when the held-out sample was drawn: replay the final-stage patch log only up to the
    # first fix the held-out check itself triggered, so later fixes can't inflate the measured number.
    H = A.get("holdout_truth", {})
    snap = {r["id"]: r for r in json.loads((ROOT / "data/pass2.json").read_text())}
    for line in (ROOT / "data/patches_final.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e["loop"] in ("holdout", "rubric-late"):
            break
        for k, v in e["fields"].items():
            if k == "ev":
                snap[e["id"]]["ev"] = {**snap[e["id"]]["ev"], **v}
            else:
                snap[e["id"]][k] = v
    out["holdout"] = {}
    for p, rows in {**passes, "final": snap}.items():
        ev_fail = {int(k) for k in A["holdout_evidence_failures"][p]}
        g = {int(i): grade(rows[int(i)], t, ev_fail) for i, t in H.items()}
        tot = sum(g[i][f] for i in g for f in FIELDS)
        out["holdout"][p] = {"accuracy": tot / (len(g) * len(FIELDS)), "correct": tot, "n": len(g) * len(FIELDS),
                             "per_field": {f: sum(g[i][f] for i in g) / len(g) for f in FIELDS},
                             "misses": [{"id": i, "app": rows[i]["app"], "field": f} for i in sorted(g) for f in FIELDS if not g[i][f]]}
    (ROOT / "verification/scores.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for p, s in out["passes"].items():
        print(f"{p:6} {s['accuracy']:.1%}  ({s['correct']}/{out['n_judgments']})  " +
              "  ".join(f"{f}={v:.0%}" for f, v in s["per_field"].items()))
    L = out["loops"]
    print(f"loops: {L['pass1_errors']} pass-1 errors, flagged {L['errors_flagged']} (recall {L['recall']:.0%}), "
          f"fixed {L['errors_fixed_by_loops']}; row precision {L['precision']:.0%} "
          f"({L['flagged_rows_with_error']}/{L['flagged_rows']}); regressions {len(L['regressions_pass1_to_pass2'])}")
    for p, h in out["holdout"].items():
        print(f"holdout {p:6} {h['accuracy']:.1%} ({h['correct']}/{h['n']})  misses: " + ", ".join(f"{m['app']}:{m['field']}" for m in h["misses"]))
    print("missed by automated loops:", ", ".join(f"{m['app']}:{m['field']}" for m in L["missed_by_loops"]))


if __name__ == "__main__":
    main()
