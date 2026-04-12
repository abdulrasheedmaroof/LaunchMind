"""
utils/llm.py -- Thin wrapper around the Groq API.
All agents call this to perform LLM reasoning.
"""

import os
import time
from groq import Groq


def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 5) -> str:
    """
    Call Groq (Llama 3) with a system prompt and a user prompt.
    Retries with exponential back-off on transient failures.
    Returns the raw text response from the model.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    for attempt in range(1, max_retries + 1):
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                model=model,
                temperature=0.7,
                max_tokens=4096,
            )
            return chat_completion.choices[0].message.content
        except Exception as exc:
            print(f"  [!] Groq attempt {attempt}/{max_retries} failed: {exc}")
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
            else:
                print("  [X] All Groq retries exhausted. Re-raising.")
                raise


def parse_json_response(raw: str) -> dict:
    """
    Strip markdown fences from an LLM response and parse as JSON.
    Falls back to an empty dict on parse failure.
    """
    import json
    cleaned = raw.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Drop first line (```json or ```) and last line (```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"  [!] JSON parse failed: {exc}\n  Raw: {cleaned[:200]}")
        return {}