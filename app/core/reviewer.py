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


MAX_DIFF_CHARS = 100_000

NOISE_EXTENSIONS = (
    ".min.js",
    ".min.css",
    ".map",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
)

NOISE_FILENAMES = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "go.sum",
)


def is_noise_file(file_path: str) -> bool:
    name = file_path.lower().strip()
    base = name.split("/")[-1]
    if base in NOISE_FILENAMES:
        return True
    if any(name.endswith(ext) for ext in NOISE_EXTENSIONS):
        return True
    return False


def preprocess_diff(diff_text: str, max_chars: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """
    Clean diff by omitting lockfiles and binary assets, then truncating to max_chars.
    Returns (cleaned_diff, was_truncated).
    """
    if not diff_text or not diff_text.strip():
        return ("", False)

    chunks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    cleaned_chunks = []
    skipped_files = []

    for chunk in chunks:
        if not chunk.strip():
            continue
        match = re.search(r"^diff --git a/(\S+) b/(\S+)", chunk, re.MULTILINE)
        if match:
            path = match.group(2)
            if is_noise_file(path):
                skipped_files.append(path)
                continue
        cleaned_chunks.append(chunk)

    filtered_diff = "".join(cleaned_chunks)
    if skipped_files:
        filtered_diff = f"# Omitted lock/generated files: {', '.join(skipped_files[:10])}\n\n" + filtered_diff

    was_truncated = False
    if len(filtered_diff) > max_chars:
        filtered_diff = filtered_diff[:max_chars]
        last_nl = filtered_diff.rfind("\n")
        if last_nl > max_chars * 0.8:
            filtered_diff = filtered_diff[:last_nl]
        filtered_diff += f"\n\n# [Diff truncated: exceeded review safety limit of {max_chars // 1000}KB]"
        was_truncated = True

    return (filtered_diff, was_truncated)


def review_diff(diff_text: str, client: Anthropic | None = None) -> list[dict]:
    """
    Send a diff to Claude and return a list of finding dicts.

    Each finding: {file_path, line_number, severity, body}
    Returns [] if there are no issues.
    """
    cleaned_diff, _ = preprocess_diff(diff_text)
    if not cleaned_diff.strip():
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