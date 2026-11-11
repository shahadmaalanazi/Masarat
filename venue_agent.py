
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4
import hashlib

from venue_data import (
    AFC_OFFICIAL_SCHEDULE_SOURCE,
    AFC_POSTPONEMENT_SOURCE,
    MATCHES,
    TICKET_ANNOUNCEMENT,
    get_match,
    list_matches,
    list_venues,
)


def estimate_ticket_price(match_id):
    match_key = str(match_id).strip().upper()
    value = int(
        hashlib.sha256(match_key.encode("utf-8")).hexdigest()[:8],
        16
    )
    return 50 + (value % 151)


@dataclass(slots=True)
class ACLMessage:
    sender: str
    receiver: str
    performative: str
    content: dict
    ontology: str = "afc-asian-cup-venue-information"
    message_id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.message_id:
            self.message_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class AgentResponse:
    status: str
    summary: str
    records: list[dict]
    request_message: ACLMessage
    response_message: ACLMessage
    agent_status: str = "COMPLETED"


class VenueAgent:
    name = "Venue Agent"
    role = "Returns the original AFC fixture schedule and venue information."

    def __init__(self) -> None:
        self.status = "IDLE"
        self.last_action = "Waiting for a venue or match request."
        self.last_response: AgentResponse | None = None

    def handle_acl(self, message: ACLMessage) -> AgentResponse:
        if message.performative != "REQUEST":
            return self._respond(
                message,
                "NOT_FOUND",
                "Venue Agent accepts ACL REQUEST messages only.",
                []
            )

        self.status = "RUNNING"
        content = message.content or {}
        action = str(
            content.get("action", "list_venues")
        ).strip().lower()

        if action == "list_venues":
            records = list_venues()
            return self._respond(
                message,
                "OFFICIAL_STATIC",
                f"Loaded {len(records)} official venue references.",
                records
            )

        if action == "get_tournament_window":
            record = {
                "announced_window": "2027-12-23 to 2028-01-21",
                "schedule_version": "CURRENT_TOURNAMENT_WINDOW",
                "source": AFC_POSTPONEMENT_SOURCE,
            }
            return self._respond(
                message,
                "OFFICIAL_STATIC",
                "Returned the announced tournament window.",
                [record]
            )

        if action == "get_matches":
            records = list_matches()
            return self._respond(
                message,
                "ORIGINAL_SCHEDULE",
                f"Loaded {len(records)} original AFC fixtures.",
                records
            )

        if action == "get_ticket_status":
            record = dict(TICKET_ANNOUNCEMENT)
            record["ticket_availability"] = "UNCONFIRMED"

            return self._respond(
                message,
                "UNCONFIRMED",
                "Historical tournament ticket prices started at SAR 30. "
                "Match-specific prices and current availability are unconfirmed.",
                [record]
            )

        if action == "get_match":
            match_id = content.get("match_id", "")
            record = get_match(match_id)

            if record is None:
                return self._respond(
                    message,
                    "NOT_FOUND",
                    f"{match_id} was not found in the 51-fixture official schedule.",
                    [{"match_id": match_id, "data_status": "NOT_FOUND"}]
                )

            # Simulated ticket price for this specific match
            record["ticket_price_sar"] = estimate_ticket_price(
                record["match_id"]
            )
            record["ticket_price_type"] = "ESTIMATED_SIMULATED"
            record["ticket_availability"] = "SIMULATED_AVAILABLE"

            summary = (
                f"{record['match_id']}: "
                f"{record['team_1']} vs {record['team_2']} — "
                f"{record['date']} at {record['time']}, "
                f"{record['stadium']}, {record['city']}. "
                f"Estimated simulated ticket price: "
                f"SAR {record['ticket_price_sar']}."
            )

            return self._respond(
                message,
                "FOUND",
                summary,
                [record]
            )

        if action == "find_venue":
            query = str(
                content.get("query", "")
            ).strip().casefold()

            if not query:
                return self._respond(
                    message,
                    "NOT_FOUND",
                    "Provide a stadium or city name to search.",
                    []
                )

            venues = list_venues()

            exact_cities = [
                venue for venue in venues
                if query == venue["city"].casefold()
            ]

            matched = exact_cities or [
                venue for venue in venues
                if query in venue["name"].casefold()
                or query in venue["city"].casefold()
            ]

            if not matched:
                return self._respond(
                    message,
                    "NOT_FOUND",
                    f"No venue reference matched '{content.get('query')}'.",
                    []
                )

            return self._respond(
                message,
                "OFFICIAL_STATIC",
                f"Found {len(matched)} venue or city reference(s).",
                matched
            )

        return self._respond(
            message,
            "NOT_FOUND",
            f"Unknown request action: {action}.",
            []
        )

    def _respond(
        self,
        request: ACLMessage,
        status: str,
        summary: str,
        records: list[dict]
    ) -> AgentResponse:

        self.status = "COMPLETED" if status in {
            "OFFICIAL_STATIC",
            "ORIGINAL_SCHEDULE",
            "FOUND",
            "UNCONFIRMED",
            "NOT_FOUND"
        } else "FAILED"

        self.last_action = (
            f"{request.content.get('action', 'request')}: {status}"
        )

        response_message = ACLMessage(
            sender=self.name,
            receiver=request.sender,
            performative="INFORM",
            content={
                "status": status,
                "summary": summary,
                "records": records
            },
        )

        response = AgentResponse(
            status,
            summary,
            records,
            request,
            response_message,
            self.status
        )

        self.last_response = response
        return response


def make_request(
    action: str,
    requester: str = "Coordinator Agent",
    **content
) -> ACLMessage:

    return ACLMessage(
        sender=requester,
        receiver=VenueAgent.name,
        performative="REQUEST",
        content={"action": action, **content}
    )
