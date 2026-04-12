"""
agents/product_agent.py -- Product Manager Agent
Receives a task from the CEO and produces a structured product specification.
"""

import uuid
import json
from datetime import datetime, timezone

from message_bus import send_message, log_message
from utils.llm import call_llm, parse_json_response


class ProductAgent:
    NAME = "product"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_message(self, to_agent: str, msg_type: str, payload: dict,
                      parent_id: str = None) -> dict:
        msg = {
            "message_id": f"msg-{uuid.uuid4().hex[:8]}",
            "from_agent": self.NAME,
            "to_agent": to_agent,
            "message_type": msg_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if parent_id:
            msg["parent_message_id"] = parent_id
        return msg

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _generate_spec(self, idea: str, extra_focus: str = "") -> dict:
        system_prompt = (
            "You are a senior product manager at a tech startup. "
            "Your job is to produce a rigorous, highly specific product specification. "
            "Always return a valid JSON object with no markdown fences and no extra text."
        )
        user_prompt = f"""
Startup Idea: {idea}
Additional Focus: {extra_focus}

Produce a product specification JSON with EXACTLY these fields:
{{
  "project_name": "<a creative, 1-2 word brand name for this startup>",
  "value_proposition": "<one sentence: what the product does and for whom>",
  "personas": [
    {{"name": "<first name>", "role": "<job/lifestyle>", "pain_point": "<specific frustration related to the idea>"}},
    {{"name": "...", "role": "...", "pain_point": "..."}}
  ],
  "features": [
    {{"name": "<feature>", "description": "<1-2 sentences>", "priority": 1}},
    {{"name": "...", "description": "...", "priority": 2}},
    {{"name": "...", "description": "...", "priority": 3}},
    {{"name": "...", "description": "...", "priority": 4}},
    {{"name": "...", "description": "...", "priority": 5}}
  ],
  "user_stories": [
    "As a <user>, I want to <action> so that <benefit>.",
    "As a <user>, I want to <action> so that <benefit>.",
    "As a <user>, I want to <action> so that <benefit>."
  ]
}}

Make every field highly specific to the provided idea. NO generic placeholders. 
Do NOT use the name 'LeftoverLoot' unless it is part of the provided Startup Idea.
Return ONLY the JSON object.
"""
        print("  🧠 [PRODUCT] Calling LLM to generate product spec …")
        raw = call_llm(system_prompt, user_prompt)
        spec = parse_json_response(raw)

        # Validate minimum structure; fall back to defaults on catastrophic failure
        if not spec.get("value_proposition") or not spec.get("project_name"):
            spec = self._fallback_spec(idea)
        return spec

    @staticmethod
    def _fallback_spec(idea: str) -> dict:
        # Crude fallback parsing
        name = idea.split("—")[0].strip() if "—" in idea else "StartupX"
        return {
            "project_name": name,
            "value_proposition": f"A platform based on the idea: {idea}",
            "personas": [
                {
                    "name": "Alex",
                    "role": "Target User",
                    "pain_point": "Needs a better way to solve the core problem addressed by this idea.",
                }
            ],
            "features": [
                {
                    "name": "Core Platform",
                    "description": "The primary interface for users to interact with the service.",
                    "priority": 1,
                }
            ],
            "user_stories": [
                f"As a user, I want to use {name} so that I can benefit from this innovation."
            ],
        }

    # ── Public run method ─────────────────────────────────────────────────────

    def run(self, startup_idea: str, task_message_id: str = None,
            extra_focus: str = "") -> dict:
        """
        Generate the product specification and broadcast it via the message bus.
        Returns the spec dict for the CEO to review.
        """
        print("\n" + "─" * 55)
        print("👔 PRODUCT AGENT: Generating product specification …")

        spec = self._generate_spec(startup_idea, extra_focus)

        print("  ✅ Spec generated:")
        print(f"     project_name      : {spec.get('project_name', '')}")
        print(f"     value_proposition : {spec.get('value_proposition', '')[:80]}...")
        print(f"     personas          : {len(spec.get('personas', []))} defined")

        # Send spec to Engineer
        msg_eng = self._make_message(
            to_agent="engineer",
            msg_type="task",
            payload={"product_spec": spec},
            parent_id=task_message_id,
        )
        send_message(msg_eng)

        # Send spec to Marketing
        msg_mkt = self._make_message(
            to_agent="marketing",
            msg_type="task",
            payload={"product_spec": spec},
            parent_id=task_message_id,
        )
        send_message(msg_mkt)

        # Confirmation back to CEO
        msg_confirm = self._make_message(
            to_agent="ceo",
            msg_type="confirmation",
            payload={"status": "product_spec_ready", "spec_summary": spec.get("value_proposition", "")},
            parent_id=task_message_id,
        )
        send_message(msg_confirm)

        return spec