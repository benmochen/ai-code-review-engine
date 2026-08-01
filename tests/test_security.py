"""
Tests for webhook signature verification — run with: pytest tests/test_security.py -v

No database or app needed; these exercise the HMAC helper directly.
"""
import hashlib
import hmac

import pytest

from app.core.security import verify_webhook_signature

SECRET = "topsecret"
BODY = b'{"action": "opened"}'


def sign(body: bytes = BODY, secret: str = SECRET) -> str:
    """Build the header GitHub would send for this body and secret."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ──────────────────────────────────────────────
# The happy path
# ──────────────────────────────────────────────
def test_valid_signature_accepted():
    assert verify_webhook_signature(BODY, sign(), SECRET) is True


# ──────────────────────────────────────────────
# Malformed / hostile signature headers
#
# Every one of these is attacker-controlled input, so the contract is
# "return False" — never raise. A raised exception becomes a 500, which
# both leaks that the input was unexpected and misreports an
# unauthorized request as a server fault.
# ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "signature_header",
    [
        pytest.param("sha256=" + "a" * 64, id="wrong_ascii_digest"),
        pytest.param("sha256=café", id="non_ascii"),
        pytest.param(
            "sha256=" + "".join(chr(i) for i in range(200, 264)), id="latin1_junk_64_chars"
        ),
        pytest.param("", id="empty_header"),
        pytest.param(None, id="missing_header"),
        pytest.param("deadbeef", id="no_sha256_prefix"),
        pytest.param("sha256=" + "🔥" * 16, id="emoji"),
    ],
)
def test_bad_signature_rejected(signature_header):
    assert verify_webhook_signature(BODY, signature_header, SECRET) is False


def test_non_ascii_does_not_raise():
    """Regression: non-ASCII in the header used to raise TypeError out of
    hmac.compare_digest, surfacing as a 500 instead of a 401."""
    try:
        result = verify_webhook_signature(BODY, "sha256=café", SECRET)
    except Exception as exc:  # pragma: no cover - only runs if the bug returns
        pytest.fail(f"should return False, raised {type(exc).__name__}: {exc}")
    assert result is False


# ──────────────────────────────────────────────
# The actual security contract
#
# Above proves it doesn't crash; these prove it doesn't wrongly accept.
# ──────────────────────────────────────────────
def test_wrong_secret_rejected():
    """A signature made with someone else's secret must not verify."""
    forged = sign(secret="not-the-real-secret")
    assert verify_webhook_signature(BODY, forged, SECRET) is False


def test_tampered_body_rejected():
    """A valid signature for a different body must not verify this one."""
    signature = sign(body=b'{"action": "opened"}')
    tampered = b'{"action": "closed"}'
    assert verify_webhook_signature(tampered, signature, SECRET) is False


def test_empty_body_still_verifies():
    """An empty payload is unusual but legitimate — it must still round-trip."""
    assert verify_webhook_signature(b"", sign(body=b""), SECRET) is True
