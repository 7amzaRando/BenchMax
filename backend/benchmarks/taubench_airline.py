"""Tau3-Airline benchmark — multi-turn customer-service tool use.

Port of the airline domain from tau3-bench (sierra-research/tau2-bench,
tag v1.0.1, MIT license). The model plays a customer-service agent against
a simulated user (a second call to the same local model), must use domain
tools over many turns, and is graded on whether the user's goal was
achieved — the multi-turn coherence that single-call BFCL does not measure.

Upstream design reimplemented (not imported — upstream requires Python
>=3.12 plus litellm/pydantic/fastapi; BenchMax is Python 3.11):
- Half-duplex loop: fixed agent greeting -> alternate agent/user turns ->
  tool calls executed synchronously in-process (plain dict ops).
- Termination: agent ``###STOP###``, user ``###STOP###`` / ``###TRANSFER###``
  / ``###OUT-OF-SCOPE###``, 30 agent-turn cap, abort at 10 consecutive
  tool errors (upstream ``max_steps=100`` per routing hop / ``max_errors=10``).
- Grading (upstream ``reward_basis=[DB, COMMUNICATE]`` for all 50 tasks):
  DB 1.0 iff end-state DB hash equals the gold hash, where gold = fresh
  base DB + replay of the task's reference actions. Reference actions are
  NOT a checklist — any trajectory reaching an equivalent end state passes.
  COMMUNICATE 1.0 iff every ``communicate_info`` string appears as a
  case-insensitive substring of the agent's messages (commas stripped from
  the message side only — upstream semantics). Empty -> auto-pass.
  Final score = DB x COMMUNICATE.
- Tool-call protocol is text (GAIA pattern): fenced ```tool JSON blocks.
  Upstream error strings are kept verbatim — models react to them.

Data files (via scripts/fetch_taubench_airline.py):
  data/taubench_airline_full.json (50 samples), _mini.json (5),
  data/taubench_airline_db.json (7 MB base DB, deep-copied per sample),
  data/taubench_airline_policy.md, data/taubench_airline_user_guidelines.md
"""

import ast
import copy
import hashlib
import json
import logging
import operator
import re
import threading
import time
from typing import Any, Dict, List, Optional

from backend.benchmarks.multi_turn_base import (
    MultiTurnBenchmark,
    _clear_live_turn,
    _set_live_turn,
)
from backend.benchmarks.base import resolve_data_file

logger = logging.getLogger(__name__)

# ── Conversation protocol ─────────────────────────────────────────────
GREETING = "Hi! How can I help you today?"
AGENT_STOP = "###STOP###"
USER_STOP_TOKENS = ("###STOP###", "###TRANSFER###", "###OUT-OF-SCOPE###")
MAX_CONSECUTIVE_TOOL_ERRORS = 10

AGENT_INSTRUCTION = (
    "You are a customer service agent that helps the user according to the "
    "<policy> provided below.\n"
    "In each turn you can either:\n"
    "- Send a message to the user.\n"
    "- Make a tool call.\n"
    "You cannot do both at the same time.\n\n"
    "Try to be helpful and always follow the policy. Always make sure you "
    "generate valid JSON only."
)

TOOL_PROTOCOL = (
    "To make a tool call, output a JSON block on its own lines:\n"
    "```tool\n{\"name\": \"tool_name\", \"arguments\": {\"param\": \"value\"}}\n```\n"
    "You may make multiple tool calls in one turn by emitting multiple blocks.\n"
    "After receiving tool results, continue helping the user. When the user's "
    "request is fully resolved, end your message with ###STOP### on its own line."
)

# ── Tool schemas (hand-written from upstream tools.py) ─────────────────
# OpenAI-style {name, description, parameters} used to render the prompt.
TOOL_SCHEMAS = [
    {"name": "book_reservation", "description": "Book a new flight reservation for a user.",
     "parameters": {"type": "object",
        "properties": {"user_id": {"type": "string"}, "origin": {"type": "string"},
            "destination": {"type": "string"}, "flight_type": {"type": "string", "description": "one_way or round_trip"},
            "cabin": {"type": "string", "description": "basic_economy, economy, or business"},
            "flights": {"type": "array", "description": "Array of {flight_number, date} objects"},
            "passengers": {"type": "array", "description": "Array of {first_name, last_name, dob} objects"},
            "payment_methods": {"type": "array", "description": "Array of {payment_id, amount} objects; amounts must add up to the total price"},
            "total_baggages": {"type": "integer"}, "nonfree_baggages": {"type": "integer"},
            "insurance": {"type": "string", "description": "yes or no"}},
        "required": ["user_id", "origin", "destination", "flight_type", "cabin", "flights", "passengers", "payment_methods", "total_baggages", "nonfree_baggages", "insurance"]}},
    {"name": "calculate", "description": "Calculate the result of a mathematical expression (+, -, *, /, parentheses).",
     "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
        "required": ["expression"]}},
    {"name": "cancel_reservation", "description": "Cancel a whole reservation (refunds recorded, status set to cancelled).",
     "parameters": {"type": "object", "properties": {"reservation_id": {"type": "string"}},
        "required": ["reservation_id"]}},
    {"name": "get_reservation_details", "description": "Get the details of a reservation.",
     "parameters": {"type": "object", "properties": {"reservation_id": {"type": "string"}},
        "required": ["reservation_id"]}},
    {"name": "get_user_details", "description": "Get the details of a user, including their reservations.",
     "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}},
        "required": ["user_id"]}},
    {"name": "list_all_airports", "description": "Returns a list of all available airports (IATA code + city).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "search_direct_flight", "description": "Search for direct flights between two airports on a specific date (YYYY-MM-DD).",
     "parameters": {"type": "object",
        "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}, "date": {"type": "string"}},
        "required": ["origin", "destination", "date"]}},
    {"name": "search_onestop_flight", "description": "Search for one-stop flights between two airports on a specific date (YYYY-MM-DD). Returns pairs of flights.",
     "parameters": {"type": "object",
        "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}, "date": {"type": "string"}},
        "required": ["origin", "destination", "date"]}},
    {"name": "send_certificate", "description": "Send a certificate (payment credit) to a user. Be careful!",
     "parameters": {"type": "object",
        "properties": {"user_id": {"type": "string"}, "amount": {"type": "integer"}},
        "required": ["user_id", "amount"]}},
    {"name": "transfer_to_human_agents", "description": "Transfer the user to a human agent with a summary. Only transfer if the user explicitly asks or the issue cannot be solved with the available tools.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}},
        "required": ["summary"]}},
    {"name": "update_reservation_baggages", "description": "Update the baggage counts of a reservation (extra bags cost $50 each, charged to payment_id).",
     "parameters": {"type": "object",
        "properties": {"reservation_id": {"type": "string"}, "total_baggages": {"type": "integer"},
            "nonfree_baggages": {"type": "integer"}, "payment_id": {"type": "string"}},
        "required": ["reservation_id", "total_baggages", "nonfree_baggages", "payment_id"]}},
    {"name": "update_reservation_flights", "description": "Update the flights/cabin of a reservation. flights must list the ENTIRE new itinerary (unchanged segments included). Price difference charged to payment_id.",
     "parameters": {"type": "object",
        "properties": {"reservation_id": {"type": "string"}, "cabin": {"type": "string"},
            "flights": {"type": "array", "description": "Array of {flight_number, date} for the full new itinerary"},
            "payment_id": {"type": "string"}},
        "required": ["reservation_id", "cabin", "flights", "payment_id"]}},
    {"name": "update_reservation_passengers", "description": "Update passenger details. The number of passengers must match.",
     "parameters": {"type": "object",
        "properties": {"reservation_id": {"type": "string"},
            "passengers": {"type": "array", "description": "Array of {first_name, last_name, dob}, same length as before"}},
        "required": ["reservation_id", "passengers"]}},
    {"name": "get_flight_status", "description": "Get the status of a flight on a date (available, landed, cancelled, ...).",
     "parameters": {"type": "object",
        "properties": {"flight_number": {"type": "string"}, "date": {"type": "string"}},
        "required": ["flight_number", "date"]}},
]

_AIRPORTS = [
    ("SFO", "San Francisco"), ("JFK", "New York"), ("LAX", "Los Angeles"),
    ("ORD", "Chicago"), ("DFW", "Dallas"), ("DEN", "Denver"),
    ("SEA", "Seattle"), ("ATL", "Atlanta"), ("MIA", "Miami"),
    ("BOS", "Boston"), ("PHX", "Phoenix"), ("IAH", "Houston"),
    ("LAS", "Las Vegas"), ("MCO", "Orlando"), ("EWR", "Newark"),
    ("CLT", "Charlotte"), ("MSP", "Minneapolis"), ("DTW", "Detroit"),
    ("PHL", "Philadelphia"), ("LGA", "LaGuardia"),
]

_SAFE_ARITH_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_calculate(expression: str) -> str:
    """Upstream calculate(): charset whitelist + eval, rounded to 2 decimals."""
    if not all(c in "0123456789+-*/(). " for c in expression):
        raise ValueError("Invalid characters in expression")
    tree = ast.parse(expression.strip(), mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Not a number: {node.value!r}")
        if isinstance(node, ast.BinOp):
            op = _SAFE_ARITH_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _SAFE_ARITH_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return str(round(float(_eval(tree)), 2))


def _db_hash(db: Dict[str, Any]) -> str:
    """Upstream get_dict_hash(): sha256 over canonical (sorted-key) JSON."""
    return hashlib.sha256(
        json.dumps(db, sort_keys=True, default=str).encode()
    ).hexdigest()


# ── Airline tool environment (plain-dict port of upstream AirlineTools) ─
# All error strings are kept verbatim from upstream tools.py — models react
# to them, and the gold-replay self-check depends on identical behavior.

class _AirlineEnv:
    """In-memory airline DB + tool implementations operating on plain dicts."""

    def __init__(self, db: Dict[str, Any]):
        self.db = db

    # -- lookups --
    def _get_user(self, user_id: str) -> Dict[str, Any]:
        users = self.db.get("users", {})
        if user_id not in users:
            raise ValueError(f"User {user_id} not found")
        return users[user_id]

    def _get_reservation(self, reservation_id: str) -> Dict[str, Any]:
        reservations = self.db.get("reservations", {})
        if reservation_id not in reservations:
            raise ValueError(f"Reservation {reservation_id} not found")
        return reservations[reservation_id]

    def _get_flight(self, flight_number: str) -> Dict[str, Any]:
        flights = self.db.get("flights", {})
        if flight_number not in flights:
            raise ValueError(f"Flight {flight_number} not found")
        return flights[flight_number]

    def _get_flight_instance(self, flight_number: str, date: str) -> Dict[str, Any]:
        flight = self._get_flight(flight_number)
        dates = flight.get("dates", {})
        if date not in dates:
            raise ValueError(f"Flight {flight_number} not found on date {date}")
        return dates[date]

    @staticmethod
    def _is_available(instance: Dict[str, Any]) -> bool:
        return (
            instance.get("status") == "available"
            and isinstance(instance.get("available_seats"), dict)
            and isinstance(instance.get("prices"), dict)
        )

    def _get_new_reservation_id(self) -> str:
        for reservation_id in ["HATHAT", "HATHAU", "HATHAV"]:
            if reservation_id not in self.db.get("reservations", {}):
                return reservation_id
        raise ValueError("Too many reservations")

    @staticmethod
    def _get_datetime() -> str:
        return "2024-05-15T15:00:00"

    def _search_direct_flight(
        self,
        date: str,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        leave_after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for flight in self.db.get("flights", {}).values():
            dates = flight.get("dates", {})
            if not (
                (origin is None or flight.get("origin") == origin)
                and (destination is None or flight.get("destination") == destination)
                and (date in dates)
                and (dates[date].get("status") == "available")
                and (
                    leave_after is None
                    or flight.get("scheduled_departure_time_est", "") >= leave_after
                )
            ):
                continue
            inst = dates[date]
            results.append({
                "flight_number": flight.get("flight_number"),
                "origin": flight.get("origin"),
                "destination": flight.get("destination"),
                "status": "available",
                "scheduled_departure_time_est": flight.get("scheduled_departure_time_est"),
                "scheduled_arrival_time_est": flight.get("scheduled_arrival_time_est"),
                "available_seats": inst.get("available_seats"),
                "prices": inst.get("prices"),
                "date": date,
            })
        return results

    def _payment_for_update(
        self, user: Dict[str, Any], payment_id: str, total_price: float
    ) -> Optional[Dict[str, Any]]:
        methods = user.get("payment_methods", {})
        if payment_id not in methods:
            raise ValueError("Payment method not found")
        method = methods[payment_id]
        if method.get("source") == "certificate":
            raise ValueError("Certificate cannot be used to update reservation")
        if method.get("source") == "gift_card" and method.get("amount", 0) < total_price:
            raise ValueError("Gift card balance is not enough")
        if method.get("source") == "gift_card":
            method["amount"] -= total_price
        if total_price != 0:
            return {"payment_id": payment_id, "amount": total_price}
        return None

    @staticmethod
    def _norm_payment(p: Dict[str, Any]) -> Dict[str, Any]:
        """Accept payment_id or id keys from model JSON (upstream: payment_id)."""
        if "payment_id" in p:
            return {"payment_id": p["payment_id"], "amount": p.get("amount", 0)}
        if "id" in p:
            return {"payment_id": p["id"], "amount": p.get("amount", 0)}
        raise ValueError(f"Payment method {p} not found")

    # -- tools --
    def book_reservation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        user_id = args["user_id"]
        flights = args.get("flights") or []
        passengers = args.get("passengers") or []
        payments_in = args.get("payment_methods") or []
        payments = [self._norm_payment(p) for p in payments_in]
        user = self._get_user(user_id)
        reservation_id = self._get_new_reservation_id()

        reservation: Dict[str, Any] = {
            "reservation_id": reservation_id,
            "user_id": user_id,
            "origin": args.get("origin"),
            "destination": args.get("destination"),
            "flight_type": args.get("flight_type"),
            "cabin": args.get("cabin"),
            "flights": [],
            "passengers": copy.deepcopy(passengers),
            "payment_history": copy.deepcopy(payments),
            "created_at": self._get_datetime(),
            "total_baggages": args.get("total_baggages"),
            "nonfree_baggages": args.get("nonfree_baggages"),
            "insurance": args.get("insurance"),
        }

        cabin = args.get("cabin")
        total_price = 0
        flight_date_data: List[Dict[str, Any]] = []
        for fi in flights:
            flight_number = fi.get("flight_number")
            date = fi.get("date")
            self._get_flight(flight_number)
            inst = self._get_flight_instance(flight_number, date)
            if not self._is_available(inst):
                raise ValueError(
                    f"Flight {flight_number} not available on date {date}"
                )
            if inst["available_seats"].get(cabin, 0) < len(passengers):
                raise ValueError(f"Not enough seats on flight {flight_number}")
            price = inst["prices"][cabin]
            flight = self._get_flight(flight_number)
            reservation["flights"].append({
                "origin": flight.get("origin"),
                "destination": flight.get("destination"),
                "flight_number": flight_number,
                "date": date,
                "price": price,
            })
            flight_date_data.append(inst)
            total_price += price * len(passengers)

        if args.get("insurance") == "yes":
            total_price += 30 * len(passengers)
        total_price += 50 * (args.get("nonfree_baggages") or 0)

        for pm in payments:
            pid, amount = pm["payment_id"], pm["amount"]
            if pid not in user.get("payment_methods", {}):
                raise ValueError(f"Payment method {pid} not found")
            method = user["payment_methods"][pid]
            if method.get("source") in {"gift_card", "certificate"}:
                if method.get("amount", 0) < amount:
                    raise ValueError(
                        f"Not enough balance in payment method {pid}"
                    )

        total_payment = sum(p["amount"] for p in payments)
        if total_payment != total_price:
            raise ValueError(
                f"Payment amount does not add up, total price is {total_price}, "
                f"but paid {total_payment}"
            )

        for pm in payments:
            pid, amount = pm["payment_id"], pm["amount"]
            method = user["payment_methods"][pid]
            if method.get("source") == "gift_card":
                method["amount"] -= amount
            elif method.get("source") == "certificate":
                user["payment_methods"].pop(pid)

        for inst in flight_date_data:
            inst["available_seats"][cabin] -= len(passengers)
        self.db["reservations"][reservation_id] = reservation
        user.setdefault("reservations", []).append(reservation_id)
        return reservation

    def cancel_reservation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reservation = self._get_reservation(args["reservation_id"])
        refunds = [
            {"payment_id": p.get("payment_id"), "amount": -p.get("amount", 0)}
            for p in reservation.get("payment_history", [])
        ]
        reservation.setdefault("payment_history", []).extend(refunds)
        reservation["status"] = "cancelled"
        # Upstream: seats release not implemented for cancellation.
        return reservation

    def send_certificate(self, args: Dict[str, Any]) -> str:
        user = self._get_user(args["user_id"])
        amount = args["amount"]
        methods = user.setdefault("payment_methods", {})
        for pid in ("certificate_3221322", "certificate_3221323", "certificate_3221324"):
            if pid not in methods:
                methods[pid] = {"id": pid, "amount": amount, "source": "certificate"}
                return f"Certificate {pid} added to user {args['user_id']} with amount {amount}."
        raise ValueError("Too many certificates")

    def update_reservation_baggages(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reservation = self._get_reservation(args["reservation_id"])
        user = self._get_user(reservation["user_id"])
        total_price = 50 * max(
            0, (args.get("nonfree_baggages") or 0) - (reservation.get("nonfree_baggages") or 0)
        )
        payment = self._payment_for_update(user, args["payment_id"], total_price)
        if payment is not None:
            reservation.setdefault("payment_history", []).append(payment)
        reservation["total_baggages"] = args.get("total_baggages")
        reservation["nonfree_baggages"] = args.get("nonfree_baggages")
        return reservation

    def update_reservation_flights(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reservation = self._get_reservation(args["reservation_id"])
        user = self._get_user(reservation["user_id"])
        cabin = args.get("cabin")
        flights = args.get("flights") or []

        total_price = 0
        new_flights: List[Dict[str, Any]] = []
        for fi in flights:
            fn, date = fi.get("flight_number"), fi.get("date")
            match = next(
                (rf for rf in reservation.get("flights", [])
                 if rf.get("flight_number") == fn
                 and rf.get("date") == date
                 and cabin == reservation.get("cabin")),
                None,
            )
            if match is not None:
                total_price += match.get("price", 0) * len(reservation.get("passengers", []))
                new_flights.append(match)
                continue
            flight = self._get_flight(fn)
            inst = self._get_flight_instance(fn, date)
            if not self._is_available(inst):
                raise ValueError(f"Flight {fn} not available on date {date}")
            if inst["available_seats"].get(cabin, 0) < len(reservation.get("passengers", [])):
                raise ValueError(f"Not enough seats on flight {fn}")
            entry = {
                "flight_number": fn,
                "date": date,
                "price": inst["prices"][cabin],
                "origin": flight.get("origin"),
                "destination": flight.get("destination"),
            }
            total_price += entry["price"] * len(reservation.get("passengers", []))
            new_flights.append(entry)

        total_price -= sum(
            f.get("price", 0) for f in reservation.get("flights", [])
        ) * len(reservation.get("passengers", []))

        payment = self._payment_for_update(user, args["payment_id"], total_price)
        if payment is not None:
            reservation.setdefault("payment_history", []).append(payment)

        reservation["flights"] = new_flights
        reservation["cabin"] = cabin
        # Upstream: seat counts in the flight DB are intentionally not updated.
        return reservation

    def update_reservation_passengers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reservation = self._get_reservation(args["reservation_id"])
        passengers = args.get("passengers") or []
        if len(passengers) != len(reservation.get("passengers", [])):
            raise ValueError("Number of passengers does not match")
        reservation["passengers"] = copy.deepcopy(passengers)
        return reservation

    def call(self, name: str, args: Dict[str, Any]) -> Any:
        """Dispatch a tool call by name. Raises ValueError on unknown tools."""
        if name == "book_reservation":
            return self.book_reservation(args)
        if name == "calculate":
            return _safe_calculate(args.get("expression", ""))
        if name == "cancel_reservation":
            return self.cancel_reservation(args)
        if name == "get_reservation_details":
            return self._get_reservation(args["reservation_id"])
        if name == "get_user_details":
            return self._get_user(args["user_id"])
        if name == "list_all_airports":
            return [{"iata": iata, "city": city} for iata, city in _AIRPORTS]
        if name == "search_direct_flight":
            return self._search_direct_flight(
                date=args["date"], origin=args.get("origin"),
                destination=args.get("destination"))
        if name == "search_onestop_flight":
            return self._search_onestop(args["origin"], args["destination"], args["date"])
        if name == "send_certificate":
            return self.send_certificate(args)
        if name == "transfer_to_human_agents":
            return "Transfer successful"
        if name == "update_reservation_baggages":
            return self.update_reservation_baggages(args)
        if name == "update_reservation_flights":
            return self.update_reservation_flights(args)
        if name == "update_reservation_passengers":
            return self.update_reservation_passengers(args)
        if name == "get_flight_status":
            return self._get_flight_instance(args["flight_number"], args["date"]).get("status")
        raise ValueError(f"Unknown tool '{name}'")

    def _search_onestop(
        self, origin: str, destination: str, date: str
    ) -> List[List[Dict[str, Any]]]:
        # Verbatim upstream quirk: date2 built without zero-padding.
        results = []
        for r1 in self._search_direct_flight(date=date, origin=origin, destination=None):
            sched_arr = r1.get("scheduled_arrival_time_est") or ""
            date2 = (
                f"2024-05-{int(date[-2:]) + 1}"
                if "+1" in sched_arr
                else date
            )
            for r2 in self._search_direct_flight(
                date=date2, origin=r1.get("destination"),
                destination=destination, leave_after=sched_arr,
            ):
                r2_out = dict(r2)
                r2_out["date"] = date2
                r1_out = dict(r1)
                r1_out["date"] = date
                results.append([r1_out, r2_out])
        return results


WRITE_TOOLS = frozenset({
    "book_reservation", "cancel_reservation", "send_certificate",
    "update_reservation_baggages", "update_reservation_flights",
    "update_reservation_passengers",
})


class Tau3AirlineBenchmark(MultiTurnBenchmark):
    """tau3-bench airline domain: multi-turn customer-service tool use."""

    _base_db: Optional[Dict[str, Any]] = None
    _policy: Optional[str] = None
    _guidelines: Optional[str] = None
    _data_lock = threading.Lock()

    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)
        # Working DBs for samples currently being evaluated (task_id -> db).
        # score() reads the working DB stashed here by evaluate_sample().
        self._live_db: Dict[str, Dict[str, Any]] = {}

    # -- data loading --
    @classmethod
    def _load_shared(cls) -> None:
        """Load base DB + policy + guidelines once (thread-safe)."""
        if cls._base_db is not None and cls._policy is not None and cls._guidelines is not None:
            return
        with cls._data_lock:
            if cls._base_db is None:
                p = resolve_data_file(__file__, "taubench_airline_db.json")
                if not p:
                    raise FileNotFoundError(
                        "Tau3-Airline DB not found. Run "
                        "'python scripts/fetch_taubench_airline.py' or install via the dataset installer."
                    )
                with open(p, encoding="utf-8") as f:
                    cls._base_db = json.load(f)
                logger.info("Loaded Tau3-Airline base DB: %d reservations",
                            len(cls._base_db.get("reservations", {})))
            for attr, fname in (("_policy", "taubench_airline_policy.md"),
                                ("_guidelines", "taubench_airline_user_guidelines.md")):
                if getattr(cls, attr) is None:
                    p = resolve_data_file(__file__, fname)
                    if not p:
                        raise FileNotFoundError(
                            f"Tau3-Airline file {fname} not found. Run "
                            "'python scripts/fetch_taubench_airline.py'."
                        )
                    with open(p, encoding="utf-8") as f:
                        setattr(cls, attr, f.read())

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(
            "taubench_airline_full.json",
            fetch_hint="Run 'python scripts/fetch_taubench_airline.py' or use the dataset installer.",
        )
        return self._load_json_cached(path)

    # -- prompt construction --
    @staticmethod
    def _request_messages(system_prompt: str,
                           conversation: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Build the API request: system + history without leading non-user messages.

        The agent greeting stays in the stored trajectory (upstream fidelity)
        but must not be sent: several chat templates (e.g. ornith) raise
        "No user query found in messages" when the first non-system message
        is not user-role, and the stream comes back empty.
        Returns [] when no user message exists at all (caller must not send).
        """
        rest = list(conversation)
        while rest and rest[0].get("role") != "user":
            rest = rest[1:]
        if not rest:
            return []
        return [{"role": "system", "content": system_prompt}] + rest

    def _format_tools_for_prompt(self) -> str:
        lines = []
        for tool in TOOL_SCHEMAS:
            params = tool.get("parameters", {}).get("properties", {})
            required = tool.get("parameters", {}).get("required", [])
            lines.append(f"- {tool['name']}: {tool['description']}")
            for pname, pinfo in params.items():
                req = "(required)" if pname in required else "(optional)"
                desc = pinfo.get("description", pinfo.get("type", ""))
                lines.append(f"    {pname}: {desc} {req}")
        return "\n".join(lines)

    def _agent_system_prompt(self) -> str:
        self._load_shared()
        assert self._policy is not None
        return (
            "<instructions>\n" + AGENT_INSTRUCTION + "\n</instructions>\n"
            "<policy>\n" + self._policy.strip() + "\n</policy>\n\n"
            "You have access to the following tools:\n\n"
            + self._format_tools_for_prompt() + "\n\n"
            + TOOL_PROTOCOL
        )

    @staticmethod
    def _render_scenario(scenario: Dict[str, Any]) -> str:
        """Upstream UserScenario.__str__ format (persona + structured instructions)."""
        lines = []
        persona = scenario.get("persona")
        if persona:
            lines.append("Persona:")
            lines.append("\t" + persona.replace("\n", "\n\t"))
        ins = scenario.get("instructions") or {}
        if isinstance(ins, str):
            ins = {"task_instructions": ins}
        sub = [
            f"Domain: {ins.get('domain', 'airline')}",
            "Reason for call:\n\t" + str(ins.get("reason_for_call", "")).replace("\n", "\n\t"),
        ]
        if ins.get("known_info"):
            sub.append("Known info:\n\t" + str(ins["known_info"]).replace("\n", "\n\t"))
        if ins.get("unknown_info"):
            sub.append("Unknown info:\n\t" + str(ins["unknown_info"]).replace("\n", "\n\t"))
        sub.append("Task instructions:\n\t" + str(ins.get("task_instructions", "")).replace("\n", "\n\t"))
        lines.append("Instructions:")
        lines.append("\t" + "\n".join(sub).replace("\n", "\n\t"))
        return "\n".join(lines)

    def _user_system_prompt(self, sample: Dict[str, Any]) -> str:
        self._load_shared()
        assert self._guidelines is not None
        scenario = self._render_scenario(sample.get("user_scenario") or {})
        return (
            self._guidelines.strip()
            + "\n\n<scenario>\n" + scenario + "\n</scenario>"
        )

    # -- tool-call parsing (GAIA text protocol) --
    @staticmethod
    def _parse_tool_calls(response: str) -> List[Dict[str, Any]]:
        tool_calls = []
        for match in re.finditer(r"```tool\s*\n(.*?)\n\s*```", response, re.DOTALL):
            try:
                call = json.loads(match.group(1).strip())
                if "name" in call:
                    tool_calls.append({
                        "name": call["name"],
                        "arguments": call.get("arguments", {}) or {},
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        if not tool_calls:
            # Strategy 2: bare JSON objects (balanced-brace scan so nested
            # "arguments" objects decode — a flat [^{}]* regex cannot).
            decoder = json.JSONDecoder()
            for m in re.finditer(r"\{", response):
                try:
                    obj, _ = decoder.raw_decode(response[m.start():])
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and "name" in obj:
                    tool_calls.append({
                        "name": obj["name"],
                        "arguments": obj.get("arguments", {}) or {},
                    })
        return tool_calls

    # -- gold computation + grading --
    def _gold_hash(self, sample: Dict[str, Any]) -> str:
        """Fresh base DB + replay of reference actions (upstream gold env)."""
        self._load_shared()
        assert self._base_db is not None
        db = copy.deepcopy(self._base_db)
        env = _AirlineEnv(db)
        for action in sample.get("reference_actions") or []:
            try:
                env.call(action.get("name", ""), action.get("arguments") or {})
            except Exception as e:
                logger.warning("Gold replay: %s(%s) failed: %s",
                               action.get("name"), action.get("arguments"), e)
        return _db_hash(db)

    def replay_reference(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """Replay reference actions on a fresh DB (gold-replay self-check helper).

        Returns the gold DB dict. Stable across calls iff the port is
        deterministic — the acceptance self-check hashes this twice.
        """
        self._load_shared()
        assert self._base_db is not None
        db = copy.deepcopy(self._base_db)
        env = _AirlineEnv(db)
        errors = []
        for action in sample.get("reference_actions") or []:
            try:
                env.call(action.get("name", ""), action.get("arguments") or {})
            except Exception as e:
                errors.append(f"{action.get('name')}: {e}")
        return {"db": db, "hash": _db_hash(db), "errors": errors}

    @staticmethod
    def _communicate_match(sample: Dict[str, Any],
                           conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """Upstream CommunicateEvaluator semantics: case-insensitive substring,
        commas stripped from the message side only. Empty -> auto-pass."""
        needed = sample.get("communicate_info") or []
        if not needed:
            return {"match": True, "missing": [], "needed": []}
        agent_texts = [
            m.get("content", "") for m in conversation if m.get("role") == "assistant"
        ]
        missing = [
            info for info in needed
            if not any(info.lower() in (t or "").lower().replace(",", "")
                       for t in agent_texts)
        ]
        return {"match": not missing, "missing": missing, "needed": needed}

    # -- MultiTurnBenchmark contract --
    async def evaluate_turn(
        self,
        turn_idx: int,
        conversation: List[Dict[str, str]],
        sample: Dict[str, Any],
        params: Dict[str, Any],
        model_name: str,
    ) -> Dict[str, Any]:
        """Single agent turn: generate with full history, parse tool calls."""
        messages = self._request_messages(self._agent_system_prompt(), conversation)
        if not messages:
            # No user message yet (e.g. empty user-sim opener) — nothing
            # valid to send; the loop treats this as an empty response.
            return {"response": "", "tool_calls": None, "done": False, "gen": None}
        gen = await self._generate_chat(messages, params, model_name)
        response = gen.get("answer_content", "") or gen.get("raw_response", "")
        tool_calls = self._parse_tool_calls(response)
        done = AGENT_STOP in response
        return {
            "response": response,
            "tool_calls": tool_calls if tool_calls else None,
            "done": done,
            "gen": gen,
        }

    async def execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        sample: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Execute tool calls against the sample's working DB (in-memory)."""
        task_id = sample.get("task_id", "")
        db = self._live_db.get(task_id)
        if db is None:
            return [{"role": "tool",
                     "content": f"Error: no working DB for task {task_id}"}]
        env = _AirlineEnv(db)
        results = []
        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("arguments", {}) or {}
            if not isinstance(args, dict):
                results.append({"role": "tool", "tool": name,
                                "content": f"Error: arguments for '{name}' must be a JSON object"})
                continue
            try:
                out = env.call(name, args)
                results.append({"role": "tool", "tool": name,
                                "content": f"{name}({json.dumps(args, default=str)}) = "
                                           f"{json.dumps(out, default=str)}"})
            except Exception as e:
                # Verbatim upstream error strings surface to the model.
                results.append({"role": "tool", "tool": name,
                                "content": f"Error: {e}"})
        return results

    def score(
        self,
        sample: Dict[str, Any],
        conversation: List[Dict[str, str]],
        final_response: str,
    ) -> Dict[str, Any]:
        """Final score = DB match x COMMUNICATE match (upstream reward_basis)."""
        task_id = sample.get("task_id", "")
        db = self._live_db.get(task_id)
        if db is None:
            return {"correct": False, "score": 0.0,
                    "details": {"error": "no working DB — sample was never evaluated"}}
        db_match = _db_hash(db) == self._gold_hash(sample)
        comm = self._communicate_match(sample, conversation)
        correct = bool(db_match and comm["match"])
        return {
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "details": {
                "db_match": db_match,
                "communicate_match": comm["match"],
                "communicate_missing": comm["missing"],
                "communicate_needed": comm["needed"],
                "category": sample.get("category", "airline"),
            },
        }

    # -- half-duplex conversation loop (overrides single-party base loop) --
    async def _user_turn(
        self,
        conversation: List[Dict[str, str]],
        sample: Dict[str, Any],
        params: Dict[str, Any],
        model_name: str,
    ) -> Dict[str, Any]:
        """User-simulator turn: same local model, guidelines+scenario prompt,
        flipped roles (agent texts as 'user'). Sees text only — never tools."""
        flipped: List[Dict[str, str]] = []
        for m in conversation:
            role, content = m.get("role"), m.get("content", "")
            if role == "assistant" and content.strip():
                flipped.append({"role": "user", "content": content})
            elif role == "user" and content.strip():
                flipped.append({"role": "assistant", "content": content})
        messages = self._request_messages(self._user_system_prompt(sample), flipped)
        if not messages:
            return {"response": "", "done": True, "gen": None}
        self._truncate_conversation(messages, await self._get_model_context_limit(model_name))
        # Truncation drops oldest pairs — re-strip in case a non-user
        # message floated to the front.
        messages = self._request_messages(messages[0]["content"], messages[1:])
        if not messages:
            return {"response": "", "done": True, "gen": None}
        gen = await self._generate_chat(messages, params, model_name)
        response = gen.get("answer_content", "") or gen.get("raw_response", "")
        done = any(tok in response for tok in USER_STOP_TOKENS)
        return {"response": response, "done": done, "gen": gen}

    async def evaluate_sample(
        self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str
    ) -> Dict[str, Any]:
        """Run the half-duplex agent/user simulation and score the end state."""
        self._load_shared()
        assert self._base_db is not None
        task_id = sample.get("task_id", "")
        max_turns = sample.get("max_turns", 30)
        max_wall_clock = sample.get("max_wall_clock_sec", 1200)

        working_db = copy.deepcopy(self._base_db)
        self._live_db[task_id] = working_db

        conversation: List[Dict[str, str]] = [
            {"role": "assistant", "content": GREETING}
        ]
        turn_details: List[Dict[str, Any]] = [
            {"turn": -1, "role": "assistant", "content": GREETING}
        ]

        total = {"thinking": 0, "response": 0, "prompt": 0}
        total_elapsed = 0.0
        last_tps = 0.0
        last_ttft = 0.0

        def _accumulate(gen: Optional[Dict[str, Any]]) -> None:
            nonlocal total_elapsed, last_tps, last_ttft
            if not gen:
                return
            total["thinking"] += gen.get("thinking_tokens", 0)
            total["response"] += gen.get("response_tokens", 0)
            total["prompt"] += gen.get("prompt_tokens", 0)
            total_elapsed += gen.get("elapsed_time", 0.0)
            last_tps = gen.get("tps", 0.0)
            last_ttft = gen.get("ttft", 0.0)

        def _record(turn: int, role: str, content: str,
                    gen: Optional[Dict[str, Any]],
                    tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
            entry: Dict[str, Any] = {
                "turn": turn, "role": role, "content": (content or "")[:4000],
            }
            if gen:
                entry.update({
                    "tps": gen.get("tps", 0.0), "ttft": gen.get("ttft", 0.0),
                    "thinking_tokens": gen.get("thinking_tokens", 0),
                    "response_tokens": gen.get("response_tokens", 0),
                    "prompt_tokens": gen.get("prompt_tokens", 0),
                    "elapsed_time": gen.get("elapsed_time", 0.0),
                })
            if tool_calls:
                entry["tool_calls"] = tool_calls
            turn_details.append(entry)

        sample_start = time.time()
        run_id = params.get("_run_id") or params.get("run_id")
        agent_turns = 0
        consecutive_errors = 0
        termination = "max_turns"

        try:
            # First user turn answers the greeting.
            user_first = await self._user_turn(
                conversation, sample, params, model_name)
            _accumulate(user_first.get("gen"))
            if (user_first.get("response") or "").strip():
                conversation.append({"role": "user",
                                     "content": user_first["response"]})
                _record(0, "user", user_first["response"], user_first.get("gen"))
            if user_first.get("done"):
                termination = "user_stop"

            while agent_turns < max_turns and termination == "max_turns":
                if time.time() - sample_start >= max_wall_clock:
                    termination = "wall_clock"
                    logger.warning("Tau3-Airline %s: wall-clock cap hit", task_id)
                    break
                agent_turns += 1
                _set_live_turn(run_id, agent_turns, max_turns,
                               time.time() - sample_start)

                try:
                    turn = await self.evaluate_turn(
                        agent_turns - 1, conversation, sample, params, model_name)
                except Exception as e:
                    logger.error("Tau3-Airline %s agent turn %d failed: %s",
                                 task_id, agent_turns, e)
                    termination = "agent_error"
                    turn_details.append({"turn": agent_turns, "role": "assistant",
                                         "content": f"[agent turn failed: {e}]"})
                    break

                gen = turn.get("gen")
                _accumulate(gen)
                response = turn.get("response", "") or ""
                tool_calls = turn.get("tool_calls")
                agent_stop = turn.get("done", False)

                if not response.strip() and not tool_calls:
                    logger.info("Tau3-Airline %s: empty agent response, stopping",
                                task_id)
                    _record(agent_turns, "assistant", "[empty response]", gen)
                    termination = "empty_response"
                    break

                if response.strip():
                    conversation.append({"role": "assistant", "content": response})
                _record(agent_turns, "assistant", response, gen, tool_calls)

                transferred = False
                if tool_calls:
                    tool_results = await self.execute_tools(tool_calls, sample)
                    conversation.extend(tool_results)
                    for tr in tool_results:
                        turn_details.append({
                            "turn": agent_turns, "role": "tool",
                            "content": tr.get("content", "")[:2000],
                            "tool": tr.get("tool", ""),
                        })
                        if (tr.get("content", "") or "").startswith("Error:"):
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 0
                    transferred = any(
                        c.get("name") == "transfer_to_human_agents"
                        for c in tool_calls
                    )
                    if consecutive_errors >= MAX_CONSECUTIVE_TOOL_ERRORS:
                        logger.warning("Tau3-Airline %s: %d consecutive tool errors",
                                       task_id, consecutive_errors)
                        termination = "too_many_tool_errors"
                        break

                if agent_stop:
                    termination = "agent_stop"
                    break
                if transferred:
                    termination = "transfer"
                    break

                # User answers the agent's text (tool traffic stays hidden).
                if response.strip():
                    try:
                        user_turn = await self._user_turn(
                            conversation, sample, params, model_name)
                    except Exception as e:
                        logger.error("Tau3-Airline %s user turn failed: %s",
                                     task_id, e)
                        termination = "user_error"
                        break
                    _accumulate(user_turn.get("gen"))
                    user_response = user_turn.get("response") or ""
                    if user_response.strip():
                        conversation.append({"role": "user", "content": user_response})
                    _record(agent_turns, "user", user_response or "[empty response]",
                            user_turn.get("gen"))
                    if user_turn.get("done"):
                        termination = "user_stop"
                        break
                    if not user_response.strip():
                        termination = "empty_response"
                        break
        finally:
            _clear_live_turn()

        final_response = ""
        for m in reversed(conversation):
            if m.get("role") == "assistant" and (m.get("content") or "").strip():
                final_response = m["content"]
                break
        try:
            score_result = self.score(sample, conversation, final_response)
        except Exception as e:
            logger.error("Tau3-Airline %s score() failed: %s", task_id, e)
            score_result = {"correct": False, "score": 0.0,
                            "details": {"error": f"Scoring failed: {e}"}}
        finally:
            self._live_db.pop(task_id, None)

        prompt_summary = "\n".join(
            m["content"] for m in conversation if m.get("role") == "user")
        raw_response = "\n---\n".join(
            m["content"] for m in conversation if m.get("role") == "assistant")

        return self._result(
            prompt_summary,
            {"elapsed_time": total_elapsed, "tps": last_tps, "ttft": last_ttft,
             "thinking_tokens": total["thinking"],
             "response_tokens": total["response"],
             "prompt_tokens": total["prompt"],
             "raw_response": raw_response},
            correct=score_result.get("correct", False),
            error_message=None if score_result.get("correct")
            else score_result.get("details", {}).get("error"),
            scoring_details={
                "score": score_result.get("score", 0.0),
                "turns_used": agent_turns,
                "conversation_length": len(conversation),
                "turns": turn_details,
                "max_turns": max_turns,
                "termination": termination,
                **score_result.get("details", {}),
            },
        )
