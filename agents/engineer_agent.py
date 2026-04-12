"""
agents/engineer_agent.py -- Engineer Agent
Reads the product spec, generates an HTML landing page,
then takes real actions on GitHub.
"""

import uuid
import json
import os
import base64
from datetime import datetime, timezone

import requests

from message_bus import send_message
from utils.llm import call_llm, parse_json_response


GITHUB_API = "https://api.github.com"


class EngineerAgent:
    NAME = "engineer"

    def __init__(self):
        self.token = os.environ["GITHUB_TOKEN"]
        self.repo = os.environ["GITHUB_REPO"]
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.branch_name = "agent-landing-page"

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
        if not resp.ok:
            print(f"  ⚠️  GitHub {method} {path} → {resp.status_code}: {resp.text[:300]}")
        return resp

    # ── GitHub operations ─────────────────────────────────────────────────────

    def _get_default_branch_sha(self) -> tuple[str, str]:
        resp = self._gh("GET", f"/repos/{self.repo}")
        if not resp.ok:
            raise RuntimeError(f"Cannot reach repo {self.repo}: {resp.status_code}")
        default_branch = resp.json().get("default_branch", "main")

        ref_resp = self._gh("GET", f"/repos/{self.repo}/git/ref/heads/{default_branch}")
        if ref_resp.ok:
            sha = ref_resp.json()["object"]["sha"]
            return default_branch, sha

        # Repo empty fallback
        init_content = base64.b64encode(
            "# LaunchMind Startup Repository\nInitial commit by EngineerAgent.\n".encode("utf-8")
        ).decode()
        create_resp = self._gh(
            "PUT",
            f"/repos/{self.repo}/contents/README.md",
            json={
                "message": "Initial commit",
                "content": init_content,
                "committer": {"name": "EngineerAgent", "email": "agent@launchmind.ai"},
            },
        )
        sha = create_resp.json()["commit"]["sha"]
        return default_branch, sha

    def _create_branch(self, base_sha: str) -> bool:
        self._gh("DELETE", f"/repos/{self.repo}/git/refs/heads/{self.branch_name}")
        resp = self._gh(
            "POST",
            f"/repos/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{self.branch_name}", "sha": base_sha},
        )
        return resp.ok

    def _commit_file(self, html_content: str, project_name: str) -> bool:
        encoded = base64.b64encode(html_content.encode("utf-8")).decode()
        existing = self._gh("GET", f"/repos/{self.repo}/contents/index.html",
                            params={"ref": self.branch_name})
        payload = {
            "message": f"feat: add {project_name} landing page [by EngineerAgent]",
            "content": encoded,
            "branch": self.branch_name,
            "committer": {"name": "EngineerAgent", "email": "agent@launchmind.ai"},
        }
        if existing.ok:
            payload["sha"] = existing.json()["sha"]

        resp = self._gh("PUT", f"/repos/{self.repo}/contents/index.html", json=payload)
        return resp.ok

    def _create_issue(self, project_name: str, issue_body: str) -> str:
        resp = self._gh(
            "POST",
            f"/repos/{self.repo}/issues",
            json={
                "title": f"Initial landing page — {project_name}",
                "body": issue_body,
                "labels": ["enhancement", "landing-page"],
            },
        )
        return resp.json().get("html_url", "") if resp.ok else ""

    def _open_pr(self, default_branch: str, pr_title: str, pr_body: str) -> str:
        resp = self._gh(
            "POST",
            f"/repos/{self.repo}/pulls",
            json={
                "title": pr_title,
                "body": pr_body,
                "head": self.branch_name,
                "base": default_branch,
            },
        )
        return resp.json().get("html_url", "") if resp.ok else ""

    # ── LLM calls ─────────────────────────────────────────────────────────────

    def _generate_html(self, spec: dict) -> str:
        system_prompt = (
            "You are a senior frontend developer. "
            "Generate a complete, self-contained HTML landing page with inline CSS. "
            "Return ONLY the raw HTML — no markdown, no fences, no explanation."
        )
        name = spec.get("project_name", "Startup")
        vp = spec.get("value_proposition", "")
        features = spec.get("features", [])
        feat_list = "\n".join(f"  - {f['name']}: {f['description']}" for f in features)
        
        user_prompt = f"""
Create a full HTML landing page for '{name}' startup.
Value Proposition: {vp}
Features: {feat_list}

Requirements:
- Modern, mobile-friendly design with a unique color palette based on the startup name.
- Hero section with headline + subheadline + CTA button.
- Feature grid and 'How It Works' section.
- Footer with © 2026 {name}
- Pure HTML + CSS, no external deps.
"""
        print("  🧠 [ENGINEER] Calling LLM to generate HTML landing page …")
        return call_llm(system_prompt, user_prompt)

    def _generate_issue_body(self, spec: dict) -> str:
        name = spec.get("project_name", "the startup")
        user_prompt = f"Write a GitHub issue body for the task: 'Build the initial landing page for {name}'. Spec: {spec.get('value_proposition','')}"
        return call_llm("You are a technical engineer. Return markdown text.", user_prompt)

    def _generate_pr_text(self, spec: dict) -> tuple[str, str]:
        name = spec.get("project_name", "the startup")
        user_prompt = f"Generate a JSON object with 'title' and 'body' for a GitHub PR adding the {name} landing page. Spec: {spec.get('value_proposition','')}"
        raw = call_llm("Return ONLY JSON {title, body}.", user_prompt)
        parsed = parse_json_response(raw)
        return parsed.get("title", f"feat: Add {name} landing page"), parsed.get("body", "Initial landing page.")

    # ── Public run method ─────────────────────────────────────────────────────

    def run(self, product_spec: dict, task_message_id: str = None) -> dict:
        print("\n" + "─" * 55)
        print("⚙️  ENGINEER AGENT: Building landing page & pushing to GitHub …")

        project_name = product_spec.get("project_name", "Startup")

        # 1. Generate HTML
        html = self._generate_html(product_spec)
        
        # 2. GitHub Actions
        default_branch, base_sha = self._get_default_branch_sha()
        self._create_branch(base_sha)
        self._commit_file(html, project_name)

        issue_body = self._generate_issue_body(product_spec)
        issue_url = self._create_issue(project_name, issue_body)

        pr_title, pr_body = self._generate_pr_text(product_spec)
        pr_url = self._open_pr(default_branch, pr_title, pr_body)

        result = {
            "html_content": html,
            "pr_url": pr_url,
            "issue_url": issue_url,
            "branch": self.branch_name,
        }

        msg = self._make_message("ceo", "result", result, task_message_id)
        send_message(msg)

        print(f"  🎉 Engineer done! PR: {pr_url}")
        return result