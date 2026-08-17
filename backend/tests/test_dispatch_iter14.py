"""Dispatch Management System API, RBAC, filtering, confirmation, and dashboard tests."""
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
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"


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


def _new_session(email, password):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(
        f"{API}/auth/login", json={"email": email, "password": password}, timeout=30
    )
    if response.status_code != 200:
        pytest.fail(f"Authentication failed for {email}: {response.status_code} {response.text[:500]}")
    return session, response.json()


@pytest.fixture(scope="module")
def admin_session():
    email, password = _credentials()
    session, login_data = _new_session(email, password)
    assert login_data["email"] == email
    assert login_data["role"] == "super_admin"
    assert "permissions" in login_data
    assert isinstance(login_data["permissions"], list)
    return session


@pytest.fixture(scope="module")
def dispatch_data(admin_session):
    """Create isolated Dispatch reference data and schedules, then deactivate/delete them."""
    tag = uuid.uuid4().hex[:10]
    created = {"employees": [], "schedules": [], "clients": [], "vendors": [], "officers": [], "posts": []}

    client_payload = {
        "code": f"TEST_C_{tag}",
        "name": f"TEST_Dispatch_Client_{tag}",
        "email": f"client_{tag}@example.com",
        "status": "active",
    }
    response = admin_session.post(f"{API}/dispatch/clients", json=client_payload, timeout=30)
    assert response.status_code == 200, response.text
    client = response.json()
    assert client["name"] == client_payload["name"]
    created["clients"].append(client["id"])

    vendor_payload = {
        "code": f"TEST_V_{tag}",
        "name": f"TEST_Dispatch_Vendor_{tag}",
        "status": "active",
    }
    response = admin_session.post(f"{API}/dispatch/vendors", json=vendor_payload, timeout=30)
    assert response.status_code == 200, response.text
    vendor = response.json()
    assert vendor["name"] == vendor_payload["name"]
    created["vendors"].append(vendor["id"])

    officer_payload = {
        "officer_code": f"TEST_O_{tag}",
        "name": f"TEST_Officer_{tag}",
        "vendor_id": vendor["id"],
        "status": "active",
    }
    response = admin_session.post(f"{API}/dispatch/officers", json=officer_payload, timeout=30)
    assert response.status_code == 200, response.text
    officer = response.json()
    assert officer["vendor_id"] == vendor["id"]
    created["officers"].append(officer["id"])

    post_payload = {
        "post_pin": f"QA-{tag}",
        "name": f"TEST_Post_{tag}",
        "client_id": client["id"],
        "vendor_id": vendor["id"],
        "required_officers": 2,
        "status": "active",
    }
    response = admin_session.post(f"{API}/dispatch/post-sites", json=post_payload, timeout=30)
    assert response.status_code == 200, response.text
    post = response.json()
    assert post["post_pin"] == post_payload["post_pin"]
    created["posts"].append(post["id"])

    common = {
        "client_id": client["id"],
        "vendor_id": vendor["id"],
        "post_site_id": post["id"],
        "officer_id": officer["id"],
    }
    day_payload = {
        **common,
        "date": "2036-07-10",
        "shift_type": "Morning",
        "start_time": "08:00",
        "end_time": "16:00",
        "duty_rate": 21.5,
        "billing_rate": 34.75,
        "work_order_number": f"TEST_WO_{tag}",
        "remarks": f"TEST_day_{tag}",
    }
    response = admin_session.post(f"{API}/dispatch/schedules", json=day_payload, timeout=30)
    assert response.status_code == 200, response.text
    day_schedule = response.json()
    created["schedules"].append(day_schedule["id"])

    overnight_payload = {
        **common,
        "date": "2036-07-11",
        "shift_type": "Night",
        "start_time": "22:00",
        "end_time": "06:00",
        "remarks": f"TEST_overnight_{tag}",
    }
    response = admin_session.post(f"{API}/dispatch/schedules", json=overnight_payload, timeout=30)
    assert response.status_code == 200, response.text
    overnight_schedule = response.json()
    created["schedules"].append(overnight_schedule["id"])

    data = {
        "tag": tag,
        "client": client,
        "vendor": vendor,
        "officer": officer,
        "post": post,
        "day": day_schedule,
        "overnight": overnight_schedule,
        "common": common,
        "created": created,
    }
    yield data

    for schedule_id in created["schedules"]:
        admin_session.delete(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    for post_id in created["posts"]:
        admin_session.delete(f"{API}/dispatch/post-sites/{post_id}", timeout=30)
    for officer_id in created["officers"]:
        admin_session.delete(f"{API}/dispatch/officers/{officer_id}", timeout=30)
    for vendor_id in created["vendors"]:
        admin_session.delete(f"{API}/dispatch/vendors/{vendor_id}", timeout=30)
    for client_id in created["clients"]:
        admin_session.delete(f"{API}/dispatch/clients/{client_id}", timeout=30)
    for employee_id in created["employees"]:
        admin_session.delete(f"{API}/employees/{employee_id}", timeout=30)


def _create_employee(admin_session, dispatch_data, role="employee", permissions=None):
    tag = uuid.uuid4().hex[:10]
    password = "TestDispatch@123"
    payload = {
        "email": f"test_dispatch_{role}_{tag}@example.com",
        "name": f"TEST Dispatch {role} {tag}",
        "password": password,
        "role": role,
        "permissions": permissions or [],
    }
    response = admin_session.post(f"{API}/employees", json=payload, timeout=30)
    assert response.status_code == 200, response.text
    employee = response.json()
    dispatch_data["created"]["employees"].append(employee["id"])
    return employee, payload, password


# Authentication and permission registry.
def test_health_and_admin_login_permissions(admin_session):
    response = requests.get(f"{API}/health", timeout=30)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    me = admin_session.get(f"{API}/auth/me", timeout=30)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["role"] == "super_admin"
    assert "permissions" in body and isinstance(body["permissions"], list)


def test_permission_registry_requires_auth_and_returns_codes(admin_session):
    unauthenticated = requests.get(f"{API}/dispatch/permissions/registry", timeout=30)
    assert unauthenticated.status_code == 401
    response = admin_session.get(f"{API}/dispatch/permissions/registry", timeout=30)
    assert response.status_code == 200, response.text
    permissions = response.json()["permissions"]
    assert isinstance(permissions, list)
    for required in (
        "dispatch.dashboard.view",
        "dispatch.schedule.view",
        "dispatch.schedule.create",
        "dispatch.clients.create",
        "dispatch.financial.view",
        "dispatch.confirmation.manage",
    ):
        assert required in permissions


# Client and vendor CRUD with persistence and soft-delete verification.
def test_client_crud_soft_delete(admin_session):
    tag = uuid.uuid4().hex[:8]
    payload = {"code": f"TEST_CRUD_C_{tag}", "name": f"TEST Client CRUD {tag}"}
    create = admin_session.post(f"{API}/dispatch/clients", json=payload, timeout=30)
    assert create.status_code == 200, create.text
    client = create.json()
    client_id = client["id"]
    assert client["name"] == payload["name"] and client["status"] == "active"
    listed = admin_session.get(f"{API}/dispatch/clients", params={"search": tag}, timeout=30)
    assert listed.status_code == 200
    assert any(item["id"] == client_id for item in listed.json())
    update = admin_session.put(
        f"{API}/dispatch/clients/{client_id}", json={"name": f"TEST Client Updated {tag}"}, timeout=30
    )
    assert update.status_code == 200
    assert update.json()["name"] == f"TEST Client Updated {tag}"
    persisted = admin_session.get(f"{API}/dispatch/clients/{client_id}", timeout=30)
    assert persisted.status_code == 200
    assert persisted.json()["name"] == f"TEST Client Updated {tag}"
    deleted = admin_session.delete(f"{API}/dispatch/clients/{client_id}", timeout=30)
    assert deleted.status_code == 200
    after = admin_session.get(f"{API}/dispatch/clients/{client_id}", timeout=30)
    assert after.status_code == 200
    assert after.json()["status"] == "inactive"


def test_vendor_crud_soft_delete(admin_session):
    tag = uuid.uuid4().hex[:8]
    payload = {"code": f"TEST_CRUD_V_{tag}", "name": f"TEST Vendor CRUD {tag}"}
    create = admin_session.post(f"{API}/dispatch/vendors", json=payload, timeout=30)
    assert create.status_code == 200, create.text
    vendor = create.json()
    vendor_id = vendor["id"]
    listed = admin_session.get(f"{API}/dispatch/vendors", params={"search": tag}, timeout=30)
    assert listed.status_code == 200
    assert any(item["id"] == vendor_id for item in listed.json())
    updated_name = f"TEST Vendor Updated {tag}"
    update = admin_session.put(f"{API}/dispatch/vendors/{vendor_id}", json={"name": updated_name}, timeout=30)
    assert update.status_code == 200 and update.json()["name"] == updated_name
    persisted = admin_session.get(f"{API}/dispatch/vendors/{vendor_id}", timeout=30)
    assert persisted.status_code == 200 and persisted.json()["name"] == updated_name
    deleted = admin_session.delete(f"{API}/dispatch/vendors/{vendor_id}", timeout=30)
    assert deleted.status_code == 200
    after = admin_session.get(f"{API}/dispatch/vendors/{vendor_id}", timeout=30)
    assert after.status_code == 200 and after.json()["status"] == "inactive"


# Security officer status validation and persistence.
def test_officer_status_transitions_and_invalid_status(admin_session, dispatch_data):
    officer_id = dispatch_data["officer"]["id"]
    for status in ("inactive", "suspended", "terminated", "on_leave", "active"):
        response = admin_session.put(
            f"{API}/dispatch/officers/{officer_id}", json={"status": status}, timeout=30
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status
        persisted = admin_session.get(f"{API}/dispatch/officers/{officer_id}", timeout=30)
        assert persisted.status_code == 200 and persisted.json()["status"] == status
    invalid = admin_session.put(
        f"{API}/dispatch/officers/{officer_id}", json={"status": "vacation"}, timeout=30
    )
    assert invalid.status_code == 400
    assert "Invalid officer status" in invalid.json()["detail"]


def test_create_officer_invalid_status_is_400(admin_session, dispatch_data):
    response = admin_session.post(
        f"{API}/dispatch/officers",
        json={
            "name": f"TEST Invalid Officer {dispatch_data['tag']}",
            "vendor_id": dispatch_data["vendor"]["id"],
            "status": "invalid",
        },
        timeout=30,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid officer status"


# Post-site uniqueness enforcement.
def test_post_pin_duplicate_is_rejected(admin_session, dispatch_data):
    payload = {
        "post_pin": dispatch_data["post"]["post_pin"],
        "name": "TEST Duplicate PIN",
        "client_id": dispatch_data["client"]["id"],
        "vendor_id": dispatch_data["vendor"]["id"],
    }
    response = admin_session.post(f"{API}/dispatch/post-sites", json=payload, timeout=30)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


# Duty-hour calculation, conflict detection, filters, and pagination.
def test_schedule_duty_hours_are_backend_computed(admin_session, dispatch_data):
    day = admin_session.get(f"{API}/dispatch/schedules/{dispatch_data['day']['id']}", timeout=30)
    overnight = admin_session.get(
        f"{API}/dispatch/schedules/{dispatch_data['overnight']['id']}", timeout=30
    )
    assert day.status_code == 200 and overnight.status_code == 200
    assert day.json()["duty_hours"] == 8.0
    assert overnight.json()["duty_hours"] == 8.0
    assert day.json()["shift_status"] == "Not Started"
    assert day.json()["confirmation_status"] == "Not Confirmed"


def test_officer_overlapping_schedule_conflict_409(admin_session, dispatch_data):
    payload = {
        **dispatch_data["common"],
        "date": "2036-07-10",
        "shift_type": "Afternoon",
        "start_time": "15:30",
        "end_time": "18:00",
    }
    response = admin_session.post(f"{API}/dispatch/schedules", json=payload, timeout=30)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "already has another shift" in detail
    assert "08:00" in detail and "16:00" in detail


@pytest.mark.parametrize(
    "field,value_key",
    [
        ("officer_id", "officer"),
        ("vendor_id", "vendor"),
        ("client_id", "client"),
        ("post_site_id", "post"),
    ],
)
def test_schedule_id_filters(admin_session, dispatch_data, field, value_key):
    value = dispatch_data[value_key]["id"]
    response = admin_session.get(f"{API}/dispatch/schedules", params={field: value}, timeout=30)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 2
    assert body["items"] and all(item[field] == value for item in body["items"])


def test_schedule_post_pin_regex_filter(admin_session, dispatch_data):
    fragment = dispatch_data["post"]["post_pin"].lower()[3:9]
    response = admin_session.get(
        f"{API}/dispatch/schedules", params={"post_pin": fragment}, timeout=30
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 2
    assert all(fragment.lower() in item["post_pin"].lower() for item in body["items"])


def test_schedule_enum_date_and_combined_filters(admin_session, dispatch_data):
    filters = [
        {"shift_type": "Night"},
        {"confirmation_status": "Not Confirmed"},
        {"shift_status": "Not Started"},
        {"date_from": "2036-07-11", "date_to": "2036-07-11"},
    ]
    for params in filters:
        response = admin_session.get(f"{API}/dispatch/schedules", params=params, timeout=30)
        assert response.status_code == 200, response.text
        assert response.json()["items"], f"No rows for filter {params}"
    combined = {
        "officer_id": dispatch_data["officer"]["id"],
        "vendor_id": dispatch_data["vendor"]["id"],
        "client_id": dispatch_data["client"]["id"],
        "post_site_id": dispatch_data["post"]["id"],
        "post_pin": dispatch_data["post"]["post_pin"].lower(),
        "shift_type": "Night",
        "confirmation_status": "Not Confirmed",
        "shift_status": "Not Started",
        "date_from": "2036-07-11",
        "date_to": "2036-07-11",
    }
    response = admin_session.get(f"{API}/dispatch/schedules", params=combined, timeout=30)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == dispatch_data["overnight"]["id"]


def test_schedule_pagination_contract(admin_session, dispatch_data):
    response = admin_session.get(
        f"{API}/dispatch/schedules", params={"page": 1, "limit": 50}, timeout=30
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(("items", "total", "page", "limit")).issubset(body)
    assert body["page"] == 1 and body["limit"] == 50
    assert isinstance(body["items"], list) and isinstance(body["total"], int)
    assert len(body["items"]) <= 50


# Confirmation mutation and reverse-chronological history.
def test_confirmation_updates_schedule_and_history(admin_session, dispatch_data):
    schedule_id = dispatch_data["day"]["id"]
    first = admin_session.post(
        f"{API}/dispatch/schedules/{schedule_id}/confirm",
        json={"confirmation_status": "Pending", "confirmation_method": "Text", "remarks": "TEST first"},
        timeout=30,
    )
    assert first.status_code == 200, first.text
    time.sleep(0.05)
    second = admin_session.post(
        f"{API}/dispatch/schedules/{schedule_id}/confirm",
        json={"confirmation_status": "Confirmed", "confirmation_method": "Call", "remarks": "TEST second"},
        timeout=30,
    )
    assert second.status_code == 200, second.text
    schedule = admin_session.get(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    assert schedule.status_code == 200
    assert schedule.json()["confirmation_status"] == "Confirmed"
    assert schedule.json()["confirmation_method"] == "Call"
    history = admin_session.get(f"{API}/dispatch/schedules/{schedule_id}/history", timeout=30)
    assert history.status_code == 200, history.text
    entries = history.json()
    assert len(entries) >= 2
    assert entries[0]["status"] == "Confirmed" and entries[0]["remarks"] == "TEST second"
    assert entries[1]["status"] == "Pending" and entries[1]["remarks"] == "TEST first"
    timestamps = [datetime.fromisoformat(entry["contacted_at"]) for entry in entries]
    assert timestamps == sorted(timestamps, reverse=True)


# Explicit permission denial, financial redaction, and HD bypass.
def test_employee_without_permissions_gets_403(admin_session, dispatch_data):
    _, payload, password = _create_employee(admin_session, dispatch_data, permissions=[])
    session, login = _new_session(payload["email"], password)
    assert login["permissions"] == []
    clients = session.get(f"{API}/dispatch/clients", timeout=30)
    schedules = session.get(f"{API}/dispatch/schedules", timeout=30)
    assert clients.status_code == 403
    assert "dispatch.clients.view" in clients.json()["detail"]
    assert schedules.status_code == 403
    assert "dispatch.schedule.view" in schedules.json()["detail"]


def test_employee_financial_fields_are_protected(admin_session, dispatch_data):
    permissions = ["dispatch.schedule.view", "dispatch.schedule.create"]
    _, payload, password = _create_employee(admin_session, dispatch_data, permissions=permissions)
    session, login = _new_session(payload["email"], password)
    assert login["permissions"] == permissions

    listing = session.get(
        f"{API}/dispatch/schedules",
        params={"officer_id": dispatch_data["officer"]["id"]},
        timeout=30,
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert items
    for item in items:
        assert "duty_rate" not in item
        assert "billing_rate" not in item
        assert "work_order_number" not in item

    forbidden_payload = {
        **dispatch_data["common"],
        "date": "2036-07-12",
        "shift_type": "Morning",
        "start_time": "08:00",
        "end_time": "16:00",
        "duty_rate": 10.0,
    }
    forbidden = session.post(f"{API}/dispatch/schedules", json=forbidden_payload, timeout=30)
    assert forbidden.status_code == 403
    assert "financial fields" in forbidden.json()["detail"]

    allowed_payload = dict(forbidden_payload)
    allowed_payload.pop("duty_rate")
    allowed_payload["remarks"] = "TEST non-financial create"
    allowed = session.post(f"{API}/dispatch/schedules", json=allowed_payload, timeout=30)
    assert allowed.status_code == 200, allowed.text
    created = allowed.json()
    dispatch_data["created"]["schedules"].append(created["id"])
    assert "duty_rate" not in created
    persisted = session.get(f"{API}/dispatch/schedules/{created['id']}", timeout=30)
    assert persisted.status_code == 200
    assert "duty_rate" not in persisted.json()


def test_create_employee_response_returns_supplied_permissions(admin_session, dispatch_data):
    expected = ["dispatch.schedule.view", "dispatch.clients.view"]
    employee, _, _ = _create_employee(admin_session, dispatch_data, permissions=expected)
    assert employee["permissions"] == expected


def test_hd_role_bypasses_dispatch_permissions(admin_session, dispatch_data):
    _, payload, password = _create_employee(admin_session, dispatch_data, role="hd", permissions=[])
    session, login = _new_session(payload["email"], password)
    assert login["role"] == "hd" and login["permissions"] == []
    endpoints = (
        "/dispatch/clients",
        "/dispatch/vendors",
        "/dispatch/officers",
        "/dispatch/post-sites",
        "/dispatch/schedules",
        "/dispatch/dashboard/stats",
        f"/dispatch/schedules/{dispatch_data['day']['id']}/history",
    )
    for endpoint in endpoints:
        response = session.get(f"{API}{endpoint}", timeout=30)
        assert response.status_code == 200, f"HD GET {endpoint}: {response.status_code} {response.text}"

    tag = uuid.uuid4().hex[:8]
    create = session.post(
        f"{API}/dispatch/clients", json={"name": f"TEST HD Client {tag}"}, timeout=30
    )
    assert create.status_code == 200, create.text
    client_id = create.json()["id"]
    dispatch_data["created"]["clients"].append(client_id)
    delete = session.delete(f"{API}/dispatch/clients/{client_id}", timeout=30)
    assert delete.status_code == 200, delete.text


# Dashboard aggregate response contract.
def test_dashboard_stats_contract(admin_session, dispatch_data):
    response = admin_session.get(f"{API}/dispatch/dashboard/stats", timeout=30)
    assert response.status_code == 200, response.text
    body = response.json()
    expected = {
        "today_total",
        "confirmed",
        "pending",
        "no_response",
        "declined",
        "late",
        "absent",
        "clients",
        "vendors",
        "officers",
        "post_sites",
        "open_positions",
    }
    assert expected.issubset(body)
    assert all(isinstance(body[key], int) and body[key] >= 0 for key in expected)


# Existing OfficeFlow API smoke regression using the current documented admin account.
def test_existing_officeflow_core_endpoints_smoke(admin_session):
    checks = {
        "/companies": list,
        "/employees": list,
        "/tasks": list,
        "/attendance/today": dict,
        "/reports/summary": dict,
    }
    report_params = {"month": 8, "year": 2026}
    for endpoint, expected_type in checks.items():
        params = report_params if endpoint == "/reports/summary" else None
        response = admin_session.get(f"{API}{endpoint}", params=params, timeout=30)
        assert response.status_code == 200, f"GET {endpoint}: {response.status_code} {response.text}"
        assert isinstance(response.json(), expected_type)
