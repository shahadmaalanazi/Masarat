from langsmith import traceable


@traceable(name="Student2ContractAdapter")
def prepare_coordinator_data(travel_result, hotel_result):
    round_trip_options = []

    for item in travel_result.get("round_trip_options", []):
        outbound = item["outbound"]
        inbound = item["inbound"]
        round_trip_options.append({
            "id": f"{outbound['id']}:{outbound['seat_class']}|{inbound['id']}:{inbound['seat_class']}",
            "outbound": outbound,
            "inbound": inbound,
            "origin": outbound["origin"],
            "destination": outbound["destination"],
            "departure_date": outbound["travel_date"],
            "return_date": inbound["travel_date"],
            "transport_cost_sar": item["transport_cost_sar"],
            "transport_available": True,
            "comfort_score": item.get("comfort_score"),
            "data_type": item.get("data_type", "SYNTHETIC_BOOKING_INVENTORY")
        })

    if round_trip_options:
        recommended = travel_result.get("recommended_option")
        recommended_id = None
        if recommended:
            go = recommended["outbound"]
            back = recommended["inbound"]
            recommended_id = f"{go['id']}:{go['seat_class']}|{back['id']}:{back['seat_class']}"
        total = travel_result.get("transport_cost_sar")
        if total is None and recommended:
            total = recommended.get("transport_cost_sar")
    else:
        recommended_id = None
        total = None

    hotel_options = []
    for item in hotel_result.get("accommodation_options", []):
        hotel_options.append({
            "hotel_id": item["hotel_id"],
            "name": item["name"],
            "city": item["city"],
            "room_type": item.get("room_type"),
            "checkin": item.get("checkin"),
            "checkout": item.get("checkout"),
            "nights": item.get("nights"),
            "rooms_remaining": item.get("rooms_remaining"),
            "comfort_score": item.get("comfort_score"),
            "simulated_stay_cost_sar": item.get("total_sar"),
            "accommodation_cost_sar": item.get("accommodation_cost_sar", item.get("total_sar")),
            "accommodation_available": item.get("accommodation_available"),
            "booking_status": item.get("booking_status"),
            "source": item.get("source"),
            "data_type": item.get("data_type", "UNKNOWN")
        })

    hotel_recommended = hotel_result.get("recommended_option") or {}

    return {
        "travel_options": round_trip_options,
        "round_trip_options": round_trip_options,
        "accommodation_options": hotel_options,
        "travel_status": travel_result.get("status"),
        "accommodation_status": hotel_result.get("status"),
        "transport_cost_sar": total,
        "recommended_round_trip": travel_result.get("recommended_option") if round_trip_options else None,
        "recommended_travel_id": recommended_id,
        "recommended_hotel_id": hotel_recommended.get("hotel_id"),
        "acl_messages": travel_result.get("acl_messages", []) + hotel_result.get("acl_messages", [])
    }
