# CampusEats-LaunchMind Multi-Agent System

> A peer-to-peer marketplace where university students list and buy homemade meals from each other on campus — built and launched autonomously by a team of 5 collaborating AI agents.

---

## What Is This?

LaunchMind is a **Multi-Agent System (MAS)** built for the FAST NUCES Agentic AI course assignment. It takes a startup idea as input and autonomously runs an entire micro-startup pipeline — defining the product, building a landing page, pushing code to GitHub, sending a marketing email, and posting to Slack — without any human doing it manually.

The startup idea used in this project is **CampusEats**: university students cook extra food at home and list it for sale to nearby students on campus, creating a affordable, community-driven food marketplace.

---

## Agent Architecture

```
Startup Idea (string input)
          │
          ▼
  ┌───────────────┐
  │   CEO Agent   │  ← orchestrator · 3 LLM calls · feedback loops
  └───────┬───────┘
          │ dispatches tasks via shared Message Bus
    ┌─────┼──────────────┐
    ▼     ▼              ▼
Product  Engineer    Marketing
 Agent    Agent       Agent
    │       │             │
    │   GitHub PR    Slack + SendGrid
    └───┬───┘
        │  HTML + copy sent to
        ▼
     QA Agent
        │  verdict + PR comments → CEO
        ▼
  CEO final decision → revision loop if fail
        │
        ▼
  CEO posts final Slack summary
```

### Which agent talks to which

| From | To | Message Type | What's sent |
|------|----|--------------|-------------|
| CEO | Product | `task` | startup idea + focus instruction |
| Product | CEO | `confirmation` | spec ready signal |
| Product | Engineer | `task` | full product_spec JSON |
| Product | Marketing | `task` | full product_spec JSON |
| CEO | Product | `revision_request` | LLM feedback if spec is weak |
| Engineer | CEO | `result` | PR URL + issue URL + HTML |
| Marketing | CEO | `result` | copy JSON + email/Slack status |
| CEO | QA | `task` | HTML + marketing copy + PR URL |
| QA | CEO | `result` | verdict + html_review + copy_review |
| CEO | Engineer | `revision_request` | QA issues to fix (if verdict = fail) |

---

## The 5 Agents

### 1. CEO Agent (`agents/ceo_agent.py`)
The brain. Makes **3 LLM calls** during its lifecycle:
- **LLM Call 1** — `decompose_idea()`: breaks the startup idea into structured tasks for each sub-agent
- **LLM Call 2** — `review_product_spec()`: reviews the Product spec and triggers a revision if it is not specific enough
- **LLM Call 3** — `analyze_qa_report()`: reads QA verdict and decides to approve or send a revision request to Engineer

### 2. Product Agent (`agents/product_agent.py`)
Generates a full product specification JSON including `project_name`, `value_proposition`, 2 personas with pain points, 5 prioritised features, and 3 user stories. Sends the spec to Engineer, Marketing, and CEO via the message bus.

### 3. Engineer Agent (`agents/engineer_agent.py`)
Generates a complete HTML landing page with inline CSS and takes real actions on GitHub:
- Creates a new branch (`agent-landing-page`)
- Commits `index.html` authored by `EngineerAgent <agent@launchmind.ai>`
- Opens a GitHub issue titled "Initial landing page — CampusEats"
- Opens a pull request with an LLM-generated title and body

### 4. Marketing Agent (`agents/marketing_agent.py`)
Generates a tagline, short description, cold outreach email, Twitter post, LinkedIn post, and Instagram caption. Then:
- Sends the cold email via **SendGrid** (free tier)
- Posts a **Slack Block Kit** message to `#launches` with tagline, description, and PR link

### 5. QA Agent (`agents/qa_agent.py`)
Reviews the Engineer's HTML against the product spec and the Marketing copy for quality. Posts **at least 2 inline review comments** on the GitHub PR via the GitHub API. Sends a structured `pass/fail` verdict back to the CEO.

---

## Dynamic Decision-Making (Feedback Loops)

This system has **two feedback loops** — not a fixed pipeline.

**Loop 1 — Product spec review:**
CEO receives the Product spec → sends it to the LLM with a critical review prompt → if verdict is `fail`, sends a `revision_request` back to the Product agent with specific feedback → Product agent regenerates the spec.

**Loop 2 — QA-driven Engineer revision:**
QA agent reviews the HTML landing page → if verdict is `fail` → CEO sends a `revision_request` to the Engineer with the specific issues → Engineer regenerates and recommits.

---

## Message Schema

Every message passed between agents follows this exact schema:

```json
{
  "message_id": "msg-a1b2c3d4",
  "from_agent": "ceo",
  "to_agent": "product",
  "message_type": "task",
  "payload": {
    "idea": "CampusEats — students list homemade food for sale to other students",
    "focus": "Define core user personas and top 5 features"
  },
  "timestamp": "2026-04-13T09:00:00Z",
  "parent_message_id": "msg-00000000"
}
```

`message_type` is one of: `task`, `result`, `revision_request`, `confirmation`.

The full message history is printed to the terminal at the end of every run via `print_full_history()`.

---

## Project Structure

```
launchmind-campuseats/
├── main.py                  ← entry point, run this
├── message_bus.py           ← shared in-memory message store
├── requirements.txt
├── .env                     ← your keys (never commit this)
├── .env.example             ← template with placeholder values
├── .gitignore
├── agents/
│   ├── __init__.py
│   ├── ceo_agent.py
│   ├── product_agent.py
│   ├── engineer_agent.py
│   ├── marketing_agent.py
│   └── qa_agent.py
└── utils/
    ├── __init__.py
    └── llm.py               ← Groq API wrapper with retry logic
```

---

## Platform Integrations

| Platform | Agent | What it does |
|----------|-------|-------------|
| **GitHub** | Engineer | Creates branch, commits `index.html`, opens issue and pull request |
| **GitHub PR Comments** | QA | Posts ≥ 2 inline review comments on the PR |
| **Slack** | Marketing + CEO | Marketing posts Block Kit launch message; CEO posts final summary |
| **SendGrid** | Marketing | Sends LLM-generated cold outreach email to test inbox |
| **Groq (Llama 3.3 70B)** | All agents | All LLM reasoning — completely free |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/abdulrasheedmaroof/LaunchMind.git
cd LaunchMind
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get your free API keys

**Groq (free, no credit card)**
- Go to [console.groq.com](https://console.groq.com) → sign up → API Keys → Create

**GitHub Personal Access Token**
- GitHub → Settings → Developer Settings → Personal Access Tokens (classic)
- Scopes needed: `repo`, `workflow`
- Create a public repo named `launchmind-campuseats`

**Slack Bot Token**
- [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
- OAuth & Permissions → Bot Token Scopes → add: `chat:write`, `channels:read`, `channels:join`
- Install to Workspace → copy the `xoxb-...` token
- Create channel `#launches` in your workspace → `/invite @YourBotName`

**SendGrid (free — 100 emails/day, no credit card)**
- [sendgrid.com](https://sendgrid.com) → sign up free
- Settings → API Keys → Create API Key → Mail Send permission
- Settings → Sender Authentication → verify your email address

### 4. Create your `.env` file

```env
GROQ_API_KEY=gsk_your_key_here
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=yourusername/launchmind-campuseats
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=#launches
SENDGRID_API_KEY=SG.your_key_here
SENDGRID_FROM_EMAIL=yourverified@email.com
RECEIVER_EMAIL=yourinbox@email.com
GROQ_MODEL=llama-3.3-70b-versatile
```

> Do not use colons. `.env` syntax is `KEY=value` only.

### 5. Run the system

```bash
python main.py
```

When prompted, press Enter to use CampusEats, or type your own idea:

```
CampusEats — a peer marketplace where university students list and buy homemade meals from each other on campus
```

---

## Expected Output

```
✅  All environment variables loaded

==================================================================
🚀  LAUNCHMIND STARTUP INCUBATOR
==================================================================

👔 PRODUCT AGENT: Generating product specification …
  🧠 [PRODUCT] Calling LLM to generate product spec …
  ✅ Spec generated:
     project_name      : CampusEats
     value_proposition : A peer-to-peer campus food marketplace ...

📤 [CEO → ENGINEER] type=task | id=msg-a1b2c3d4

⚙️  ENGINEER AGENT: Building landing page & pushing to GitHub …
  🧠 [ENGINEER] Calling LLM to generate HTML landing page …
  ✅ Branch created
  ✅ File committed
  ✅ PR opened: https://github.com/you/launchmind-campuseats/pull/1

📣 MARKETING AGENT: Generating copy, sending email & Slack …
  🧠 [MARKETING] Calling LLM to generate marketing copy …
  ✅ Email sent to you@email.com via SendGrid
  ✅ Slack message posted to #launches

🔬 QA AGENT: Reviewing HTML and marketing copy …
  🏁 QA Verdict: PASS

  🎯 [CEO] QA Decision → APPROVE
  📢 [CEO] Posting final launch summary to Slack …

🎉  LaunchMind Pipeline COMPLETE
```

---

## Links

- **GitHub PR (Engineer Agent):** _(link appears after first run)_
- **Slack Workspace:** _(add your invite link here)_
- **Demo Video:** _(add your YouTube/Drive link here)_

---

## Group Members

| Member | Agent(s) Owned |
|--------|---------------|
| _(Name 1)_ | CEO Agent |
| _(Name 2)_ | Product Agent + Engineer Agent |
| _(Name 3)_ | Marketing Agent + QA Agent |

---

## Bonus Features

- [x] QA Agent with GitHub PR inline review comments
- [x] Two feedback loops (Product revision + Engineer revision on QA fail)
- [x] Exponential backoff retry in `utils/llm.py` (handles Groq rate limits)
- [x] SendGrid email integration (upgraded from Gmail SMTP)
- [ ] Redis pub/sub messaging (optional — dict bus is used)
