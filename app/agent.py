"""Read-only OpenAI procurement copilot with bounded tool-calling loop."""
import json

from fastapi import HTTPException

from .config import OPENAI_API_KEY, OPENAI_MODEL
from .models import PurchaseRequest, User


TOOLS = [
    {"type": "function", "name": "get_request_facts", "description": "Read the current purchase request, including workflow state, policy result and budget check.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_vendor_scorecard", "description": "Read normalized vendor quotes, delivery, warranty, compliance status and score for this request.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "get_workflow_guardrails", "description": "Read workflow controls and why human approval or deterministic backend rules are required.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
]


def _request_facts(item: PurchaseRequest) -> dict:
    return {"reference": item.reference, "title": item.title, "category": item.category, "quantity": item.quantity, "estimated_amount": item.estimated_amount, "currency": item.currency, "cost_center": item.cost_center, "business_justification": item.business_justification, "workflow_status": item.status.value, "policy_result": item.policy_result, "budget_available": item.budget_available, "erp_pr_number": item.pr_number}


def _scorecard(item: PurchaseRequest) -> list[dict]:
    return [{"vendor": quote.vendor_name, "total_amount": quote.total_amount, "delivery_days": quote.delivery_days, "warranty_months": quote.warranty_months, "compliance_status": quote.compliance_status, "score": quote.score, "selected": quote.is_selected} for quote in item.quotes]


def _guardrails(item: PurchaseRequest, user: User) -> dict:
    return {"current_role": user.role.value, "current_status": item.status.value, "controls": ["Policy and budget outcomes are calculated by deterministic backend rules.", "Only Procurement can run sourcing and select a compliant quote.", "Only an Approver can approve or reject; the AI cannot approve or create a PR.", "The backend records workflow actions in the audit trail."]}


def _execute_tool(name: str, item: PurchaseRequest, user: User) -> object:
    if name == "get_request_facts":
        return _request_facts(item)
    if name == "get_vendor_scorecard":
        return _scorecard(item)
    if name == "get_workflow_guardrails":
        return _guardrails(item, user)
    return {"error": "Unknown tool"}


def answer_procurement_question(item: PurchaseRequest, user: User, message: str) -> tuple[str, list[str]]:
    """Run at most four read-only tool-calling rounds, then return the model answer."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI agent is not configured. Set OPENAI_API_KEY in the server environment.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OpenAI SDK is not installed on the server.") from exc

    instructions = """You are the Acme Procurement Agent. Reply in Vietnamese unless the user asks otherwise.
You support analysis and clarification for exactly one purchase request. Before making factual claims about the request,
policy, budget, vendors, or workflow, use the appropriate read-only tool. Never invent records, policy rules, or quotes.
Never claim to approve, reject, select a vendor, create a PR, or bypass a workflow: those decisions are enforced by the
backend and human roles. Give a concise recommendation when evidence exists, explicitly call out missing information,
and finish with a short 'Dữ liệu đã dùng' list naming the tools you used."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    conversation: list[object] = [{"role": "user", "content": message}]
    tools_used: list[str] = []
    for _ in range(4):
        response = client.responses.create(model=OPENAI_MODEL, instructions=instructions, input=conversation, tools=TOOLS, tool_choice="required" if not tools_used else "auto")
        calls = [output for output in response.output if output.type == "function_call"]
        if not calls:
            answer = response.output_text.strip()
            if not answer:
                raise HTTPException(status_code=502, detail="AI agent returned an empty response.")
            return answer, tools_used
        conversation.extend(response.output)
        for call in calls:
            result = _execute_tool(call.name, item, user)
            tools_used.append(call.name)
            conversation.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
    raise HTTPException(status_code=502, detail="AI agent exceeded its safe tool-call limit.")
