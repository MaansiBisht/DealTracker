"""End-to-end API smoke tests via FastAPI's TestClient.

The conftest stubs out the scheduler, so these exercise routing,
validation, persistence, and the recent-events JOIN — no Selenium,
no real ticks.
"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.0.1"}


def test_platforms_lists_both_kinds(client):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    data = r.json()
    assert "amazon" in data["product"]
    assert "booking" in data["hotel"]
    assert set(data["product"]).isdisjoint(set(data["hotel"]))


def test_create_product_job(client):
    payload = {
        "url": "https://www.amazon.in/dp/B08BPQ9CZ1",
        "email": "me@example.com",
        "alert_type": "price",
        "threshold": 1000,
    }
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201
    job = r.json()
    assert job["kind"] == "product"
    assert job["platform"] == "amazon"
    assert job["status"] == "pending"
    assert job["active"] is True


def test_create_rejects_unsupported_url(client):
    r = client.post("/api/jobs", json={
        "url": "https://example.com/anything",
        "email": "me@example.com",
        "alert_type": "stock",
    })
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower()


def test_create_rejects_hotel_with_wrong_alert_type(client):
    r = client.post("/api/jobs", json={
        "url": "https://www.booking.com/hotel/in/foo.html",
        "email": "me@example.com",
        "alert_type": "stock",
    })
    assert r.status_code == 400


def test_create_rejects_price_alert_without_threshold(client):
    r = client.post("/api/jobs", json={
        "url": "https://www.amazon.in/dp/foo",
        "email": "me@example.com",
        "alert_type": "price",
    })
    assert r.status_code == 400


def test_list_jobs_filters_by_kind(client):
    client.post("/api/jobs", json={
        "url": "https://www.amazon.in/dp/B08BPQ9CZ1",
        "email": "me@example.com",
        "alert_type": "stock",
    })
    client.post("/api/jobs", json={
        "url": "https://www.booking.com/hotel/in/foo.html?checkin=2026-06-01&checkout=2026-06-02",
        "email": "me@example.com",
        "alert_type": "price_drop",
        "threshold": 4500,
    })

    products = client.get("/api/jobs?kind=product").json()
    hotels = client.get("/api/jobs?kind=hotel").json()
    assert len(products) == 1
    assert len(hotels) == 1
    assert products[0]["platform"] == "amazon"
    assert hotels[0]["platform"] == "booking"


def test_stop_job_marks_inactive(client):
    created = client.post("/api/jobs", json={
        "url": "https://www.amazon.in/dp/B08BPQ9CZ1",
        "email": "me@example.com",
        "alert_type": "stock",
    }).json()
    job_id = created["id"]

    r = client.post(f"/api/jobs/{job_id}/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is False
    assert body["status"] == "stopped"

    listing = client.get("/api/jobs").json()
    assert all(j["id"] != job_id for j in listing)


def test_stop_unknown_job_404(client):
    r = client.post("/api/jobs/does-not-exist/stop")
    assert r.status_code == 404


def test_recent_events_has_join_fields(client):
    """Stopping a job emits a job_stop event with job_kind + platform."""
    job = client.post("/api/jobs", json={
        "url": "https://www.amazon.in/dp/B08BPQ9CZ1",
        "email": "me@example.com",
        "alert_type": "stock",
    }).json()
    client.post(f"/api/jobs/{job['id']}/stop")

    events = client.get(f"/api/events/recent?job_id={job['id']}").json()
    assert any(e["kind"] == "job_stop" for e in events)
    e = events[-1]
    assert e["job_kind"] == "product"
    assert e["platform"] == "amazon"
    assert "ts" in e and "id" in e
