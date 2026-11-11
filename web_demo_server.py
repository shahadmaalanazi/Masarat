"""Local web server for the Masaraat multi-agent demo.

Run with: python web_demo_server.py
This adapter calls the existing CoordinatorAgent without changing it.
"""
from __future__ import annotations

import json
import os
import time
import sys
import types
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

def install_optional_agent_fallbacks():
    """Let the real agents run when optional tracing/LLM packages are absent.

    TravelAgent already catches model-call failures and falls back to its
    inventory-ranked option. These shims preserve that behavior; they do not
    replace any of the project agents or coordinator.
    """
    try:
        import langsmith  # noqa: F401
    except ImportError:
        module = types.ModuleType("langsmith")
        module.traceable = lambda **kwargs: (lambda fn: fn)
        sys.modules["langsmith"] = module
    try:
        import langchain_google_genai  # noqa: F401
    except ImportError:
        module = types.ModuleType("langchain_google_genai")
        class ChatGoogleGenerativeAI:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("Gemini package is not installed; using the agent's inventory-ranked fallback.")
        module.ChatGoogleGenerativeAI = ChatGoogleGenerativeAI
        sys.modules["langchain_google_genai"] = module


install_optional_agent_fallbacks()
from coordinator_agent import CoordinatorAgent
from venue_agent import estimate_ticket_price
from venue_data import list_matches
from real_data import TRANSPORT_OPTIONS


class DemoPlanSelector:
    """Deterministic preference selector used when the Gemini key is absent."""
    def select(self, request, eligible_plans):
        if request.get("priority") == "comfort":
            chosen = max(
                eligible_plans,
                key=lambda item: (item["comfort_level"], -item["total_cost_sar"]),
            )
            reason = "Highest comfort among eligible plans, with cost as a tie-breaker."
        else:
            chosen = min(eligible_plans, key=lambda item: item["total_cost_sar"])
            reason = "Lowest total cost among plans that passed the Fan Agent's constraints."
        return {
            "plan_id": chosen["plan_id"],
            "reason": reason,
        }

ROOT = Path(__file__).resolve().parent
REQUESTS_BY_IP = {}


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _cors(self):
        origin = self.headers.get("Origin", "")
        allowed = {x.strip() for x in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765").split(",") if x.strip()}
        if origin in allowed or "*" in allowed:
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
            self.send_header("Vary", "Origin")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/matches":
            origin_cities = sorted({route["origin"] for route in TRANSPORT_OPTIONS})
            matches = [
                {
                    "match_id": item["match_id"],
                    "label": f"{item['team_1']} × {item['team_2']}",
                    "city": item["city"],
                    "date": item["date"],
                    "status": item.get("schedule_status", "UNKNOWN"),
                }
                for item in list_matches()
            ]
            return self._send_json({"matches": matches, "origin_cities": origin_cities})
        if path == "/api/health":
            return self._send_json({"ok": True, "coordinator": "CoordinatorAgent"})
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/coordinate":
            return self._send_json({"error": "Not found"}, 404)
        try:
            now = time.time()
            client = self.client_address[0]
            recent = [stamp for stamp in REQUESTS_BY_IP.get(client, []) if now - stamp < 60]
            if len(recent) >= 12:
                REQUESTS_BY_IP[client] = recent
                return self._send_json({"error": "وصلت للحد المؤقت من الطلبات. حاول بعد دقيقة."}, 429)
            recent.append(now)
            REQUESTS_BY_IP[client] = recent
            size = int(self.headers.get("Content-Length", "0"))
            if size > 20_000:
                return self._send_json({"error": "Request too large"}, 413)
            request = json.loads(self.rfile.read(size))
            origin = str(request.get("origin_city", "")).strip()
            match_id = str(request.get("match_id", "")).strip().upper()
            budget = int(request.get("budget_sar", 0))
            priority = str(request.get("priority", "lowest_cost"))
            allowed_origins = {route["origin"] for route in TRANSPORT_OPTIONS}
            matches = {m["match_id"] for m in list_matches()}
            if origin not in allowed_origins or match_id not in matches or priority not in {"lowest_cost", "comfort"} or not 300 <= budget <= 100_000:
                return self._send_json({"error": "تأكد من مدينة الانطلاق والمباراة والميزانية."}, 400)

            fan_request = {
                "fan_id": "WEB-DEMO-001",
                "origin_city": origin,
                "budget_sar": budget,
                "preferred_match_ids": [match_id],
                "priority": priority,
            }
            result = CoordinatorAgent().coordinate(fan_request, selector=DemoPlanSelector())
            match = next(m for m in list_matches() if m["match_id"] == match_id)
            plans = result.get("proposed_plans", [])
            messages = result.get("message_log", [])
            return self._send_json({
                "status": result.get("status"),
                "match": {
                    "match_id": match_id,
                    "label": f"{match['team_1']} × {match['team_2']}",
                    "city": match["city"],
                    "date": match["date"],
                    "schedule_status": match.get("schedule_status", "UNKNOWN"),
                    "ticket_estimate_sar": estimate_ticket_price(match_id),
                    "ticket_price_type": "ESTIMATED_SIMULATED",
                },
                "plans": plans,
                "messages": messages,
                "pending_reasons": result.get("pending_reasons", []),
                "agent_results": result.get("agent_results", []),
                "selection_method": "lowest_cost_rules",
            })
        except Exception as exc:
            return self._send_json({"error": f"تعذر تشغيل الوكلاء: {type(exc).__name__}: {exc}"}, 500)


def serve():
    host = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), DemoHandler)
    print(f"Masaraat demo API ready at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo server stopped.")
        server.server_close()


if __name__ == "__main__":
    serve()
