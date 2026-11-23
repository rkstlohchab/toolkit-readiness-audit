"""Loop 5 (learned rule): the blind audit showed MCP 'community'/'none' claims were the least reliable field, so
every app is re-checked against the two big vendor-connector directories:

  claude.com/connectors/<slug>          Anthropic's connector directory (vendor-built remote MCP servers)
  openai.com/business/plugins/<slug>/   OpenAI's app directory (vendor-built apps, MCP-based)

A 200 whose <title> names the app is positive evidence of an official, vendor-built MCP/connector.
A 404 proves nothing (Front's official beta MCP is in neither), so absences still need a search.

usage: python -m agent.directories data/pass2.json verification/directories.json
"""
import asyncio, json, pathlib, re, sys
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
EXTRA = {  # vendor-prefixed or renamed listings
    "Mailchimp": ["intuit-mailchimp"], "QuickBooks": ["intuit-quickbooks", "quickbooks-online"],
    "Jira": ["atlassian", "atlassian-rovo"], "Monday.com": ["monday", "monday-com"], "Zoho CRM": ["zoho", "zoho-crm"],
    "Lark (Larksuite)": ["lark"], "Meta Ads": ["meta-ads", "meta"], "Google Ads": ["google-ads"],
    "LinkedIn Ads": ["linkedin"], "Threads (Meta)": ["threads"], "Magento (Adobe Commerce)": ["adobe-commerce"],
    "Amazon Selling Partner": ["amazon-seller-central", "amazon"], "MongoDB Atlas": ["mongodb"],
    "Otter AI": ["otter-ai", "otter"], "YouTube Transcript": ["transcriptapi"], "Mermaid CLI": ["mermaid-chart", "mermaid"],
    "Help Scout": ["help-scout"], "GoHighLevel": ["highlevel", "gohighlevel"], "Bright Data": ["bright-data", "brightdata"],
    "Salesforce Commerce Cloud": ["salesforce-commerce-cloud"], "WhatsApp Business": ["whatsapp"],
    "fanbasis": ["commas"], "Waterfall.io": ["waterfall"], "PitchBook": ["pitchbook", "pitchbook-premium"],
    "NotebookLM": ["notebooklm"], "SE Ranking": ["se-ranking", "seranking"], "Zoho Cliq": ["zoho-cliq"],
}


def slugs(app):
    base = re.sub(r"\(.*?\)", "", app).strip().lower()
    cands = [re.sub(r"[^a-z0-9]+", "-", base).strip("-"), re.sub(r"[^a-z0-9]", "", base)]
    return list(dict.fromkeys(EXTRA.get(app, []) + cands))


def title_matches(app, title):
    key = re.sub(r"\(.*?\)", "", app).strip().lower().split()[0].replace(".com", "")
    return key[:5] in title.lower()


async def check(client, url, app):
    try:
        r = await client.get(url)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    t = re.search(r"<title>(.*?)</title>", r.text, re.S)
    title = re.sub(r"\s+", " ", t.group(1)).strip() if t else ""
    return {"url": str(r.url), "title": title} if title_matches(app, title) else None


async def run(apps):
    out = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": UA}) as client:
        sem = asyncio.Semaphore(8)

        async def one(app):
            hits = {}
            for s in slugs(app):
                async with sem:
                    if "claude" not in hits:
                        h = await check(client, f"https://claude.com/connectors/{s}", app)
                        if h: hits["claude"] = h
                    if "openai" not in hits:
                        h = await check(client, f"https://openai.com/business/plugins/{s}/", app)
                        if h: hits["openai"] = h
            out[app] = hits
        await asyncio.gather(*(one(a) for a in apps))
    return out


def main():
    rows = json.loads(pathlib.Path(sys.argv[1]).read_text())
    res = asyncio.run(run([r["app"] for r in rows]))
    pathlib.Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
    listed = {a for a, h in res.items() if h}
    print(f"apps with a vendor connector in Claude and/or OpenAI directories: {len(listed)}")
    for r in rows:
        if r["app"] in listed and r["mcp"] != "official":
            h = res[r["app"]]
            print(f'  DIRECTORY LISTS {r["app"]:24} but claim={r["mcp"]:9} ->', "; ".join(f"{k}: {v['title'][:50]}" for k, v in h.items()))


if __name__ == "__main__":
    main()
