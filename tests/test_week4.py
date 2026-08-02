"""
Week 4 tests — Claude reviewer + full analysis job.

Run with: pytest tests/test_week4.py -v

Both the Claude API and the GitHub API are mocked, so tests run offline
with no API key and no network calls.
"""
import pytest

from app.core import reviewer as reviewer_module
from app.core.reviewer import _extract_json, review_diff
import app.workers.jobs as jobs_module
from app.core.database import SessionLocal
from app.models.models import User, Repository, Review, ReviewComment, ReviewStatus


# ──────────────────────────────────────────────
# JSON extraction (the fragile part)
# ──────────────────────────────────────────────
def test_extract_plain_json():
    out = _extract_json('{"findings": []}')
    assert out == {"findings": []}


def test_extract_json_with_fences():
    text = '```json\n{"findings": [{"body": "x"}]}\n```'
    out = _extract_json(text)
    assert len(out["findings"]) == 1


def test_extract_json_with_surrounding_prose():
    text = 'Here is my review:\n{"findings": []}\nHope that helps!'
    out = _extract_json(text)
    assert out == {"findings": []}


# ──────────────────────────────────────────────
# review_diff with a mocked Anthropic client
# ──────────────────────────────────────────────
class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, response_text):
        self._response_text = response_text

    def create(self, **kwargs):
        return _FakeMessage(self._response_text)


class _FakeAnthropic:
    def __init__(self, response_text):
        self.messages = _FakeMessages(response_text)


def test_review_diff_parses_findings():
    fake = _FakeAnthropic('{"findings": [{"file_path": "a.py", "line_number": 3, "severity": "warning", "body": "Use bcrypt"}]}')
    findings = review_diff("diff --git ...", client=fake)
    assert len(findings) == 1
    assert findings[0]["severity"] == "warning"
    assert findings[0]["file_path"] == "a.py"


def test_review_diff_empty_diff_skips_api():
    # Empty diff should return [] without needing a client
    assert review_diff("   ") == []


def test_review_diff_normalizes_bad_severity():
    fake = _FakeAnthropic('{"findings": [{"file_path": "a.py", "severity": "SUPER_BAD", "body": "x"}]}')
    findings = review_diff("diff", client=fake)
    assert findings[0]["severity"] == "info"  # normalized


def test_review_diff_skips_empty_body():
    fake = _FakeAnthropic('{"findings": [{"file_path": "a.py", "severity": "info", "body": ""}]}')
    findings = review_diff("diff", client=fake)
    assert findings == []


def test_review_diff_handles_no_issues():
    fake = _FakeAnthropic('{"findings": []}')
    assert review_diff("diff", client=fake) == []


# ──────────────────────────────────────────────
# Summary formatting
# ──────────────────────────────────────────────
def test_format_summary_no_findings():
    out = jobs_module._format_summary([], 5)
    assert "No issues found" in out


def test_format_summary_with_findings():
    findings = [
        {"file_path": "a.py", "line_number": 10, "severity": "critical", "body": "SQL injection risk"},
    ]
    out = jobs_module._format_summary(findings, 5)
    assert "Critical" in out
    assert "a.py:10" in out
    assert "SQL injection risk" in out


# ──────────────────────────────────────────────
# Full job integration
# ──────────────────────────────────────────────
def _seed_review():
    db = SessionLocal()
    try:
        user = User(github_id=1, username="ben", access_token="gho_fake")
        db.add(user); db.commit(); db.refresh(user)
        repo = Repository(github_id=2, full_name="ben/demo", owner_id=user.id)
        db.add(repo); db.commit(); db.refresh(repo)
        review = Review(repository_id=repo.id, pr_number=8, pr_title="X", status=ReviewStatus.PENDING)
        db.add(review); db.commit(); db.refresh(review)
        return review.id
    finally:
        db.close()


def test_full_job_creates_comments(client, monkeypatch):
    """End-to-end job: diff → Claude → comments stored → posted → completed."""
    review_id = _seed_review()

    # Mock diff fetch
    async def fake_diff(self, repo_full_name, pr_number):
        return "diff --git a/auth.py b/auth.py\n+password = md5(pw)\n"
    monkeypatch.setattr("app.workers.jobs.GitHubClient.get_pr_diff", fake_diff)

    # Mock Claude to return two findings
    def fake_review_diff(diff_text, client=None):
        return [
            {"file_path": "auth.py", "line_number": 1, "severity": "critical", "body": "md5 is insecure for passwords"},
            {"file_path": "auth.py", "line_number": 1, "severity": "info", "body": "Consider adding a type hint"},
        ]
    monkeypatch.setattr("app.workers.jobs.review_diff", fake_review_diff)

    # Mock the GitHub comment post
    posted = {}
    async def fake_post(self, repo_full_name, pr_number, body):
        posted["body"] = body
        return {"id": 999}
    monkeypatch.setattr("app.workers.jobs.GitHubClient.post_issue_comment", fake_post)

    result = jobs_module.process_review(review_id)

    assert result["status"] == "completed"
    assert result["findings"] == 2
    assert result["posted_to_github"] is True

    # Verify comments persisted
    db = SessionLocal()
    try:
        comments = db.query(ReviewComment).filter(ReviewComment.review_id == review_id).all()
        assert len(comments) == 2
        assert all(c.posted_to_github for c in comments)
        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.COMPLETED
    finally:
        db.close()

    # The posted summary should mention the critical finding
    assert "md5" in posted["body"]


def test_job_completes_even_if_github_post_fails(client, monkeypatch):
    """If posting to GitHub fails, review still completes; comments not marked posted."""
    review_id = _seed_review()

    async def fake_diff(self, repo_full_name, pr_number):
        return "diff --git a/x.py b/x.py\n+x=1\n"
    monkeypatch.setattr("app.workers.jobs.GitHubClient.get_pr_diff", fake_diff)

    def fake_review_diff(diff_text, client=None):
        return [{"file_path": "x.py", "line_number": 1, "severity": "warning", "body": "y"}]
    monkeypatch.setattr("app.workers.jobs.review_diff", fake_review_diff)

    async def failing_post(self, repo_full_name, pr_number, body):
        raise RuntimeError("GitHub 403")
    monkeypatch.setattr("app.workers.jobs.GitHubClient.post_issue_comment", failing_post)

    result = jobs_module.process_review(review_id)

    assert result["status"] == "completed"  # still completes
    assert result["posted_to_github"] is False

    db = SessionLocal()
    try:
        comments = db.query(ReviewComment).filter(ReviewComment.review_id == review_id).all()
        assert len(comments) == 1
        assert comments[0].posted_to_github is False  # not marked posted
    finally:
        db.close()


def test_job_fails_gracefully_on_claude_error(client, monkeypatch):
    """If Claude raises, the review is marked FAILED."""
    review_id = _seed_review()

    async def fake_diff(self, repo_full_name, pr_number):
        return "diff --git a/x.py b/x.py\n+x=1\n"
    monkeypatch.setattr("app.workers.jobs.GitHubClient.get_pr_diff", fake_diff)

    def boom(diff_text, client=None):
        raise RuntimeError("API overloaded")
    monkeypatch.setattr("app.workers.jobs.review_diff", boom)

    result = jobs_module.process_review(review_id)
    assert result["status"] == "failed"

    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.FAILED
    finally:
        db.close()
