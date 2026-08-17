"""Iteration 24 tests for Dispatch work-order filtering and live attendance statistics."""
import os
import re
import uuid
from datetime import date
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
API = f"{base_url.rstrip('/')}/api"


def _credentials():
    path = Path("/app/memory/test_credentials.md")
    if not path.exists():
        pytest.skip("Missing /app/memory/test_credentials.md")
    text = path.read_text(encoding="utf-8")
    email = re.search(r"(?im)^\s*[-*]\s*Email:\s*([^\s]+)", text)
    password = re.search(r"(?im)^\s*[-*]\s*Password:\s*([^\s]+)", text)
    if not email or not password:
        pytest.skip("Admin email/password missing from test_credentials.md")
    return email.group(1), password.group(1)


@pytest.fixture(scope="module")
def dispatch_context():
    """Authenticate and create isolated references plus one schedule for today's aggregate tests."""
    email, password = _credentials()
    admin = requests.Session()
    admin.headers.update({"Content-Type": "application/json"})
    login = admin.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if login.status_code != 200:
        pytest.fail(f"Authentication failed: {login.status_code} {login.text[:500]}")
    actor = login.json()
    assert actor["email"] == email
    assert actor["role"] == "super_admin"

    tag = uuid.uuid4().hex[:10]
    created = {"schedules": [], "posts": [], "officers": [], "vendors": [], "clients": []}

    def post(path, payload):
        response = admin.post(f"{API}{path}", json=payload, timeout=30)
        assert response.status_code == 200, f"POST {path}: {response.status_code} {response.text}"
        return response.json()

    client = post("/dispatch/clients", {"code": f"TEST_I24_C_{tag}", "name": f"TEST Iter24 Client {tag}"})
    created["clients"].append(client["id"])
    vendor = post("/dispatch/vendors", {"code": f"TEST_I24_V_{tag}", "name": f"TEST Iter24 Vendor {tag}"})
    created["vendors"].append(vendor["id"])
    officer = post("/dispatch/officers", {
        "officer_code": f"TEST_I24_O_{tag}",
        "name": f"TEST Iter24 Officer {tag}",
        "vendor_id": vendor["id"],
        "status": "active",
    })
    created["officers"].append(officer["id"])
    post_site = post("/dispatch/post-sites", {
        "post_pin": f"TEST-I24-{tag}",
        "name": f"TEST Iter24 Post {tag}",
        "client_id": client["id"],
        "vendor_id": vendor["id"],
        "required_officers": 1,
    })
    created["posts"].append(post_site["id"])

    before = admin.get(f"{API}/dispatch/dashboard/stats", timeout=30)
    assert before.status_code == 200, before.text
    baseline_stats = before.json()

    schedule = post("/dispatch/schedules", {
        "date": date.today().isoformat(),
        "shift_type": "Morning",
        "start_time": "01:00",
        "end_time": "02:00",
        "client_id": client["id"],
        "vendor_id": vendor["id"],
        "post_site_id": post_site["id"],
        "officer_id": officer["id"],
        "work_order_number": "WO-TEST-77",
        "remarks": f"TEST Iter24 schedule {tag}",
    })
    created["schedules"].append(schedule["id"])

    yield {
        "admin": admin,
        "actor": actor,
        "schedule": schedule,
        "baseline_stats": baseline_stats,
        "created": created,
    }

    for schedule_id in created["schedules"]:
        admin.delete(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    for post_id in created["posts"]:
        admin.delete(f"{API}/dispatch/post-sites/{post_id}", timeout=30)
    for officer_id in created["officers"]:
        admin.delete(f"{API}/dispatch/officers/{officer_id}", timeout=30)
    for vendor_id in created["vendors"]:
        admin.delete(f"{API}/dispatch/vendors/{vendor_id}", timeout=30)
    for client_id in created["clients"]:
        admin.delete(f"{API}/dispatch/clients/{client_id}", timeout=30)


# Work-order query performs case-insensitive substring matching and excludes non-matches.
def test_work_order_filter_exact_target_and_no_match(dispatch_context):
    admin = dispatch_context["admin"]
    schedule_id = dispatch_context["schedule"]["id"]

    matched = admin.get(f"{API}/dispatch/schedules", params={"work_order": "test-77"}, timeout=30)
    assert matched.status_code == 200, matched.text
    body = matched.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == schedule_id
    assert body["items"][0]["work_order_number"] == "WO-TEST-77"

    missing = admin.get(f"{API}/dispatch/schedules", params={"work_order": "TEST-99"}, timeout=30)
    assert missing.status_code == 200, missing.text
    assert missing.json()["total"] == 0
    assert missing.json()["items"] == []


# Dashboard stats expose integer checked-in/out counters and follow status transitions.
def test_dashboard_checked_in_then_checked_out_counts(dispatch_context):
    admin = dispatch_context["admin"]
    schedule_id = dispatch_context["schedule"]["id"]
    baseline = dispatch_context["baseline_stats"]

    initial = admin.get(f"{API}/dispatch/dashboard/stats", timeout=30)
    assert initial.status_code == 200, initial.text
    initial_body = initial.json()
    for field in ("checked_in", "checked_out"):
        assert field in initial_body
        assert isinstance(initial_body[field], int)
        assert initial_body[field] >= 0

    check_in = admin.post(
        f"{API}/dispatch/schedules/{schedule_id}/status",
        json={"shift_status": "Check-in", "actual_check_in": "01:00"},
        timeout=30,
    )
    assert check_in.status_code == 200, check_in.text
    assert check_in.json()["shift_status"] == "Check-in"

    after_check_in = admin.get(f"{API}/dispatch/dashboard/stats", timeout=30)
    assert after_check_in.status_code == 200, after_check_in.text
    checked_in_stats = after_check_in.json()
    assert checked_in_stats["checked_in"] == baseline["checked_in"] + 1
    assert checked_in_stats["checked_out"] == baseline["checked_out"]

    checkout = admin.post(
        f"{API}/dispatch/schedules/{schedule_id}/status",
        json={"shift_status": "Checkout", "actual_check_out": "02:00"},
        timeout=30,
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["shift_status"] == "Checkout"

    after_checkout = admin.get(f"{API}/dispatch/dashboard/stats", timeout=30)
    assert after_checkout.status_code == 200, after_checkout.text
    checked_out_stats = after_checkout.json()
    assert checked_out_stats["checked_in"] == baseline["checked_in"]
    assert checked_out_stats["checked_out"] == baseline["checked_out"] + 1
    assert all(isinstance(checked_out_stats[field], int) for field in (
        "checked_in", "checked_out", "pending", "no_response", "absent"
    ))
