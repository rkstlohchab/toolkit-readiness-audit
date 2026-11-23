"""Loop 2b: is there an OFFICIAL MCP server? Checked against the official MCP Registry.

registry.modelcontextprotocol.io namespaces are verified: `com.stripe/*` can only be published by someone who
proved control of stripe.com (DNS/HTTP), `io.github.<org>/*` by that GitHub org. So:

  official  = a registry entry whose namespace is the vendor's reversed domain, or whose repo/namespace is the
              vendor's GitHub org
  community = entries exist for the app name but none are vendor-owned
  absent    = nothing in the registry (NOT proof there is no MCP: many vendors never publish there)

usage: python -m agent.mcp_registry data/pass1.json verification/mcp_registry.json
"""
import asyncio, json, pathlib, re, sys
from urllib.parse import urlparse
import httpx

REG = "https://registry.modelcontextprotocol.io/v0/servers"

# search term + vendor identity (domains / GitHub orgs). Domains come from the app's own docs/site.
VENDOR = {
    1: ("salesforce", ["salesforce.com", "force.com"], ["salesforcecli", "forcedotcom", "salesforce"]),
    2: ("hubspot", ["hubspot.com"], ["hubspot", "HubSpot"]),
    3: ("pipedrive", ["pipedrive.com"], ["pipedrive"]),
    4: ("attio", ["attio.com"], ["attio"]),
    5: ("twenty", ["twenty.com"], ["twentyhq"]),
    6: ("podio", ["podio.com"], ["podio"]),
    7: ("zoho", ["zoho.com", "zohocrm.com"], ["zoho"]),
    8: ("close", ["close.com"], ["closeio", "close"]),
    9: ("copper", ["copper.com"], ["copperinc"]),
    10: ("dealcloud", ["dealcloud.com", "intapp.com"], ["intapp"]),
    11: ("zendesk", ["zendesk.com"], ["zendesk"]),
    12: ("intercom", ["intercom.com", "intercom.io"], ["intercom"]),
    13: ("freshdesk", ["freshdesk.com", "freshworks.com"], ["freshworks"]),
    14: ("front", ["front.com", "frontapp.com"], ["frontapp"]),
    15: ("pylon", ["usepylon.com"], ["usepylon"]),
    16: ("liveagent", ["liveagent.com", "qualityunit.com"], ["QualityUnit"]),
    17: ("plain", ["plain.com"], ["team-plain"]),
    18: ("helpscout", ["helpscout.com", "helpscout.net"], ["helpscout"]),
    19: ("gorgias", ["gorgias.com"], ["gorgias"]),
    20: ("gladly", ["gladly.com", "gladly.ai"], ["gladly"]),
    21: ("slack", ["slack.com", "slack.dev"], ["slackapi", "slack"]),
    22: ("twilio", ["twilio.com"], ["twilio-labs", "twilio"]),
    23: ("cliq", ["zoho.com"], ["zoho"]),
    24: ("lark", ["larksuite.com", "feishu.cn"], ["larksuite"]),
    25: ("pumble", ["pumble.com", "cake.com"], ["cake-com"]),
    26: ("discord", ["discord.com"], ["discord"]),
    27: ("telegram", ["telegram.org"], ["telegram"]),
    28: ("whatsapp", ["whatsapp.com", "facebook.com", "meta.com"], ["facebook", "meta"]),
    29: ("aircall", ["aircall.io"], ["aircall"]),
    30: ("vonage", ["vonage.com"], ["Vonage", "vonage"]),
    31: ("google-ads", ["google.com"], ["googleads", "google"]),
    32: ("meta-ads", ["facebook.com", "meta.com"], ["facebook", "meta"]),
    33: ("linkedin", ["linkedin.com"], ["linkedin"]),
    34: ("highlevel", ["gohighlevel.com", "leadconnectorhq.com"], ["GoHighLevel"]),
    35: ("mailchimp", ["mailchimp.com", "intuit.com"], ["mailchimp"]),
    36: ("klaviyo", ["klaviyo.com"], ["klaviyo"]),
    37: ("systeme", ["systeme.io"], ["systeme"]),
    38: ("pinterest", ["pinterest.com"], ["pinterest"]),
    39: ("threads", ["threads.net", "threads.com", "meta.com"], ["meta"]),
    40: ("sendgrid", ["sendgrid.com", "twilio.com"], ["sendgrid", "twilio-labs"]),
    41: ("shopify", ["shopify.com", "shopify.dev"], ["Shopify"]),
    42: ("woocommerce", ["woocommerce.com", "automattic.com"], ["woocommerce", "Automattic"]),
    43: ("bigcommerce", ["bigcommerce.com"], ["bigcommerce"]),
    44: ("commerce-cloud", ["salesforce.com"], ["SalesforceCommerceCloud", "salesforce"]),
    45: ("magento", ["adobe.com", "magento.com"], ["magento", "adobe"]),
    46: ("squarespace", ["squarespace.com"], ["Squarespace"]),
    47: ("ecwid", ["ecwid.com", "lightspeedhq.com"], ["Ecwid"]),
    48: ("gumroad", ["gumroad.com"], ["antiwork", "gumroad"]),
    49: ("amazon-sp", ["amazon.com", "amazonservices.com"], ["amzn", "aws"]),
    50: ("fanbasis", ["fanbasis.com", "commas.com"], ["fanbasis"]),
    51: ("dataforseo", ["dataforseo.com"], ["dataforseo"]),
    52: ("seranking", ["seranking.com"], ["seranking"]),
    53: ("ahrefs", ["ahrefs.com"], ["ahrefs"]),
    54: ("mrscraper", ["mrscraper.com"], ["mrscraper"]),
    55: ("apify", ["apify.com"], ["apify"]),
    56: ("firecrawl", ["firecrawl.dev"], ["firecrawl", "mendableai"]),
    57: ("brightdata", ["brightdata.com"], ["brightdata", "luminati-io"]),
    58: ("sherlock", ["sherlock-project.github.io"], ["sherlock-project"]),
    59: ("waterfall", ["waterfall.io"], ["waterfall-io"]),
    60: ("clay", ["clay.com"], ["clay-run"]),
    61: ("github", ["github.com"], ["github"]),
    62: ("vercel", ["vercel.com"], ["vercel"]),
    63: ("netlify", ["netlify.com"], ["netlify"]),
    64: ("cloudflare", ["cloudflare.com"], ["cloudflare"]),
    65: ("supabase", ["supabase.com"], ["supabase-community", "supabase"]),
    66: ("neo4j", ["neo4j.com", "neo4j.io"], ["neo4j", "neo4j-contrib"]),
    67: ("snowflake", ["snowflake.com"], ["Snowflake-Labs", "snowflakedb"]),
    68: ("mongodb", ["mongodb.com"], ["mongodb-js", "mongodb"]),
    69: ("datadog", ["datadoghq.com"], ["DataDog"]),
    70: ("sentry", ["sentry.io", "sentry.dev"], ["getsentry"]),
    71: ("notion", ["notion.com", "notion.so"], ["makenotion"]),
    72: ("airtable", ["airtable.com"], ["Airtable"]),
    73: ("linear", ["linear.app"], ["linear"]),
    74: ("atlassian", ["atlassian.com"], ["atlassian"]),
    75: ("asana", ["asana.com"], ["Asana"]),
    76: ("monday", ["monday.com"], ["mondaycom"]),
    77: ("clickup", ["clickup.com"], ["clickup"]),
    78: ("coda", ["coda.io"], ["coda"]),
    79: ("smartsheet", ["smartsheet.com"], ["smartsheet", "smartsheet-platform"]),
    80: ("harvest", ["getharvest.com", "harvestapp.com"], ["harvesthq"]),
    81: ("stripe", ["stripe.com"], ["stripe"]),
    82: ("plaid", ["plaid.com"], ["plaid"]),
    83: ("binance", ["binance.com"], ["binance"]),
    84: ("paygent", ["paygent.com", "nmi.com"], ["nmi"]),
    85: ("ipayx", ["ipayx.ai"], ["ipayx"]),
    86: ("quickbooks", ["intuit.com", "quickbooks.com"], ["intuit"]),
    87: ("xero", ["xero.com"], ["XeroAPI"]),
    88: ("brex", ["brex.com"], ["brexhq"]),
    89: ("ramp", ["ramp.com"], ["ramp-public"]),
    90: ("pitchbook", ["pitchbook.com"], ["pitchbook"]),
    91: ("notebooklm", ["google.com"], ["google", "googleapis"]),
    92: ("otter", ["otter.ai"], ["otterai"]),
    93: ("fathom", ["fathom.ai", "fathom.video"], ["fathom-video"]),
    94: ("consensus", ["consensus.app"], ["consensus-app"]),
    95: ("reducto", ["reducto.ai"], ["reductoai"]),
    96: ("devin", ["devin.ai", "cognition.ai", "deepwiki.com"], ["CognitionAI", "cognition-ai"]),
    97: ("higgsfield", ["higgsfield.ai"], ["higgsfield-ai"]),
    98: ("mermaid", ["mermaid.js.org", "mermaidchart.com"], ["mermaid-js", "Mermaid-Chart"]),
    99: ("transcriptapi", ["transcriptapi.com"], ["transcriptapi"]),
    100: ("grain", ["grain.com"], ["grainhq"]),
}


def reverse(domain):
    return ".".join(reversed(domain.lower().split(".")))


def vendor_owned(entry, domains, orgs):
    name = entry.get("name", "")
    ns = name.split("/")[0].lower()
    if any(ns == reverse(d) or ns.startswith(reverse(d) + ".") for d in domains):
        return "namespace"
    if ns.startswith("io.github."):
        if ns.split(".", 2)[2] in [o.lower() for o in orgs]:
            return "github-namespace"
    repo = ((entry.get("repository") or {}).get("url") or "").lower()
    m = re.match(r"https://github\.com/([^/]+)/", repo + "/")
    if m and m.group(1) in [o.lower() for o in orgs]:
        return "github-repo"
    for r in entry.get("remotes") or []:
        host = urlparse(r.get("url", "")).netloc.lower()
        if any(host == d or host.endswith("." + d) for d in domains):
            return "remote-host"
    return None


async def search(client, term, cap=300):
    out, cursor = [], None
    while len(out) < cap:
        params = {"search": term, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = await client.get(REG, params=params)
        if r.status_code != 200:
            break
        d = r.json()
        out += [s.get("server", s) for s in d.get("servers", [])]
        cursor = (d.get("metadata") or {}).get("nextCursor")
        if not cursor:
            break
    return out


async def run(ids):
    res = {}
    async with httpx.AsyncClient(timeout=30) as client:
        sem = asyncio.Semaphore(6)

        async def one(i):
            term, domains, orgs = VENDOR[i]
            async with sem:
                entries = await search(client, term)
            seen, official = set(), []
            for e in entries:
                if e.get("name") in seen:
                    continue
                seen.add(e.get("name"))
                how = vendor_owned(e, domains, orgs)
                if how:
                    official.append({"name": e["name"], "how": how,
                                     "remote": [x.get("url") for x in (e.get("remotes") or [])][:1],
                                     "repo": (e.get("repository") or {}).get("url", "")})
            res[i] = {"term": term, "entries": len(seen), "official": official,
                      "verdict": "official" if official else ("community" if seen else "absent")}
        await asyncio.gather(*(one(i) for i in ids))
    return res


def main():
    rows = json.loads(pathlib.Path(sys.argv[1]).read_text())
    res = asyncio.run(run([r["id"] for r in rows]))
    pathlib.Path(sys.argv[2]).write_text(json.dumps({str(k): v for k, v in sorted(res.items())}, indent=1))
    agree = disagree = 0
    for r in rows:
        v = res[r["id"]]["verdict"]
        if v == "official" and r["mcp"] != "official":
            print(f'  REGISTRY SAYS OFFICIAL, draft says {r["mcp"]:9}: {r["app"]:24} {res[r["id"]]["official"][0]["name"]}')
            disagree += 1
        elif v == "official":
            agree += 1
    print(f"registry-confirmed official MCPs: {sum(1 for v in res.values() if v['verdict']=='official')} | "
          f"agree with draft: {agree} | draft missed: {disagree}")


if __name__ == "__main__":
    main()
