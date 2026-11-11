
from datetime import datetime, timedelta
from langsmith import traceable
from acl import create_acl_message


@traceable(name="ScheduleChecker")
def check_schedule(
    fan_request,
    match_info,
    departure_datetime=None,
    arrival_datetime=None,
    checkin_date=None,
    checkout_date=None
):
    fan_id = fan_request["fan_id"]

    match_time = datetime.fromisoformat(
        match_info["match_datetime"]
    )

    if arrival_datetime is None:
        status = "PENDING_TRAVEL_SCHEDULE"
        reason = "Arrival date and time are unknown."

    else:
        arrival = datetime.fromisoformat(arrival_datetime)

        if arrival >= match_time:
            status = "SCHEDULE_CONFLICT"
            reason = "Arrival is after or at match start."

        elif match_time - arrival < timedelta(hours=2):
            status = "SCHEDULE_CONFLICT"
            reason = "Less than 2 hours before match start."

        else:
            status = "TRAVEL_TIME_OK"
            reason = "Arrival is before the match."

    # Check accommodation dates if available.
    if (
        status == "TRAVEL_TIME_OK"
        and checkin_date is not None
        and checkout_date is not None
    ):
        checkin = datetime.fromisoformat(
            checkin_date
        ).date()

        checkout = datetime.fromisoformat(
            checkout_date
        ).date()

        if checkout <= checkin:
            status = "SCHEDULE_CONFLICT"
            reason = "Invalid hotel stay dates."

        elif not (checkin <= match_time.date() < checkout):
            status = "SCHEDULE_CONFLICT"
            reason = "Hotel stay does not cover match date."

    message = create_acl_message(
        "CoordinatorAgent",
        "FanAgent",
        "INFORM",
        {
            "schedule_status": status,
            "reason": reason
        },
        fan_id
    )

    return {
        "status": status,
        "reason": reason,
        "acl_messages": [message]
    }

@traceable(name="TravelChronologyChecker")
def check_travel_chronology(
    departure_datetime,
    arrival_datetime,
    match_datetime
):
    departure = datetime.fromisoformat(departure_datetime)
    arrival = datetime.fromisoformat(arrival_datetime)
    match = datetime.fromisoformat(match_datetime)

    if departure >= arrival:
        return {
            "status": "SCHEDULE_CONFLICT",
            "reason": "Departure must be before arrival."
        }

    if arrival >= match:
        return {
            "status": "SCHEDULE_CONFLICT",
            "reason": "Arrival is after match start."
        }

    if match - arrival < timedelta(hours=2):
        return {
            "status": "SCHEDULE_CONFLICT",
            "reason": "Insufficient time before match."
        }

    return {
        "status": "TRAVEL_TIME_OK",
        "reason": "Travel schedule is valid."
    }

@traceable(name="FullScheduleValidator")
def validate_full_schedule(
    fan_request,
    match_info,
    departure_datetime=None,
    arrival_datetime=None,
    checkin_date=None,
    checkout_date=None
):
    fan_id = fan_request["fan_id"]

    # Unknown travel time must not be accepted
    if departure_datetime is None or arrival_datetime is None:
        status = "PENDING_SCHEDULE_DATA"
        reason = "Travel departure or arrival time is missing."

    elif checkin_date is None or checkout_date is None:
        status = "PENDING_SCHEDULE_DATA"
        reason = "Hotel check-in or check-out date is missing."

    else:
        travel_check = check_travel_chronology(
            departure_datetime,
            arrival_datetime,
            match_info["match_datetime"]
        )

        if travel_check["status"] != "TRAVEL_TIME_OK":
            status = "SCHEDULE_CONFLICT"
            reason = travel_check["reason"]

        else:
            match_date = datetime.fromisoformat(
                match_info["match_datetime"]
            ).date()

            checkin = datetime.fromisoformat(
                checkin_date
            ).date()

            checkout = datetime.fromisoformat(
                checkout_date
            ).date()

            if checkout <= checkin:
                status = "SCHEDULE_CONFLICT"
                reason = "Checkout must be after check-in."

            elif not (checkin <= match_date < checkout):
                status = "SCHEDULE_CONFLICT"
                reason = "Hotel stay does not cover match date."

            else:
                status = "SCHEDULE_OK"
                reason = "Travel and hotel dates are valid."

    message = create_acl_message(
        "CoordinatorAgent",
        "FanAgent",
        "INFORM",
        {
            "schedule_status": status,
            "reason": reason
        },
        fan_id
    )

    return {
        "status": status,
        "reason": reason,
        "acl_messages": [message]
    }
