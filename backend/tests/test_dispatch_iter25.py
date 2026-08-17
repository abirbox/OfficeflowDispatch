"""Iteration 25 tests for Dispatch entity detail, selected-column export, redaction, and status remarks."""
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
def entity_context():
    """Create isolated report records and a report-only employee, then clean them up."""
    email, password = _credentials()
    admin, actor = _login(email, password)
    assert actor["role"] == "super_admin"
    tag = uuid.uuid4().hex[:10]
    today = date.today()
    yesterday = today - timedelta(days=1)
    created = {"schedules": [], "posts": [], "officers": [], "vendors": [], "clients": [], "employees": []}

    def post(path, payload):
        response = admin.post(f"{API}{path}", json=payload, timeout=30)
        assert response.status_code == 200, f"POST {path}: {response.status_code} {response.text}"
        return response.json()

    client = post("/dispatch/clients", {"code": f"TEST_I25_C_{tag}", "name": f"TEST I25 Client {tag}"})
    created["clients"].append(client["id"])
    vendor = post("/dispatch/vendors", {"code": f"TEST_I25_V_{tag}", "name": f"TEST I25 Vendor {tag}"})
    created["vendors"].append(vendor["id"])
    officer = post("/dispatch/officers", {
        "officer_code": f"TEST_I25_O_{tag}", "name": f"TEST I25 Officer {tag}",
        "vendor_id": vendor["id"], "status": "active",
    })
    created["officers"].append(officer["id"])
    post_site = post("/dispatch/post-sites", {
        "post_pin": f"TEST-I25-{tag}", "name": f"TEST I25 Post {tag}",
        "client_id": client["id"], "vendor_id": vendor["id"], "required_officers": 1,
    })
    created["posts"].append(post_site["id"])

    common = {
        "client_id": client["id"], "vendor_id": vendor["id"], "post_site_id": post_site["id"],
        "officer_id": officer["id"], "shift_type": "Morning", "start_time": "08:00", "end_time": "16:00",
        "duty_rate": 20.0, "billing_rate": 35.0, "work_order_number": f"TEST-WO-I25-{tag}",
    }
    first = post("/dispatch/schedules", {**common, "date": yesterday.isoformat(), "remarks": "TEST base detail remark"})
    second = post("/dispatch/schedules", {**common, "date": today.isoformat(), "remarks": "TEST second detail remark"})
    created["schedules"].extend([first["id"], second["id"]])

    completed = admin.post(
        f"{API}/dispatch/schedules/{first['id']}/status",
        json={"shift_status": "Completed", "actual_check_in": "08:00", "actual_check_out": "16:00", "remarks": "TEST completed history"},
        timeout=30,
    )
    assert completed.status_code == 200, completed.text
    late = admin.post(
        f"{API}/dispatch/schedules/{second['id']}/status",
        json={"shift_status": "Late Clock In", "actual_check_in": "08:17", "remarks": "Traffic on Bridge Rd"},
        timeout=30,
    )
    assert late.status_code == 200, late.text

    employee_password = "TestEntity25@123"
    employee_payload = {
        "email": f"test_entity_i25_{tag}@example.com", "name": f"TEST Entity Reporter {tag}",
        "password": employee_password, "role": "employee",
        "permissions": ["dispatch.reports.view", "dispatch.reports.export"],
    }
    employee = post("/employees", employee_payload)
    created["employees"].append(employee["id"])
    reporter, reporter_login = _login(employee_payload["email"], employee_password)
    assert reporter_login["permissions"] == ["dispatch.reports.view", "dispatch.reports.export"]

    yield {
        "admin": admin, "actor": actor, "reporter": reporter, "tag": tag,
        "today": today.isoformat(), "yesterday": yesterday.isoformat(),
        "client": client, "vendor": vendor, "officer": officer, "post": post_site,
        "first": first, "second": second, "created": created,
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


def _params(context, entity_type="officer", entity_id=None):
    ids = {
        "officer": context["officer"]["id"], "client": context["client"]["id"],
        "vendor": context["vendor"]["id"], "post_site": context["post"]["id"],
    }
    return {
        "entity_type": entity_type, "entity_id": entity_id or ids[entity_type],
        "date_from": context["yesterday"], "date_to": context["today"],
    }


# Entity detail validates required query values and the shared 92-day report cap.
def test_entity_detail_validation(entity_context):
    admin = entity_context["admin"]
    invalid_type = admin.get(f"{API}/dispatch/reports/entity-detail", params={"entity_type": "office", "entity_id": "x"}, timeout=30)
    assert invalid_type.status_code == 400
    assert "entity_type must be" in invalid_type.json()["detail"]

    missing_id = admin.get(f"{API}/dispatch/reports/entity-detail", params={"entity_type": "officer"}, timeout=30)
    assert missing_id.status_code == 400
    assert missing_id.json()["detail"] == "entity_id is required"

    over_cap = admin.get(f"{API}/dispatch/reports/entity-detail", params={
        "entity_type": "officer", "entity_id": entity_context["officer"]["id"],
        "date_from": (date.today() - timedelta(days=93)).isoformat(), "date_to": date.today().isoformat(),
    }, timeout=30)
    assert over_cap.status_code == 400
    assert "exceed 3 months" in over_cap.json()["detail"]


# All supported entities return the documented response envelope and two day-by-day rows.
@pytest.mark.parametrize("entity_type", ["officer", "client", "vendor", "post_site"])
def test_entity_detail_contract_for_each_entity(entity_context, entity_type):
    response = entity_context["admin"].get(
        f"{API}/dispatch/reports/entity-detail", params=_params(entity_context, entity_type), timeout=30
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity_type"] == entity_type
    assert body["entity_id"] == _params(entity_context, entity_type)["entity_id"]
    assert isinstance(body["entity"], dict) and body["entity"]["id"] == body["entity_id"]
    assert body["date_from"] == entity_context["yesterday"]
    assert body["date_to"] == entity_context["today"]
    assert body["count"] == 2 == len(body["items"])
    assert [item["date"] for item in body["items"]] == [entity_context["yesterday"], entity_context["today"]]
    required = {
        "date", "shift_type", "start_time", "end_time", "actual_check_in", "actual_check_out",
        "duty_hours", "remarks", "shift_status", "confirmation_status",
    }
    for item in body["items"]:
        assert required <= item.keys()


# Summary counts and hours aggregate the matching schedules only.
def test_entity_detail_summary_aggregates(entity_context):
    response = entity_context["admin"].get(
        f"{API}/dispatch/reports/entity-detail", params=_params(entity_context), timeout=30
    )
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["total_shifts"] == 2
    assert summary["completed"] == 1
    assert summary["absent"] == 0
    assert summary["late"] == 1
    assert summary["total_hours"] == 16.0
    assert summary["billing_amount"] == 560.0
    assert summary["cost_amount"] == 320.0
    assert summary["margin"] == 240.0


# Privileged item rows include raw rates plus calculated billing/cost/margin values.
def test_entity_detail_admin_item_financial_fields_and_values(entity_context):
    response = entity_context["admin"].get(
        f"{API}/dispatch/reports/entity-detail", params=_params(entity_context), timeout=30
    )
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        assert item["duty_rate"] == 20.0
        assert item["billing_rate"] == 35.0
        assert item["work_order_number"] == f"TEST-WO-I25-{entity_context['tag']}"
        assert item["billing_amount"] == 280.0
        assert item["cost_amount"] == 160.0
        assert item["margin"] == 120.0


# Report-only users receive neither item nor summary financial values.
def test_entity_detail_financial_redaction_without_permission(entity_context):
    response = entity_context["reporter"].get(
        f"{API}/dispatch/reports/entity-detail", params=_params(entity_context), timeout=30
    )
    assert response.status_code == 200, response.text
    forbidden = {"billing_amount", "cost_amount", "margin", "duty_rate", "billing_rate", "work_order_number"}
    assert forbidden.isdisjoint(response.json()["summary"])
    for item in response.json()["items"]:
        assert forbidden.isdisjoint(item)


# Selected-column CSV has exactly the selected public labels in requested spec order.
def test_entity_detail_selected_columns_csv(entity_context):
    response = entity_context["admin"].get(f"{API}/dispatch/reports/export/entity-detail", params={
        **_params(entity_context), "format": "csv", "columns": "date,officer_name,duty_hours",
    }, timeout=30)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["Date", "Officer", "Hours"]
    assert len(rows) == 3
    assert all(len(row) == 3 for row in rows)



# Duplicate and unknown selected keys are ignored without disturbing first-seen caller order.
def test_entity_detail_selected_columns_csv_dedupes_and_drops_unknowns(entity_context):
    response = entity_context["admin"].get(f"{API}/dispatch/reports/export/entity-detail", params={
        **_params(entity_context), "format": "csv", "columns": "officer_name,date,officer_name,foo",
    }, timeout=30)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["Officer", "Date"]
    assert len(rows) == 3
    assert all(len(row) == 2 for row in rows)


# PDF entity export is a non-empty valid PDF document.
def test_entity_detail_pdf_export(entity_context):
    response = entity_context["admin"].get(f"{API}/dispatch/reports/export/entity-detail", params={
        **_params(entity_context), "format": "pdf", "columns": "date,officer_name,duty_hours",
    }, timeout=30)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 500


# Redacted users cannot force financial columns into selected-column exports.
def test_entity_detail_export_financial_columns_redacted(entity_context):
    response = entity_context["reporter"].get(f"{API}/dispatch/reports/export/entity-detail", params={
        **_params(entity_context), "format": "csv",
        "columns": "date,duty_rate,billing_rate,work_order_number,officer_name",
    }, timeout=30)
    assert response.status_code == 200, response.text
    header = next(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert header == ["Date", "Officer"]


# Status endpoint preserves an optional remark in unified full history and updates actor metadata.
def test_status_remark_is_persisted_to_full_history(entity_context):
    admin = entity_context["admin"]
    schedule_id = entity_context["second"]["id"]
    persisted = admin.get(f"{API}/dispatch/schedules/{schedule_id}", timeout=30)
    assert persisted.status_code == 200
    assert persisted.json()["shift_status"] == "Late Clock In"
    assert persisted.json()["last_modified_by_name"] == entity_context["actor"]["name"]

    history = admin.get(f"{API}/dispatch/schedules/{schedule_id}/actions", timeout=30)
    assert history.status_code == 200, history.text
    entry = next(item for item in history.json() if item["action"] == "Late Clock In")
    assert entry["remarks"] == "Traffic on Bridge Rd"
    assert entry["actor_id"] == entity_context["actor"]["id"]
