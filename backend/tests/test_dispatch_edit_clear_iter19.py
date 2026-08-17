"""Targeted regression for clearing Dispatch editable optional remarks."""
import os
import re
import uuid
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
        pytest.skip("Admin credentials missing from test_credentials.md")
    return email.group(1), password.group(1)


# Explicit null from the edit form must clear remarks and produce an accurate field diff.
def test_clear_remarks_persists_and_audits():
    email, password = _credentials()
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    login = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert login.status_code == 200, login.text

    tag = uuid.uuid4().hex[:10]
    created = {}

    def post(path, payload):
        response = session.post(f"{API}{path}", json=payload, timeout=30)
        assert response.status_code == 200, f"POST {path}: {response.status_code} {response.text}"
        return response.json()

    try:
        created["client"] = post("/dispatch/clients", {"code": f"TEST_CLR_C_{tag}", "name": f"TEST Clear Client {tag}"})
        created["vendor"] = post("/dispatch/vendors", {"code": f"TEST_CLR_V_{tag}", "name": f"TEST Clear Vendor {tag}"})
        created["officer"] = post("/dispatch/officers", {
            "officer_code": f"TEST_CLR_O_{tag}", "name": f"TEST Clear Officer {tag}",
            "vendor_id": created["vendor"]["id"], "status": "active",
        })
        created["post"] = post("/dispatch/post-sites", {
            "post_pin": f"TEST-CLR-{tag}", "name": f"TEST Clear Post {tag}",
            "client_id": created["client"]["id"], "vendor_id": created["vendor"]["id"],
        })
        created["schedule"] = post("/dispatch/schedules", {
            "client_id": created["client"]["id"], "vendor_id": created["vendor"]["id"],
            "officer_id": created["officer"]["id"], "post_site_id": created["post"]["id"],
            "date": "2039-02-10", "shift_type": "Morning", "start_time": "08:00",
            "end_time": "16:00", "remarks": f"TEST clear me {tag}",
        })
        sid = created["schedule"]["id"]

        update = session.put(f"{API}/dispatch/schedules/{sid}", json={"remarks": None}, timeout=30)
        assert update.status_code == 200, update.text
        persisted = session.get(f"{API}/dispatch/schedules/{sid}", timeout=30)
        assert persisted.status_code == 200, persisted.text
        history = session.get(f"{API}/dispatch/schedules/{sid}/actions", timeout=30)
        assert history.status_code == 200, history.text

        issues = []
        if update.json().get("remarks") is not None or persisted.json().get("remarks") is not None:
            issues.append("explicit null did not clear persisted remarks")
        latest = history.json()[0]
        if latest.get("action") != "Edited":
            issues.append(f"latest action was {latest.get('action')!r}, expected 'Edited'")
        if latest.get("old_value", {}).get("remarks") != f"TEST clear me {tag}":
            issues.append(f"audit old_value missing original remarks: {latest.get('old_value')!r}")
        if "remarks" not in latest.get("new_value", {}) or latest["new_value"]["remarks"] is not None:
            issues.append(f"audit new_value missing remarks:null: {latest.get('new_value')!r}")
        assert not issues, "; ".join(issues)

        # An empty payload changes no user-editable fields and must not emit a bogus Edited audit.
        action_count = len(history.json())
        no_op = session.put(f"{API}/dispatch/schedules/{sid}", json={}, timeout=30)
        assert no_op.status_code == 200, no_op.text
        assert no_op.json().get("remarks") is None
        after_no_op = session.get(f"{API}/dispatch/schedules/{sid}/actions", timeout=30)
        assert after_no_op.status_code == 200, after_no_op.text
        assert len(after_no_op.json()) == action_count, "empty PUT unexpectedly appended an audit action"
    finally:
        if created.get("schedule"):
            session.delete(f"{API}/dispatch/schedules/{created['schedule']['id']}", timeout=30)
        if created.get("post"):
            session.delete(f"{API}/dispatch/post-sites/{created['post']['id']}", timeout=30)
        if created.get("officer"):
            session.delete(f"{API}/dispatch/officers/{created['officer']['id']}", timeout=30)
        if created.get("vendor"):
            session.delete(f"{API}/dispatch/vendors/{created['vendor']['id']}", timeout=30)
        if created.get("client"):
            session.delete(f"{API}/dispatch/clients/{created['client']['id']}", timeout=30)
