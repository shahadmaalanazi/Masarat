
"""Masarat Fan Agent: hard constraints + Gemini preference-based plan selection.

The Coordinator calls handle_coordinator_proposal(fan_request, proposal_message).
The LLM is used for genuine ranking among viable trips. It never gets to
waive budget, availability, match preference, or scheduling constraints.
"""
from __future__ import annotations

import json
import os
import re
from functools import wraps
from datetime import datetime
from math import isfinite

from acl import create_acl_message, validate_proposal_message

try:
    from langsmith import traceable
except ImportError:
    # Keep local/offline unit tests runnable without network installations.
    # Real traced AI execution explicitly requires the LangSmith dependency.
    def traceable(*, name=None, run_type="chain"):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if os.getenv("LANGSMITH_TRACING", "false").lower() == "true":
                    raise RuntimeError("LangSmith not installed. Run: pip install -r requirements.txt")
                return fn(*args, **kwargs)
            return wrapped
        return decorator


REQUIRED_REQUEST = {
    "fan_id", "origin_city", "budget_sar", "preferred_match_ids", "priority"
}

REQUIRED_PLAN = {
    "plan_id", "match_id", "city", "match_datetime", "ticket_price_sar",
    "transport_cost_sar", "accommodation_cost_sar",
    "comfort_level", "ticket_available", "transport_available",
    "accommodation_available", "schedule_conflict"
}

PRIORITIES = {"lowest_cost", "comfort"}


def _check_number(value, field, *, min_value=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    if not isfinite(value) or value < min_value:
        raise ValueError(f"{field} must be finite and >= {min_value}")


def validate_fan_request(request):
    if not isinstance(request, dict):
        raise TypeError("fan_request must be a dictionary")

    missing = REQUIRED_REQUEST - request.keys()
    if missing:
        raise ValueError(f"Missing request fields: {sorted(missing)}")

    for field in ("fan_id", "origin_city"):
        if not isinstance(request[field], str) or not request[field].strip():
            raise ValueError(f"{field} must be non-empty text")

    _check_number(request["budget_sar"], "budget_sar", min_value=0)

    if (not isinstance(request["preferred_match_ids"], list)
            or not request["preferred_match_ids"]
            or not all(isinstance(v, str) and v for v in request["preferred_match_ids"])):
        raise ValueError("preferred_match_ids must be a nonempty list of strings")

    if not isinstance(request["priority"], str) or request["priority"] not in PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(PRIORITIES)}")


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise TypeError("Each proposed plan must be a dictionary")

    missing = REQUIRED_PLAN - plan.keys()
    if missing:
        raise ValueError(f"Missing plan fields: {sorted(missing)}")

    for field in ("plan_id", "match_id", "city", "match_datetime"):
        if not isinstance(plan[field], str) or not plan[field].strip():
            raise ValueError(f"{field} must be non-empty text")

    try:
        datetime.fromisoformat(plan["match_datetime"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("match_datetime must be an ISO 8601 datetime string") from exc

    for field in (
        "ticket_price_sar",
        "transport_cost_sar",
        "accommodation_cost_sar",
    ):
        _check_number(plan[field], field)

    if type(plan["comfort_level"]) is not int or not 1 <= plan["comfort_level"] <= 5:
        raise ValueError("comfort_level must be an integer in [1, 5]")

    for field in (
        "ticket_available",
        "transport_available",
        "accommodation_available",
        "schedule_conflict",
    ):
        if type(plan[field]) is not bool:
            raise ValueError(f"{field} must be boolean")


def plan_total(plan):
    return round(sum(plan[field] for field in (
        "ticket_price_sar",
        "transport_cost_sar",
        "accommodation_cost_sar",
    )), 2)


@traceable(name="Masarat.CheckConstraints", run_type="chain")
def assess_plans(fan_request, proposed_plans):
    """Return validated plans enriched with cost, plus explicit rejection reasons."""
    validate_fan_request(fan_request)

    if not isinstance(proposed_plans, list):
        raise TypeError("proposed_plans must be a list")

    eligible, rejected = [], []
    seen_ids = set()

    for raw_plan in proposed_plans:
        validate_plan(raw_plan)

        if raw_plan["plan_id"] in seen_ids:
            raise ValueError(f"Duplicate plan_id: {raw_plan['plan_id']}")

        seen_ids.add(raw_plan["plan_id"])
        plan = {**raw_plan, "total_cost_sar": plan_total(raw_plan)}

        reasons = []

        if plan["match_id"] not in fan_request["preferred_match_ids"]:
            reasons.append("Match is not in the fan's preferred matches")

        if plan["total_cost_sar"] > fan_request["budget_sar"]:
            reasons.append("Budget exceeded")

        if not plan["ticket_available"]:
            reasons.append("Ticket unavailable")

        if not plan["transport_available"]:
            reasons.append("Transport unavailable")

        if not plan["accommodation_available"]:
            reasons.append("Accommodation unavailable")

        if plan["schedule_conflict"]:
            reasons.append("Schedule conflict")

        if reasons:
            rejected.append({
                "plan_id": plan["plan_id"],
                "reasons": reasons,
            })
        else:
            eligible.append(plan)

    return eligible, rejected


class GeminiPlanSelector:
    """LLM used as the agent's decision component, not just as a text explainer."""

    def __init__(self, model=None):
        if model is not None:
            self.llm = model
            self.model_name = "custom-injected-model"
            return

        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("GOOGLE_API_KEY is required for genuine Gemini AI selection")

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install AI packages: pip install -r requirements.txt") from exc

        self.model_name = "gemini-3.5-flash-lite"
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            thinking_level="minimal",
        )

    @traceable(name="Masarat.GeminiSelectPlan", run_type="chain")
    def select(self, request, eligible_plans):
        if not eligible_plans:
            raise ValueError("No eligible plans to choose from")

        selection_data = [
            {
                k: p[k]
                for k in (
                    "plan_id",
                    "total_cost_sar",
                    "comfort_level",
                    "city",
                    "match_id",
                )
            }
            for p in eligible_plans
        ]

        prompt = (
            "You are Masarat Fan Agent, a preference-aware travel decision maker for "
            "a SIMULATED Saudi football tournament. All options below have passed hard checks. "
            "You MUST rank the real listed options based on the fan priority, and choose exactly one. "
            "Priority meanings: lowest_cost=minimize total_cost_sar; "
            "comfort=maximize comfort_level. Use other factors for tie-breaking. "
            "Do not invent new options or modify costs. "
            "Respond with a single JSON object only: "
            '{"plan_id":"existing ID","reason":"short practical justification"}.\n'
            f"Fan: {json.dumps(request, ensure_ascii=False)}\n"
            f"Eligible plans: {json.dumps(selection_data, ensure_ascii=False)}"
        )

        response = self.llm.invoke(prompt)
        content = response.content

        if isinstance(content, str):
            raw_text = content.strip()
        elif isinstance(content, list):
            raw_text = " ".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            ).strip()
        else:
            raw_text = str(content).strip()

        raw_text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            raw_text,
            flags=re.I,
        ).strip()

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemini must return valid JSON, got: {raw_text[:200]}"
            ) from exc

        valid_ids = {p["plan_id"] for p in eligible_plans}

        if not isinstance(parsed, dict) or parsed.get("plan_id") not in valid_ids:
            raise ValueError("Gemini chose a plan_id not in eligible plans")

        if not isinstance(parsed.get("reason"), str) or not parsed["reason"].strip():
            raise ValueError("Gemini must explain its choice")

        return {
            "plan_id": parsed["plan_id"],
            "reason": parsed["reason"].strip(),
        }


@traceable(name="Masarat.FanAgent", run_type="chain")
def fan_agent(fan_request, proposed_plans, selector=None):
    """Return fan_decision and ACL messages. Coordinator consumes this result.

    For a real run, leave selector=None: Gemini is initialized automatically.
    For an offline logic test, inject a test selector; that is NOT a real AI run.
    """
    eligible, rejected = assess_plans(fan_request, proposed_plans)

    messages = []

    if not eligible:
        decision = {
            "status": "REFUSE",
            "plan_id": None,
            "total_cost_sar": None,
            "reason": "No proposed plan meets all mandatory constraints.",
            "request_alternative": True,
            "selection_method": "hard_constraints",
        }

    elif len(eligible) == 1:
        selected = eligible[0]

        decision = {
            "status": "ACCEPT",
            "plan_id": selected["plan_id"],
            "total_cost_sar": selected["total_cost_sar"],
            "reason": "Only one plan meets all mandatory constraints.",
            "request_alternative": False,
            "selection_method": "single_eligible_plan",
        }

    else:
        try:
            active_selector = selector if selector is not None else GeminiPlanSelector()
            choice = active_selector.select(fan_request, eligible)

            valid_ids = {p["plan_id"] for p in eligible}

            if not isinstance(choice, dict) or choice.get("plan_id") not in valid_ids:
                raise ValueError("AI selector returned an ineligible or invented plan_id")

            if not isinstance(choice.get("reason"), str) or not choice["reason"].strip():
                raise ValueError("AI selector must return a nonempty reason")

            selected = next(
                p for p in eligible
                if p["plan_id"] == choice["plan_id"]
            )

        except Exception as exc:
            decision = {
                "status": "ERROR",
                "plan_id": None,
                "total_cost_sar": None,
                "reason": "AI selection could not be completed; no travel plan was accepted.",
                "request_alternative": False,
                "selection_method": "ai_error",
                "error_code": "AI_SELECTION_FAILED",
                "error_type": type(exc).__name__,
            }

        else:
            decision = {
                "status": "ACCEPT",
                "plan_id": selected["plan_id"],
                "total_cost_sar": selected["total_cost_sar"],
                "reason": choice["reason"].strip(),
                "request_alternative": False,
                "selection_method": (
                    "gemini_ai"
                    if (
                        selector is None
                        or (
                            isinstance(selector, GeminiPlanSelector)
                            and selector.model_name != "custom-injected-model"
                        )
                    )
                    else "test_selector"
                ),
            }

    messages.append(create_acl_message(
        sender="FanAgent",
        receiver="CoordinatorAgent",
        performative="INFORM" if decision["status"] == "ERROR" else decision["status"],
        content={
            "fan_decision": decision,
            "rejected_plans": rejected,
        },
        conversation_id=fan_request["fan_id"],
    ))

    return {
        "fan_decision": decision,
        "eligible_plan_ids": [p["plan_id"] for p in eligible],
        "rejected_plans": rejected,
        "acl_messages": messages,
    }


def make_fan_request_message(fan_request):
    validate_fan_request(fan_request)

    return create_acl_message(
        "FanAgent",
        "CoordinatorAgent",
        "REQUEST",
        {"fan_request": fan_request},
        fan_request["fan_id"],
    )


def handle_coordinator_proposal(fan_request, proposal_message, selector=None):
    """Team integration entrypoint for a CoordinatorAgent PROPOSE message."""
    validate_fan_request(fan_request)

    if proposal_message.get("conversation_id") != fan_request["fan_id"]:
        raise ValueError("Conversation ID does not match the fan")

    plans = validate_proposal_message(proposal_message)

    return fan_agent(fan_request, plans, selector=selector)
