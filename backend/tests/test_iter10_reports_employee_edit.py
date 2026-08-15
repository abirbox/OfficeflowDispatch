"""Iteration 10 tests: Reports endpoints (RBAC), Employee edit password/status,
office-locations for map, and regression smoke on prior endpoints."""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mahossain432@gmail.com"
ADMIN_PASSWORD = "Admin@2026Secure"
EMP_EMAIL = "employee@officeflow.com"
EMP_PASSWORD = "Employee@123"


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def employee_session():
    s = requests.Session()
    # try login; if fails, try to register the employee via admin
    r = _login(s, EMP_EMAIL, EMP_PASSWORD)
    if r.status_code != 200:
        # register
        reg = s.post(f"{API}/auth/register", json={
            "email": EMP_EMAIL, "password": EMP_PASSWORD, "name": "Test Employee"
        })
        r = _login(s, EMP_EMAIL, EMP_PASSWORD)
    if r.status_code != 200:
        pytest.skip("employee login not available")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------------- Auth basics ----------------
class TestAuth:
    def test_admin_me(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        d = r.json()
        assert d.get("email") == ADMIN_EMAIL
        assert d.get("role") in ["super_admin", "admin"]


# ---------------- Reports ----------------
class TestReports:
    def test_summary_admin(self, admin_session):
        r = admin_session.get(f"{API}/reports/summary")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["employees", "attendance", "shifts", "overtime", "leaves", "payroll", "period"]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["employees"].get("total_active"), int)

    def test_summary_month_year(self, admin_session):
        r = admin_session.get(f"{API}/reports/summary", params={"month": 1, "year": 2026})
        assert r.status_code == 200
        d = r.json()
        assert d["period"]["month"] == 1 and d["period"]["year"] == 2026

    def test_summary_forbidden_for_employee(self, employee_session):
        r = employee_session.get(f"{API}/reports/summary")
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text}"

    def test_attendance_report(self, admin_session):
        r = admin_session.get(f"{API}/reports/attendance")
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and "total" in d
        assert d["total"] == len(d["rows"])

    def test_attendance_report_forbidden(self, employee_session):
        r = employee_session.get(f"{API}/reports/attendance")
        assert r.status_code == 403

    def test_payroll_report(self, admin_session):
        r = admin_session.get(f"{API}/reports/payroll", params={"month": 1, "year": 2026})
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and "total" in d

    def test_overtime_report(self, admin_session):
        r = admin_session.get(f"{API}/reports/overtime")
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and "total" in d


# ---------------- Employee edit (password/status/salary) ----------------
class TestEmployeeEdit:
    @pytest.fixture(scope="class")
    def temp_emp_id(self, admin_session):
        # Create a dedicated test employee
        email = f"TEST_editemp_{int(time.time())}@example.com"
        r = admin_session.post(f"{API}/employees", json={
            "email": email,
            "name": "TEST Edit Emp",
            "password": "Initial@123",
            "role": "employee",
            "salary": 1000.0,
        })
        assert r.status_code == 200, r.text
        emp = r.json()
        yield emp["id"], email
        # cleanup - delete
        admin_session.delete(f"{API}/employees/{emp['id']}")

    def test_update_name_salary_role(self, admin_session, temp_emp_id):
        emp_id, _ = temp_emp_id
        r = admin_session.put(f"{API}/employees/{emp_id}", json={
            "name": "TEST Edited Name",
            "salary": 2500.5,
            "role": "manager",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST Edited Name"
        assert d["salary"] == 2500.5
        assert d["role"] == "manager"

        # GET verify
        g = admin_session.get(f"{API}/employees/{emp_id}")
        assert g.status_code == 200
        assert g.json()["salary"] == 2500.5

    def test_suspend_status(self, admin_session, temp_emp_id):
        emp_id, _ = temp_emp_id
        r = admin_session.put(f"{API}/employees/{emp_id}", json={"status": "suspended"})
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"
        # reactivate
        r = admin_session.put(f"{API}/employees/{emp_id}", json={"status": "active"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_password_change_and_login(self, admin_session, temp_emp_id):
        emp_id, email = temp_emp_id
        new_pw = "NewPass@456"
        r = admin_session.put(f"{API}/employees/{emp_id}", json={"password": new_pw})
        assert r.status_code == 200
        # verify by logging in
        s = requests.Session()
        login = _login(s, email, new_pw)
        assert login.status_code == 200, f"login with new pw failed: {login.status_code} {login.text}"

    def test_password_too_short(self, admin_session, temp_emp_id):
        emp_id, _ = temp_emp_id
        r = admin_session.put(f"{API}/employees/{emp_id}", json={"password": "abc"})
        assert r.status_code == 400

    def test_delete_sets_inactive(self, admin_session):
        # Create a throwaway
        email = f"TEST_delemp_{int(time.time())}@example.com"
        c = admin_session.post(f"{API}/employees", json={
            "email": email, "name": "TEST Del", "password": "Init@123", "role": "employee"
        })
        assert c.status_code == 200
        emp_id = c.json()["id"]
        d = admin_session.delete(f"{API}/employees/{emp_id}")
        assert d.status_code == 200
        g = admin_session.get(f"{API}/employees/{emp_id}")
        assert g.status_code == 200
        assert g.json()["status"] == "inactive"

    def test_non_admin_cannot_edit(self, employee_session, temp_emp_id):
        emp_id, _ = temp_emp_id
        r = employee_session.put(f"{API}/employees/{emp_id}", json={"name": "Hacked"})
        assert r.status_code == 403


# ---------------- Office locations for Live Map ----------------
class TestOfficeLocations:
    def test_list_offices(self, admin_session):
        r = admin_session.get(f"{API}/office-locations")
        assert r.status_code == 200
        data = r.json()
        # list may be a list or wrapper
        rows = data if isinstance(data, list) else data.get("rows") or data.get("items") or []
        assert isinstance(rows, list)


# ---------------- Regression smoke ----------------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/shifts",
        "/overtime",
        "/leaves",
        "/notifications",
        "/admin/dashboard-stats",
        "/admin/employee-status",
        "/settings",
        "/attendance",
        "/office-locations",
        "/companies",
    ])
    def test_endpoints_accessible(self, admin_session, path):
        r = admin_session.get(f"{API}{path}")
        assert r.status_code in (200, 201), f"{path} => {r.status_code} {r.text[:200]}"

    def test_settings_public(self):
        r = requests.get(f"{API}/settings/public")
        assert r.status_code == 200

    def test_currencies_and_timezones(self, admin_session):
        r1 = admin_session.get(f"{API}/settings/currencies")
        r2 = admin_session.get(f"{API}/settings/timezones")
        assert r1.status_code == 200 and r2.status_code == 200
