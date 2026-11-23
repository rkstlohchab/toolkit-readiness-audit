"""Record schema for one researched app. Shared by the research agent, verifiers and page builder.

Every enum below is deliberately small so results can be clustered and graded objectively.
"""

AUTH = ["OAuth2", "OAuth1", "API key", "Token", "Basic", "Signature", "None"]
# OAuth2    any OAuth 2.0 flow (auth-code, PKCE, client-credentials, JWT bearer)
# OAuth1    OAuth 1.0a
# API key   static key/secret issued per account or project (header, query or body)
# Token     user/bot-scoped bearer token minted in the UI (PAT, bot token, integration token)
# Basic     HTTP Basic (often key-as-username)
# Signature per-request signing: HMAC, JWT signed with a private key, SigV4
# None      no credentials (local CLI / open-source library)

ACCESS = {
    "free": "Self-serve, free: free plan, free developer account, sandbox/test mode, or open source",
    "trial": "Self-serve, but only a time-limited trial or one-off free credits",
    "paid": "Self-serve sign-up, but API access needs a paid plan/tier",
    "approval": "Self-serve sign-up, but vendor review/approval is needed (developer token, app review, production access)",
    "gated": "Partnership, contact-sales or existing-customer-only; no self-serve path",
    "local": "No credentials at all (local tool / library)",
}

API = ["REST", "GraphQL", "SOAP", "gRPC", "WebSocket", "CLI/library", "MCP-only", "None"]
BREADTH = ["broad", "moderate", "narrow"]          # broad ~ 100+ endpoints / many objects; narrow ~ <15 endpoints
MCP = ["official", "community", "none"]            # official = published/hosted by the vendor

VERDICT = {
    "build-now": "Public docs + self-serve credentials + standard auth. Can ship a toolkit today.",
    "build-with-caveats": "Buildable, but a known friction: paid tier to test, app review for production, per-instance host, request signing, rate-limit policy.",
    "needs-outreach": "Blocked on the vendor: partnership, customer account, or sales-gated credentials.",
    "not-viable": "No usable public API surface today.",
}

FIELDS = [
    "id", "app", "cat", "what",
    "auth", "auth_d",          # list[AUTH], detail
    "access", "access_d",      # ACCESS key, detail
    "api", "breadth", "api_d", # list[API], BREADTH, detail
    "mcp", "mcp_d",            # MCP, detail
    "verdict", "blocker",      # VERDICT key, short blocker phrase
    "ev",                      # evidence URLs: {"auth","access","api","mcp"}
    "conf",                    # high | medium | low  (agent's self-reported confidence)
]

# Fields graded in verification (see verification/RUBRIC.md)
GRADED = ["auth", "access", "api", "mcp", "verdict", "evidence"]
