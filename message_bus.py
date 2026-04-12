"""
message_bus.py — Shared in-memory message bus for LaunchMind agents.
All agents communicate by appending/reading structured JSON messages here.
"""

from collections import defaultdict
import json

# ── Core message store ────────────────────────────────────────────────────────
# Each key is an agent name; value is a list of messages addressed to that agent
message_bus: dict = defaultdict(list)

# ── Full history log (for demo — evaluator can inspect every message) ─────────
message_history: list = []


def log_message(message: dict) -> None:
    """Record a message in the global history log and print a trace line."""
    message_history.append(message)
    print(
        f"\n📨 [BUS] {message['from_agent'].upper()} → {message['to_agent'].upper()} "
        f"| type={message['message_type']} | id={message['message_id']}"
    )


def send_message(message: dict) -> None:
    """Route a message to the recipient's queue and log it."""
    log_message(message)
    message_bus[message["to_agent"]].append(message)


def get_messages(agent_name: str) -> list:
    """Return all queued messages for a given agent (does not clear the queue)."""
    return list(message_bus.get(agent_name, []))


def print_full_history() -> None:
    """Pretty-print the complete inter-agent message log (for demo)."""
    divider = "=" * 65
    print(f"\n{divider}")
    print("📋  COMPLETE INTER-AGENT MESSAGE HISTORY")
    print(divider)
    for idx, msg in enumerate(message_history, 1):
        print(f"\n  [{idx}]  {msg['timestamp']}")
        print(f"        FROM : {msg['from_agent']}")
        print(f"        TO   : {msg['to_agent']}")
        print(f"        TYPE : {msg['message_type']}   ID: {msg['message_id']}")
        if msg.get("parent_message_id"):
            print(f"        PARENT: {msg['parent_message_id']}")
        payload_str = json.dumps(msg["payload"], indent=6)
        if len(payload_str) > 600:
            payload_str = payload_str[:600] + "\n      ... (truncated)"
        print(f"        PAYLOAD:\n{payload_str}")
    print(f"\n{divider}\n")