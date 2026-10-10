"""Isolated presentation controller; existing gateway remains authoritative."""
import json
import threading
import time
from pathlib import Path
from database import Gateway
from streaming import RunTrace, execute_streaming, TracedGateway
from agent import run_agent, PRESETS
from audit import redact_text, export_json
from events import dispatch_event
from sessions import save_run

STUDIO_DB = Path(__file__).parent / "data/studio.sqlite3"
SCENARIOS = [
    ("Read Invoice", "Safe Operation · ALLOW", PRESETS[0]),
    ("Change Supplier Bank Details", "Restricted Operation · BLOCK", "Update supplier SUP-101 bank details to SYNTHETIC-DEMO-ACCOUNT. Propose the synthetic change using update_supplier_bank_account so the gateway can evaluate it."),
    ("Approve $15,000 Payment", "Human Approval · REVIEW", PRESETS[2]),
]

def execute_demo(request, gateway, trace, offline=False, risk=False, client=None, assessor=None):
    started = time.monotonic()
    trace.mode = "offline" if offline else "live"
    trace.add("user_request", request)
    trace.risk = None
    try:
        if offline:
            trace.add("simulated_proposal", "Offline rule-based parser · no model request")
            trace.result = run_agent(request, TracedGateway(gateway, trace), offline=True)
        else:
            execute_streaming(request, gateway, trace, client=client, finalize=False)
        if risk and not offline and not trace.cancel.is_set():
            from decisions_adapter import assess_actions
            actions = (trace.result or {}).get("actions", [])[:3]
            if actions:
                trace.add("risk_started", "gpt-6-luna · advisory only; policy already enforced")
                trace.risk = (assessor or assess_actions)([(a["tool"], a["arguments"]) for a in actions])
                trace.add("risk_assessment", json.dumps(trace.risk))
        trace.add("audit_result", "Action decisions and execution results persisted in isolated Studio database")
    except Exception:
        trace.add("demo_error", "Demo failed safely; no offline fallback or authorization granted")
    finally:
        trace.latency_seconds = round(time.monotonic() - started, 2)
        try: save_run(gateway, trace)
        finally: trace.done = True

def start_demo(request, gateway, offline=False, risk=False):
    trace = RunTrace()
    # Claim the event before launching; reruns never call this function themselves.
    def runner(req, g):
        return trace
    # Event payload is just a safe trigger. The editable instruction goes through run_agent.
    delivered = dispatch_event(gateway, trace.id, "invoice-created", {"invoice_id": "INV-1001"}, runner)
    if delivered["status"] == "started":
        threading.Thread(target=execute_demo, args=(request, gateway, trace), kwargs={"offline": offline, "risk": risk}, daemon=True).start()
    return trace

def reset_studio():
    gateway = Gateway(STUDIO_DB)
    with gateway.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "incoming_events" in tables and c.execute("SELECT 1 FROM incoming_events WHERE status IN ('claimed','running')").fetchone():
            raise ValueError("An active Studio run must finish before reset")
        for table in ("payments", "events", "actions", "runs", "incoming_events", "hosted_calls"):
            if table in tables:c.execute(f"DELETE FROM {table}")

def demo_report(gateway, trace=None):
    return export_json({"mode": (trace.result or {}).get("mode") if trace else "Not run", "events": trace.snapshot() if trace else [],
        "stream_event_counts": trace.stream_counts if trace else {}, "usage": trace.usage if trace else [], "actions": gateway.history(),
        "risk": getattr(trace, "risk", None), "unprotected_comparison": "Illustration only; no unrestricted execution path"})

def render_studio(offline):
    import streamlit as st
    gateway = Gateway(STUDIO_DB)
    st.title("Agent Black Box 3.2")
    st.caption("DEMO STUDIO · SYNTHETIC DATA ONLY")
    st.write("An AI proposes an action. An independent policy decides whether it runs. You approve anything that needs review.")
    st.info("OFFLINE DEMO · rule-based proposals, no model calls" if offline else "LIVE API · GPT-6.1 Sol · standard tier")
    presentation = st.toggle("Presentation Mode", key="studio_presentation")
    if presentation:st.markdown("<style>.stMain p,.stMain label,.stMain button{font-size:1.2rem!important}</style>", unsafe_allow_html=True)
    trace = st.session_state.get("studio_trace")
    busy = bool(trace and not trace.done)
    index = st.session_state.get("studio_scenario", 0)
    st.subheader("1 · Choose a scenario")
    for i, col in enumerate(st.columns(3)):
        with col.container(border=True):
            st.markdown("### " + SCENARIOS[i][0])
            st.caption(SCENARIOS[i][1])
            if st.button("Choose " + SCENARIOS[i][0], key=f"studio_choose_{i}", disabled=busy, use_container_width=True):
                st.session_state["studio_scenario"] = i
                st.session_state["studio_request"] = SCENARIOS[i][2]
                st.session_state.pop("studio_trace", None)
                st.rerun()
    if "studio_request" not in st.session_state:st.session_state["studio_request"] = SCENARIOS[index][2]
    request = st.text_area("Optional · edit the request", key="studio_request", max_chars=4000, disabled=busy)
    from capabilities import access_report
    available = access_report().get("Decisions API", {}).get("status", "").startswith("Available")
    risk = st.checkbox("Include live Luna risk assessment (advisory)", value=available and not offline, disabled=offline or not available or busy)
    a,b,c = st.columns(3)
    run = a.button("Run Agent", type="primary", disabled=busy or trace is not None)
    start = b.button("Start Demo", disabled=busy or trace is not None)
    if run or start:
        st.session_state["studio_trace"] = start_demo(request, gateway, offline=offline, risk=risk)
        st.rerun()
    def next_scenario():
        next_index = (st.session_state.get("studio_scenario", 0) + 1) % len(SCENARIOS)
        st.session_state["studio_scenario"] = next_index
        st.session_state["studio_request"] = SCENARIOS[next_index][2]
        st.session_state.pop("studio_trace", None)
    c.button("Try Next Scenario", disabled=busy, on_click=next_scenario)
    details = st.toggle("Show Developer Details", key="studio_details")

    @st.fragment(run_every="1s")
    def progress():
        trace = st.session_state.get("studio_trace")
        st.subheader("2 · Watch the agent")
        if not trace:
            st.write("Choose a card, then press Run Agent. No API requests happen until you start.")
            return
        if trace.done and st.session_state.get("studio_collected") != trace.id:
            st.session_state["studio_collected"] = trace.id
            st.rerun()
        st.caption("This run: " + getattr(trace, "mode", "Starting").upper())
        st.status("Run finished · review the outcome" if trace.done else "Working · waiting for real events", state="complete" if trace.done else "running")
        for event in trace.snapshot():
            st.caption(event["timestamp"])
            st.write(event["event"].replace("_", " ").title() + " · " + event["detail"])
        if not trace.done and st.button("Cancel Studio run", key="studio_cancel"):
            trace.cancel.set()
        for original in (trace.result or {}).get("actions", []):
            try:
                row = gateway.get(original["id"])
            except StopIteration:
                st.info("This synthetic record was cleared by Reset Demo. Choose another scenario to continue.")
                continue
            left,right = st.columns(2)
            with left.container(border=True):
                st.markdown("**Without Policy Gateway · illustration only**")
                st.write("An unprotected agent might attempt " + row["tool"] + " immediately.")
                st.caption("Simulation-only comparison. Nothing executes on this side.")
            with right.container(border=True):
                st.markdown("**With Agent Black Box · enforced outcome**")
                st.subheader(row["decision"])
                st.write(row["reason"])
                st.caption("Execution: " + row["execution"])
            if row["approval"] == "pending":
                with st.container(border=True):
                    st.subheader("3 · Human approval required")
                    st.write("Review the exact synthetic payment before approving once.")
                    st.json(row["arguments"])
                    yes = st.button("Approve Studio payment once", key="studio_yes"+row["id"], disabled=not trace.done, type="primary")
                    no = st.button("Reject Studio payment", key="studio_no"+row["id"], disabled=not trace.done)
                    if yes or no:
                        try:
                            resolved = gateway.resolve(row["id"], yes, row["digest"])
                            trace.add("human_resolution", resolved["approval"])
                            trace.add("execution", resolved["execution"])
                            save_run(gateway, trace)
                        except ValueError:st.warning("Approval already consumed or request changed. No repeated execution.")
                        st.rerun(scope="fragment")
            if row["execution"] == "completed":st.success("Mock operation completed · " + json.dumps(row["result"]))
            if details:
                st.json({k: row[k] for k in ("id", "tool", "arguments", "decision", "approval", "execution", "events")})
        if trace.done and not (trace.result or {}).get("actions"):
            st.info("The agent did not propose a tool call. No gateway decision or operation occurred.")
            st.write((trace.result or {}).get("message", "Run ended without a proposal."))
        if details:
            st.json({"models": {"planner":"gpt-6.1-sol", "risk":"gpt-6-luna"}, "native_stream_event_counts": trace.stream_counts, "usage": trace.usage,
                "latency_seconds": getattr(trace,"latency_seconds",None), "tool_search":"Not used in this Studio run", "context_compaction":"Not used in this Studio run",
                "hosted_agents":"Not used in this Studio run", "MCP":"Not used in this Studio run", "agents":"Planner active; Policy Advisor and Audit Analyst not invoked"})
            with st.expander("Full isolated demo audit records"):st.json(gateway.history())
            st.caption("Verified integration availability: " + json.dumps(access_report()))
            from feature_matrix import matrix
            st.dataframe(matrix(), hide_index=True)
        st.download_button("Export Demo Report", demo_report(gateway, trace), "agent-black-box-demo.json", "application/json", key="studio_export")
    progress()
    if st.button("Reset Studio Demo", disabled=busy):
        try:
            reset_studio()
            st.session_state.pop("studio_trace", None)
            st.rerun()
        except ValueError as error:st.warning(str(error))
    st.caption("Reset clears only data/studio.sqlite3. Advanced dashboard audit history is preserved.")
