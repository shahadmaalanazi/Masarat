
import sqlite3
import random
import uuid
from datetime import date, timedelta
from contextlib import closing
from real_data import HOTELS, TRANSPORT_OPTIONS

DB = "masarat_inventory.db"
START = date(2027, 1, 5)
DAYS = 35


def connect():
    db = sqlite3.connect(DB, timeout=10, isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    return db


def initialize_inventory(reset=False):
    import os

    if reset and os.path.exists(DB):
        os.remove(DB)

    with closing(connect()) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                kind TEXT,
                item_id TEXT,
                travel_date TEXT,
                class_name TEXT,
                price_sar INTEGER,
                remaining INTEGER CHECK(remaining >= 0),
                PRIMARY KEY(kind, item_id, travel_date, class_name)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id TEXT PRIMARY KEY,
                fan_id TEXT,
                kind TEXT,
                item_id TEXT,
                start_date TEXT,
                end_date TEXT,
                class_name TEXT,
                total_sar INTEGER,
                status TEXT
            )
        """)

        # Do not regenerate inventory after bookings exist.
        if db.execute(
            "SELECT COUNT(*) FROM stock"
        ).fetchone()[0] > 0:
            return

        rng = random.Random(2027)

        for day in range(DAYS):
            current_date = (
                START + timedelta(days=day)
            ).isoformat()

            # Hotel rooms
            for hotel in HOTELS:
                base = hotel.get("reference_nightly_sar") or 550

                for room_type, multiplier in [
                    ("Standard", 1.0),
                    ("Deluxe", 1.4),
                    ("Suite", 2.2)
                ]:
                    price = round(
                        base * multiplier *
                        rng.uniform(0.88, 1.17)
                    )

                    rooms = rng.randint(2, 12)

                    db.execute(
                        "INSERT INTO stock VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            "hotel",
                            hotel["id"],
                            current_date,
                            room_type,
                            price,
                            rooms
                        )
                    )

            # Transport seats
            for route in TRANSPORT_OPTIONS:
                base = route.get("reference_oneway_sar") or 300

                for service_number in (1, 2):
                    service_id = f"{route['id']}-{service_number}"

                    for seat_type, multiplier, capacity in [
                        ("Economy", 1.0, rng.randint(18, 65)),
                        ("Business", 2.5, rng.randint(3, 10))
                    ]:
                        price = round(
                            base * multiplier *
                            rng.uniform(0.85, 1.35)
                        )

                        db.execute(
                            "INSERT INTO stock VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                "transport",
                                service_id,
                                current_date,
                                seat_type,
                                price,
                                capacity
                            )
                        )


def search_inventory(kind, item_id, travel_date):
    with closing(connect()) as db:
        return db.execute(
            """
            SELECT class_name, price_sar, remaining
            FROM stock
            WHERE kind = ?
              AND item_id = ?
              AND travel_date = ?
            ORDER BY price_sar
            """,
            (kind, item_id, travel_date)
        ).fetchall()


def reserve(
    fan_id,
    kind,
    item_id,
    start_date,
    class_name,
    end_date=None
):
    if kind not in ("hotel", "transport"):
        raise ValueError("Invalid inventory type")

    first = date.fromisoformat(start_date)
    end = (
        date.fromisoformat(end_date)
        if end_date else first + timedelta(days=1)
    )

    if end <= first:
        raise ValueError("Invalid date range")

    if kind == "transport" and (end - first).days != 1:
        raise ValueError("Each transport reservation is one leg")

    dates = [
        (first + timedelta(days=i)).isoformat()
        for i in range((end - first).days)
    ]

    with closing(connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")

            prices = []

            for current_date in dates:
                row = db.execute(
                    """
                    SELECT price_sar, remaining
                    FROM stock
                    WHERE kind = ?
                      AND item_id = ?
                      AND travel_date = ?
                      AND class_name = ?
                    """,
                    (kind, item_id, current_date, class_name)
                ).fetchone()

                if row is None or row[1] < 1:
                    db.execute("ROLLBACK")
                    return {
                        "status": "SOLD_OUT",
                        "date": current_date
                    }

                prices.append(row[0])

            for current_date in dates:
                db.execute(
                    """
                    UPDATE stock
                    SET remaining = remaining - 1
                    WHERE kind = ?
                      AND item_id = ?
                      AND travel_date = ?
                      AND class_name = ?
                      AND remaining > 0
                    """,
                    (kind, item_id, current_date, class_name)
                )

            booking_id = str(uuid.uuid4())[:8]
            total = sum(prices)

            db.execute(
                "INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    booking_id,
                    fan_id,
                    kind,
                    item_id,
                    start_date,
                    end.isoformat(),
                    class_name,
                    total,
                    "CONFIRMED"
                )
            )

            db.execute("COMMIT")

            return {
                "status": "CONFIRMED",
                "booking_id": booking_id,
                "total_sar": total
            }

        except Exception:
            db.execute("ROLLBACK")
            raise


def reserve_bundle(fan_id, items, budget_sar=None):
    """Atomically book simulated HOTEL nights and TRANSPORT legs together.

    items: [{"kind":"hotel"|"transport", "item_id":str,
             "start_date":"YYYY-MM-DD", "end_date":"YYYY-MM-DD" optional,
             "class_name":str}]. A match ticket is NOT included.
    """
    if not items:
        raise ValueError("Bundle must contain at least one item")
    demands = {}
    for item in items:
        kind = item["kind"]
        if kind not in ("hotel", "transport"):
            raise ValueError("Unknown inventory kind")
        start = date.fromisoformat(item["start_date"])
        end = date.fromisoformat(item.get("end_date") or (
            start + timedelta(days=1)).isoformat())
        if end <= start:
            raise ValueError("End date must be later than start")
        if kind == "transport" and (end-start).days != 1:
            raise ValueError("Each transport item is one leg")
        for i in range((end-start).days):
            key = (kind, item["item_id"],
                   (start+timedelta(days=i)).isoformat(), item["class_name"])
            demands[key] = demands.get(key, 0) + 1
    with closing(connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            total = 0
            for (kind, item_id, day, cls), amount in demands.items():
                row = db.execute("""SELECT price_sar, remaining FROM stock
                    WHERE kind=? AND item_id=? AND travel_date=? AND class_name=?""",
                    (kind, item_id, day, cls)).fetchone()
                if row is None or row[1] < amount:
                    db.execute("ROLLBACK")
                    return {"status": "SOLD_OUT", "item_id": item_id,
                            "date": day, "bookings": []}
                total += row[0] * amount
            if budget_sar is not None and total > budget_sar:
                db.execute("ROLLBACK")
                return {"status": "OVER_BUDGET", "total_sar": total,
                        "bookings": []}
            for (kind, item_id, day, cls), amount in demands.items():
                updated = db.execute("""UPDATE stock SET remaining=remaining-?
                    WHERE kind=? AND item_id=? AND travel_date=? AND class_name=?
                    AND remaining>=?""", (amount, kind, item_id, day, cls, amount))
                if updated.rowcount != 1:
                    raise RuntimeError("Inventory changed before booking")
            ids = []
            for item in items:
                start = item["start_date"]
                end = item.get("end_date") or (
                    date.fromisoformat(start)+timedelta(days=1)).isoformat()
                item_total = 0
                for i in range((date.fromisoformat(end)-date.fromisoformat(start)).days):
                    day = (date.fromisoformat(start)+timedelta(days=i)).isoformat()
                    item_total += db.execute("""SELECT price_sar FROM stock
                        WHERE kind=? AND item_id=? AND travel_date=? AND class_name=?""",
                        (item["kind"], item["item_id"], day,
                         item["class_name"])).fetchone()[0]
                book_id = str(uuid.uuid4())
                db.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (book_id, fan_id, item["kind"], item["item_id"],
                            start, end, item["class_name"], item_total, "CONFIRMED"))
                ids.append(book_id)
            db.execute("COMMIT")
            return {"status": "CONFIRMED", "total_sar": total,
                    "bookings": ids}
        except Exception:
            db.execute("ROLLBACK")
            raise
