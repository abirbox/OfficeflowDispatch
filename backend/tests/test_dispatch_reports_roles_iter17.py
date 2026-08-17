"""Dispatch reports, export RBAC/redaction, and privileged role assignment tests."""
import csv
import io
import os
import re
import uuid
from datetime import date, timedelta
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
def admin_session():
    email, password = _credentials()
    session, user = _login(email, password)
    assert user["email"] == email
    assert user["role"] == "super_admin"
    return session


@pytest.fixture(scope="module")
def report_context(admin_session):
    """Create one isolated current-date schedule and test users, then clean up."""
    tag = uuid.uuid4().hex[:10]
    today = date.today().isoformat()
    password = "TestReports@123"
    created = {"schedules": [], "posts": [], "officers": [], "vendors": [], "clients": [], "employees": []}

    def post(path, payload):
        response = admin_session.post(f"{API}{path}", json=payload, timeout=30)
        assert response.status_code == 200, f"POST {path}: {response.status_code} {response.text}"
        return response.json()

    client = post("/dispatch/clients", {"code": f"TEST_RC_{tag}", "name": f"TEST Report Client {tag}"})
    created["clients"].append(client["id"])
    vendor = post("/dispatch/vendors", {"code": f"TEST_RV_{tag}", "name": f"TEST Report Vendor {tag}"})
    created["vendors"].append(vendor["id"])
    officer = post("/dispatch/officers", {
        "officer_code": f"TEST_RO_{tag}", "name": f"TEST Report Officer {tag}",
        "vendor_id": vendor["id"], "status": "active",
    })
    created["officers"].append(officer["id"])
    post_site = post("/dispatch/post-sites", {
        "post_pin": f"TEST-RP-{tag}", "name": f"TEST Report Post {tag}",
        "client_id": client["id"], "vendor_id": vendor["id"], "required_officers": 1,
    })
    created["posts"].append(post_site["id"])
    schedule = post("/dispatch/schedules", {
        "client_id": client["id"], "vendor_id": vendor["id"], "post_site_id": post_site["id"],
        "officer_id": officer["id"], "date": today, "shift_type": "Morning",
        "start_time": "08:00", "end_time": "16:00", "duty_rate": 20.0,
        "billing_rate": 35.0, "work_order_number": f"TEST-WO-{tag}",
    })
    created["schedules"].append(schedule["id"])
    update = admin_session.put(
        f"{API}/dispatch/schedules/{schedule['id']}", json={"shift_status": "Completed"}, timeout=30
    )
    assert update.status_code == 200, update.text
    assert update.json()["shift_status"] == "Completed"

    def create_employee(role, permissions, label):
        payload = {
            "email": f"test_reports_{label}_{tag}@example.com", "name": f"TEST Reports {label} {tag}",
            "password": password, "role": role, "permissions": permissions,
        }
        employee = post("/employees", payload)
        created["employees"].append(employee["id"])
        return employee, payload

    no_perm, no_perm_payload = create_employee("employee", [], "none")
    reporter, reporter_payload = create_employee(
        "employee", ["dispatch.reports.view", "dispatch.reports.export"], "redacted"
    )

    context = {
        "tag": tag, "today": today, "password": password, "created": created,
        "client": client, "vendor": vendor, "officer": officer, "post": post_site,
        "schedule": schedule, "no_perm": no_perm, "no_perm_payload": no_perm_payload,
        "reporter": reporter, "reporter_payload": reporter_payload,
    }
    yield context

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


# Report endpoint contracts, authorization, aggregation, and date validation.
@pytest.mark.parametrize("endpoint", [
    "/dispatch/reports/schedules", "/dispatch/reports/by-officer",
    "/dispatch/reports/by-post-site", "/dispatch/reports/by-client", "/dispatch/reports/by-vendor",
])
def test_all_report_endpoints_return_valid_contract(admin_session, report_context, endpoint):
    response = admin_session.get(
        f"{API}{endpoint}", params={"date_from": report_context["today"], "date_to": report_context["today"]}, timeout=30
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date_from"] == report_context["today"]
    assert body["date_to"] == report_context["today"]
    assert isinstance(body["items"], list)
    assert body["count"] == len(body["items"])


def test_reports_require_view_and_export_permissions(admin_session, report_context):
    session, login = _login(report_context["no_perm_payload"]["email"], report_context["password"])
    assert login["permissions"] == []
    paths = [
        "/dispatch/reports/schedules", "/dispatch/reports/by-officer", "/dispatch/reports/by-post-site",
        "/dispatch/reports/by-client", "/dispatch/reports/by-vendor",
    ]
    for path in paths:
        response = session.get(f"{API}{path}", timeout=30)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"
        assert "dispatch.reports.view" in response.json()["detail"]
    export = session.get(f"{API}/dispatch/reports/export", params={"type": "by-officer", "format": "csv"}, timeout=30)
    assert export.status_code == 403
    assert "dispatch.reports.export" in export.json()["detail"]


def test_export_permission_is_separate_from_view(admin_session, report_context):
    tag = report_context["tag"]
    payload = {
        "email": f"test_reports_viewonly_{tag}@example.com", "name": f"TEST Reports View Only {tag}",
        "password": report_context["password"], "role": "employee", "permissions": ["dispatch.reports.view"],
    }
    create = admin_session.post(f"{API}/employees", json=payload, timeout=30)
    assert create.status_code == 200, create.text
    report_context["created"]["employees"].append(create.json()["id"])
    session, _ = _login(payload["email"], payload["password"])
    view = session.get(f"{API}/dispatch/reports/by-officer", timeout=30)
    export = session.get(f"{API}/dispatch/reports/export", params={"type": "by-officer", "format": "csv"}, timeout=30)
    assert view.status_code == 200, view.text
    assert export.status_code == 403
    assert "dispatch.reports.export" in export.json()["detail"]


def test_report_date_range_over_92_days_is_rejected(admin_session):
    date_from = date.today() - timedelta(days=93)
    response = admin_session.get(
        f"{API}/dispatch/reports/by-officer",
        params={"date_from": date_from.isoformat(), "date_to": date.today().isoformat()}, timeout=30,
    )
    assert response.status_code == 400, response.text
    assert "exceed 3 months" in response.json()["detail"]


def test_by_officer_financial_aggregation_is_correct_for_super_admin(admin_session, report_context):
    response = admin_session.get(
        f"{API}/dispatch/reports/by-officer",
        params={"date_from": report_context["today"], "date_to": report_context["today"]}, timeout=30,
    )
    assert response.status_code == 200, response.text
    row = next(item for item in response.json()["items"] if item["officer_id"] == report_context["officer"]["id"])
    assert row["officer_name"] == report_context["officer"]["name"]
    assert row["total_shifts"] == 1
    assert row["completed"] == 1
    assert row["total_hours"] == 8.0
    assert row["billing_amount"] == 280.0
    assert row["cost_amount"] == 160.0
    assert row["margin"] == 120.0


def test_financial_fields_and_csv_columns_are_redacted_without_financial_permission(report_context):
    session, login = _login(report_context["reporter_payload"]["email"], report_context["password"])
    assert login["permissions"] == ["dispatch.reports.view", "dispatch.reports.export"]
    params = {"date_from": report_context["today"], "date_to": report_context["today"]}
    response = session.get(f"{API}/dispatch/reports/by-officer", params=params, timeout=30)
    assert response.status_code == 200, response.text
    row = next(item for item in response.json()["items"] if item["officer_id"] == report_context["officer"]["id"])
    assert "billing_amount" not in row
    assert "cost_amount" not in row
    assert "margin" not in row

    export = session.get(
        f"{API}/dispatch/reports/export", params={**params, "type": "by-officer", "format": "csv"}, timeout=30
    )
    assert export.status_code == 200, export.text
    header = next(csv.reader(io.StringIO(export.content.decode("utf-8"))))
    assert "Billing" not in header
    assert "Cost" not in header
    assert "Margin" not in header


# CSV and PDF export content and media contracts.
def test_csv_export_has_expected_header_and_content_type(admin_session, report_context):
    response = admin_session.get(
        f"{API}/dispatch/reports/export",
        params={"type": "by-officer", "format": "csv", "date_from": report_context["today"], "date_to": report_context["today"]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith(b"Officer,Shifts,Completed,")
    assert report_context["officer"]["name"].encode() in response.content


def test_pdf_export_is_non_empty_valid_pdf(admin_session, report_context):
    response = admin_session.get(
        f"{API}/dispatch/reports/export",
        params={"type": "by-officer", "format": "pdf", "date_from": report_context["today"], "date_to": report_context["today"]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 500


# Privileged role creation/update restrictions and super-admin allowance.
def test_privileged_role_assignment_restrictions_and_super_admin_allowance(admin_session, report_context):
    tag = report_context["tag"]
    password = report_context["password"]

    def admin_create(label, role):
        payload = {
            "email": f"test_role_{label}_{tag}@example.com", "name": f"TEST Role {label} {tag}",
            "password": password, "role": role, "permissions": [],
        }
        response = admin_session.post(f"{API}/employees", json=payload, timeout=30)
        assert response.status_code == 200, response.text
        employee = response.json()
        assert employee["role"] == role
        report_context["created"]["employees"].append(employee["id"])
        return employee, payload

    hd, _ = admin_create("hd", "hd")
    super_admin, _ = admin_create("superadmin", "super_admin")
    hr, hr_payload = admin_create("hr", "hr")
    target, _ = admin_create("target", "employee")

    # Super admin can update an HD account normally.
    update_hd = admin_session.put(f"{API}/employees/{hd['id']}", json={"name": f"TEST Updated HD {tag}"}, timeout=30)
    assert update_hd.status_code == 200, update_hd.text
    assert update_hd.json()["name"] == f"TEST Updated HD {tag}"
    persisted_hd = admin_session.get(f"{API}/employees/{hd['id']}", timeout=30)
    assert persisted_hd.status_code == 200
    assert persisted_hd.json()["name"] == f"TEST Updated HD {tag}"

    hr_session, hr_login = _login(hr_payload["email"], password)
    assert hr_login["role"] == "hr"

    create_hd = hr_session.post(f"{API}/employees", json={
        "email": f"test_role_forbidden_hd_{tag}@example.com", "name": f"TEST Forbidden HD {tag}",
        "password": password, "role": "hd", "permissions": [],
    }, timeout=30)
    assert create_hd.status_code == 403, create_hd.text
    assert "Only Super Admin can assign the 'hd' role" in create_hd.json()["detail"]

    promote = hr_session.put(f"{API}/employees/{target['id']}", json={"role": "hd"}, timeout=30)
    assert promote.status_code == 403, promote.text
    assert "Only Super Admin can assign the 'hd' role" in promote.json()["detail"]
    target_after = admin_session.get(f"{API}/employees/{target['id']}", timeout=30)
    assert target_after.status_code == 200
    assert target_after.json()["role"] == "employee"

    edit_hd = hr_session.put(f"{API}/employees/{hd['id']}", json={"name": "TEST Forbidden Edit"}, timeout=30)
    assert edit_hd.status_code == 403, edit_hd.text
    assert "Only Super Admin can modify a privileged account" in edit_hd.json()["detail"]

    edit_super = hr_session.put(f"{API}/employees/{super_admin['id']}", json={"name": "TEST Forbidden Edit"}, timeout=30)
    assert edit_super.status_code == 403, edit_super.text
    assert "Only Super Admin can modify a privileged account" in edit_super.json()["detail"]
