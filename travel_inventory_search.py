
from datetime import date
from contextlib import closing
from langsmith import traceable
from booking_inventory import connect
from real_data import TRANSPORT_OPTIONS

COMFORT = {
    "Economy": 1,
    "Business": 3
}


@traceable(name="TravelInventorySearch")
def find_transport_options(
    origin, destination, travel_date,
    budget, priority="lowest_cost"
):
    date.fromisoformat(travel_date)

    options = []

    with closing(connect()) as db:
        for route in TRANSPORT_OPTIONS:
            if route["origin"] != origin:
                continue
            if route["destination"] != destination:
                continue

            for service_no in (1, 2):
                service_id = f"{route['id']}-{service_no}"

                rows = db.execute("""
                    SELECT class_name, price_sar, remaining
                    FROM stock
                    WHERE kind = 'transport'
                      AND item_id = ?
                      AND travel_date = ?
                      AND remaining > 0
                """, (service_id, travel_date)).fetchall()

                for seat_class, price, remaining in rows:
                    if price > budget:
                        continue

                    options.append({
                        "id": service_id,
                        "route_id": route["id"],
                        "provider": route["provider"],
                        "origin": origin,
                        "destination": destination,
                        "mode": route["mode"],
                        "route": route["route"],
                        "travel_date": travel_date,
                        "seat_class": seat_class,
                        "comfort_score": COMFORT[seat_class],
                        "simulated_oneway_cost_sar": price,
                        "seats_remaining": remaining,
                        "transport_cost_sar": None,
                        "transport_available": True,
                        "reference_oneway_sar":
                            route.get("reference_oneway_sar"),
                        "source": route["source"],
                        "data_type": "SYNTHETIC_BOOKING_INVENTORY"
                    })

    if priority == "comfort":
        options.sort(key=lambda x: (
            -x["comfort_score"],
            x["simulated_oneway_cost_sar"]
        ))

    elif priority == "balanced":
        options.sort(key=lambda x: (
            x["simulated_oneway_cost_sar"]
            / x["comfort_score"]
        ))

    else:
        options.sort(
            key=lambda x: x["simulated_oneway_cost_sar"]
        )

    return {
        "options": options,
        "recommended": options[0] if options else None,
        "status": (
            "OPTIONS_FOUND" if options
            else "NO_AVAILABLE_OPTION"
        )
    }
