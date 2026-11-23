"""Browser loop for a single page: render in headless Chrome, print visible text (optionally grep).

Used when docs are client-rendered SPAs that plain HTTP (and summarizing fetchers) can't read.

usage: python -m agent.browse URL [regex] [--chars 4000]
"""
import asyncio, re, sys
from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


async def render(url):
    async with async_playwright() as p:
        try:
            b = await p.chromium.launch(channel="chrome", headless=True)
        except Exception:                      # no system Chrome: Playwright's bundled Chromium
            b = await p.chromium.launch(headless=True)
        page = await (await b.new_context(user_agent=UA)).new_page()
        # 'networkidle' never fires on docs sites with analytics beacons; DOM-ready + a fixed hydrate wait is robust
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        text = re.sub(r"[ \t]+", " ", await page.evaluate("document.body.innerText"))
        links = await page.evaluate("[...document.querySelectorAll('a')].map(a=>a.href)")
        await b.close()
        return resp.status if resp else 0, page.url, text, links


def main():
    url = sys.argv[1]
    pat = next((a for a in sys.argv[2:] if not a.startswith("--") and not a.isdigit()), None)
    n = int(sys.argv[sys.argv.index("--chars") + 1]) if "--chars" in sys.argv else 4000
    status, final, text, links = asyncio.run(render(url))
    print(f"[{status}] {final}  ({len(text)} chars)")
    if pat:
        for m in re.finditer(pat, text, re.I):
            print("…", text[max(0, m.start() - 160): m.end() + 200].replace("\n", " "), "…")
        for l in sorted(set(links)):
            if re.search(pat, l, re.I):
                print("link:", l)
    else:
        print(text[:n])


if __name__ == "__main__":
    main()
