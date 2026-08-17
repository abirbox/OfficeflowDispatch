"""Dispatch schedule attendance actions, audit history, lifecycle logging, and RBAC tests."""
import os
import re
import time
import uuid
from datetime import datetime
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


def _login(email, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if response.status_code != 200:
        pytest.fail(f"Authentication failed for {email}: {response.status_code} {response.text[:500]}")
    return session, response.json()


@pytest.fixture(scope="module")
def admin_context():
    """Create isolated references, four schedules, and a view-only employee; clean up afterwards."""
    email, password = _credentials()
    admin, actor = _login(email, password)
    assert actor["role"] == "super_admin"
    tag = uuid.uuid4().hex[:10]
    created = {"schedules": [], "posts": [], "officers": [], "vendors": [], "clients": [], "employees": []}

    def post(path, payload):
        response = admin.post(f"{API}{path}", json=payload, timeout=30)
        assert response.status_code == 200, f"POST {path}: {response.status_code} {response.text}"
        return response.json()

    client = post("/dispatch/clients", {"code": f"TEST_AC_{tag}", "name": f"TEST Actions Client {tag}"})
    created["clients"].append(client["id"])
    vendor = post("/dispatch/vendors", {"code": f"TEST_AV_{tag}", "name": f"TEST Actions Vendor {tag}"})
    created["vendors"].append(vendor["id"])
    officer = post("/dispatch/officers", {
        "officer_code": f"TEST_AO_{tag}", "name": f"TEST Actions Officer {tag}",
        "vendor_id": vendor["id"], "status": "active",
    })
    created["officers"].append(officer["id"])
    post_site = post("/dispatch/post-sites", {
        "post_pin": f"TEST-ACT-{tag}", "name": f"TEST Actions Post {tag}",
        "client_id": client["id"], "vendor_id": vendor["id"], "required_officers": 1,
    })
    created["posts"].append(post_site["id"])

    common = {
        "client_id": client["id"], "vendor_id": vendor["id"], "post_site_id": post_site["id"],
        "officer_id": officer["id"], "shift_type": "Morning", "start_time": "08:00", "end_time": "16:00",
    }
    schedules = {}
    for index, label in enumerate(("lifecycle", "cancel", "delete", "permission"), start=1):
        schedule = post("/dispatch/schedules", {
            **common, "date": f"2037-04-{index:02d}", "remarks": f"TEST {label} {tag}"
        })
        schedules[label] = schedule
        created["schedules"].append(schedule["id"])

    employee_password = "TestActions@123"
    employee_payload = {
        "email": f"test_actions_view_{tag}@example.com", "name": f"TEST Actions Viewer {tag}",
        "password": employee_password, "role": "employee", "permissions": ["dispatch.schedule.view"],
    }
    viewer = post("/employees", employee_payload)
    created["employees"].append(viewer["id"])

    yield {
        "admin": admin, "actor": actor, "tag": tag, "created": created, "schedules": schedules,
        "viewer_payload": employee_payload, "viewer_password": employee_password,
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
    for employee_id in created["employees"]:
        admin.delete(f"{API}/employees/{employee_id}", timeout=30)


# Created audit entry and API response contract.
def test_created_action_exists_with_complete_contract(admin_context):
    admin = admin_context["admin"]
    schedule = admin_context["schedules"]["lifecycle"]
    response = admin.get(f"{API}/dispatch/schedules/{schedule['id']}/actions", timeout=30)
    assert response.status_code == 200, response.text
    actions = response.json()
    assert isinstance(actions, list) and actions
    created = actions[0]
    assert created["action"] == "Created"
    assert created["old_value"] is None
    assert created["new_value"] == "Not Started"
    assert created["actor_id"] == admin_context["actor"]["id"]
    assert created["actor_name"] == admin_context["actor"]["name"]
    assert created["actor_role"] == "super_admin"
    for field in ("actor_id", "actor_name", "actor_role", "action", "old_value", "new_value", "remarks", "at"):
        assert field in created, f"Created history entry is missing required field: {field}"
    datetime.fromisoformat(created["at"])


# Quick statuses, PUT status/edit, confirmation, last-modified data, and reverse chronological history.
def test_status_updates_and_full_action_history(admin_context):
    admin = admin_context["admin"]
    actor = admin_context["actor"]
    schedule_id = admin_context["schedules"]["lifecycle"]["id"]

    check_in = admin.post(f"{API}/dispatch/schedules/{schedule_id}/status", json={
        "shift_status": "Check-in", "actual_check_in": "08:05", "remarks": "TEST checked in"
    }, timeout=30)
    assert check_in.status_code == 200, check_in.text
    body = check_in.json()
    assert body["shift_status"] == "Check-in" and body["actual_check_in"] == "08:05"
    assert body["last_modified_by_id"] == actor["id"]
    assert body["last_modified_by_name"] == actor["name"]
    assert body["last_modified_action"] == "Check-in"
    datetime.fromisoformat(body["last_modified_at"])

    time.sleep(0.05)
    checkout = admin.post(f"{API}/dispatch/schedules/{schedule_id}/status", json={
        "shift_status": "Checkout", "actual_check_out": "16:02", "remarks": "TEST checked out"
    }, timeout=30)
    assert checkout.status_code == 200, checkout.text
    out = checkout.json()
    assert out["shift_status"] == "Checkout" and out["actual_check_out"] == "16:02"
    assert out["last_modified_by_name"] == actor["name"]
    assert out["last_modified_action"] == "Checkout"

    time.sleep(0.05)
    put_status = admin.put(
        f"{API}/dispatch/schedules/{schedule_id}", json={"shift_status": "Late Clock Out"}, timeout=30
    )
    assert put_status.status_code == 200, put_status.text
    assert put_status.json()["shift_status"] == "Late Clock Out"
    assert put_status.json()["last_modified_action"] == "Late Clock Out"

    time.sleep(0.05)
    edited = admin.put(
        f"{API}/dispatch/schedules/{schedule_id}", json={"remarks": "TEST edited remarks"}, timeout=30
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["remarks"] == "TEST edited remarks"
    assert edited.json()["last_modified_action"] == "Edited"

    time.sleep(0.05)
    confirmed = admin.post(f"{API}/dispatch/schedules/{schedule_id}/confirm", json={
        "confirmation_status": "Confirmed", "confirmation_method": "Call", "remarks": "TEST confirmed"
    }, timeout=30)
    assert confirmed.status_code == 200, confirmed.text

    persisted = admin.get(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    assert persisted.status_code == 200
    assert persisted.json()["shift_status"] == "Late Clock Out"
    assert persisted.json()["confirmation_status"] == "Confirmed"
    assert persisted.json()["last_modified_action"] == "Confirmation: Confirmed"

    history = admin.get(f"{API}/dispatch/schedules/{schedule_id}/actions", timeout=30)
    assert history.status_code == 200, history.text
    entries = history.json()
    actions = [entry["action"] for entry in entries]
    for expected in ("Created", "Check-in", "Checkout", "Late Clock Out", "Edited", "Confirmation: Confirmed"):
        assert expected in actions
    by_action = {entry["action"]: entry for entry in entries}
    assert by_action["Check-in"]["old_value"] == "Not Started"
    assert by_action["Check-in"]["new_value"] == "Check-in"
    assert by_action["Checkout"]["old_value"] == "Check-in"
    assert by_action["Checkout"]["new_value"] == "Checkout"
    timestamps = [datetime.fromisoformat(entry["at"]) for entry in entries]
    assert timestamps == sorted(timestamps, reverse=True)
    for entry in entries:
        for field in ("actor_id", "actor_name", "actor_role", "action", "old_value", "new_value", "remarks", "at"):
            assert field in entry, f"{entry.get('action')} entry missing required field: {field}"
    newest = entries[0]
    assert newest["action"] == "Confirmation: Confirmed"
    assert newest["old_value"] == "Not Confirmed" and newest["new_value"] == "Confirmed"
    assert newest["remarks"] == "TEST confirmed"


# Invalid enum handling must not mutate persisted state or append history.
def test_invalid_status_returns_400_without_mutation(admin_context):
    admin = admin_context["admin"]
    schedule_id = admin_context["schedules"]["permission"]["id"]
    before = admin.get(f"{API}/dispatch/schedules/{schedule_id}/actions", timeout=30).json()
    response = admin.post(
        f"{API}/dispatch/schedules/{schedule_id}/status", json={"shift_status": "FooBar"}, timeout=30
    )
    assert response.status_code == 400, response.text
    assert "Shift status must be one of" in response.json()["detail"]
    persisted = admin.get(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    assert persisted.status_code == 200 and persisted.json()["shift_status"] == "Not Started"
    after = admin.get(f"{API}/dispatch/schedules/{schedule_id}/actions", timeout=30).json()
    assert len(after) == len(before)


# View-only employee may read history but may not record a status.
def test_view_only_employee_actions_rbac(admin_context):
    payload = admin_context["viewer_payload"]
    viewer, login = _login(payload["email"], admin_context["viewer_password"])
    assert login["permissions"] == ["dispatch.schedule.view"]
    schedule_id = admin_context["schedules"]["permission"]["id"]
    history = viewer.get(f"{API}/dispatch/schedules/{schedule_id}/actions", timeout=30)
    assert history.status_code == 200, history.text
    assert isinstance(history.json(), list) and history.json()
    forbidden = viewer.post(
        f"{API}/dispatch/schedules/{schedule_id}/status", json={"shift_status": "Absent"}, timeout=30
    )
    assert forbidden.status_code == 403, forbidden.text
    assert "dispatch.schedule.edit" in forbidden.json()["detail"]


# Cancellation and deletion actions are written to the audit collection.
def test_cancel_and_delete_are_logged(admin_context):
    admin = admin_context["admin"]
    cancel_id = admin_context["schedules"]["cancel"]["id"]
    cancelled = admin.post(f"{API}/dispatch/schedules/{cancel_id}/cancel", timeout=30)
    assert cancelled.status_code == 200, cancelled.text
    persisted = admin.get(f"{API}/dispatch/schedules/{cancel_id}", timeout=30)
    assert persisted.status_code == 200
    assert persisted.json()["shift_status"] == "Cancelled"
    assert persisted.json()["last_modified_action"] == "Cancelled"
    cancel_actions = admin.get(f"{API}/dispatch/schedules/{cancel_id}/actions", timeout=30).json()
    assert cancel_actions[0]["action"] == "Cancelled"
    assert cancel_actions[0]["old_value"] == "Not Started" and cancel_actions[0]["new_value"] == "Cancelled"

    delete_id = admin_context["schedules"]["delete"]["id"]
    deleted = admin.delete(f"{API}/dispatch/schedules/{delete_id}", timeout=30)
    assert deleted.status_code == 200, deleted.text
    missing = admin.get(f"{API}/dispatch/schedules/{delete_id}", timeout=30)
    assert missing.status_code == 404
    delete_actions = admin.get(f"{API}/dispatch/schedules/{delete_id}/actions", timeout=30)
    assert delete_actions.status_code == 200, delete_actions.text
    deleted_entry = delete_actions.json()[0]
    assert deleted_entry["action"] == "Deleted"
    assert deleted_entry["old_value"] == "Not Started"
    assert deleted_entry["new_value"] is None
    for field in ("actor_id", "actor_name", "actor_role", "action", "old_value", "new_value", "remarks", "at"):
        assert field in deleted_entry, f"Deleted history entry is missing required field: {field}"
