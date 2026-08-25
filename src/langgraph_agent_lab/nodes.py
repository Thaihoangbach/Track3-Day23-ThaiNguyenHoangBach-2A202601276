"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event


class ClassificationResult(BaseModel):
    """Structured output schema for classify_node."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="Intent category for the support query."
    )
    risk_level: Literal["low", "high"] = Field(
        description="'high' for routes with side effects (risky), 'low' otherwise."
    )


CLASSIFY_PROMPT = """You are the intent router for a customer support agent.
Classify the customer query into exactly one route.

Routes, in priority order (check risky first, simple last):
- risky: actions with side effects — refunds, deletions, cancellations, sending emails
- tool: information lookups — order status, tracking, search queries
- missing_info: vague or incomplete queries lacking actionable context
- error: system failures — timeouts, crashes, service unavailable
- simple: general questions answerable without tools or actions

Query: {query}"""


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.

    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***

    Use .with_structured_output() or equivalent to get reliable enum classification.
    The LLM should classify into one of: simple, tool, missing_info, risky, error.

    Hints:
    - See llm.py for the get_llm() helper
    - Use Pydantic model or TypedDict with .with_structured_output()
    - Set risk_level to "high" for risky routes, "low" otherwise
    - Priority guide: risky > tool > missing_info > error > simple

    Return: {"route": str, "risk_level": str, "events": [make_event(...)]}
    """
    query = state.get("query", "")
    llm = get_llm().with_structured_output(ClassificationResult)
    result: ClassificationResult = llm.invoke(CLASSIFY_PROMPT.format(query=query))
    return {
        "route": result.route,
        "risk_level": result.risk_level,
        "events": [make_event("classify", "completed", f"classified as {result.route}", risk_level=result.risk_level)],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.

    Requirements:
    - Read current attempt count from state
    - If route is "error" and attempt < 2: return error result (string containing "ERROR")
    - Otherwise: return a mock success result string
    - Append result to tool_results list

    Return: {"tool_results": [result_string], "events": [make_event(...)]}
    """
    query = state.get("query", "")
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    if route == "error" and attempt < 2:
        result = f"ERROR: transient failure processing '{query[:60]}' (attempt {attempt})"
    else:
        result = f"OK: tool lookup succeeded for '{query[:60]}'"
    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", "tool executed", route=route, attempt=attempt)],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.

    SHOULD use LLM-as-judge for bonus points. Heuristic (e.g., check for "ERROR" substring)
    is acceptable for base score.

    Requirements:
    - Read the latest entry from tool_results
    - Set evaluation_result to "needs_retry" or "success"
    - This field drives route_after_evaluate conditional edge

    Note: You may need to add 'evaluation_result' to AgentState if not present.

    Return: {"evaluation_result": str, "events": [make_event(...)]}
    """
    tool_results = state.get("tool_results", []) or []
    latest = tool_results[-1] if tool_results else ""
    evaluation = "needs_retry" if "ERROR" in latest else "success"
    return {
        "evaluation_result": evaluation,
        "events": [make_event("evaluate", "completed", f"evaluation={evaluation}")],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.

    *** MUST use a real LLM call — hardcoded strings will lose points. ***

    The LLM should generate a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - original query

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "")
    tool_results = state.get("tool_results", []) or []
    approval = state.get("approval")

    context_parts = [f"Customer query: {query}"]
    if tool_results:
        context_parts.append("Tool results:\n" + "\n".join(tool_results))
    if approval:
        context_parts.append(
            f"Approval decision: approved={approval.get('approved')}, comment={approval.get('comment')}"
        )

    prompt = (
        "You are a support agent replying to a customer. Write a concise, professional final "
        "answer grounded ONLY in the context below. Do not invent facts not present in it.\n\n"
        + "\n\n".join(context_parts)
    )
    llm = get_llm()
    response = llm.invoke(prompt)
    final_answer = response.content if hasattr(response, "content") else str(response)
    return {
        "final_answer": final_answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.

    Note: You may need to add 'pending_question' to AgentState if not present.

    Return: {"pending_question": str, "final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "")
    llm = get_llm()
    prompt = (
        "The following customer support query is too vague to act on. Write ONE short, "
        "specific clarifying question to ask the customer (no preamble).\n\n"
        f"Query: {query}"
    )
    response = llm.invoke(prompt)
    question = response.content if hasattr(response, "content") else str(response)
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "clarification requested")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.

    Note: You may need to add 'proposed_action' to AgentState if not present.

    Return: {"proposed_action": str, "events": [make_event(...)]}
    """
    query = state.get("query", "")
    action_description = (
        f"Requested action: \"{query[:120]}\". This involves a side effect "
        "(e.g. refund, deletion, or outbound email) and requires human approval before execution."
    )
    return {
        "proposed_action": action_description,
        "events": [make_event("risky_action", "completed", "risky action prepared")],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt() for real HITL.

    Return: {"approval": {"approved": bool, "reviewer": str, "comment": str}, "events": [make_event(...)]}
    """
    # Extension (Phase 5): if os.getenv("LANGGRAPH_INTERRUPT") == "true", replace this mock
    # with `from langgraph.types import interrupt; decision = interrupt({...})` for real HITL.
    proposed_action = state.get("proposed_action", "")
    approval = {
        "approved": True,
        "reviewer": "mock-reviewer",
        "comment": f"Auto-approved: {proposed_action[:80]}",
    }
    return {
        "approval": approval,
        "events": [make_event("approval", "completed", "approval decision recorded", approved=True)],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.

    Requirements:
    - Read current attempt from state, increment by 1
    - Add an error message to errors list
    - Return updated attempt count

    Return: {"attempt": int, "errors": [str], "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0) + 1
    tool_results = state.get("tool_results", []) or []
    latest_error = tool_results[-1] if tool_results else "unknown failure"
    return {
        "attempt": attempt,
        "errors": [f"retry #{attempt}: {latest_error}"],
        "events": [make_event("retry", "completed", f"retry attempt {attempt}")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0)
    final_answer = (
        "We were unable to complete this request after multiple attempts "
        f"({attempt} retries). It has been escalated to our team for manual review."
    )
    return {
        "final_answer": final_answer,
        "events": [make_event("dead_letter", "completed", "max retries exceeded", attempt=attempt)],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.

    Return: {"events": [make_event("finalize", "completed", "workflow finished")]}
    """
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
