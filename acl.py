"""Masarat v1 ACL-like message format shared by all group members."""
from datetime import datetime, timezone
from uuid import uuid4

ONTOLOGY = "masarat-travel-planning-v1"
PERFORMATIVES = {"REQUEST", "INFORM", "CFP", "PROPOSE", "ACCEPT", "REFUSE"}
AGENT_NAMES = {
    "FanAgent",
    "TravelAgent",
    "AccommodationAgent",
    "VenueAgent",
    "CoordinatorAgent",
}


def create_acl_message(sender, receiver, performative, content, conversation_id):
    """Make one JSON-serializable ACL-like message. Use dict content, not raw text."""
    if sender not in AGENT_NAMES or receiver not in AGENT_NAMES:
        raise ValueError(f"Unknown agent name: {sender} -> {receiver}")
    if performative not in PERFORMATIVES:
        raise ValueError(f"Unsupported performative: {performative}")
    if not isinstance(content, dict):
        raise TypeError("ACL content must be a dictionary")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be a non-empty string")
    return {
        "message_id": uuid4().hex[:12],
        "conversation_id": conversation_id,
        "sender": sender,
        "receiver": receiver,
        "performative": performative,
        "ontology": ONTOLOGY,
        "language": "JSON",
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def validate_proposal_message(message):
    """Verify a Coordinator -> Fan PROPOSE and extract its list of trip plans."""
    if not isinstance(message, dict):
        raise TypeError("message must be a dictionary")
    if (message.get("sender"), message.get("receiver"), message.get("performative")) != (
        "CoordinatorAgent", "FanAgent", "PROPOSE"
    ):
        raise ValueError("Expected CoordinatorAgent -> FanAgent PROPOSE")
    if message.get("ontology") != ONTOLOGY:
        raise ValueError("Unexpected ACL ontology")
    content = message.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("proposed_plans"), list):
        raise ValueError("PROPOSE content must contain proposed_plans list")
    return content["proposed_plans"]
