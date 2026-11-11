
"""Masarat Student 4: orchestration, ACL routing, validation and bounded retries.

The coordinator accepts confirmed ticket information or explicitly labeled
simulated ticket estimates for planning purposes.
Simulated prices and availability are not real ticket offers or reservations.
Transport schedule validation uses travel dates only.
Exact departure and arrival times are not available or confirmed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from itertools import product

from acl import create_acl_message
from fan_agent import handle_coordinator_proposal


START_DATE = date(2027, 1, 5)
END_DATE = date(2027, 2, 8)


class CoordinatorAgent:
    name = "CoordinatorAgent"

    def __init__(
        self,
        *,
        venue_agent=None,
        travel_agent=None,
        accommodation_agent=None,
        fan_handler=None,
        max_negotiation_rounds: int = 2
    ):
        self.venue_agent = venue_agent
        self.travel_agent = travel_agent
        self.accommodation_agent = accommodation_agent
        self.fan_handler = fan_handler or handle_coordinator_proposal
        self.max_negotiation_rounds = max(
            1, int(max_negotiation_rounds)
        )
        self.message_log: list[dict] = []

    def _log(self, message: dict) -> dict:
        self.message_log.append(message)
        return message

    def _message(
        self, sender, receiver, performative, content, fan_id
    ):
        return self._log(
            create_acl_message(
                sender,
                receiver,
                performative,
                content,
                fan_id
            )
        )

    @staticmethod
    def _date_in_scope(value: str) -> bool:
        try:
            parsed = date.fromisoformat(str(value)[:10])
            return START_DATE <= parsed <= END_DATE
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _venue_record(venue_agent, match_id: str) -> dict:
        """Call the supplied VenueAgent and normalize its response record."""

        if venue_agent is None:
            from venue_agent import VenueAgent, make_request

            venue_agent = VenueAgent()
            response = venue_agent.handle_acl(
                make_request("get_match", match_id=match_id)
            )

        elif callable(venue_agent) and not hasattr(
            venue_agent, "handle_acl"
        ):
            response = venue_agent(match_id)

        else:
            from venue_agent import make_request

            response = venue_agent.handle_acl(
                make_request("get_match", match_id=match_id)
            )

        if isinstance(response, dict):
            if "records" in response:
                records = response.get("records") or []
                return records[0] if records else {}
            return response

        records = getattr(response, "records", []) or []
        return records[0] if records else {}

    @staticmethod
    def _to_match_info(record: dict, origin_city: str) -> dict:
        match_dt = record.get("original_datetime")

        if not match_dt:
            match_dt = (
                f"{record['date']}T"
                f"{record.get('time', '20:00')}:00+03:00"
            )

        match_day = date.fromisoformat(record["date"])

        # Simulated travel dates are chosen around the match.
        travel_day = match_day - timedelta(days=1)
        return_day = match_day + timedelta(days=1)

        return {
            "match_id": record.get("match_id"),
            "city": record.get("city"),
            "match_datetime": match_dt,
            "travel_date": travel_day.isoformat(),
            "return_date": return_day.isoformat(),
            "checkin_date": match_day.isoformat(),
            "checkout_date": return_day.isoformat(),
            "origin_city": origin_city,
        }

    @staticmethod
    def _is_ticket_usable(record: dict) -> bool:
        """Accept confirmed tickets or explicitly labeled simulated tickets."""

        status = str(
            record.get("ticket_availability", "")
        ).upper()

        price_type = str(
            record.get("ticket_price_type", "")
        ).upper()

        price = record.get("ticket_price_sar")

        valid_price = (
            isinstance(price, (int, float))
            and not isinstance(price, bool)
            and price >= 0
        )

        if not valid_price:
            return False

        if status in {"AVAILABLE", "CONFIRMED", "ON_SALE"}:
            return True

        if (
            status == "SIMULATED_AVAILABLE"
            and price_type == "ESTIMATED_SIMULATED"
        ):
            return True

        return False

    @staticmethod
    def _build_plans(
        fan_request: dict,
        match: dict,
        travel_result: dict,
        hotel_result: dict
    ) -> tuple[list[dict], list[str]]:

        plans = []
        pending = []

        ticket_ok = CoordinatorAgent._is_ticket_usable(match)

        if not ticket_ok:
            pending.append(
                "Ticket price and availability are not confirmed "
                "or explicitly marked as simulated by VenueAgent"
            )

        travel_options = travel_result.get(
            "round_trip_options", []
        )
        hotel_options = hotel_result.get(
            "accommodation_options", []
        )

        if not travel_options:
            pending.append(
                "No complete round-trip transport offers were returned"
            )

        if not hotel_options:
            pending.append(
                "No accommodation offers were returned"
            )

        for travel, hotel in product(
            travel_options, hotel_options
        ):

            if not ticket_ok:
                continue

            go = travel.get("outbound", {})
            back = travel.get("inbound", {})

            try:
                match_dt = datetime.fromisoformat(
                    match["original_datetime"]
                )
                match_day = match_dt.date()

                departure_day = date.fromisoformat(
                    go["travel_date"]
                )
                return_day = date.fromisoformat(
                    back["travel_date"]
                )

                checkin_day = date.fromisoformat(
                    hotel["checkin"]
                )
                checkout_day = date.fromisoformat(
                    hotel["checkout"]
                )

                conflict = (
                    departure_day > match_day
                    or return_day < match_day
                    or checkout_day <= checkin_day
                    or not (
                        checkin_day <= match_day < checkout_day
                    )
                )

            except (KeyError, TypeError, ValueError):
                pending.append(
                    "Travel dates or hotel dates "
                    "are incomplete/invalid"
                )
                continue

            transport_cost = travel.get(
                "transport_cost_sar"
            )

            hotel_cost = hotel.get(
                "accommodation_cost_sar",
                hotel.get("total_sar")
            )

            if (
                transport_cost is None
                or hotel_cost is None
            ):
                pending.append(
                    "A transport or accommodation price is unknown"
                )
                continue

            comfort_scores = [
                go.get("comfort_score", 1),
                hotel.get("comfort_score", 1)
            ]

            comfort = max(
                1,
                min(
                    5,
                    round(
                        sum(comfort_scores) / len(comfort_scores)
                    )
                )
            )

            plans.append({
                "plan_id": (
                    f"{match['match_id']}-{len(plans) + 1:03d}"
                ),
                "match_id": match["match_id"],
                "city": match["city"],
                "match_datetime": match["original_datetime"],

                "ticket_price_sar": match["ticket_price_sar"],
                "ticket_price_type": match.get(
                    "ticket_price_type",
                    "CONFIRMED"
                ),
                "ticket_availability": match.get(
                    "ticket_availability",
                    "CONFIRMED"
                ),

                "transport_cost_sar": float(transport_cost),
                "accommodation_cost_sar": float(hotel_cost),
                "comfort_level": comfort,

                "ticket_available": True,
                "transport_available": bool(
                    travel.get("transport_available", True)
                ),
                "accommodation_available": bool(
                    hotel.get("accommodation_available", True)
                ),
                "schedule_conflict": bool(conflict),

                # Exact departure and arrival times are not provided.
                "transport_schedule_status": (
                    "DATES_ONLY_NOT_TIME_CONFIRMED"
                ),

                # Data provenance for simulation and reporting.
                "transport_data_type": travel.get(
                    "data_type",
                    "UNKNOWN"
                ),
                "accommodation_data_type": hotel.get(
                    "data_type",
                    "UNKNOWN"
                ),
            })

        return plans, list(dict.fromkeys(pending))

    def coordinate(
        self,
        fan_request: dict,
        *,
        selector=None,
        review_budget: bool = False,
    ) -> dict:
        """Run one fan request through Venue, Travel, Hotel and Fan agents.

        Returns a JSON-serializable result and a centralized ACL log.
        """

        fan_id = fan_request["fan_id"]
        self.message_log = []

        self._message(
            "FanAgent",
            self.name,
            "REQUEST",
            {"fan_request": fan_request},
            fan_id
        )

        all_plans = []
        pending_reasons = []
        raw_results = []
        review_baseline = None

        for round_no in range(
            1, self.max_negotiation_rounds + 1
        ):

            self._message(
                self.name,
                "VenueAgent",
                "REQUEST",
                {
                    "action": "get_match",
                    "match_ids": fan_request["preferred_match_ids"],
                    "round": round_no
                },
                fan_id
            )

            round_plans = []

            agent_request = fan_request
            if review_budget and round_no > 1 and review_baseline:
                agent_request = {
                    **fan_request,
                    "transport_budget_sar": fan_request["budget_sar"],
                    "accommodation_budget_sar": fan_request["budget_sar"],
                    "budget_review_round": True,
                }

            for match_id in fan_request["preferred_match_ids"]:

                try:
                    venue_record = self._venue_record(
                        self.venue_agent,
                        match_id
                    )

                    if not venue_record:
                        pending_reasons.append(
                            f"Venue record not found: {match_id}"
                        )
                        continue

                    match_info = self._to_match_info(
                        venue_record,
                        fan_request["origin_city"]
                    )

                    if not self._date_in_scope(
                        match_info["match_datetime"][:10]
                    ):
                        pending_reasons.append(
                            f"Match {match_id} is outside "
                            "5 Jan–8 Feb 2027"
                        )
                        continue

                    self._message(
                        "VenueAgent",
                        self.name,
                        "INFORM",
                        {"match": venue_record},
                        fan_id
                    )

                    self._message(
                        self.name,
                        "TravelAgent",
                        "CFP" if round_no > 1 else "REQUEST",
                        {"match_info": match_info},
                        fan_id
                    )

                    travel_fn = self.travel_agent

                    if travel_fn is None:
                        from travel_agent import round_trip_agent
                        travel_fn = round_trip_agent

                    travel_result = travel_fn(
                        agent_request,
                        match_info
                    )

                    travel_replies = [
                        msg for msg in travel_result.get(
                            "acl_messages", []
                        )
                        if msg.get("sender") == "TravelAgent"
                        and msg.get("receiver") == self.name
                    ]
                    if travel_replies:
                        for msg in travel_replies:
                            self._log(msg)
                    else:
                        self._message(
                            "TravelAgent",
                            self.name,
                            "INFORM",
                            {
                                "status": travel_result.get("status"),
                                "round_trip_count": len(
                                    travel_result.get(
                                        "round_trip_options", []
                                    )
                                )
                            },
                            fan_id
                        )

                    self._message(
                        self.name,
                        "AccommodationAgent",
                        "CFP" if round_no > 1 else "REQUEST",
                        {"match_info": match_info},
                        fan_id
                    )

                    hotel_fn = self.accommodation_agent

                    if hotel_fn is None:
                        from accommodation_agent import (
                            accommodation_agent
                        )
                        hotel_fn = accommodation_agent

                    hotel_result = hotel_fn(
                        agent_request,
                        match_info,
                        request_type=(
                            "CFP" if round_no > 1 else "REQUEST"
                        )
                    )

                    hotel_replies = [
                        msg for msg in hotel_result.get(
                            "acl_messages", []
                        )
                        if msg.get("sender") == "AccommodationAgent"
                        and msg.get("receiver") == self.name
                    ]
                    if hotel_replies:
                        for msg in hotel_replies:
                            self._log(msg)
                    else:
                        self._message(
                            "AccommodationAgent",
                            self.name,
                            "INFORM",
                            {
                                "status": hotel_result.get("status"),
                                "option_count": len(
                                    hotel_result.get(
                                        "accommodation_options", []
                                    )
                                )
                            },
                            fan_id
                        )

                    plans, pending = self._build_plans(
                        fan_request,
                        venue_record,
                        travel_result,
                        hotel_result
                    )

                    if review_budget and round_no > 1 and review_baseline:
                        for plan in plans:
                            plan["plan_id"] = f"ALT-{plan['plan_id']}"
                        plans = [
                            plan for plan in plans
                            if (
                                plan["transport_cost_sar"]
                                != review_baseline["transport_cost_sar"]
                                or plan["accommodation_cost_sar"]
                                != review_baseline["accommodation_cost_sar"]
                            )]

                    round_plans.extend(plans)
                    pending_reasons.extend(pending)

                    raw_results.append({
                        "match_id": match_id,
                        "travel": travel_result,
                        "accommodation": hotel_result
                    })

                except Exception as exc:
                    self._message(
                        "CoordinatorAgent",
                        "CoordinatorAgent",
                        "INFORM",
                        {
                            "status": "AGENT_FAILURE",
                            "round": round_no,
                            "match_id": match_id,
                            "error_type": type(exc).__name__,
                            "error": str(exc)
                        },
                        fan_id
                    )

                    pending_reasons.append(
                        f"Agent failure for {match_id}: "
                        f"{type(exc).__name__}: {exc}"
                    )

            # Deduplicate by plan id.
            known = {
                plan["plan_id"]
                for plan in all_plans
            }

            all_plans.extend(
                plan for plan in round_plans
                if plan["plan_id"] not in known
            )

            if not round_plans:
                continue

            # Send proposals to FanAgent.
            proposal = self._message(
                self.name,
                "FanAgent",
                "PROPOSE",
                {"proposed_plans": round_plans},
                fan_id
            )

            try:
                fan_result = self.fan_handler(
                    fan_request,
                    proposal,
                    selector=selector
                )

            except TypeError:
                fan_result = self.fan_handler(
                    fan_request,
                    proposal
                )

            for msg in fan_result.get("acl_messages", []):
                self._log(msg)

            decision = fan_result.get("fan_decision", {})
            status = decision.get("status")

            if status == "ACCEPT":
                if review_budget and round_no == 1:
                    review_baseline = next(
                        (
                            plan for plan in round_plans
                            if plan["plan_id"] == decision.get("plan_id")
                        ),
                        None,
                    )
                    if review_baseline:
                        continue

                if review_baseline and round_no > 1 and (
                    decision.get("total_cost_sar", float("inf"))
                    >= review_baseline["ticket_price_sar"]
                    + review_baseline["transport_cost_sar"]
                    + review_baseline["accommodation_cost_sar"]
                ):
                    # Keep the original plan when the reviewed offers do not
                    # lower its total; the alternative offers remain in logs.
                    self._message(
                        self.name,
                        self.name,
                        "INFORM",
                        {
                            "status": "BUDGET_REVIEW_COMPLETE",
                            "selected_plan_id": review_baseline["plan_id"],
                            "reviewed_plan_id": decision.get("plan_id"),
                            "reviewed_total_sar": decision.get(
                                "total_cost_sar"
                            ),
                            "baseline_total_sar": (
                                review_baseline["ticket_price_sar"]
                                + review_baseline["transport_cost_sar"]
                                + review_baseline["accommodation_cost_sar"]
                            ),
                            "reason": "No lower-cost alternative was offered.",
                        },
                        fan_id,
                    )
                    break

                self._message(
                    self.name,
                    self.name,
                    "INFORM",
                    {
                        "status": "ACCEPTED_SIMULATION_NOT_RESERVED",
                        "plan_id": decision.get("plan_id"),
                        "budget_review": (
                            {
                                "requested": True,
                                "baseline_total_sar": review_baseline[
                                    "ticket_price_sar"
                                ] + review_baseline["transport_cost_sar"]
                                + review_baseline["accommodation_cost_sar"],
                                "alternative_found": True,
                            }
                            if review_baseline else None
                        ),
                    },
                    fan_id
                )

                return {
                    "status": "ACCEPTED_SIMULATION_NOT_RESERVED",
                    "fan_decision": decision,
                    "eligible_plan_ids": fan_result.get(
                        "eligible_plan_ids", []
                    ),
                    "rejected_plans": fan_result.get(
                        "rejected_plans", []
                    ),
                    "proposed_plans": all_plans,
                    "budget_review": (
                        {
                            "requested": True,
                            "baseline_plan_id": review_baseline["plan_id"],
                            "baseline_total_sar": (
                                review_baseline["ticket_price_sar"]
                                + review_baseline["transport_cost_sar"]
                                + review_baseline["accommodation_cost_sar"]
                            ),
                            "alternative_found": True,
                            "alternative_plan_id": decision.get("plan_id"),
                            "alternative_total_sar": decision.get(
                                "total_cost_sar"
                            ),
                        }
                        if review_baseline else None
                    ),
                    "pending_reasons": list(
                        dict.fromkeys(pending_reasons)
                    ),
                    "message_log": self.message_log,
                    "agent_results": raw_results
                }

            if status == "ERROR":
                return {
                    "status": "FAN_AGENT_ERROR",
                    "fan_decision": decision,
                    "eligible_plan_ids": fan_result.get(
                        "eligible_plan_ids", []
                    ),
                    "rejected_plans": fan_result.get(
                        "rejected_plans", []
                    ),
                    "proposed_plans": all_plans,
                    "pending_reasons": list(
                        dict.fromkeys(pending_reasons)
                    ),
                    "message_log": self.message_log,
                    "agent_results": raw_results
                }

            if (
                status != "REFUSE"
                or not decision.get("request_alternative", False)
            ):
                return {
                    "status": "REFUSED_NO_FEASIBLE_PLAN",
                    "fan_decision": decision,
                    "eligible_plan_ids": fan_result.get(
                        "eligible_plan_ids", []
                    ),
                    "rejected_plans": fan_result.get(
                        "rejected_plans", []
                    ),
                    "proposed_plans": all_plans,
                    "pending_reasons": list(
                        dict.fromkeys(pending_reasons)
                    ),
                    "message_log": self.message_log,
                    "agent_results": raw_results
                }

        if not all_plans:
            return {
                "status": "PENDING_DATA",
                "fan_decision": None,
                "proposed_plans": [],
                "pending_reasons": list(
                    dict.fromkeys(pending_reasons)
                ),
                "message_log": self.message_log,
                "agent_results": raw_results
            }

        # All bounded rounds ended with a hard-constraint refusal.
        if review_baseline:
            baseline_total = (
                review_baseline["ticket_price_sar"]
                + review_baseline["transport_cost_sar"]
                + review_baseline["accommodation_cost_sar"]
            )
            self._message(
                self.name,
                self.name,
                "INFORM",
                {
                    "status": "ACCEPTED_SIMULATION_NOT_RESERVED",
                    "plan_id": review_baseline["plan_id"],
                    "budget_review": {
                        "requested": True,
                        "baseline_total_sar": baseline_total,
                        "alternative_found": False,
                    },
                },
                fan_id,
            )
            return {
                "status": "ACCEPTED_SIMULATION_NOT_RESERVED",
                "fan_decision": {
                    "status": "ACCEPT",
                    "plan_id": review_baseline["plan_id"],
                    "total_cost_sar": baseline_total,
                },
                "eligible_plan_ids": [review_baseline["plan_id"]],
                "rejected_plans": [],
                "proposed_plans": all_plans,
                "budget_review": {
                    "requested": True,
                    "baseline_plan_id": review_baseline["plan_id"],
                    "baseline_total_sar": baseline_total,
                    "alternative_found": False,
                },
                "pending_reasons": list(dict.fromkeys(pending_reasons)),
                "message_log": self.message_log,
                "agent_results": raw_results,
            }

        return {
            "status": "REFUSED_NO_FEASIBLE_PLAN",
            "fan_decision": (
                fan_result.get("fan_decision")
                if "fan_result" in locals()
                else None
            ),
            "eligible_plan_ids": [],
            "rejected_plans": (
                fan_result.get("rejected_plans", [])
                if "fan_result" in locals()
                else []
            ),
            "proposed_plans": all_plans,
            "budget_review": (
                {
                    "requested": True,
                    "alternative_found": False,
                    "best_available_total_sar": min(
                        plan["ticket_price_sar"]
                        + plan["transport_cost_sar"]
                        + plan["accommodation_cost_sar"]
                        for plan in all_plans
                    ) if all_plans else None,
                }
                if review_budget else None
            ),
            "pending_reasons": list(
                dict.fromkeys(pending_reasons)
            ),
            "message_log": self.message_log,
            "agent_results": raw_results
        }


def run_coordinator(fan_request: dict, **kwargs) -> dict:
    """Convenience entry point for the demo app."""
    return CoordinatorAgent(**kwargs).coordinate(fan_request)



