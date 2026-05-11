"""Per-user authorization — Step 4 enforcement.

Two-user setup per test: a regular user and an admin. Verifies that
every protected endpoint scopes correctly. The admin sees everything;
the regular user sees their own slice; the third party (no session)
gets 401 from every protected endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.server.db import SessionLocal
from src.server.models import Job


# ---------- jobs list / create / stop --------------------------------------


def _create_job(client, *, url="https://www.amazon.in/dp/B08BPQ9CZ1", alert_type="stock", **extra):
    payload = {
        "url": url,
        "email": "me@example.com",
        "alert_type": alert_type,
        **extra,
    }
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


class TestJobIsolation:
    def test_regular_user_sees_only_own_jobs(self, auth_client):
        alice_client, alice = auth_client(email="alice@example.com")
        bob_client, _bob = auth_client(email="bob@example.com")

        _create_job(alice_client)
        _create_job(bob_client, url="https://www.flipkart.com/foo/p/itm123")

        alice_jobs = alice_client.get("/api/jobs").json()
        bob_jobs = bob_client.get("/api/jobs").json()

        assert len(alice_jobs) == 1
        assert len(bob_jobs) == 1
        assert alice_jobs[0]["platform"] == "amazon"
        assert bob_jobs[0]["platform"] == "flipkart"
        assert alice_jobs[0]["user_id"] == alice.id

    def test_admin_sees_every_users_jobs(self, auth_client):
        admin_client, _admin = auth_client(email="admin@example.com", is_admin=True)
        alice_client, _alice = auth_client(email="alice@example.com")

        _create_job(alice_client)
        _create_job(admin_client, url="https://www.flipkart.com/foo/p/itm123")

        admin_jobs = admin_client.get("/api/jobs").json()
        assert len(admin_jobs) == 2
        platforms = {j["platform"] for j in admin_jobs}
        assert platforms == {"amazon", "flipkart"}

    def test_create_sets_user_id_to_current_user(self, auth_client):
        c, user = auth_client(email="ada@example.com")
        job = _create_job(c)
        assert job["user_id"] == user.id

    def test_protected_endpoints_require_session(self, app):
        c = TestClient(app)
        assert c.get("/api/jobs").status_code == 401
        assert c.post("/api/jobs", json={
            "url": "https://www.amazon.in/dp/x",
            "email": "x@y.com",
            "alert_type": "stock",
        }).status_code == 401
        assert c.get("/api/events/recent").status_code == 401


class TestStopAuthorization:
    def test_regular_user_cannot_stop_someone_elses_job(self, auth_client):
        alice_client, _ = auth_client(email="alice@example.com")
        bob_client, _ = auth_client(email="bob@example.com")

        alices_job = _create_job(alice_client)
        r = bob_client.post(f"/api/jobs/{alices_job['id']}/stop")
        assert r.status_code == 403

        # Job is still active because the stop was refused.
        with SessionLocal() as db:
            j = db.get(Job, alices_job["id"])
            assert j is not None
            assert j.active is True

    def test_admin_can_stop_anyones_job(self, auth_client):
        alice_client, _ = auth_client(email="alice@example.com")
        admin_client, _ = auth_client(email="admin@example.com", is_admin=True)

        alices_job = _create_job(alice_client)
        r = admin_client.post(f"/api/jobs/{alices_job['id']}/stop")
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_owner_can_stop_their_own_job(self, auth_client):
        c, _user = auth_client(email="ada@example.com")
        job = _create_job(c)
        r = c.post(f"/api/jobs/{job['id']}/stop")
        assert r.status_code == 200

    def test_stop_unknown_id_404(self, auth_client):
        c, _ = auth_client(email="alice@example.com")
        r = c.post("/api/jobs/does-not-exist/stop")
        assert r.status_code == 404


# ---------- recent events ---------------------------------------------------


class TestRecentEventsIsolation:
    def test_regular_user_only_sees_own_events(self, auth_client):
        alice_client, _ = auth_client(email="alice@example.com")
        bob_client, _ = auth_client(email="bob@example.com")

        a_job = _create_job(alice_client)
        b_job = _create_job(bob_client, url="https://www.flipkart.com/foo/p/itm456")

        # Both stop their own jobs → each gets one job_stop event.
        alice_client.post(f"/api/jobs/{a_job['id']}/stop")
        bob_client.post(f"/api/jobs/{b_job['id']}/stop")

        alice_events = alice_client.get("/api/events/recent").json()
        bob_events = bob_client.get("/api/events/recent").json()

        assert all(e["job_id"] == a_job["id"] for e in alice_events)
        assert all(e["job_id"] == b_job["id"] for e in bob_events)

    def test_admin_sees_all_events(self, auth_client):
        alice_client, _ = auth_client(email="alice@example.com")
        admin_client, _ = auth_client(email="admin@example.com", is_admin=True)

        a_job = _create_job(alice_client)
        b_job = _create_job(admin_client, url="https://www.flipkart.com/foo/p/itm789")
        alice_client.post(f"/api/jobs/{a_job['id']}/stop")
        admin_client.post(f"/api/jobs/{b_job['id']}/stop")

        events = admin_client.get("/api/events/recent").json()
        job_ids = {e["job_id"] for e in events}
        assert {a_job["id"], b_job["id"]} <= job_ids


# ---------- telegram connection -------------------------------------------


class TestTelegramConnection:
    def test_connection_reflects_user_row(self, auth_client):
        c, user = auth_client(email="ada@example.com")

        # No pairing yet.
        r = c.get("/api/telegram/connection")
        assert r.status_code == 200
        assert r.json() == {"paired": False, "chat_id": None, "display_name": None}

        # Manually mark this user as paired (simulating /start landing).
        from src.server.models import User as UserModel
        with SessionLocal() as db:
            u = db.get(UserModel, user.id)
            u.telegram_chat_id = "987654321"
            u.telegram_display_name = "Ada Lovelace"
            db.commit()

        r = c.get("/api/telegram/connection")
        assert r.json() == {
            "paired": True,
            "chat_id": "987654321",
            "display_name": "Ada Lovelace",
        }

    def test_disconnect_clears_pairing(self, auth_client):
        c, user = auth_client(email="ada@example.com")
        from src.server.models import User as UserModel
        with SessionLocal() as db:
            u = db.get(UserModel, user.id)
            u.telegram_chat_id = "987654321"
            u.telegram_display_name = "Ada"
            db.commit()

        r = c.post("/api/telegram/disconnect")
        assert r.status_code == 200
        body = c.get("/api/telegram/connection").json()
        assert body == {"paired": False, "chat_id": None, "display_name": None}

    def test_connection_requires_auth(self, app):
        c = TestClient(app)
        assert c.get("/api/telegram/connection").status_code == 401
        assert c.post("/api/telegram/disconnect").status_code == 401
