"""
RBAC + Auto-GPS regression tests.

Covers:
- Employee restrictions on /companies, /employees, /tasks
- Task filtering by assigned_to for employees
- Auto GPS session lifecycle around attendance check-in / check-out
- Admin retains full access
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
    # Cookies with Secure+SameSite=None -> ensure Session captures them (https OK)
    return s, r.json()


@pytest.fixture(scope="module")
def admin():
    s, me = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s, me


@pytest.fixture(scope="module")
def employee():
    s, me = _login(EMP_EMAIL, EMP_PASSWORD)
    return s, me


# ---------- RBAC ----------
class TestRBACEmployee:
    def test_employee_role(self, employee):
        _, me = employee
        assert me["role"] == "employee", f"Expected employee role, got {me}"

    def test_employee_cannot_list_companies(self, employee):
        s, _ = employee
        r = s.get(f"{API}/companies")
        assert r.status_code == 403, f"{r.status_code} {r.text}"

    def test_employee_cannot_list_employees(self, employee):
        s, _ = employee
        r = s.get(f"{API}/employees")
        assert r.status_code == 403, f"{r.status_code} {r.text}"

    def test_employee_cannot_create_task(self, employee):
        s, _ = employee
        r = s.post(f"{API}/tasks", json={
            "title": "TEST_should_fail", "priority": "medium", "status": "todo"
        })
        assert r.status_code == 403, f"{r.status_code} {r.text}"

    def test_employee_task_list_filtered(self, admin, employee):
        admin_s, _ = admin
        emp_s, emp_me = employee
        emp_id = emp_me["id"]

        # Admin creates a task assigned to employee
        title_ok = f"TEST_emp_task_{uuid.uuid4().hex[:6]}"
        r = admin_s.post(f"{API}/tasks", json={
            "title": title_ok, "priority": "low", "status": "todo",
            "assigned_to": emp_id,
        })
        assert r.status_code == 200, r.text
        tid_ok = r.json()["id"]

        # Admin creates another task NOT assigned to employee
        title_no = f"TEST_other_task_{uuid.uuid4().hex[:6]}"
        r2 = admin_s.post(f"{API}/tasks", json={
            "title": title_no, "priority": "low", "status": "todo",
        })
        assert r2.status_code == 200, r2.text
        tid_no = r2.json()["id"]

        try:
            # Even if employee passes assigned_to=<someone else>, server must ignore it
            listing = emp_s.get(f"{API}/tasks", params={"assigned_to": "someone-else"})
            assert listing.status_code == 200
            items = listing.json()
            titles = [t["title"] for t in items]
            assert title_ok in titles, f"Employee cannot see own task: {titles}"
            assert title_no not in titles, "Employee should NOT see unassigned task"
            for t in items:
                assert t.get("assigned_to") == emp_id, f"Leak: {t}"

            # Detail: allowed task -> 200
            rok = emp_s.get(f"{API}/tasks/{tid_ok}")
            assert rok.status_code == 200

            # Detail: unassigned -> 404
            rno = emp_s.get(f"{API}/tasks/{tid_no}")
            assert rno.status_code == 404

            # Update: unassigned -> 404
            rup = emp_s.put(f"{API}/tasks/{tid_no}", json={"status": "in_progress"})
            assert rup.status_code == 404
        finally:
            admin_s.delete(f"{API}/tasks/{tid_ok}")
            admin_s.delete(f"{API}/tasks/{tid_no}")


class TestRBACAdmin:
    def test_admin_companies(self, admin):
        s, _ = admin
        r = s.get(f"{API}/companies")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_employees(self, admin):
        s, _ = admin
        r = s.get(f"{API}/employees")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_tasks(self, admin):
        s, _ = admin
        r = s.get(f"{API}/tasks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_can_create_task(self, admin):
        s, _ = admin
        payload = {"title": f"TEST_admin_{uuid.uuid4().hex[:6]}", "priority": "medium", "status": "todo"}
        r = s.post(f"{API}/tasks", json=payload)
        assert r.status_code == 200
        tid = r.json()["id"]
        s.delete(f"{API}/tasks/{tid}")


# ---------- Auto GPS ----------
class TestAutoGPS:
    """Uses admin account. Resets today's attendance & active GPS via direct DB
    access so the test is deterministic. Backend enforces one attendance record
    per user per day, so we must wipe it before we can exercise check-in."""

    def _reset_state(self, user_id):
        from pymongo import MongoClient
        from datetime import date as _d
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        cli = MongoClient(mongo_url)
        db = cli[db_name]
        today = _d.today().isoformat()
        db.attendance.delete_many({"user_id": user_id, "date": today})
        db.gps_sessions.delete_many({"user_id": user_id, "status": "active"})
        cli.close()

    def test_auto_gps_lifecycle(self, admin):
        s, me = admin
        self._reset_state(me["id"])

        # Check-in with location
        r = s.post(f"{API}/attendance/check-in", json={
            "latitude": 12.9716, "longitude": 77.5946, "notes": "TEST_auto_gps"
        })
        # If already checked in earlier (400), we can still verify current active session
        if r.status_code not in (200, 400):
            pytest.fail(f"check-in unexpected: {r.status_code} {r.text}")

        # Active GPS should be true
        act = s.get(f"{API}/gps/active")
        assert act.status_code == 200
        body = act.json()
        assert body["active"] is True, f"Expected active GPS session, got {body}"
        sess = body["session"]
        assert sess is not None
        assert "Auto-started with attendance check-in" in (sess.get("notes") or "")

        # Idempotent: another check-in call must not create a second active session
        r2 = s.post(f"{API}/attendance/check-in", json={
            "latitude": 12.9716, "longitude": 77.5946
        })
        # Second call returns 400 (already checked in). GPS session should still be the same.
        act2 = s.get(f"{API}/gps/active")
        assert act2.status_code == 200
        assert act2.json()["active"] is True
        assert act2.json()["session"]["id"] == sess["id"], "GPS session duplicated on repeat check-in"

        # Check-out -> GPS should end
        rco = s.post(f"{API}/attendance/check-out", json={
            "latitude": 12.9716, "longitude": 77.5946
        })
        assert rco.status_code == 200, rco.text

        act3 = s.get(f"{API}/gps/active")
        assert act3.status_code == 200
        assert act3.json()["active"] is False, f"GPS should be ended: {act3.json()}"
