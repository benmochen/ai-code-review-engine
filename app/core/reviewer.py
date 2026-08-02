"""
Claude-powered code review.

Sends a PR diff to Claude and asks for a STRUCTURED list of findings as
JSON, which maps directly onto our ReviewComment rows. We prompt for
JSON-only output and parse defensively (stripping any stray markdown
fences, tolerating an empty findings list).

Severity values must match the Severity enum in models.py:
    info | warning | error | critical
"""
import json
import re
from anthropic import Anthropic
from app.core.config import get_settings

settings = get_settings()

MODEL = settings.claude_model
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are an expert code reviewer. You review pull request diffs \
and report concrete, actionable findings: bugs, security issues, performance \
problems, and clear style violations. You do not nitpick or praise.

Respond with ONLY a JSON object, no prose, no markdown fences. Schema:

{
  "findings": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "warning",
      "body": "Concise explanation of the issue and how to fix it."
    }
  ]
}

Rules:
- severity is one of: "info", "warning", "error", "critical"
- line_number is the line in the new file, or null if not applicable
- If the diff has no real issues, return {"findings": []}
- Keep each body under 400 characters and specific to the code shown."""

VALID_SEVERITIES = {"info", "warning", "error", "critical"}


def _extract_json(text: str) -> dict:
    """Parse Claude's response into a dict, tolerating stray formatting."""
    text = text.strip()

    # Strip markdown code fences if the model added them despite instructions
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: find the first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def review_diff(diff_text: str, client: Anthropic | None = None) -> list[dict]:
    """
    Send a diff to Claude and return a list of finding dicts.

    Each finding: {file_path, line_number, severity, body}
    Returns [] if there are no issues.
    """
    if not diff_text.strip():
        return []

    client = client or Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Review this pull request diff:\n\n{diff_text}",
            }
        ],
    )

    # Concatenate all text blocks from the response
    raw = "".join(
        block.text for block in message.content if block.type == "text"
    )

    parsed = _extract_json(raw)
    findings = parsed.get("findings", [])

    # Validate + normalize each finding
    clean = []
    for f in findings:
        severity = str(f.get("severity", "info")).lower()
        if severity not in VALID_SEVERITIES:
            severity = "info"
        body = (f.get("body") or "").strip()
        if not body:
            continue  # skip findings with no explanation
        clean.append({
            "file_path": f.get("file_path") or "unknown",
            "line_number": f.get("line_number"),
            "severity": severity,
            "body": body[:2000],
        })
    return clean