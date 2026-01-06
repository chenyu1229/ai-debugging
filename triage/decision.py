from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

ALLOWED_CLASS = ["Code Bug","Environment Issue","Flaky Test","Unknown"]
ALLOWED_ACTION = ["Retry","Create Ticket","Escalate","Ignore","Block CI"]

def analyze_with_rules(pytest_output: str) -> Dict[str, Any]:
    """
    Deterministic baseline.
    This is important because it gives you:
    - stability
    - a fallback when LLM fails
    - something to compare LLM against (eval)
    """
    text = pytest_output

    # extremely simple signals (you'll expand later)
    if "TimeoutError" in text or "ConnectionError" in text:
        return {
            "classification": "Environment Issue",
            "action": "Retry",
            "block_ci": False,
            "confidence": 0.75,
            "reason": "Looks like infrastructure/network timeout; typically not a code regression."
        }

    if "ZeroDivisionError" in text or "KeyError" in text or "AssertionError" in text:
        return {
            "classification": "Code Bug",
            "action": "Block CI",
            "block_ci": True,
            "confidence": 0.80,
            "reason": "Likely code/logic issue; should block CI and be fixed."
        }

    return {
        "classification": "Unknown",
        "action": "Escalate",
        "block_ci": False,
        "confidence": 0.40,
        "reason": "Not enough signal; needs human review."
    }

def _extract_json(text: str) -> Dict[str, Any] | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj
    except json.JSONDecodeError:
        return None

# def analyze_with_openai(pytest_output: str) -> Dict[str, Any]:
#     """
#     Optional LLM triage (OpenAI). Requires OPENAI_API_KEY.
#     Uses strict JSON output to make it automatable.
#     """
#     from openai import OpenAI  # lazy import so rules-only users don't care

#     # If key missing, raise to allow caller to fall back to rules.
#     if not os.getenv("OPENAI_API_KEY"):
#         raise RuntimeError("OPENAI_API_KEY not set")

#     client = OpenAI()

# #     prompt = f"""You are a senior SDET / platform engineer.
# # Given pytest failure output, return STRICT JSON ONLY (no markdown, no extra text).
# # Schema:
# # - classification: one of {ALLOWED_CLASS}
# # - action: one of {ALLOWED_ACTION}
# # - block_ci: boolean
# # - confidence: number 0..1
# # - reason: short 1-2 sentences

# # pytest_output:
# # {pytest_output}
# # """
#     prompt = f"""
#     You are a senior software engineer performing CI failure triage.

#     Given pytest failure output, return STRICT JSON ONLY.
#     Do NOT include markdown or explanations outside JSON.

#     Schema:
#     - classification: one of ["Code Bug","Environment Issue","Flaky Test","Unknown"]
#     - action: one of ["Retry","Block CI","Create Ticket","Escalate"]
#     - block_ci: boolean
#     - confidence: number between 0 and 1
#     - suspected_files: list of file paths (may be empty)
#     - suspected_functions: list of function names (may be empty)
#     - root_cause_summary: one concise sentence
#     - next_steps: list of concrete engineering actions (strings)

#     Guidelines:
#     - If the failure is deterministic and code-related, block CI.
#     - If it looks like an environment issue, do not block CI.
#     - Be conservative: if uncertain, leave suspected_files/functions empty.

#     pytest_output:
#     {pytest_output}
#     """


#     resp = client.responses.create(
#         model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
#         input=prompt
#     )

#     text = resp.output_text.strip()
#     obj = _extract_json(text)
#     if not obj:
#         raise RuntimeError("LLM did not return parseable JSON")

#     # minimal validation / normalization
#     if obj.get("classification") not in ALLOWED_CLASS:
#         obj["classification"] = "Unknown"
#     if obj.get("action") not in ALLOWED_ACTION:
#         obj["action"] = "Escalate"
#     if "block_ci" not in obj:
#         obj["block_ci"] = False
#     if "confidence" not in obj:
#         obj["confidence"] = 0.5
#     if "reason" not in obj:
#         obj["reason"] = "LLM returned incomplete output."

#     return obj

def analyze_with_openai(pytest_output: str) -> Dict[str, Any]:
    """
    Optional LLM triage (OpenAI). Requires OPENAI_API_KEY.
    Uses strict JSON output to make it automatable.
    """
    from google import genai  # lazy import so rules-only users don't care

    # If key missing, raise to allow caller to fall back to rules.
    client = genai.Client(
    api_key=os.environ["GOOGLE_API_KEY"]
)

    prompt = f"""
    You are a senior software engineer performing CI failure triage.

    Given pytest failure output, return STRICT JSON ONLY.
    Do NOT include markdown or explanations outside JSON.

    Schema:
    - classification: one of ["Code Bug","Environment Issue","Flaky Test","Unknown"]
    - action: one of ["Retry","Block CI","Create Ticket","Escalate"]
    - block_ci: boolean
    - confidence: number between 0 and 1
    - suspected_files: list of file paths (may be empty)
    - suspected_functions: list of function names (may be empty)
    - root_cause_summary: one concise sentence
    - next_steps: list of concrete engineering actions (strings)
    - code recommended: provided correctted code

    Guidelines:
    - If the failure is deterministic and code-related, block CI.
    - If it looks like an environment issue, do not block CI.
    - Be conservative: if uncertain, leave suspected_files/functions empty.

    pytest_output:
    {pytest_output}
    """


    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents = prompt
    )


    text = response.text.strip()
    obj = _extract_json(text)
    print(text)
    if not obj:
        raise RuntimeError("LLM did not return parseable JSON")

    # minimal validation / normalization
    if obj.get("classification") not in ALLOWED_CLASS:
        obj["classification"] = "Unknown"
    if obj.get("action") not in ALLOWED_ACTION:
        obj["action"] = "Escalate"
    if "block_ci" not in obj:
        obj["block_ci"] = False
    if "confidence" not in obj:
        obj["confidence"] = 0.5
    # if "reason" not in obj:
    #     obj["reason"] = "LLM returned incomplete output."

    return obj

