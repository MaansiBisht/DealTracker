"""Magic-link auth — flow, rate limit, admin claim, orphan claim.

The tests patch `send_email` so SMTP is never touched; everything else
exercises the real session middleware, real LoginToken rows, and the
real consume/claim pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.server import magic_link
from src.server.db import SessionLocal
from src.server.models import Job, LoginToken, TelegramPairing, User


# ---------- shared helpers --------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_send_email(monkeypatch):
    """Replace SMTP with a list-collector — every test gets its own."""
    sent: list[tuple[str, str, str]] = []

    def _fake_send(subject: str, body: str, recipient_email: str) -> None:
        sent.append((subject, body, recipient_email))

    monkeypatch.setattr("src.server.routes.send_email", _fake_send)
    monkeypatch.setattr("src.utils.email.send_email", _fake_send)
    yield sent


def _last_token_for(email: str) -> str:
    with SessionLocal() as db:
        rows = db.query(LoginToken).filter(LoginToken.email == email.lower()).all()
        assert rows, f"no token issued for {email}"
        return rows[-1].token


# ---------- request-magic-link ---------------------------------------------


class TestRequestMagicLink:
    def test_issues_token_and_emails_user(self, client, _stub_send_email):
        r = client.post("/api/auth/request-magic-link", json={"email": "ada@example.com"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert len(_stub_send_email) == 1
        subject, body, recipient = _stub_send_email[0]
        assert recipient == "ada@example.com"
        assert "login link" in subject.lower()
        assert "/api/auth/verify?token=" in body

    def test_lowercases_email_in_storage(self, client):
        client.post("/api/auth/request-magic-link", json={"email": "Mixed@Case.IO"})
        with SessionLocal() as db:
            rows = db.query(LoginToken).all()
            assert len(rows) == 1
            assert rows[0].email == "mixed@case.io"

    def test_rejects_invalid_email_format(self, client):
        r = client.post("/api/auth/request-magic-link", json={"email": "not-an-email"})
        assert r.status_code == 422  # Pydantic EmailStr validation

    def test_rate_limited_after_five_per_email(self, client, _stub_send_email):
        for _ in range(5):
            r = client.post("/api/auth/request-magic-link", json={"email": "spam@example.com"})
            assert r.status_code == 200
        # Sixth in the same hour → 429 with Retry-After.
        r = client.post("/api/auth/request-magic-link", json={"email": "spam@example.com"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert int(r.headers["Retry-After"]) > 0

    def test_smtp_failure_surfaces_503(self, client, monkeypatch):
        def _boom(*_a, **_kw):
            raise RuntimeError("smtp down")

        monkeypatch.setattr("src.server.routes.send_email", _boom)
        r = client.post("/api/auth/request-magic-link", json={"email": "ada@example.com"})
        assert r.status_code == 503


# ---------- verify ----------------------------------------------------------


class TestVerify:
    def test_valid_token_creates_session_and_redirects_home(self, client):
        client.post("/api/auth/request-magic-link", json={"email": "ada@example.com"})
        token = _last_token_for("ada@example.com")

        r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"].endswith("/")
        # Session cookie is now set on the client.
        assert "dealtracker_session" in client.cookies

        # /api/auth/me succeeds with the same client.
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["user"]["email"] == "ada@example.com"
        assert body["user"]["is_admin"] is False

    def test_token_is_single_use(self, client):
        client.post("/api/auth/request-magic-link", json={"email": "ada@example.com"})
        token = _last_token_for("ada@example.com")

        first = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
        assert first.status_code == 303

        # Use a fresh client (no session) so the second click really tests the token.
        from fastapi.testclient import TestClient
        c2 = TestClient(client.app)
        second = c2.get(f"/api/auth/verify?token={token}", follow_redirects=False)
        assert second.status_code == 303
        assert "login_error=token_already_used" in second.headers["location"]

    def test_unknown_token_redirects_with_error(self, client):
        r = client.get("/api/auth/verify?token=this-token-was-never-issued", follow_redirects=False)
        assert r.status_code == 303
        assert "login_error=unknown_token" in r.headers["location"]

    def test_expired_token_redirects_with_error(self, client):
        client.post("/api/auth/request-magic-link", json={"email": "ada@example.com"})
        token = _last_token_for("ada@example.com")
        # Manually expire the token by rewriting expires_at.
        with SessionLocal() as db:
            row = db.get(LoginToken, token)
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
        assert r.status_code == 303
        assert "login_error=token_expired" in r.headers["location"]


# ---------- /me & logout ----------------------------------------------------


class TestMeAndLogout:
    def test_me_returns_401_without_session(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_returns_user_and_telegram_status(self, auth_client):
        c, _user = auth_client(email="bob@example.com")
        r = c.get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == "bob@example.com"
        assert "telegram_bot_configured" in body

    def test_logout_clears_session(self, auth_client):
        c, _user = auth_client(email="bob@example.com")
        assert c.get("/api/auth/me").status_code == 200
        r = c.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # After logout the cookie is wiped, so /me fails.
        c.cookies.clear()
        assert c.get("/api/auth/me").status_code == 401


# ---------- admin + orphan claim -------------------------------------------


class TestAdminClaim:
    def test_admin_email_promotes_user_to_admin(self, client):
        # conftest sets ADMIN_EMAIL=admin@example.com.
        client.post("/api/auth/request-magic-link", json={"email": "admin@example.com"})
        token = _last_token_for("admin@example.com")
        client.get(f"/api/auth/verify?token={token}", follow_redirects=False)

        body = client.get("/api/auth/me").json()
        assert body["user"]["is_admin"] is True

    def test_non_admin_email_stays_regular(self, client):
        client.post("/api/auth/request-magic-link", json={"email": "regular@example.com"})
        token = _last_token_for("regular@example.com")
        client.get(f"/api/auth/verify?token={token}", follow_redirects=False)

        body = client.get("/api/auth/me").json()
        assert body["user"]["is_admin"] is False

    def test_first_admin_signin_claims_orphan_rows(self, client):
        with SessionLocal() as db:
            db.add(Job(
                kind="product", url="https://example.com/a", alert_type="stock",
                platform="amazon", status="pending", active=True,
                email="orphan@example.com",
            ))
            db.add(TelegramPairing(token="abcdef123456ghij"))
            db.commit()
            orphan_job = db.query(Job).filter(Job.user_id.is_(None)).count()
            orphan_pair = db.query(TelegramPairing).filter(TelegramPairing.user_id.is_(None)).count()
            assert orphan_job == 1 and orphan_pair == 1

        client.post("/api/auth/request-magic-link", json={"email": "admin@example.com"})
        token = _last_token_for("admin@example.com")
        client.get(f"/api/auth/verify?token={token}", follow_redirects=False)

        with SessionLocal() as db:
            admin = db.query(User).filter(User.email == "admin@example.com").one()
            still_orphan_jobs = db.query(Job).filter(Job.user_id.is_(None)).count()
            still_orphan_pairs = db.query(TelegramPairing).filter(TelegramPairing.user_id.is_(None)).count()
            owned_jobs = db.query(Job).filter(Job.user_id == admin.id).count()
            owned_pairs = db.query(TelegramPairing).filter(TelegramPairing.user_id == admin.id).count()

        assert still_orphan_jobs == 0
        assert still_orphan_pairs == 0
        assert owned_jobs == 1
        assert owned_pairs == 1

    def test_regular_signin_does_not_claim_orphans(self, client):
        with SessionLocal() as db:
            db.add(Job(
                kind="product", url="https://example.com/b", alert_type="stock",
                platform="amazon", status="pending", active=True,
            ))
            db.commit()

        client.post("/api/auth/request-magic-link", json={"email": "regular@example.com"})
        token = _last_token_for("regular@example.com")
        client.get(f"/api/auth/verify?token={token}", follow_redirects=False)

        with SessionLocal() as db:
            orphans = db.query(Job).filter(Job.user_id.is_(None)).count()
        assert orphans == 1  # untouched


# ---------- pruning ---------------------------------------------------------


def test_prune_expired_tokens_drops_old_rows():
    with SessionLocal() as db:
        db.add(LoginToken(
            token="old-token-1234567890",
            email="old@example.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            expires_at=datetime.now(timezone.utc) - timedelta(days=2) + timedelta(minutes=15),
        ))
        db.add(LoginToken(
            token="fresh-token-1234567890",
            email="fresh@example.com",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        ))
        db.commit()
        assert db.query(LoginToken).count() == 2

    with SessionLocal() as db:
        dropped = magic_link.prune_expired_tokens(db, older_than_hours=24)
    assert dropped == 1

    with SessionLocal() as db:
        remaining = [r.email for r in db.query(LoginToken).all()]
    assert remaining == ["fresh@example.com"]
