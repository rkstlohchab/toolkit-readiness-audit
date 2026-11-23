"""Batch claim probe: fetch candidate evidence URLs (HTTP -> headless Chrome fallback) and grep each page for
the pattern that would support a specific claim. Used by the re-research loop to repair citations fast.

usage: python -m agent.probe probes.json      # [{"id":1,"field":"auth","url":"...","pat":"oauth|connected app"}]
"""
import asyncio, json, pathlib, re, sys
from agent.fetch_evidence import run, CACHE


def main():
    probes = json.loads(pathlib.Path(sys.argv[1]).read_text())
    meta = asyncio.run(run(sorted({p["url"] for p in probes})))
    for p in probes:
        m = meta[p["url"]]
        text = (CACHE / m["cache"]).read_text()
        hits = [text[max(0, x.start() - 110): x.end() + 130] for x in re.finditer(p["pat"], text, re.I)][:2]
        mark = "OK " if (m["state"] == "ok" and hits) else ("NOHIT" if m["state"] == "ok" else m["state"].upper())
        print(f'[{mark}] #{p["id"]} {p["field"]:6} {m["status"]} {m.get("via","")} {p["url"]}')
        for h in hits:
            print("      …" + re.sub(r"\s+", " ", h) + "…")


if __name__ == "__main__":
    main()
