# Agent Black Box 3.2 — implementation matrix

Announcement context: [OpenAI DevDay 2026 recap](https://openai.com/index/devday-2026-recap/). Verified locally October 10, 2026. The dashboard reads saved evidence from ignored local validation reports; it does not probe paid services on load.

| Capability | Actual implementation | Evidence and status | Account access |
|---|---|---|---|
| Planner function calling | Official Responses API, configured `gpt-6.1-sol`, standard tier | Original three scenarios passed real API validation | Required |
| Real-time progress | Responses `stream=True` SSE; public lifecycle, proposals, policy, execution, completed public text | Live streamed $15,000 event returned REVIEW; no payment execution | Required |
| Planner / Policy Advisor / Audit Analyst | Application-managed logical roles, independent Responses requests; advisors have no tools | Both specialists passed real requests; no hosted orchestration implied | Required for live summaries |
| Local discovery | Permission-filtered schema/metadata registry | Automated tests; discoverability never grants permission | No |
| Native discovery | Responses `tool_search` with client execution and `tool_search_output`; local scoped resolver | Actual two-request exchange passed; no execution in discovery | Required |
| Local context management | Deterministic application-level audit projection; exact IDs, decisions, approvals, unresolved actions | Automated tests; full audit retained | No |
| Native compaction | `responses.compact`; canonical output retained, exact local audit state appended | Real request and subsequent secured Responses invoice continuation passed; encrypted output never displayed | Required |
| MCP protocol | Official MCP Python SDK 2.3; real stdio subprocess/client handshake; invoice, ticket, payment proposal | Actual protocol `2026-07-28` exchange passed; payment stayed pending | No OpenAI key needed |
| Event-driven workflow | Synthetic Event Simulator; strict payload validation and durable SQLite claims | Live event-to-streaming workflow passed; concurrent dedup tests passed | Only for live planner |
| Native MCP Events | Experimental trigger/event extension is not integrated | Not enabled; [working-group status](https://modelcontextprotocol.io/community/working-groups/triggers-events) reviewed | Integration would require compatible host/extension |
| Hosted Agents API | Official REST sessions, `required_actions`, tool-result events; `environment.type=none` | GET access HTTP 200; real hosted invoice function result submitted | Required |
| Decisions API | Official REST `POST /v1/decisions`, separate Luna advisory adapter | Real HTTP 200; three scenarios classified LOW/HIGH/HIGH. Gateway still ALLOW/BLOCK/REVIEW | API access; HTTPX bypasses 2.x SDK limitation |
| Sites showcase | Separate buildless static HTML/JavaScript candidate | Frontend-only simulated risk and audit; no API calls or publication | Hosting compatibility/entitlement not tested |
| Computer use | No adapter enabled | Skipped: no isolated synthetic computer environment configured; no account eligibility claimed | Required plus isolation |
| Human approvals | Existing deterministic gateway, exact argument digest, single-use SQLite transaction | Baseline and concurrency/tampering tests pass | No (local single-user demo) |
| Demo reset | Separate `data/demo.sqlite3`; fixed allowlist of synthetic tables | Reset-isolation test passes; normal audit untouched | No |
| Demo Studio | Streamlit landing page, three secured scenarios, trace, exact payment approval, safe report export | 89 automated tests pass; offline payment screenshot shows REVIEW and pending execution | Live mode requires API access |
| Studio reset | Separate `data/studio.sqlite3`; fixed allowlist, refuses active runs | Isolation and active-run reset tests pass; normal audit retained | No |

## Official API sources

- [Responses streaming](https://developers.openai.com/api/docs/guides/streaming-responses)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Context compaction](https://developers.openai.com/api/docs/guides/compaction)
- [Hosted Agents quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart)
- [Hosted function actions and tool results](https://developers.openai.com/api/docs/guides/agents-api/tools/functions)
- [Decisions](https://developers.openai.com/api/docs/guides/decisions)
- [Computer use](https://developers.openai.com/api/docs/guides/tools-computer-use)
- [Official MCP SDK client](https://py.sdk.modelcontextprotocol.io/client/)

Saved live results show integration evidence, not a guarantee of future project eligibility. All enterprise effects remain synthetic. Astra, Fast Mode, and Ultrafast are never selected.
