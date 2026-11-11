from coordinator_agent import CoordinatorAgent

fan_request = {
    "fan_id": "F001",
    "origin_city": "Jeddah",
    "budget_sar": 1500,
    "preferred_match_ids": ["M001"],
    "priority": "lowest_cost",
}

result = CoordinatorAgent().coordinate(fan_request)

print("Status:", result["status"])
print("Pending reasons:", result["pending_reasons"])