"""Shared-budget validation. A one-way ticket is not a round trip."""
from langsmith import traceable
from acl import create_acl_message


@traceable(name="SharedBudgetChecker")
def check_shared_budget(fan_request, travel_result, hotel_result,
                        ticket_price_sar=None):
    budget = fan_request["budget_sar"]
    travel = travel_result.get("recommended_option")
    hotel = hotel_result.get("recommended_option")
    one_way = travel.get("simulated_oneway_cost_sar") if travel else None
    stay = hotel.get("accommodation_cost_sar") if hotel else None
    round_trip = travel.get("transport_cost_sar") if travel else None

    if travel is None or hotel is None:
        status, total = "NO_COMPLETE_PLAN", None
    elif round_trip is None or stay is None or ticket_price_sar is None:
        status, total = "PENDING_PRICE_DATA", None
    else:
        total = round_trip + stay + ticket_price_sar
        status = "WITHIN_BUDGET" if total <= budget else "OVER_BUDGET"

    # Partial known amounts for an estimate, never a confirmed grand total.
    known_simulated = sum(x for x in (one_way, stay, ticket_price_sar)
                          if isinstance(x, (int, float)))
    msg = create_acl_message("CoordinatorAgent", "FanAgent", "INFORM", {
        "budget_status": status, "confirmed_total_sar": total,
        "fan_budget_sar": budget,
        "known_partial_simulated_sar": known_simulated,
        "missing_round_trip": round_trip is None,
    }, fan_request["fan_id"])
    return {"status": status, "confirmed_total_sar": total,
            "fan_budget_sar": budget,
            "known_partial_simulated_sar": known_simulated,
            "acl_messages": [msg]}
