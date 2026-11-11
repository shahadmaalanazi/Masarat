
from datetime import date, timedelta
from contextlib import closing
from langsmith import traceable
from booking_inventory import connect
from real_data import HOTELS

COMFORT_SCORES = {
    "Standard": 1,
    "Deluxe": 2,
    "Suite": 3
}

@traceable(name="HotelInventorySearch")
def find_hotel_options(
    city,
    checkin,
    checkout,
    budget,
    priority="lowest_cost"
):
    start = date.fromisoformat(checkin)
    end = date.fromisoformat(checkout)

    if end <= start:
        raise ValueError("Invalid stay dates")

    nights = (end - start).days
    dates = [
        (start + timedelta(days=i)).isoformat()
        for i in range(nights)
    ]

    options = []

    with closing(connect()) as db:
        for hotel in HOTELS:
            if hotel["city"] != city:
                continue

            for room_type, comfort in COMFORT_SCORES.items():
                rows = db.execute(
                    """
                    SELECT travel_date, price_sar, remaining
                    FROM stock
                    WHERE kind = 'hotel'
                      AND item_id = ?
                      AND class_name = ?
                      AND travel_date >= ?
                      AND travel_date < ?
                    """,
                    (hotel["id"], room_type, checkin, checkout)
                ).fetchall()

                if len(rows) != nights:
                    continue

                if any(r[2] <= 0 for r in rows):
                    continue

                total = sum(r[1] for r in rows)

                if total > budget:
                    continue

                options.append({
                    "hotel_id": hotel["id"],
                    "name": hotel["name"],
                    "city": city,
                    "room_type": room_type,
                    "comfort_score": comfort,
                    "checkin": checkin,
                    "checkout": checkout,
                    "nights": nights,
                    "total_sar": total,
                    "rooms_remaining": min(r[2] for r in rows),
                    "source": hotel["source"],
                    "data_type": "SYNTHETIC_BOOKING_INVENTORY"
                })

    if priority == "comfort":
        options.sort(
            key=lambda x: (-x["comfort_score"], x["total_sar"])
        )
    elif priority == "balanced":
        options.sort(
            key=lambda x: (
                x["total_sar"] / x["comfort_score"]
            )
        )
    else:
        options.sort(key=lambda x: x["total_sar"])

    return {
        "options": options,
        "recommended": options[0] if options else None,
        "status": "OPTIONS_FOUND" if options else "NO_AVAILABLE_OPTION"
    }
