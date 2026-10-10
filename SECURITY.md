# Security and public-demo scope

This is a local hackathon prototype with synthetic business records, not a production approval service. Keep Streamlit bound to localhost. The approval UI has no authenticated reviewer identity; never expose it as an enterprise payment endpoint.

The deterministic gateway is the sole authorization authority. Model assessments and summaries grant no permissions. Unknown tools fail closed; supplier banking changes are blocked; payments above USD 10,000 require exact-bound, single-use approval. MCP tools and hosted-agent proposals use the same gateway. Computer use is disabled.

Credentials belong only in ignored `.env` or server-managed secret storage. `.env.example` contains a placeholder. Do not place credentials in browser code, screenshots, exported evidence, or Git history. Runtime SQLite data, logs, environment folders and local verification reports are excluded from publication; `data/sample_invoices.json` is an intentionally synthetic fixture.

Before publication, scan both current files and every reachable Git object. Pattern scans cannot guarantee absence of all sensitive data. Rotate any credential ever exposed, even after removing it from a working file. Publish only a reviewed clean-history snapshot; never blindly push an older local history that contained credentials.

If a secret is discovered, report the affected file and provider without reproducing its value. Do not enable production integrations or weaken approval enforcement to make a demo pass.
