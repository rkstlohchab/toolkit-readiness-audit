"""Loop 1 (link liveness) + Loop 2 input (page text) + Composio catalog check.

For every evidence URL cited by a records file:
  1. plain HTTP GET (httpx, redirects followed)
  2. if the page is thin (JS-rendered SPA), blocked (401/403/429) or errored -> re-render it in a real
     headless Chrome via Playwright and take document.body.innerText  ("browser loop")
  3. cache the visible text under data/cache/pages/<sha1>.txt and write a status table

Also probes composio.dev/toolkits/<slug> for each app to see whether a Composio toolkit already exists.

usage: python -m agent.fetch_evidence data/pass1.json verification/links_pass1.json [--no-browser]
"""
import asyncio, hashlib, json, pathlib, re, sys, time
import httpx
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/pages"
CACHE.mkdir(parents=True, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
THIN = 1200          # fewer visible chars than this => probably a JS shell, try the browser


def key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


async def http_fetch(client, url):
    t0 = time.time()
    try:
        r = await client.get(url)
        text = visible_text(r.text) if "html" in r.headers.get("content-type", "") else r.text[:200000]
        return {"url": url, "status": r.status_code, "final_url": str(r.url), "chars": len(text),
                "via": "http", "ms": int((time.time() - t0) * 1000)}, text
    except Exception as e:  # DNS failure, TLS, timeout
        return {"url": url, "status": 0, "error": type(e).__name__, "chars": 0, "via": "http"}, ""


async def browser_fetch(urls):
    """Render pages in the locally installed Chrome. Returns {url: (meta, text)}."""
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome", headless=True)
        except Exception:                      # no system Chrome (e.g. CI): use Playwright's bundled Chromium
            browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA)
        sem = asyncio.Semaphore(4)

        async def one(url):
            async with sem:
                page = await ctx.new_page()
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2500)          # let SPAs hydrate
                    text = re.sub(r"\s+", " ", await page.evaluate("document.body.innerText"))
                    out[url] = ({"url": url, "status": resp.status if resp else 0, "final_url": page.url,
                                 "chars": len(text), "via": "browser"}, text)
                except Exception as e:
                    out[url] = ({"url": url, "status": 0, "error": type(e).__name__, "chars": 0,
                                 "via": "browser"}, "")
                finally:
                    await page.close()

        await asyncio.gather(*(one(u) for u in urls))
        await browser.close()
    return out


def classify(m):
    s = m["status"]
    if s == 0:
        return "dead"
    if s in (401, 403, 429, 503):
        return "blocked"
    if s >= 400:
        return "dead"
    return "ok" if m["chars"] >= THIN else "thin"


async def run(urls, use_browser=True):
    results = {}
    limits = httpx.Limits(max_connections=16)
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": UA},
                                 limits=limits) as client:
        pairs = await asyncio.gather(*(http_fetch(client, u) for u in urls))
    for meta, text in pairs:
        meta["state"] = classify(meta)
        results[meta["url"]] = (meta, text)

    retry = [u for u, (m, _) in results.items() if m["state"] != "ok"]
    if use_browser and retry:
        print(f"  browser loop: re-rendering {len(retry)} thin/blocked/dead pages in headless Chrome")
        for u, (m, t) in (await browser_fetch(retry)).items():
            m["state"] = classify(m)
            m["http_state"] = results[u][0]["state"]
            if m["state"] == "ok" or m["chars"] > results[u][0]["chars"]:
                results[u] = (m, t)
            else:
                results[u][0]["browser_state"] = m["state"]

    for u, (m, t) in results.items():
        (CACHE / f"{key(u)}.txt").write_text(t)
        m["cache"] = f"{key(u)}.txt"
    return {u: m for u, (m, _) in results.items()}


# ---------------------------------------------------------------- Composio catalog check
SLUG_OVERRIDES = {
    "Zoho CRM": ["zoho", "zoho_crm", "zohocrm"], "Zoho Cliq": ["zoho_cliq", "zohocliq", "cliq"],
    "Lark (Larksuite)": ["lark", "larksuite"], "WhatsApp Business": ["whatsapp"],
    "Google Ads": ["googleads", "google_ads"], "Meta Ads": ["metaads", "meta_ads", "facebook"],
    "LinkedIn Ads": ["linkedin", "linkedin_ads"], "GoHighLevel": ["gohighlevel", "highlevel"],
    "Threads (Meta)": ["threads"], "Magento (Adobe Commerce)": ["magento", "adobe_commerce"],
    "Amazon Selling Partner": ["amazon", "amazon_selling_partner", "amazon_sp_api"],
    "Salesforce Commerce Cloud": ["salesforce_commerce_cloud", "salesforce_commerce"],
    "Monday.com": ["monday", "mondaycom"], "MongoDB Atlas": ["mongodb", "mongodb_atlas"],
    "Help Scout": ["help_scout", "helpscout"], "Bright Data": ["brightdata", "bright_data"],
    "Waterfall.io": ["waterfall", "waterfall_io"], "Otter AI": ["otter", "otter_ai", "otterai"],
    "YouTube Transcript": ["youtube_transcript", "transcriptapi", "youtube"],
    "Mermaid CLI": ["mermaid", "mermaid_cli"], "Paygent Connect": ["paygent", "paygent_connect"],
    "SE Ranking": ["se_ranking", "seranking"], "QuickBooks": ["quickbooks"], "Close": ["close", "close_crm"],
    "Twenty": ["twenty", "twenty_crm"], "Copper": ["copper", "copper_crm"], "Plain": ["plain"],
    "Front": ["front", "frontapp"], "Pylon": ["pylon", "usepylon"], "Grain": ["grain"],
    "Devin": ["devin"], "Coda": ["coda"], "Clay": ["clay"], "Fathom": ["fathom"],
    "NotebookLM": ["notebook_lm", "notebooklm"], "Mermaid CLI": ["mermaid_chart", "mermaid", "mermaid_cli"],
}


def slug_candidates(app):
    base = re.sub(r"\(.*?\)", "", app).strip().lower()
    roots = SLUG_OVERRIDES.get(app, []) + [re.sub(r"[^a-z0-9]", "", base), re.sub(r"[^a-z0-9]+", "_", base).strip("_")]
    # Composio also lists some toolkits under suffixed slugs (pylon_mcp, notebook_lm, otter_ai_mcp, mermaid_chart_mcp)
    out = []
    for r in roots:
        out += [r, r + "_mcp", r + "_ai", r + "_api"]
    return list(dict.fromkeys(out))


async def composio_catalog(apps):
    out = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": UA}) as client:
        async def one(app):
            for slug in slug_candidates(app):
                r = await client.get(f"https://composio.dev/toolkits/{slug}")
                if r.status_code == 200:
                    m = re.search(r"<title>(.*?)</title>", r.text, re.S)
                    title = m.group(1).strip() if m else ""
                    if "MCP Server" in title and "Toolkits -" not in title:     # skip category pages
                        out[app] = {"slug": slug, "url": str(r.url), "title": title}
                        return
            out[app] = None
        sem = asyncio.Semaphore(8)

        async def guarded(a):
            async with sem:
                await one(a)
        await asyncio.gather(*(guarded(a) for a in apps))
    return out


def main():
    src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    rows = json.loads(src.read_text())
    urls = sorted({u for r in rows for u in r["ev"].values() if u})
    print(f"{src.name}: {len(urls)} unique evidence URLs across {len(rows)} apps")
    meta = asyncio.run(run(urls, use_browser="--no-browser" not in sys.argv))
    counts = {}
    for m in meta.values():
        counts[m["state"]] = counts.get(m["state"], 0) + 1
    print("  final states:", counts, "| rescued by browser:",
          sum(1 for m in meta.values() if m.get("via") == "browser" and m["state"] == "ok"))
    out = {"source": src.name, "urls": meta}
    if "--catalog" in sys.argv:
        out["composio"] = asyncio.run(composio_catalog([r["app"] for r in rows]))
        print("  composio toolkits found:", sum(1 for v in out["composio"].values() if v), "/", len(rows))
    dst.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
