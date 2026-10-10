"""Documented Responses SSE adapter; only public completed data reaches traces."""
from datetime import datetime, timezone
import threading
import uuid
from agent import run_agent
from audit import redact_text

class Cancelled(Exception):
    pass

class RunTrace:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.events = []
        self.result = None
        self.actions = []
        self.done = False
        self.stream_counts = {}
        self.usage = []
        self.add("run_started", "Planner Agent")

    def add(self, kind, detail):
        with self.lock:
            self.events.append({"timestamp": datetime.now(timezone.utc).isoformat(), "run_id": self.id,
                                "event": kind, "detail": redact_text(detail)})

    def snapshot(self):
        with self.lock:
            return list(self.events)

class StreamingClient:
    def __init__(self, client, trace):
        self.client, self.trace = client, trace
        self.responses = self

    def create(self, **kwargs):
        if self.trace.cancel.is_set():
            raise Cancelled("Run cancelled before API request")
        self.trace.add("api_started", "Responses SSE · standard tier")
        stream = self.client.responses.create(**kwargs, stream=True)
        final = None
        try:
            for event in stream:
                with self.trace.lock:
                    self.trace.stream_counts[event.type] = self.trace.stream_counts.get(event.type, 0) + 1
                if self.trace.cancel.is_set():
                    raise Cancelled("Run cancelled; no further proposals will execute")
                if event.type == "response.output_item.added" and event.item.type == "function_call":
                    self.trace.add("tool_proposal", event.item.name)
                elif event.type == "response.output_text.done":
                    self.trace.add("public_response", event.text)
                elif event.type == "response.completed":
                    final = event.response
                    usage = getattr(final, "usage", None)
                    if usage is not None:
                        with self.trace.lock:
                            self.trace.usage.append({k: getattr(usage, k, None) for k in ("input_tokens", "output_tokens", "total_tokens")})
                    self.trace.add("api_completed", f'Tokens: {getattr(usage, "total_tokens", "unknown")}')
                elif event.type in ("error", "response.failed", "response.incomplete"):
                    raise RuntimeError("Responses stream ended with " + event.type)
            if final is None:
                raise RuntimeError("Responses stream closed without a completed response")
            return final
        finally:
            stream.close()

class TracedGateway:
    def __init__(self, gateway, trace):
        self.gateway, self.trace = gateway, trace

    def propose(self, request, tool, args, source="live"):
        if self.trace.cancel.is_set():
            raise Cancelled("Cancelled before policy evaluation")
        self.trace.add("policy_check", tool)
        row = self.gateway.propose(request, tool, args, source)
        self.trace.actions.append(row)
        self.trace.add("policy_decision", f'{row["id"]} · {row["decision"]} · {row["reason"]}')
        self.trace.add("execution", row["execution"])
        if row["approval"] == "pending":
            self.trace.add("approval_pending", row["id"])
        return row

def execute_streaming(request, gateway, trace, client=None, context=None, finalize=True):
    try:
        if client is None:
            from openai import OpenAI
            client = OpenAI(timeout=30, max_retries=0)
        trace.result = run_agent(request, TracedGateway(gateway, trace), client=StreamingClient(client, trace), context=context)
        if trace.cancel.is_set():
            trace.add("cancelled", "No further actions. Already committed actions remain audited.")
        elif any(r["tool"] == "agent_api_failure" for r in trace.result["actions"]):
            trace.add("api_error", trace.result["message"])
        else:
            trace.add("run_completed", "Gateway outcomes recorded")
    except Cancelled:
        trace.result = {"mode": "live", "message": "Run cancelled; committed actions remain audited.", "actions": list(trace.actions)}
        trace.add("cancelled", trace.result["message"])
    except Exception:
        trace.result = {"mode": "live", "message": "Run failed safely; no offline fallback.", "actions": list(trace.actions)}
        trace.add("api_error", trace.result["message"])
    finally:
        if finalize:
            from sessions import save_run
            try:
                save_run(gateway, trace)
            except Exception:
                trace.add("persistence_error", "Run trace save failed; action audits remain in gateway storage.")
            finally:
                trace.done = True

def start_streaming(request, gateway, context=None):
    trace = RunTrace()
    thread = threading.Thread(target=execute_streaming, args=(request, gateway, trace), kwargs={"context": context}, daemon=True)
    thread.start()
    return trace
