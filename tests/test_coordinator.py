
from coordinator_agent import CoordinatorAgent
from fan_agent import assess_plans

FAN = {
    "fan_id": "F001",
    "origin_city": "Riyadh",
    "budget_sar": 2000,
    "preferred_match_ids": ["M001"],
    "priority": "lowest_cost"
}


class FakeVenue:
    def __init__(self, confirmed=True):
        self.confirmed = confirmed

    def __call__(self, match_id):
        return {
            "match_id": match_id,
            "city": "Jeddah",
            "date": "2027-01-07",
            "time": "20:00",
            "original_datetime": "2027-01-07T20:00:00+03:00",
            "ticket_availability": (
                "AVAILABLE" if self.confirmed else "UNCONFIRMED"
            ),
            "ticket_price_sar": 100,
        }


def travel(_fan, _match):
    return {
        "status": "SIMULATED_ROUND_TRIP_READY",
        "round_trip_options": [{
            "outbound": {
                "travel_date": "2027-01-06",
                "comfort_score": 3
            },
            "inbound": {
                "travel_date": "2027-01-08",
                "comfort_score": 3
            },
            "transport_cost_sar": 300,
            "transport_available": True,
            "data_type": "SYNTHETIC_BOOKING_INVENTORY"
        }]
    }


def hotel(_fan, match, request_type="REQUEST"):
    return {
        "status": "SIMULATED_OFFER_READY",
        "accommodation_options": [{
            "checkin": match["checkin_date"],
            "checkout": match["checkout_date"],
            "total_sar": 400,
            "accommodation_available": True,
            "comfort_score": 2,
            "data_type": "SYNTHETIC_BOOKING_INVENTORY"
        }]
    }


def accept_handler(_fan, proposal, selector=None):
    plans = proposal["content"]["proposed_plans"]
    assert len(plans) == 1

    return {
        "fan_decision": {
            "status": "ACCEPT",
            "plan_id": plans[0]["plan_id"]
        },
        "eligible_plan_ids": [plans[0]["plan_id"]],
        "rejected_plans": [],
        "acl_messages": []
    }


def test_unconfirmed_ticket_fails_closed():
    result = CoordinatorAgent(
        venue_agent=FakeVenue(False),
        travel_agent=travel,
        accommodation_agent=hotel
    ).coordinate(FAN)

    assert result["status"] == "PENDING_DATA"
    assert result["proposed_plans"] == []
    assert any(
        "Ticket price" in reason
        for reason in result["pending_reasons"]
    )


def test_confirmed_complete_data_reaches_fan():
    result = CoordinatorAgent(
        venue_agent=FakeVenue(True),
        travel_agent=travel,
        accommodation_agent=hotel,
        fan_handler=accept_handler
    ).coordinate(FAN)

    assert result["status"] == "ACCEPTED_SIMULATION_NOT_RESERVED"
    assert result["proposed_plans"][0]["ticket_price_sar"] == 100
    assert result["proposed_plans"][0]["schedule_conflict"] is False

    assert result["proposed_plans"][0][
        "transport_schedule_status"
    ] == "DATES_ONLY_NOT_TIME_CONFIRMED"


def test_missing_travel_duration_does_not_block_plan():
    def no_duration(_fan, _match):
        return {
            "round_trip_options": [{
                "outbound": {
                    "travel_date": "2027-01-06",
                },
                "inbound": {
                    "travel_date": "2027-01-08",
                },
                "transport_cost_sar": 300
            }]
        }

    result = CoordinatorAgent(
        venue_agent=FakeVenue(True),
        travel_agent=no_duration,
        accommodation_agent=hotel
    ).coordinate(FAN)

    assert result["status"] == "ACCEPTED_SIMULATION_NOT_RESERVED"


def test_refusal_requests_bounded_alternative_round():
    calls = {"count": 0}

    def negotiate(_fan, proposal, selector=None):
        calls["count"] += 1

        plan_id = proposal["content"]["proposed_plans"][0]["plan_id"]

        if calls["count"] == 1:
            return {
                "fan_decision": {
                    "status": "REFUSE",
                    "request_alternative": True
                },
                "eligible_plan_ids": [],
                "rejected_plans": [{
                    "plan_id": plan_id,
                    "reasons": ["Budget exceeded"]
                }],
                "acl_messages": []
            }

        return {
            "fan_decision": {
                "status": "ACCEPT",
                "plan_id": plan_id
            },
            "eligible_plan_ids": [plan_id],
            "rejected_plans": [],
            "acl_messages": []
        }

    result = CoordinatorAgent(
        venue_agent=FakeVenue(True),
        travel_agent=travel,
        accommodation_agent=hotel,
        fan_handler=negotiate,
        max_negotiation_rounds=2
    ).coordinate(FAN)

    assert calls["count"] == 2
    assert result["status"] == "ACCEPTED_SIMULATION_NOT_RESERVED"


def test_travel_agent_failure_is_handled_safely():
    def failing_travel(_fan, _match):
        raise RuntimeError("Simulated TravelAgent failure")

    result = CoordinatorAgent(
        venue_agent=FakeVenue(True),
        travel_agent=failing_travel,
        accommodation_agent=hotel
    ).coordinate(FAN)

    assert result["status"] == "PENDING_DATA"
    assert result["proposed_plans"] == []

    assert any(
        "Agent failure" in reason
        for reason in result["pending_reasons"]
    )

    assert any(
        msg["content"].get("status") == "AGENT_FAILURE"
        for msg in result["message_log"]
    )


def test_schedule_conflict_is_detected():
    match = {
        "match_id": "M001",
        "city": "Riyadh",
        "original_datetime": "2027-01-07T20:00:00",
        "ticket_price_sar": 100,
        "ticket_price_type": "ESTIMATED_SIMULATED",
        "ticket_availability": "SIMULATED_AVAILABLE",
    }

    travel_result = {
        "round_trip_options": [{
            "outbound": {
                "travel_date": "2027-01-08",
                "comfort_score": 4,
            },
            "inbound": {
                "travel_date": "2027-01-09",
                "comfort_score": 4,
            },
            "transport_cost_sar": 300,
            "transport_available": True,
        }]
    }

    hotel_result = {
        "accommodation_options": [{
            "checkin": "2027-01-07",
            "checkout": "2027-01-08",
            "accommodation_cost_sar": 400,
            "comfort_score": 4,
        }]
    }

    plans, pending = CoordinatorAgent._build_plans(
        FAN,
        match,
        travel_result,
        hotel_result
    )

    assert len(plans) == 1
    assert plans[0]["schedule_conflict"] is True

    eligible, rejected = assess_plans(FAN, plans)

    assert len(eligible) == 0
    assert len(rejected) == 1
    assert "Schedule conflict" in rejected[0]["reasons"]

def test_budget_exceeded_is_rejected():
    plan = {
        "plan_id": "M001-001",
        "match_id": "M001",
        "city": "Jeddah",
        "match_datetime": "2027-01-07T20:00:00",
        "ticket_price_sar": 100,
        "transport_cost_sar": 1200,
        "accommodation_cost_sar": 1000,
        "comfort_level": 3,
        "ticket_available": True,
        "transport_available": True,
        "accommodation_available": True,
        "schedule_conflict": False,
    }

    eligible, rejected = assess_plans(FAN, [plan])

    assert len(eligible) == 0
    assert len(rejected) == 1
    assert "Budget exceeded" in rejected[0]["reasons"]


