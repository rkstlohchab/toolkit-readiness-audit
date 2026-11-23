"""Merge the Pass-1 draft parts, hash them, and draw the evaluation sample BEFORE any verification runs.

The hash is printed on the case-study page so a reader can confirm the "first pass" numbers were
computed against the draft as it existed before the verification loops touched anything.

usage: python -m agent.freeze
"""
import hashlib, json, random, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = 20261123          # fixed: sample is reproducible
PER_CATEGORY = 3         # 3 x 10 categories = 30-app stratified sample


def main():
    parts = sorted((ROOT / "data/pass1").glob("*.json"))
    rows = [r for p in parts for r in json.loads(p.read_text())]
    rows.sort(key=lambda r: r["id"])
    assert [r["id"] for r in rows] == list(range(1, 101)), "expected ids 1..100"

    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
    digest = hashlib.sha256(blob).hexdigest()
    (ROOT / "data/pass1.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))

    by_cat = collections.defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r["id"])
    rng = random.Random(SEED)
    sample = sorted(i for cat in sorted(by_cat) for i in rng.sample(by_cat[cat], PER_CATEGORY))

    (ROOT / "verification").mkdir(exist_ok=True)
    (ROOT / "verification/sample.json").write_text(json.dumps(
        {"seed": SEED, "per_category": PER_CATEGORY, "pass1_sha256": digest, "ids": sample}, indent=1))
    print(f"pass1: {len(rows)} rows  sha256={digest[:16]}…  sample={sample}")


if __name__ == "__main__":
    main()
