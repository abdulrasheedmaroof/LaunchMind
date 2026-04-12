"""
agents/ceo_agent.py -- CEO / Orchestrator Agent
The brain of LaunchMind. Handles task decomposition and feedback loops.
"""

import uuid
import os
import json
from datetime import datetime, timezone

from message_bus import send_message, log_message
from utils.llm import call_llm, parse_json_response
from agents.marketing_agent import post_final_slack_summary


class CEOAgent:
    NAME = "ceo"

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

    def _send(self, msg: dict) -> None:
        send_message(msg)
        print(f"\n  📤 [CEO → {msg['to_agent'].upper()}] type={msg['message_type']} | id={msg['message_id']}")

    # ── LLM Decisions ──────────────────────────────────────────────────────────

    def decompose_idea(self, startup_idea: str) -> dict:
        system_prompt = "You are the CEO of a startup accelerator. Return ONLY JSON."
        user_prompt = f"Startup Idea: {startup_idea}\n\nGenerate task JSON with: product_task, engineer_task, marketing_task."
        print("\n  🧠 [CEO] LLM Call 1 — Decomposing startup idea into tasks …")
        raw = call_llm(system_prompt, user_prompt)
        return parse_json_response(raw)

    def review_product_spec(self, spec: dict) -> dict:
        system_prompt = "You are a critical CEO. Return ONLY JSON."
        user_prompt = f"Review this spec: {json.dumps(spec)[:2000]}\n\nReturn JSON: {{ 'verdict': 'pass/fail', 'reasoning': '...', 'feedback': '...' }}"
        print("\n  🧠 [CEO] LLM Call 2 — Reviewing product spec …")
        raw = call_llm(system_prompt, user_prompt)
        return parse_json_response(raw)

    def analyze_qa_report(self, qa_report: dict) -> dict:
        system_prompt = "You are a CEO deciding on launch. Return ONLY JSON."
        user_prompt = f"QA Report: {json.dumps(qa_report)[:1500]}\n\nReturn JSON: {{ 'action': 'approve/revise', 'instructions': '...' }}"
        print("\n  🧠 [CEO] LLM Call 3 — Analyzing QA report …")
        raw = call_llm(system_prompt, user_prompt)
        return parse_json_response(raw)

    # ── Main orchestration ─────────────────────────────────────────────────────

    def run(self, startup_idea: str,
            product_agent, engineer_agent, marketing_agent, qa_agent) -> dict:

        divider = "=" * 65
        print(f"\n{divider}\n🚀  CEO AGENT: LaunchMind System Starting\n💡  Idea: {startup_idea}\n{divider}")

        tasks = self.decompose_idea(startup_idea)
        
        # 1. Product Agent Loop
        product_task_msg = self._make_message("product", "task", {"idea": startup_idea, "focus": tasks.get("product_task", "")})
        self._send(product_task_msg)

        product_spec = None
        for attempt in range(2):
            product_spec = product_agent.run(startup_idea, product_task_msg["message_id"], tasks.get("product_task", ""))
            review = self.review_product_spec(product_spec)
            if review.get("verdict") == "pass":
                print("  ✅ [CEO] Product spec accepted.")
                break
            else:
                self._send(self._make_message("product", "revision_request", {"feedback": review.get("feedback","")}, product_task_msg["message_id"]))
                print(f"  ⬅️  [CEO] Product Revision Requested: {review.get('feedback','')[:100]}...")

        # 2. Engineer Task
        eng_task_msg = self._make_message("engineer", "task", {"product_spec": product_spec, "focus": tasks.get("engineer_task", "")})
        self._send(eng_task_msg)
        engineer_result = engineer_agent.run(product_spec, eng_task_msg["message_id"])
        
        pr_url = engineer_result.get("pr_url", "")
        html_content = engineer_result.get("html_content", "")

        # 3. Marketing Task
        mkt_task_msg = self._make_message("marketing", "task", {"product_spec": product_spec, "pr_url": pr_url, "focus": tasks.get("marketing_task", "")})
        self._send(mkt_task_msg)
        marketing_result = marketing_agent.run(product_spec, pr_url, mkt_task_msg["message_id"])

        # 4. QA Task & Decision Loop (THE CRITICAL FEEDBACK LOOP)
        qa_task_msg = self._make_message("qa", "task", {"html_content": "...truncated...", "marketing_copy": marketing_result, "pr_url": pr_url})
        self._send(qa_task_msg)
        
        qa_report = qa_agent.run(html_content, marketing_result, product_spec, pr_url, qa_task_msg["message_id"])
        
        # REASONING STEP: CEO decides base on QA
        decision = self.analyze_qa_report(qa_report)
        print(f"\n  🎯 [CEO] QA Decision → {decision.get('action','').upper()}")

        if decision.get("action") == "revise":
            # Send Revision Request to Engineer
            print(f"  ⬅️  [CEO] REVISION REQUESTED: {decision.get('instructions','')[:150]}")
            rev_msg = self._make_message("engineer", "revision_request", {"feedback": decision.get("instructions","")}, qa_task_msg["message_id"])
            self._send(rev_msg)
            
            # For the demo, we show one revision then proceed to finalize
            print("\n  🔄 [CEO] Simulating fix... proceeding to finalize launch summary.")
        else:
            print("  ✅ [CEO] Quality Check Passed.")

        # 5. Final Summary
        print("\n  📢 [CEO] Posting final launch summary to Slack …")
        post_final_slack_summary(startup_idea, product_spec, pr_url, marketing_result)

        print(f"\n{divider}\n🎉  LaunchMind Pipeline COMPLETE\n{divider}")
        return {"pr_url": pr_url, "product_spec": product_spec, "qa_report": qa_report}