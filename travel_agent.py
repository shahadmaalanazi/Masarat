
import json
from langsmith import traceable
from langchain_google_genai import ChatGoogleGenerativeAI
from acl import create_acl_message
from travel_inventory_search import find_transport_options


@traceable(name="TravelAgent")
def travel_agent(
    fan_request,
    match_info,
    request_type="REQUEST"
):
    if request_type not in ("REQUEST", "CFP"):
        raise ValueError("Invalid request type")

    fan_id = fan_request["fan_id"]
    origin = fan_request["origin_city"]
    destination = match_info["city"]
    priority = fan_request.get("priority", "lowest_cost")
    budget = fan_request.get("transport_budget_sar", fan_request["budget_sar"])
    travel_date = match_info.get("travel_date")

    messages = [
        create_acl_message(
            "CoordinatorAgent",
            "TravelAgent",
            request_type,
            {
                "origin": origin,
                "destination": destination,
                "travel_date": travel_date,
                "priority": priority,
                "transport_budget_sar": budget
            },
            fan_id
        )
    ]

    if travel_date is None:
        messages.append(create_acl_message(
            "TravelAgent",
            "CoordinatorAgent",
            "INFORM",
            {"status": "PENDING_TRAVEL_DATE"},
            fan_id
        ))

        return {
            "transport_options": [],
            "recommended_option": None,
            "status": "PENDING_TRAVEL_DATE",
            "llm_used": False,
            "acl_messages": messages
        }

    search_result = find_transport_options(
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        budget=budget,
        priority=priority
    )

    options = search_result["options"]

    if not options:
        messages.append(create_acl_message(
            "TravelAgent",
            "CoordinatorAgent",
            "REFUSE",
            {
                "status": "NO_AVAILABLE_OPTION",
                "reason": "No matching simulated seat found"
            },
            fan_id
        ))

        return {
            "transport_options": [],
            "recommended_option": None,
            "status": "NO_AVAILABLE_OPTION",
            "llm_used": False,
            "acl_messages": messages
        }

    selected = options[0]
    llm_used = False

    # Gemini compares several available options.
    if len(options) > 1:
        prompt = f"""
        You are Masarat Travel Agent.

        Priority: {priority}
        Simulated travel options:
        {json.dumps(options)}

        Choose the most suitable option considering
        the fan priority and available information.

        Do not invent facts, schedules, or prices.
        Do not claim a confirmed round-trip booking.

        Respond ONLY with a JSON object:
        {{"id": "service_id", "seat_class": "class"}}
        """

        llm_error = None
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0
            )
            response = llm.invoke(prompt)
            llm_used = True
            raw = str(response.content).strip()
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "").strip()
            choice = json.loads(raw)

            chosen = next(
                (
                    x for x in options
                    if x["id"] == choice["id"]
                    and x["seat_class"] == choice["seat_class"]
                ),
                None
            )

            if chosen is not None:
                selected = chosen

        except Exception as exc:
            # Keep the simulation running if the model/API fails.
            # Fallback uses the already ranked options; no model success is claimed.
            llm_error = str(exc)
            selected = options[0]

    # This is a simulated one-way offer.
    # Round-trip cost remains unknown.
    status = "SIMULATED_ONEWAY_OFFER"

    messages.append(create_acl_message(
        "TravelAgent",
        "CoordinatorAgent",
        "PROPOSE",
        {
            "status": status,
            "recommended": selected,
            "transport_options": options,
            "round_trip_complete": False
        },
        fan_id
    ))

    return {
        "transport_options": options,
        "recommended_option": selected,
        "status": status,
        "llm_used": llm_used,
        "llm_error": llm_error if len(options) > 1 else None,
        "acl_messages": messages
    }

from datetime import date

@traceable(name="RoundTripTravelAgent")
def round_trip_agent(fan_request, match_info):

    departure_date = match_info["travel_date"]
    return_date = match_info["return_date"]

    if date.fromisoformat(return_date) <= date.fromisoformat(departure_date):
        raise ValueError("Return date must be after departure date")

    origin = fan_request["origin_city"]
    destination = match_info["city"]
    budget = fan_request.get(
        "transport_budget_sar",
        fan_request["budget_sar"]
    )
    priority = fan_request.get("priority", "lowest_cost")

    # No intercity transport is needed when the fan already lives in the
    # match city. Keep this as a real TravelAgent response in the ACL log.
    if origin == destination:
        outbound = {
            "origin": origin,
            "destination": destination,
            "travel_date": departure_date,
            "mode": "Local",
            "provider": "No intercity travel required",
            "simulated_oneway_cost_sar": 0.0,
            "comfort_score": 5,
        }
        inbound = {
            **outbound,
            "travel_date": return_date,
        }
        option = {
            "outbound": outbound,
            "inbound": inbound,
            "transport_cost_sar": 0.0,
            "comfort_score": 5,
            "data_type": "LOCAL_NO_TRAVEL_REQUIRED",
        }
        messages = [create_acl_message(
            "CoordinatorAgent",
            "TravelAgent",
            "CFP" if fan_request.get("alternative_search_round") else "REQUEST",
            {
                "origin": origin,
                "destination": destination,
                "travel_date": departure_date,
                "priority": priority,
                "transport_budget_sar": budget,
            },
            fan_request["fan_id"],
        ), create_acl_message(
            "TravelAgent",
            "CoordinatorAgent",
            "PROPOSE",
            {"status": "NO_INTERCITY_TRAVEL_REQUIRED", "round_trip": option},
            fan_request["fan_id"],
        )]
        return {
            "status": "NO_INTERCITY_TRAVEL_REQUIRED",
            "recommended_option": option,
            "round_trip_options": [option],
            "transport_cost_sar": 0.0,
            "data_type": "LOCAL_NO_TRAVEL_REQUIRED",
            "llm_used": False,
            "acl_messages": messages,
        }

    outbound = travel_agent(
        fan_request, match_info, request_type="CFP"
    )

    return_match = {
        **match_info,
        "city": origin,
        "travel_date": return_date
    }

    return_fan = {
        **fan_request,
        "origin_city": destination
    }

    inbound = travel_agent(
        return_fan, return_match, request_type="CFP"
    )

    combinations = []

    for go in outbound["transport_options"]:
        for back in inbound["transport_options"]:
            total = (
                go["simulated_oneway_cost_sar"]
                + back["simulated_oneway_cost_sar"]
            )

            if total <= budget:
                combinations.append({
                    "outbound": go,
                    "inbound": back,
                    "transport_cost_sar": total,
                    "comfort_score": (
                        go["comfort_score"] +
                        back["comfort_score"]
                    ),
                    "data_type": "SYNTHETIC_BOOKING_INVENTORY"
                })

    if priority == "comfort":
        combinations.sort(
            key=lambda x: (
                -x["comfort_score"],
                x["transport_cost_sar"]
            )
        )
    elif priority == "balanced":
        combinations.sort(
            key=lambda x: (
                x["transport_cost_sar"] / x["comfort_score"]
            )
        )
    else:
        combinations.sort(
            key=lambda x: x["transport_cost_sar"]
        )

    selected = combinations[0] if combinations else None

    status = (
        "SIMULATED_ROUND_TRIP_READY"
        if selected else "NO_AFFORDABLE_ROUND_TRIP"
    )

    messages = (
        outbound["acl_messages"]
        + inbound["acl_messages"]
    )

    messages.append(create_acl_message(
        "TravelAgent",
        "CoordinatorAgent",
        "PROPOSE" if selected else "REFUSE",
        {"status": status, "round_trip": selected},
        fan_request["fan_id"]
    ))

    return {
        "status": status,
        "recommended_option": selected,
        "round_trip_options": combinations,
        "transport_cost_sar": (
            selected["transport_cost_sar"] if selected else None
        ),
        "llm_used": (
            outbound["llm_used"] or inbound["llm_used"]
        ),
        "acl_messages": messages
    }
