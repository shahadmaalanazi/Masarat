
from langsmith import traceable
from acl import create_acl_message
from hotel_inventory_search import find_hotel_options


@traceable(name="AccommodationAgent")
def accommodation_agent(
    fan_request,
    match_info,
    request_type="REQUEST"
):
    fan_id = fan_request["fan_id"]
    city = match_info["city"]
    budget = fan_request.get("accommodation_budget_sar", fan_request["budget_sar"])
    priority = fan_request.get("priority", "lowest_cost")

    checkin = match_info.get("checkin_date")
    checkout = match_info.get("checkout_date")

    messages = [
        create_acl_message(
            "CoordinatorAgent",
            "AccommodationAgent",
            request_type,
            {
                "city": city,
                "checkin": checkin,
                "checkout": checkout,
                "priority": priority,
                "accommodation_budget_sar": budget
            },
            fan_id
        )
    ]

    if checkin is None or checkout is None:
        messages.append(create_acl_message(
            "AccommodationAgent",
            "CoordinatorAgent",
            "INFORM",
            {"status": "PENDING_STAY_DATES"},
            fan_id
        ))

        return {
            "accommodation_options": [],
            "recommended_option": None,
            "status": "PENDING_STAY_DATES",
            "acl_messages": messages
        }

    result = find_hotel_options(
        city=city,
        checkin=checkin,
        checkout=checkout,
        budget=budget,
        priority=priority
    )

    options = []

    for item in result["options"]:
        options.append({
            **item,
            "accommodation_cost_sar": item["total_sar"],
            "accommodation_available": True,
            "booking_status": "SIMULATED_AVAILABLE"
        })

    recommended = options[0] if options else None

    if recommended:
        status = "SIMULATED_OFFER_READY"
        performative = "PROPOSE"
    else:
        status = "NO_AVAILABLE_OPTION"
        performative = "REFUSE"

    messages.append(create_acl_message(
        "AccommodationAgent",
        "CoordinatorAgent",
        performative,
        {
            "status": status,
            "recommended": recommended,
            "accommodation_options": options
        },
        fan_id
    ))

    return {
        "accommodation_options": options,
        "recommended_option": recommended,
        "status": status,
        "acl_messages": messages
    }
