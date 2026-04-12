"""
agents/marketing_agent.py -- Marketing Agent
Reads the product spec and generates copy, sends email, and posts to Slack.
"""

import uuid
import os
import json
import requests
from datetime import datetime, timezone

from message_bus import send_message
from utils.llm import call_llm, parse_json_response


class MarketingAgent:
    NAME = "marketing"

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

    def _generate_copy(self, spec: dict) -> dict:
        name = spec.get("project_name", "the startup")
        system_prompt = (
            "You are a growth marketer. Write punchy, authentic marketing copy. "
            "Return ONLY a valid JSON object."
        )
        vp = spec.get("value_proposition", "")
        features = [f["name"] for f in spec.get("features", [])]
        
        user_prompt = f"""
Startup: {name}
Value Proposition: {vp}
Features: {", ".join(features[:3])}

Generate marketing copy as JSON with EXACTLY these keys:
{{
  "tagline": "<punchy phrase under 10 words>",
  "short_description": "<2-3 sentences>",
  "cold_email_subject": "<compelling subject>",
  "cold_email_body": "<150-200 word email. Sign off as 'The {name} Team'.>",
  "twitter_post": "<under 280 chars>",
  "linkedin_post": "<professional post>",
  "instagram_caption": "<energetic caption with emojis>"
}}
Return ONLY JSON.
"""
        print("  🧠 [MARKETING] Calling LLM to generate marketing copy …")
        raw = call_llm(system_prompt, user_prompt)
        return parse_json_response(raw)

    # ── Email via SendGrid ───────────────────────────────────────────────────

    def _send_email(self, project_name: str, subject: str, body: str) -> bool:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        from_email = os.environ["SENDGRID_FROM_EMAIL"]
        to_email = os.environ["RECEIVER_EMAIL"]
        api_key = os.environ["SENDGRID_API_KEY"]

        html_body = body.replace("\n", "<br>")
        html = f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:auto;padding:20px;">
          <h2 style="color:#f97316;">🍱 {project_name}</h2>
          <p>{html_body}</p>
          <hr style="border:none;border-top:1px solid #eee;">
          <p style="font-size:12px;color:#999;">
            You received this because you are part of the {project_name} early access program.
          </p>
        </div></body></html>
        """

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )

        try:
            sg = SendGridAPIClient(api_key)
            response = sg.send(message)
            if response.status_code in (200, 202):
                print(f"  ✅ Email sent to {to_email} via SendGrid")
                return True
            else:
                print(f"  ❌ SendGrid error: {response.status_code} {response.body}")
                return False
        except Exception as exc:
            print(f"  ❌ SendGrid failed: {exc}")
            return False

    # ── Slack Block Kit post ──────────────────────────────────────────────────

    def _post_to_slack(self, project_name: str, copy: dict, pr_url: str) -> bool:
        token = os.environ["SLACK_BOT_TOKEN"]
        channel = os.environ.get("SLACK_CHANNEL", "#launches")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚀 New Launch: {project_name}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Tagline:* {copy.get('tagline', '')}\n{copy.get('short_description', '')}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📁 GitHub PR:* <{pr_url}|View PR>" if pr_url else "*📁 GitHub PR:* N/A"},
                    {"type": "mrkdwn", "text": "*🟢 Status:* Ready for review"},
                ],
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Posted by *MarketingAgent* · LaunchMind MAS · project: {project_name.lower()}"}],
            },
        ]

        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "blocks": blocks, "text": f"🚀 {project_name} is live!"},
        )
        return resp.json().get("ok", False)

    # ── Public run method ─────────────────────────────────────────────────────

    def run(self, product_spec: dict, pr_url: str = "",
            task_message_id: str = None) -> dict:
        print("\n" + "─" * 55)
        print("📣 MARKETING AGENT: Generating copy, sending email & Slack …")

        project_name = product_spec.get("project_name", "Startup")
        copy = self._generate_copy(product_spec)
        
        email_ok = self._send_email(
            project_name=project_name,
            subject=copy.get("cold_email_subject", f"{project_name} — Early Access"),
            body=copy.get("cold_email_body", ""),
        )
        slack_ok = self._post_to_slack(project_name, copy, pr_url)

        result = {**copy, "email_sent": email_ok, "slack_posted": slack_ok, "pr_url": pr_url}
        msg = self._make_message("ceo", "result", result, task_message_id)
        send_message(msg)

        print("  🎉 Marketing Agent done!")
        return result


def post_final_slack_summary(startup_idea: str, spec: dict,
                              pr_url: str, marketing_copy: dict) -> None:
    token = os.environ["SLACK_BOT_TOKEN"]
    channel = os.environ.get("SLACK_CHANNEL", "#launches")
    name = spec.get("project_name", "Startup")
    tagline = marketing_copy.get("tagline", "Live now!")
    features = spec.get("features", [])
    feat_text = "\n".join(f"• *{f['name']}* — {f['description'][:60]}…" for f in features[:3])

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🏁 LaunchMind — Final Launch Report", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Startup:* {name}\n*Tagline:* _{tagline}_\n*Idea:* {startup_idea[:200]}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🔑 Top Features:*\n{feat_text}"}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*📁 GitHub PR:* <{pr_url}|View PR>" if pr_url else "*📁 GitHub PR:* N/A"},
                {"type": "mrkdwn", "text": "*📧 Email:* Sent ✅"},
                {"type": "mrkdwn", "text": "*🤖 Agents ran:* CEO · Product · Engineer · Marketing · QA"},
                {"type": "mrkdwn", "text": "*🟢 Status:* Total Launch Success"},
            ],
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Compiled by *CEO Agent* · LaunchMind MAS · {name}"}]},
    ]

    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, "blocks": blocks, "text": f"🏁 {name} Final Launch Report"},
    )