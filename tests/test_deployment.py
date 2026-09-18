"""
Tests for deployment readiness, safety guardrails, and reverse-proxy compatibility.
"""
import pytest
from app.core.reviewer import preprocess_diff, is_noise_file, MAX_DIFF_CHARS
from app.workers.jobs import _format_summary


def test_noise_file_detection():
    assert is_noise_file("package-lock.json") is True
    assert is_noise_file("client/pnpm-lock.yaml") is True
    assert is_noise_file("dist/bundle.min.js") is True
    assert is_noise_file("styles/main.min.css") is True
    assert is_noise_file("assets/logo.svg") is True
    assert is_noise_file("images/banner.png") is True
    assert is_noise_file("app/main.py") is False
    assert is_noise_file("src/Dashboard.jsx") is False


def test_preprocess_diff_omits_noise_files():
    diff = (
        "diff --git a/package-lock.json b/package-lock.json\n"
        "+{ \"name\": \"huge-lockfile\" }\n"
        "diff --git a/app.py b/app.py\n"
        "+def foo(): return 42\n"
    )
    cleaned, truncated = preprocess_diff(diff)
    assert truncated is False
    assert "Omitted lock/generated files" in cleaned
    assert "+def foo(): return 42" in cleaned


def test_preprocess_diff_truncation():
    large_diff = "diff --git a/big.py b/big.py\n" + ("+line\n" * 25000)
    cleaned, truncated = preprocess_diff(large_diff, max_chars=1000)
    assert truncated is True
    assert len(cleaned) <= 1200
    assert "Diff truncated" in cleaned


def test_format_summary_with_truncation():
    out = _format_summary([], 12, truncated=True)
    assert "Diff exceeded safety limits" in out


def test_health_components(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "redis" in data


def test_auth_login_uses_public_base_url(client, monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.github_client_id", "test-client-id")
    monkeypatch.setattr("app.api.auth.settings.public_base_url", "https://reviewbot.example.com")
    r = client.get("/api/auth/login", follow_redirects=False)
    assert r.status_code == 307
    location = r.headers["location"]
    assert "redirect_uri=https://reviewbot.example.com/api/auth/callback" in location


def test_spa_serving_and_api_isolation(client):
    # Non-existent API route returns 404 JSON, not SPA index.html
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
