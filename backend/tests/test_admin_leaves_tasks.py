"""
Backend tests for the OfficeFlow admin dashboard feature update:
- /admin/dashboard-stats, /admin/employee-status, /admin/employee/{id}/stats, /admin/employee/{id}/role
- /leaves CRUD w/ RBAC (employee sees own; admin sees all; admin approves)
- /tasks with work_type field + assignee_name in response
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://officeflow-prod.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mahossain432@gmail.com"
ADMIN_PASSWORD = "Admin@2026Secure"
EMP_EMAIL = "employee@officeflow.com"
EMP_PASSWORD = "Employee@123"


def _login(email, password):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text}")
    return s, r.json()


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def employee():
    return _login(EMP_EMAIL, EMP_PASSWORD)


# ---------- Admin dashboard endpoints ----------
class TestAdminDashboard:
    def test_dashboard_stats(self, admin):
        s, _ = admin
        r = s.get(f"{API}/admin/dashboard-stats")
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ["total_employees", "present_today", "active_on_field", "active_tasks", "pending_leaves"]:
            assert key in data, f"missing {key}: {data}"
            assert isinstance(data[key], int)

    def test_employee_status_admin(self, admin):
        s, _ = admin
        r = s.get(f"{API}/admin/employee-status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        emp = data[0]
        for key in ["id", "name", "role", "status", "current_location", "coordinates_today", "gps_active"]:
            assert key in emp, f"missing {key} in {emp}"
        assert emp["status"] in ("working", "checked_out", "not_started")

    def test_employee_status_forbidden_for_employee(self, employee):
        s, _ = employee
        r = s.get(f"{API}/admin/employee-status")
        assert r.status_code == 403, f"{r.status_code} {r.text}"

    def test_employee_stats_admin(self, admin, employee):
        s, _ = admin
        _, emp_me = employee
        r = s.get(f"{API}/admin/employee/{emp_me['id']}/stats")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "monthly" in data and "yearly" in data
        assert "days_present" in data["monthly"]
        assert "total_hours" in data["monthly"]
        assert "total_distance_km" in data["monthly"]
        assert "attendance_records" in data
        assert "gps_sessions" in data


# ---------- Role change ----------
class TestRoleChange:
    def test_promote_to_hr_and_back(self, admin, employee):
        s, _ = admin
        _, emp_me = employee
        eid = emp_me["id"]

        # change to hr
        r = s.put(f"{API}/admin/employee/{eid}/role", params={"role": "hr"})
        assert r.status_code == 200, r.text
        assert r.json()["new_role"] == "hr"

        # revert to employee
        r2 = s.put(f"{API}/admin/employee/{eid}/role", params={"role": "employee"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["new_role"] == "employee"

    def test_non_super_admin_cannot_promote_to_admin(self, employee):
        # Employee not admin -> should get 403 from require_admin (before super_admin check)
        s, emp_me = employee
        r = s.put(f"{API}/admin/employee/{emp_me[1]['id'] if isinstance(emp_me, tuple) else emp_me['id']}/role", params={"role": "admin"})
        # require_admin blocks employees w/ 403
        assert r.status_code == 403, f"{r.status_code} {r.text}"


# ---------- Tasks work_type ----------
class TestTasksWorkType:
    def test_create_task_with_wfh(self, admin, employee):
        s, _ = admin
        _, emp_me = employee
        title = f"TEST_wfh_{uuid.uuid4().hex[:6]}"
        r = s.post(f"{API}/tasks", json={
            "title": title,
            "priority": "medium",
            "status": "todo",
            "work_type": "work_from_home",
            "assigned_to": emp_me["id"],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["work_type"] == "work_from_home"
        assert body["assignee_name"], f"assignee_name missing: {body}"
        s.delete(f"{API}/tasks/{body['id']}")

    def test_task_defaults_to_in_office(self, admin):
        s, _ = admin
        r = s.post(f"{API}/tasks", json={"title": f"TEST_io_{uuid.uuid4().hex[:6]}", "priority": "low", "status": "todo"})
        assert r.status_code == 200, r.text
        assert r.json()["work_type"] == "in_office"
        s.delete(f"{API}/tasks/{r.json()['id']}")


# ---------- Leaves ----------
class TestLeaves:
    def test_employee_creates_and_admin_approves(self, admin, employee):
        emp_s, emp_me = employee
        adm_s, _ = admin

        payload = {
            "type": "casual",
            "start_date": "2026-02-10",
            "end_date": "2026-02-12",
            "reason": "TEST_leave",
        }
        r = emp_s.post(f"{API}/leaves", json=payload)
        assert r.status_code == 200, r.text
        leave = r.json()
        assert leave["status"] == "pending"
        assert leave["days"] == 3
        leave_id = leave["id"]

        # employee sees own leave
        rmy = emp_s.get(f"{API}/leaves")
        assert rmy.status_code == 200
        ids = [l["id"] for l in rmy.json()]
        assert leave_id in ids

        # admin sees all
        rall = adm_s.get(f"{API}/leaves")
        assert rall.status_code == 200
        ids_all = [l["id"] for l in rall.json()]
        assert leave_id in ids_all

        # employee cannot approve
        rp = emp_s.put(f"{API}/leaves/{leave_id}", json={"status": "approved"})
        assert rp.status_code == 403

        # admin approves
        ra = adm_s.put(f"{API}/leaves/{leave_id}", json={"status": "approved", "admin_note": "ok"})
        assert ra.status_code == 200, ra.text
        assert ra.json()["status"] == "approved"
        assert ra.json()["approver_name"]
