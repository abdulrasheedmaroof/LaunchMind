
"""
main.py — LaunchMind Entry Point
Run this file to start the entire multi-agent system end-to-end.

Usage:
    python main.py
"""

import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding for emoji/unicode output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables from .env before any agent imports
# override=True ensures .env values take priority over system env vars
load_dotenv(override=True)


def check_env() -> None:
    """Validate that all required environment variables are set."""
    required = [
        "GROQ_API_KEY",
        "GITHUB_TOKEN",
        "GITHUB_REPO",
        "SLACK_BOT_TOKEN",
        "SENDGRID_API_KEY",  
        "SENDGRID_FROM_EMAIL",
        "RECEIVER_EMAIL"
        ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print("❌  Missing required environment variables:")
        for k in missing:
            print(f"    - {k}")
        print("\nCopy .env.example to .env and fill in your values.")
        sys.exit(1)
    print("✅  All environment variables loaded")


def main() -> None:
    check_env()

    # ── Import agents (after env is loaded) ───────────────────────────────────
    from agents.ceo_agent import CEOAgent
    from agents.product_agent import ProductAgent
    from agents.engineer_agent import EngineerAgent
    from agents.marketing_agent import MarketingAgent
    from agents.qa_agent import QAAgent
    from message_bus import print_full_history

    # ── Define the startup idea (Interactive Prompt) ──────────────────────────
    print("\n" + "="*65)
    print("🚀  LAUNCHMIND STARTUP INCUBATOR")
    print("="*65)
    
    default_idea = (
        "LeftoverLoot — a mobile platform where restaurants and cafes list "
        "their end-of-day unsold food at 50-70% discount so that nearby users "
        "can discover and reserve those meals in real time."
    )
    
    user_input = input(f"💡 Enter your startup idea\n   (or just press Enter to use 'LeftoverLoot'): ").strip()
    
    STARTUP_IDEA = user_input if user_input else default_idea
    
    print(f"\n✅ Using Idea: {STARTUP_IDEA[:100]}...")

    # ── Instantiate all agents ─────────────────────────────────────────────────
    ceo = CEOAgent()
    product = ProductAgent()
    engineer = EngineerAgent()
    marketing = MarketingAgent()
    qa = QAAgent()

    # ── Run the pipeline through the CEO ──────────────────────────────────────
    result = ceo.run(
        startup_idea=STARTUP_IDEA,
        product_agent=product,
        engineer_agent=engineer,
        marketing_agent=marketing,
        qa_agent=qa,
    )

    # ── Print the full inter-agent message history (for demo) ─────────────────
    print_full_history()

    print("\n✅  LaunchMind run complete. See above for full message log.")
    return result


if __name__ == "__main__":
    main()
