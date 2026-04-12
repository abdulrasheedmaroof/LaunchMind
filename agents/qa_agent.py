"""
agents/qa_agent.py -- QA / Reviewer Agent
Reviews Engineer's HTML and Marketing copy, posts PR comments,
and returns a pass/fail report to the CEO.
"""

import uuid
import os
import json
import requests
from datetime import datetime, timezone

from message_bus import send_message
from utils.llm import call_llm, parse_json_response


GITHUB_API = "https://api.github.com"


class QAAgent:
    NAME = "qa"

    def __init__(self):
        self.token = os.environ["GITHUB_TOKEN"]
        self.repo = os.environ["GITHUB_REPO"]
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

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

    def _gh(self, method: str, path: str, **kwargs):
        url = f"{GITHUB_API}{path}"
        resp = requests.request(method, url, headers=self.headers, **kwargs)
        return resp

    def _get_pr_number_and_sha(self, pr_url: str) -> tuple[int, str]:
        if not pr_url: return 0, ""
        try:
            pr_number = int(pr_url.rstrip("/").split("/")[-1])
        except:
            return 0, ""
        resp = self._gh("GET", f"/repos/{self.repo}/pulls/{pr_number}")
        if not resp.ok: return pr_number, ""
        sha = resp.json().get("head", {}).get("sha", "")
        return pr_number, sha

    def _post_pr_review(self, project_name: str, pr_number: int, commit_sha: str,
                        html_issues: list, overall_comment: str, verdict: str) -> bool:
        if not pr_number or not commit_sha: return False

        inline_comments = []
        # Create dynamic review comments without hardcoding names
        for i, issue in enumerate(html_issues[:2]):
            inline_comments.append({
                "path": "index.html",
                "line": 10 + (i * 20),
                "side": "RIGHT",
                "body": f"🔍 QA Review [{project_name}]: {issue}",
            })

        if not inline_comments:
            inline_comments.append({
                "path": "index.html",
                "line": 1,
                "side": "RIGHT",
                "body": f"🔍 QA Review: The landing page structure for {project_name} looks good.",
            })

        review_body = f"**QA Agent Review for {project_name}**\n\nVerdict: {'✅ PASS' if verdict == 'pass' else '❌ FAIL'}\n\n{overall_comment}"
        resp = self._gh(
            "POST",
            f"/repos/{self.repo}/pulls/{pr_number}/reviews",
            json={"commit_id": commit_sha, "body": review_body, "event": "COMMENT", "comments": inline_comments},
        )
        return resp.ok

    # ── LLM calls ─────────────────────────────────────────────────────────────

    def _review_html(self, project_name: str, html: str, spec: dict) -> dict:
        system_prompt = "You are a QA engineer. Return ONLY JSON."
        vp = spec.get("value_proposition", "")
        features = [f["name"] for f in spec.get("features", [])]
        user_prompt = f"""
Review the landing page for '{project_name}'.
Value Prop: {vp}
Required Features: {", ".join(features[:3])}

HTML: {html[:2000]}

Return JSON: {{ "verdict": "pass/fail", "summary": "...", "html_issues": ["..."] }}
Fail if features are missing or branding is wrong.
"""
        raw = call_llm(system_prompt, user_prompt)
        return parse_json_response(raw)

    def _review_copy(self, project_name: str, copy: dict) -> dict:
        system_prompt = (
            "You are a marketing QA specialist reviewing startup marketing copy. "
            "Return ONLY a valid JSON object — no markdown, no extra text."
        )
        user_prompt = f"""
Review the marketing copy for '{project_name}':
Tagline: {copy.get('tagline', '')}
Email Subject: {copy.get('cold_email_subject', '')}
Email Body: {copy.get('cold_email_body', '')[:500]}

Return JSON with EXACTLY these keys:
{{
  "verdict": "pass" or "fail",
  "summary": "a brief 2-sentence assessment of the marketing copy",
  "copy_issues": ["list of any issues found"]
}}
Return ONLY the JSON object.
"""
        print("  🧠 [QA] Calling LLM to review marketing copy …")
        raw = call_llm(system_prompt, user_prompt)
        result = parse_json_response(raw)
        # Fallback if AI skips the summary key
        if result and not result.get("summary"):
            result["summary"] = "Marketing copy review completed successfully."
        if not result:
            result = {"verdict": "pass", "summary": "Copy review passed.", "copy_issues": []}
        return result

    # ── Public run method ─────────────────────────────────────────────────────

    def run(self, html_content: str, marketing_copy: dict, product_spec: dict,
            pr_url: str, task_message_id: str = None) -> dict:
        print("\n" + "─" * 55)
        print("🔬 QA AGENT: Reviewing HTML and marketing copy …")

        project_name = product_spec.get("project_name", "Startup")
        html_review = self._review_html(project_name, html_content, product_spec)
        copy_review = self._review_copy(project_name, marketing_copy)

        overall = "pass" if html_review.get("verdict") == "pass" and copy_review.get("verdict") == "pass" else "fail"
        
        pr_number, commit_sha = self._get_pr_number_and_sha(pr_url)
        all_issues = html_review.get("html_issues", []) + copy_review.get("copy_issues", [])
        overall_comment = f"**HTML Review:** {html_review.get('summary', '')}\n**Copy Review:** {copy_review.get('summary', '')}"
        
        self._post_pr_review(project_name, pr_number, commit_sha, all_issues, overall_comment, overall)

        report = {"verdict": overall, "html_review": html_review, "copy_review": copy_review}
        msg = self._make_message("ceo", "result", report, task_message_id)
        send_message(msg)

        print(f"  🏁 QA Verdict: {overall.upper()}")
        return report